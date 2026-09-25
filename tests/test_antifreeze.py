"""Tests unitarios para la lógica de anulación por heladas (check_antifreeze_override)."""

from unittest.mock import MagicMock
import pytest

from jb_pool_scheduler.config import Settings
from jb_pool_scheduler.executor import check_antifreeze_override
from jb_pool_scheduler.storage.repository import Repository


@pytest.fixture
def test_setup(tmp_path):
    db_file = tmp_path / "antifreeze_test.db"
    settings = Settings(
        TZ="Europe/Madrid",
        SQLITE_DB_PATH=db_file,
        NETATMO_CLIENT_ID="id",
        NETATMO_CLIENT_SECRET="secret",
        NETATMO_REFRESH_TOKEN="token",
        NETATMO_STATION_MAC="mac",
        ANTIFREEZE_TEMP_THRESHOLD=1.0,
        ANTIFREEZE_TEMP_HYSTERESIS=2.0,
        ESIOS_API_TOKEN="esios",
        TUYA_ACCESS_ID="tuya",
        TUYA_ACCESS_SECRET="secret",
        TUYA_PUMP_DEVICE_ID="pump",
        TUYA_TEMP_DEVICE_ID="temp",
        TELEGRAM_BOT_TOKEN="bot",
        TELEGRAM_CHAT_ID="chat",
    )
    repo = Repository(db_path=db_file, tz_name="Europe/Madrid")
    mock_netatmo = MagicMock()
    mock_telegram = MagicMock()
    return settings, repo, mock_netatmo, mock_telegram


def test_antifreeze_activation_and_hysteresis(test_setup):
    """Verifica transiciones de estado, histéresis y disparos únicos de alertas a Telegram."""
    settings, repo, mock_netatmo, mock_telegram = test_setup

    # 1. Temperatura templada (8 °C) -> Desactivado, sin alertas
    mock_netatmo.get_outdoor_air_temperature.return_value = 8.0
    active, _ = check_antifreeze_override(mock_netatmo, repo, settings, mock_telegram)
    assert active is False
    assert repo.get_system_state("antifreeze_active") == ""
    mock_telegram.send_antifreeze_alert.assert_not_called()

    # 2. Desciende a 0.5 °C (<= 1.0 °C) -> Transición a ACTIVO: alerta enviada
    mock_netatmo.get_outdoor_air_temperature.return_value = 0.5
    active, reason = check_antifreeze_override(mock_netatmo, repo, settings, mock_telegram)
    assert active is True
    assert "0.5 °C" in reason
    assert repo.get_system_state("antifreeze_active") == "1"
    mock_telegram.send_antifreeze_alert.assert_called_once_with(air_temp=0.5, threshold=1.0)
    mock_telegram.send_antifreeze_alert.reset_mock()

    # 3. Sube a 1.5 °C (Histéresis) -> Permanece activo, NO debe duplicar alertas
    mock_netatmo.get_outdoor_air_temperature.return_value = 1.5
    active, _ = check_antifreeze_override(mock_netatmo, repo, settings, mock_telegram)
    assert active is True
    assert repo.get_system_state("antifreeze_active") == "1"
    mock_telegram.send_antifreeze_alert.assert_not_called()
    mock_telegram.send_antifreeze_recovery.assert_not_called()

    # 4. Sube a 2.5 °C (>= 2.0 °C) -> Transición a DESACTIVADO: notificación de recuperación
    mock_netatmo.get_outdoor_air_temperature.return_value = 2.5
    active, _ = check_antifreeze_override(mock_netatmo, repo, settings, mock_telegram)
    assert active is False
    assert repo.get_system_state("antifreeze_active") == "0"
    mock_telegram.send_antifreeze_recovery.assert_called_once_with(air_temp=2.5, hysteresis=2.0)