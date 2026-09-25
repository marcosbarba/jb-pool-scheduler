from datetime import date
from unittest.mock import MagicMock, patch
from jb_pool_scheduler.clients.esios_client import PENINSULA_GEO_ID, EsiosClient


def test_get_pvpc_prices_parsing():
    target_date = date(2026, 9, 25)
    
    mock_payload = {
        "indicator": {
            "values": [
                # Hora 0 Península (debe incluirse)
                {
                    "value": 45.2,
                    "datetime": "2026-09-25T00:00:00+02:00",
                    "geo_id": PENINSULA_GEO_ID,
                },
                # Hora 0 Canarias (debe ignorarse)
                {
                    "value": 60.0,
                    "datetime": "2026-09-25T00:00:00+02:00",
                    "geo_id": 8742,
                },
                # Hora 1 Península (debe incluirse)
                {
                    "value": 38.5,
                    "datetime": "2026-09-25T01:00:00+02:00",
                    "geo_id": PENINSULA_GEO_ID,
                },
            ]
        }
    }

    client = EsiosClient()

    with patch("httpx.Client.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_payload
        mock_get.return_value = mock_response

        prices = client.get_pvpc_prices_for_date(target_date)

        assert len(prices) == 2
        assert prices[0] == 45.2
        assert prices[1] == 38.5