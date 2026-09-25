"""Tests unitarios para el cliente de Netatmo (lectura de temperatura y autenticación)."""

from unittest.mock import MagicMock, patch
import pytest

from jb_pool_scheduler.clients.netatmo_client import NetatmoClient
from jb_pool_scheduler.config import Settings


@pytest.fixture
def mock_settings():
    return Settings(
        TZ="Europe/Madrid",
        SQLITE_DB_PATH="data/test.db",
        NETATMO_CLIENT_ID="fake_client_id",
        NETATMO_CLIENT_SECRET="fake_client_secret",
        NETATMO_REFRESH_TOKEN="fake_refresh_token",
        NETATMO_STATION_MAC="70:ee:50:aa:bb:cc",
        ESIOS_API_TOKEN="fake_esios",
        TUYA_ACCESS_ID="fake_tuya_id",
        TUYA_ACCESS_SECRET="fake_tuya_secret",
        TUYA_PUMP_DEVICE_ID="fake_pump",
        TUYA_TEMP_DEVICE_ID="fake_temp",
        TELEGRAM_BOT_TOKEN="fake_bot",
        TELEGRAM_CHAT_ID="fake_chat",
    )


def test_get_outdoor_air_temperature_from_outdoor_module(mock_settings):
    """Verifica que se extraiga la temperatura cuando reside en un módulo exterior."""
    client = NetatmoClient(mock_settings)

    mock_station_payload = {
        "body": {
            "devices": [
                {
                    "_id": "70:ee:50:aa:bb:cc",
                    "station_name": "Casa",
                    "dashboard_data": {"Temperature": 22.0},  # Interior
                    "modules": [
                        {
                            "_id": "02:00:00:xx:xx:xx",
                            "module_name": "Exterior",
                            "type": "NAModule1",
                            "dashboard_data": {"Temperature": -1.4},  # Sensor exterior
                        }
                    ],
                }
            ]
        }
    }

    with patch.object(client, "_refresh_access_token", return_value="valid_token"):
        with patch("httpx.Client.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_station_payload
            mock_get.return_value = mock_resp

            temp = client.get_outdoor_air_temperature()

            assert temp == -1.4
            mock_get.assert_called_once()


def test_get_outdoor_air_temperature_from_main_device(mock_settings):
    """Verifica que tome la temperatura de la base si no hay módulos adicionales."""
    client = NetatmoClient(mock_settings)

    mock_station_payload = {
        "body": {
            "devices": [
                {
                    "_id": "70:ee:50:aa:bb:cc",
                    "modules": [],
                    "dashboard_data": {"Temperature": 0.5},
                }
            ]
        }
    }

    with patch.object(client, "_refresh_access_token", return_value="valid_token"):
        with patch("httpx.Client.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_station_payload
            mock_get.return_value = mock_resp

            assert client.get_outdoor_air_temperature() == 0.5


def test_get_outdoor_air_temperature_missing_raises_error(mock_settings):
    """Verifica que lance KeyError si el payload no contiene lecturas térmicas."""
    client = NetatmoClient(mock_settings)
    mock_station_payload = {"body": {"devices": [{"_id": "70:ee:50:aa:bb:cc", "modules": []}]}}

    with patch.object(client, "_refresh_access_token", return_value="valid_token"):
        with patch("httpx.Client.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_station_payload
            mock_get.return_value = mock_resp

            with pytest.raises(KeyError, match="No se encontró lectura"):
                client.get_outdoor_air_temperature()