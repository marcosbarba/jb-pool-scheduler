"""Script ejecutor para la comprobación y conmutación de la depuradora según el plan."""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from jb_pool_scheduler.clients.netatmo_client import NetatmoClient
from jb_pool_scheduler.clients.telegram_client import TelegramClient
from jb_pool_scheduler.clients.tuya_client import TuyaClient
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
    """Comprueba si procede registrar un nuevo ciclo de muestras térmicas."""
    with repo._get_connection() as conn:
        row = conn.execute(
            "SELECT recorded_at FROM temperature_samples ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if not row:
        return True

    last_recorded = datetime.fromisoformat(row["recorded_at"])
    return (now - last_recorded) >= timedelta(minutes=interval_minutes)


def evaluate_antifreeze_state(
    air_temp: float,
    repo: Repository,
    cfg: Settings,
    telegram: TelegramClient,
) -> tuple[bool, str]:
    """Evalúa la lógica de congelación/histéresis y notifica a Telegram en las transiciones."""
    is_currently_active = repo.get_system_state("antifreeze_active", "0") == "1"

    # Transición 1: Cae por debajo del umbral de helada
    if air_temp <= cfg.ANTIFREEZE_TEMP_THRESHOLD:
        if not is_currently_active:
            repo.set_system_state("antifreeze_active", "1")
            logger.warning("¡ALERTA ANTIHIELO ACTIVADA! Aire exterior a %.1f °C", air_temp)
            telegram.send_antifreeze_alert(air_temp=air_temp, threshold=cfg.ANTIFREEZE_TEMP_THRESHOLD)
        return True, f"Modo antihielo activo ({air_temp:.1f} °C)"

    # Transición 2: Supera el umbral de desconexión (histéresis)
    if air_temp >= cfg.ANTIFREEZE_TEMP_HYSTERESIS and is_currently_active:
        repo.set_system_state("antifreeze_active", "0")
        logger.info("Modo antihielo desactivado. Aire exterior subió a %.1f °C", air_temp)
        telegram.send_antifreeze_recovery(air_temp=air_temp, hysteresis=cfg.ANTIFREEZE_TEMP_HYSTERESIS)
        return False, ""

    # En zona intermedia de histéresis: retener el estado previo
    reason = f"Modo antihielo en curso ({air_temp:.1f} °C)" if is_currently_active else ""
    return is_currently_active, reason


def ensure_daily_schedule(repo: Repository, now: datetime, cfg: Settings) -> None:
    """Si hoy no hay tramos generados, corre la planificación de contingencia."""
    today = now.date()
    if not repo.get_schedule_for_date(today):
        logger.warning("Sin plan activo para hoy (%s). Generando de emergencia...", today)
        try:
            run_planner(target_date=today, settings=cfg)
        except Exception:
            logger.exception("Fallo al ejecutar el planificador de emergencia")


def run_cycle(settings: Settings | None = None) -> None:
    """Ciclo de ejecución: muestreo cada 15 min, verificación de antihielo y control de bomba."""
    cfg = settings or get_settings()
    tz = ZoneInfo(cfg.TZ)
    now = datetime.now(tz)
    repo = Repository(db_path=cfg.SQLITE_DB_PATH, tz_name=cfg.TZ)
    tuya = TuyaClient(cfg)
    netatmo = NetatmoClient(cfg)
    telegram = TelegramClient(cfg)

    # 1. Autocuración del plan del día
    ensure_daily_schedule(repo, now, cfg)

    # 2. Muestreo térmico unificado (cada 15 minutos)
    if should_sample_temperature(repo, now):
        # 2a. Sensor de agua (Tuya)
        try:
            water_temp = tuya.get_water_temperature()
            repo.record_temperature(water_temp, sensor_type="water", dt=now)
            logger.info("Muestra registrada (agua): %.1f °C", water_temp)
        except (KeyError, RuntimeError) as exc:
            logger.warning("Error al obtener muestra de agua de Tuya: %s", exc)

        # 2b. Sensor de aire (Netatmo) y evaluación de freeze
        try:
            air_temp = netatmo.get_outdoor_air_temperature()
            repo.record_temperature(air_temp, sensor_type="air", dt=now)
            logger.info("Muestra registrada (aire): %.1f °C", air_temp)
            # Evaluación e informe en transición
            evaluate_antifreeze_state(air_temp, repo, cfg, telegram)
        except (httpx.HTTPError, KeyError, RuntimeError) as exc:
            logger.warning("Error al obtener muestra de aire de Netatmo: %s", exc)

    # 3. Determinar estado de congelación desde BD (estable entre muestreos)
    antifreeze_active = repo.get_system_state("antifreeze_active", "0") == "1"

    # 4. Comprobar tramo económico programado
    scheduled_on = repo.is_pump_scheduled(now)

    # 5. Prioridad absoluta al modo antihielo sobre el plan
    if antifreeze_active:
        should_be_on = True
        log_reason = "FORZADO POR HIELO"
    else:
        should_be_on = scheduled_on
        log_reason = "PLAN HORARIO"

    logger.info(
        "Verificando estado para %s | Objetivo: %s | Motivo: %s",
        now.strftime("%H:%M:%S"),
        "ENCENDIDO" if should_be_on else "APAGADO",
        log_reason,
    )

    # 6. Conmutación idempotente
    current_state = tuya.get_pump_status()
    if current_state != should_be_on:
        logger.info(
            "Discrepancia detectada (actual: %s, objetivo: %s). Conmutando...",
            current_state,
            should_be_on,
        )
        tuya.set_pump_status(should_be_on)
        details = f"Motivo: {log_reason}\nHora local: {now.strftime('%H:%M:%S')}"
        telegram.send_switch_event(is_on=should_be_on, details=details)
    else:
        logger.info("Bomba en sincronía (estado: %s).", "ENCENDIDA" if current_state else "APAGADA")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecutor de control de la depuradora.")
    parser.add_argument("--loop", action="store_true", help="Modo demonio continuo")
    args = parser.parse_args()

    if args.loop:
        logger.info("Iniciando ejecutor en modo demonio (60s)...")
        while True:
            try:
                run_cycle()
            except Exception:
                logger.exception("Error durante el ciclo del ejecutor")
            time.sleep(60)
    else:
        run_cycle()


if __name__ == "__main__":
    main()