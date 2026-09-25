"""Script orquestador de planificación diaria (ejecutado habitualmente a las 20:45 CET)."""

import argparse
import logging
import sys
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from jb_pool_scheduler.clients.esios_client import EsiosClient
from jb_pool_scheduler.clients.telegram_client import TelegramClient
from jb_pool_scheduler.clients.tuya_client import TuyaClient
from jb_pool_scheduler.config import Settings, get_settings
from jb_pool_scheduler.core.heuristic import calculate_filtration_hours
from jb_pool_scheduler.core.optimizer import get_cheapest_intervals
from jb_pool_scheduler.storage.repository import Repository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("planner")


def run_planner(target_date: date | None = None, settings: Settings | None = None) -> None:
    """Ejecuta el ciclo completo de planificación para la fecha indicada (por defecto D+1)."""
    cfg = settings or get_settings()
    tz = ZoneInfo(cfg.TZ)
    repo = Repository(db_path=cfg.SQLITE_DB_PATH, tz_name=cfg.TZ)
    tuya = TuyaClient(cfg)
    esios = EsiosClient(cfg)
    telegram = TelegramClient(cfg)

    # 1. Definir fechas de referencia
    today = date.today()
    plan_date = target_date or (today + timedelta(days=1))
    logger.info("Iniciando planificación para %s (referencia térmica: %s)", plan_date, today)

    # 2. Obtener temperatura mínima de hoy (con fallback a lectura directa si la BD está vacía)
    min_temp = repo.get_min_temperature_for_day(today)
    if min_temp is None:
        logger.warning(
            "Sin muestras registradas para hoy (%s). Obteniendo temperatura instantánea de la sonda...",
            today,
        )
        current_temp = tuya.get_water_temperature()
        repo.record_temperature(current_temp)
        min_temp = current_temp

    logger.info("Temperatura mínima de referencia: %.1f °C", min_temp)

    # 3. Calcular horas de depuración necesarias
    target_hours = calculate_filtration_hours(min_temp)
    logger.info("Horas asignadas por heurística: %d h", target_hours)

    # 4. Descargar precios PVPC de ESIOS para la fecha planificada
    logger.info("Descargando precios PVPC para %s...", plan_date)
    hourly_prices = esios.get_pvpc_prices_for_date(plan_date)

    # 5. Optimizar intervalos
    intervals = get_cheapest_intervals(hourly_prices, target_hours)
    logger.info(
        "Intervalos calculados (%d tramos): %s",
        len(intervals),
        ", ".join(str(i) for i in intervals),
    )

    # 6. Persistir plan en SQLite
    repo.save_daily_schedule(plan_date, intervals)
    logger.info("Plan guardado con éxito en %s", cfg.SQLITE_DB_PATH)

    # 7. Notificar al usuario por Telegram
    telegram.send_planning_report(
        schedule_date=plan_date,
        min_water_temp=min_temp,
        target_hours=target_hours,
        intervals=intervals,
    )
    logger.info("Notificación enviada a Telegram.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Planificador diario de depuración de piscina.")
    parser.add_argument(
        "--date",
        type=str,
        help="Fecha objetivo en formato YYYY-MM-DD (por defecto D+1)",
        default=None,
    )
    args = parser.parse_args()

    parsed_target: date | None = None
    if args.date:
        parsed_target = date.fromisoformat(args.date)

    try:
        run_planner(target_date=parsed_target)
    except Exception as exc:
        logger.exception("Error crítico durante la planificación: %s", exc)
        sys.exit(1)