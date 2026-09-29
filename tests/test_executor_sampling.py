from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from jb_pool_scheduler.config import Settings
from jb_pool_scheduler.executor import run_cycle, should_sample_temperature
from jb_pool_scheduler.storage.repository import Repository

TZ = ZoneInfo("Europe/Madrid")


@pytest.fixture
def executor_env(tmp_path):
    db_file = tmp_path / "executor_test.db"
    settings = Settings(
        TZ="Europe/Madrid",
        SQLITE_DB_PATH=db_file,
        NETATMO_CLIENT_ID="id",
        NETATMO_CLIENT_SECRET="secret",
        NETATMO_REFRESH_TOKEN="token",
        NETATMO_STATION_MAC="mac",
        ESIOS_API_TOKEN="esios",
        TUYA_ACCESS_ID="tuya",
        TUYA_ACCESS_SECRET="secret",
        TUYA_PUMP_DEVICE_ID="pump",
        TUYA_TEMP_DEVICE_ID="temp",
        TELEGRAM_BOT_TOKEN="bot",
        TELEGRAM_CHAT_ID="chat",
    )
    repo = Repository(db_path=db_file, tz_name="Europe/Madrid")
    return settings, repo


def test_should_sample_temperature_logic(executor_env):
    """Comprueba el intervalo de 15 minutos entre muestras consecutivas."""
    _, repo = executor_env
    t0 = datetime(2026, 9, 29, 10, 0, tzinfo=TZ)

    # Si la BD está vacía, debe muestrear
    assert should_sample_temperature(repo, t0) is True

    repo.record_temperature(23.0, sensor_type="water", dt=t0)

    # 10 minutos después: NO debe muestrear aún
    t1 = datetime(2026, 9, 29, 10, 10, tzinfo=TZ)
    assert should_sample_temperature(repo, t1) is False

    # 15 minutos después: DEBE muestrear
    t2 = datetime(2026, 9, 29, 10, 15, tzinfo=TZ)
    assert should_sample_temperature(repo, t2) is True


def test_run_cycle_records_both_sensors_on_sample(executor_env):
    """Comprueba que run_cycle tome agua y aire y los guarde en la BD al muestrear."""
    settings, repo = executor_env

    with (
        patch("jb_pool_scheduler.executor.Repository", return_value=repo),
        patch("jb_pool_scheduler.executor.TuyaClient") as mock_tuya_cls,
        patch("jb_pool_scheduler.executor.NetatmoClient") as mock_netatmo_cls,
        patch("jb_pool_scheduler.executor.TelegramClient"),
    ):
        mock_tuya = mock_tuya_cls.return_value
        mock_netatmo = mock_netatmo_cls.return_value

        mock_tuya.get_water_temperature.return_value = 23.4
        mock_tuya.get_pump_status.return_value = False
        mock_netatmo.get_outdoor_air_temperature.return_value = 14.8

        run_cycle(settings=settings)

        # Verificar lecturas en la base de datos
        w_min, _ = repo.get_temperature_extrema_for_day(sensor_type="water")
        a_min, _ = repo.get_temperature_extrema_for_day(sensor_type="air")

        assert w_min == 23.4
        assert a_min == 14.8