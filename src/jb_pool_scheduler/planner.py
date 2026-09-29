"""Script orquestador de planificación diaria (ejecutado habitualmente a las 20:45 CET)."""

import argparse
import logging
import sys
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import httpx

from jb_pool_scheduler.clients.esios_client import EsiosClient
from jb_pool_scheduler.clients.netatmo_client import NetatmoClient
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
    netatmo = NetatmoClient(cfg)
    esios = EsiosClient(cfg)
    telegram = TelegramClient(cfg)

    # 1. Definir fechas de referencia
    today = date.now(tz).date()
    plan_date = target_date or (today + timedelta(days=1))
    logger.info("Iniciando planificación para %s (referencia térmica: %s)", plan_date, today)

    # 2. Recuperar extremos térmicos del día
    w_min, w_max = repo.get_temperature_extrema_for_day("water", target_date=today)
    a_min, a_max = repo.get_temperature_extrema_for_day("air", target_date=today)

    # Salvaguardas en caso de primer arranque sin muestras previas
    if w_min is None:
        cur_w = tuya.get_water_temperature()
        repo.record_temperature(cur_w, sensor_type="water")
        w_min = w_max = cur_w

    if a_min is None:
        try:
            cur_a = netatmo.get_outdoor_air_temperature()
            repo.record_temperature(cur_a, sensor_type="air")
            a_min = a_max = cur_a
        except (httpx.HTTPError, KeyError, RuntimeError) as exc:
            logger.warning("No se pudo obtener temperatura del aire en Netatmo para el informe: %s", exc)

    # 3. Heurística según la mínima del agua
    target_hours = calculate_filtration_hours(w_min)

    # 4. Descarga de precios y optimización
    if target_hours > 0:
        prices = esios.get_pvpc_prices_for_date(plan_date)
        intervals = get_cheapest_intervals(prices, target_hours)
    else:
        intervals = []

    repo.save_daily_schedule(plan_date, intervals)

    # 5. Envío a Telegram con los rangos completos
    telegram.send_planning_report(
        schedule_date=plan_date,
        target_hours=target_hours,
        intervals=intervals,
        water_min=w_min,
        water_max=w_max,
        air_min=a_min,
        air_max=a_max,
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
    except Exception:
        logger.exception("Error crítico durante la planificación")
        sys.exit(1)