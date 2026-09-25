"""Script ejecutor para la comprobación y conmutación de la depuradora según el plan."""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from jb_pool_scheduler.clients.telegram_client import TelegramClient
from jb_pool_scheduler.clients.tuya_client import TuyaClient
from jb_pool_scheduler.clients.netatmo_client import NetatmoClient
from jb_pool_scheduler.config import Settings, get_settings
from jb_pool_scheduler.planner import run_planner
from jb_pool_scheduler.storage.repository import Repository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("executor")


def should_sample_temperature(repo: Repository, now: datetime, interval_minutes: int = 15) -> bool:
    """Determina si procede tomar una nueva muestra de temperatura."""
    with repo._get_connection() as conn:
        row = conn.execute(
            "SELECT recorded_at FROM temperature_samples ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if not row:
        return True

    last_recorded = datetime.fromisoformat(row["recorded_at"])
    return (now - last_recorded) >= timedelta(minutes=interval_minutes)


def ensure_daily_schedule(repo: Repository, now: datetime, cfg: Settings) -> None:
    """Verifica si existe plan para hoy. Si no lo hay, ejecuta el planificador de contingencia."""
    today = now.date()
    existing_schedule = repo.get_schedule_for_date(today)

    if not existing_schedule:
        logger.warning(
            "Sin plan activo para hoy (%s). Disparando planificación de emergencia...",
            today,
        )
        try:
            # Planifica directamente para la fecha de hoy
            run_planner(target_date=today, settings=cfg)
            logger.info("Plan de contingencia para %s generado con éxito.", today)
        except Exception as exc:
            logger.exception("Fallo al ejecutar el planificador de emergencia: %s", exc)

def check_antifreeze_override(
    netatmo: NetatmoClient,
    repo: Repository,
    cfg: Settings,
    telegram: TelegramClient,
) -> tuple[bool, str]:
    """Evalúa la protección antihielo y notifica por Telegram al entrar o salir del estado crítico."""
    try:
        air_temp = netatmo.get_outdoor_air_temperature()
        logger.info("Temperatura aire exterior (Netatmo): %.1f °C", air_temp)
    except Exception as exc:
        logger.warning("No se pudo leer la temperatura de Netatmo: %s", exc)
        was_active = repo.get_system_state("antifreeze_active", "0") == "1"
        return was_active, "Error en lectura Netatmo (manteniendo estado anterior)"

    is_currently_active = repo.get_system_state("antifreeze_active", "0") == "1"

    # Transición 1: La temperatura baja del umbral y no estaba activo
    if air_temp <= cfg.ANTIFREEZE_TEMP_THRESHOLD:
        if not is_currently_active:
            repo.set_system_state("antifreeze_active", "1")
            logger.warning("¡ALERTA ANTIHIELO ACTIVADA! Aire a %.1f °C", air_temp)
            telegram.send_antifreeze_alert(
                air_temp=air_temp,
                threshold=cfg.ANTIFREEZE_TEMP_THRESHOLD,
            )
        return True, f"Modo antihielo activo ({air_temp:.1f} °C)"

    # Transición 2: La temperatura sube por encima de la histéresis y estaba activo
    if air_temp >= cfg.ANTIFREEZE_TEMP_HYSTERESIS and is_currently_active:
        repo.set_system_state("antifreeze_active", "0")
        logger.info("Modo antihielo desactivado. Aire subió a %.1f °C", air_temp)
        telegram.send_antifreeze_recovery(
            air_temp=air_temp,
            hysteresis=cfg.ANTIFREEZE_TEMP_HYSTERESIS,
        )
        return False, ""

    # Si está entre threshold e hysteresis, mantiene el estado previo sin enviar nuevos mensajes
    return is_currently_active, f"Modo antihielo en curso ({air_temp:.1f} °C)" if is_currently_active else ""

def run_cycle(settings: Settings | None = None) -> None:
    """Ejecuta un ciclo de muestreo térmico, comprobación antihielo, verificación de plan y control de la bomba."""
    cfg = settings or get_settings()
    tz = ZoneInfo(cfg.TZ)
    now = datetime.now(tz)
    repo = Repository(db_path=cfg.SQLITE_DB_PATH, tz_name=cfg.TZ)
    tuya = TuyaClient(cfg)
    netatmo = NetatmoClient(cfg)
    telegram = TelegramClient(cfg)

    # 1. Autocuración: garantizar que el día de hoy dispone de tramos planificados
    ensure_daily_schedule(repo, now, cfg)

    # 2. Muestreo periódico de la sonda de agua en Tuya
    if should_sample_temperature(repo, now):
        try:
            water_temp = tuya.get_water_temperature()
            repo.record_temperature(water_temp, dt=now)
            logger.info("Muestra térmica registrada (agua): %.1f °C", water_temp)
        except Exception as exc:
            logger.warning("No se pudo obtener muestra de temperatura del agua: %s", exc)

    # 3. Evaluación de anulación por protección antihielo (Netatmo aire exterior)
    antifreeze_active, antifreeze_reason = check_antifreeze_override(
        netatmo, repo, cfg, telegram
    )
    
    # 4. Comprobar si corresponde encendido según el plan económico en SQLite
    scheduled_on = repo.is_pump_scheduled(now)

    # 5. Determinar el estado objetivo y el motivo
    if antifreeze_active:
        should_be_on = True
        log_reason = f"FORZADO POR HIELO ({antifreeze_reason})"
    else:
        should_be_on = scheduled_on
        log_reason = "PLAN HORARIO"

    logger.info(
        "Verificando estado para %s | Objetivo: %s | Motivo: %s",
        now.strftime("%H:%M:%S"),
        "ENCENDIDO" if should_be_on else "APAGADO",
        log_reason,
    )

    # 6. Comprobar estado actual del relé en Tuya
    current_state = tuya.get_pump_status()

    # 7. Actuar solo si el estado difiere (idempotencia)
    if current_state != should_be_on:
        logger.info(
            "Discrepancia detectada (actual: %s, objetivo: %s). Conmutando...",
            current_state,
            should_be_on,
        )
        tuya.set_pump_status(should_be_on)

        # 8. Notificar a Telegram con el motivo del encendido/apagado
        details = f"Motivo: {log_reason}\nHora local: {now.strftime('%H:%M:%S')}"
        telegram.send_switch_event(is_on=should_be_on, details=details)
    else:
        logger.info(
            "Bomba sincronizada con el estado objetivo (estado: %s). Sin cambios.",
            "ENCENDIDA" if current_state else "APAGADA",
        )

def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecutor de control de la depuradora.")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Ejecutar en bucle continuo cada 60 segundos (modo demonio)",
    )
    args = parser.parse_args()

    if args.loop:
        logger.info("Iniciando ejecutor en modo demonio (intervalo: 60s)...")
        while True:
            try:
                run_cycle()
            except Exception as exc:
                logger.exception("Error durante el ciclo del ejecutor: %s", exc)
            time.sleep(60)
    else:
        run_cycle()


if __name__ == "__main__":
    main()