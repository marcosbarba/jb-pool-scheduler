"""Tests unitarios para clientes Tuya y ESIOS mediante simulación de respuestas."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from jb_pool_scheduler.clients.esios_client import (
    PENINSULA_GEO_ID,
    EsiosClient,
    IncompletePricesError,
)
from jb_pool_scheduler.clients.tuya_client import TuyaClient
from jb_pool_scheduler.config import Settings
from jb_pool_scheduler.planner import fetch_prices_with_retry


@pytest.fixture
def base_settings(tmp_path):
    return Settings(
        TZ="Europe/Madrid",
        SQLITE_DB_PATH=tmp_path / "test.db",
        NETATMO_CLIENT_ID="id",
        NETATMO_CLIENT_SECRET="secret",
        NETATMO_REFRESH_TOKEN="token",
        NETATMO_STATION_MAC="mac",
        ESIOS_API_TOKEN="fake_token",
        TUYA_ACCESS_ID="fake_id",
        TUYA_ACCESS_SECRET="fake_sec",
        TUYA_PUMP_DEVICE_ID="pump_dev",
        TUYA_TEMP_DEVICE_ID="temp_dev",
        TELEGRAM_BOT_TOKEN="bot",
        TELEGRAM_CHAT_ID="chat",
    )


def test_tuya_get_water_temperature_scaling(base_settings):
    """Comprueba que el valor entero de Tuya (ej: 245) se divida entre 10 (24.5 °C)."""
    with patch("jb_pool_scheduler.clients.tuya_client.TuyaOpenAPI"):
        client = TuyaClient(base_settings)
        # Simular lectura cruda de temp_current_external según espera tuya_client.py
        with patch.object(
            client,
            "get_device_status",
            return_value=[
                {"code": "temp_current", "value": 240},
                {"code": "temp_current_external", "value": 245},
            ],
        ):
            temp = client.get_water_temperature()
            assert temp == 24.5


def test_tuya_set_pump_status_idempotent(base_settings):
    """Si la bomba ya está en el estado deseado, no debe llamar al comando POST."""
    with patch("jb_pool_scheduler.clients.tuya_client.TuyaOpenAPI"):
        client = TuyaClient(base_settings)

        with (
            patch.object(client, "get_pump_status", return_value=True),
            patch.object(client.api, "post") as mock_post,
        ):
            changed = client.set_pump_status(True)
            assert changed is False
            mock_post.assert_not_called()


def _esios_payload(prices: list[float], extra_geo: bool = False) -> dict:
    values = [
        {"value": p, "datetime": f"2026-09-30T{h:02d}:00:00+02:00", "geo_id": PENINSULA_GEO_ID}
        for h, p in enumerate(prices)
    ]
    if extra_geo:
        values.append({"value": 75.0, "datetime": "2026-09-30T00:00:00+02:00", "geo_id": 8742})
    return {"indicator": {"values": values}}


def _fetch_esios(base_settings, payload):
    with patch("httpx.Client.get") as mock_get:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = payload
        mock_get.return_value = resp
        return EsiosClient(base_settings).get_pvpc_prices_for_date(date(2026, 9, 30))


def test_esios_pvpc_parsing_and_geo_filter(base_settings):
    """Verifica que ESIOS filtre solo la Península (8741) y descarte Canarias o Baleares."""
    prices = _fetch_esios(base_settings, _esios_payload([50.0 + h for h in range(24)], extra_geo=True))

    assert len(prices) == 24
    assert prices[0] == 50.0
    assert prices[23] == 73.0


def test_esios_rejects_incomplete_day(base_settings):
    with pytest.raises(IncompletePricesError):
        _fetch_esios(base_settings, _esios_payload([55.0, 45.0, 60.0]))


def test_esios_rejects_flat_prices(base_settings):
    with pytest.raises(IncompletePricesError):
        _fetch_esios(base_settings, _esios_payload([100.0] * 24))


def test_planner_retries_until_prices_complete():
    esios = MagicMock()
    esios.get_pvpc_prices_for_date.side_effect = [IncompletePricesError("parcial"), {0: 1.0}]

    with patch("jb_pool_scheduler.planner.time.sleep") as sleep:
        prices = fetch_prices_with_retry(esios, date(2026, 9, 30), retries=3, wait_seconds=1)

    assert prices == {0: 1.0}
    sleep.assert_called_once_with(1)


def test_planner_gives_up_after_retries():
    esios = MagicMock()
    esios.get_pvpc_prices_for_date.side_effect = IncompletePricesError("parcial")

    with patch("jb_pool_scheduler.planner.time.sleep"), pytest.raises(IncompletePricesError):
        fetch_prices_with_retry(esios, date(2026, 9, 30), retries=2, wait_seconds=1)
    assert esios.get_pvpc_prices_for_date.call_count == 3
