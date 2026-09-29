from datetime import date
from unittest.mock import patch

import pytest

from jb_pool_scheduler.clients.telegram_client import TelegramClient
from jb_pool_scheduler.config import Settings
from jb_pool_scheduler.core.optimizer import TimeInterval


@pytest.fixture
def mock_telegram_client():
    settings = Settings(
        TZ="Europe/Madrid",
        SQLITE_DB_PATH="data/test.db",
        NETATMO_CLIENT_ID="id",
        NETATMO_CLIENT_SECRET="secret",
        NETATMO_REFRESH_TOKEN="token",
        NETATMO_STATION_MAC="mac",
        ESIOS_API_TOKEN="esios",
        TUYA_ACCESS_ID="tuya",
        TUYA_ACCESS_SECRET="secret",
        TUYA_PUMP_DEVICE_ID="pump",
        TUYA_TEMP_DEVICE_ID="temp",
        TELEGRAM_BOT_TOKEN="fake_token",
        TELEGRAM_CHAT_ID="123456",
    )
    return TelegramClient(settings)


def test_send_planning_report_formats_all_extrema(mock_telegram_client):
    """Verifica que el informe incluya min/max tanto para agua como para aire exterior."""
    target_date = date(2026, 9, 30)
    intervals = [TimeInterval(start_hour=2, end_hour=5)]

    with patch.object(mock_telegram_client, "send_message") as mock_send:
        mock_send.return_value = True

        mock_telegram_client.send_planning_report(
            schedule_date=target_date,
            target_hours=3,
            intervals=intervals,
            water_min=20.5,
            water_max=24.8,
            air_min=11.2,
            air_max=27.3,
        )

        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]

        # Comprobar presencia de métricas
        assert "20.5 °C" in msg and "24.8 °C" in msg
        assert "11.2 °C" in msg and "27.3 °C" in msg
        assert "Agua piscina:" in msg
        assert "Aire exterior:" in msg