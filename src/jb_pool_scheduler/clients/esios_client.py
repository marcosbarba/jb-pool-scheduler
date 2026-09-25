"""Cliente para la descarga y parseo de precios horarios PVPC desde REE / ESIOS."""

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo
import httpx
from jb_pool_scheduler.config import Settings, get_settings

logger = logging.getLogger(__name__)

# ID geográfico oficial de España Peninsular en ESIOS
PENINSULA_GEO_ID = 8741


class EsiosClient:
    """Gestiona la consulta del indicador 1001 (PVPC) en api.esios.ree.es."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.tz = ZoneInfo(self.settings.TZ)
        self.base_url = "https://api.esios.ree.es"

    def get_pvpc_prices_for_date(self, target_date: date) -> dict[int, float]:
        """Descarga los precios del PVPC para las 24 horas del día especificado.

        :param target_date: Fecha objetivo (normalmente D+1).
        :return: Diccionario {hora (0-23): precio en €/MWh}.
        """
        date_str = target_date.isoformat()
        url = f"{self.base_url}/indicators/1001"
        params = {
            "start_date": f"{date_str}T00:00:00",
            "end_date": f"{date_str}T23:59:59",
        }
        headers = {
            "Accept": "application/json; application/vnd.esios-api-v2+json",
            "Content-Type": "application/json",
            "x-api-key": self.settings.ESIOS_API_TOKEN,
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("Error HTTP al consultar ESIOS (%s): %s", e.response.status_code, e.response.text)
            raise
        except Exception as e:
            logger.error("Error de conexión con ESIOS: %s", e)
            raise

        values = data.get("indicator", {}).get("values", [])
        if not values:
            raise ValueError(f"No hay precios disponibles en ESIOS para la fecha {date_str}")

        hourly_prices: dict[int, float] = {}

        for entry in values:
            # Filtrar por territorio peninsular
            if entry.get("geo_id") != PENINSULA_GEO_ID:
                continue

            # Convertir timestamp a hora local
            dt = datetime.fromisoformat(entry["datetime"]).astimezone(self.tz)
            if dt.date() == target_date:
                hourly_prices[dt.hour] = float(entry["value"])

        if len(hourly_prices) < 24:
            logger.warning(
                "ESIOS solo devolvió %d de 24 horas para %s (posible publicación incompleta).",
                len(hourly_prices),
                date_str,
            )

        return hourly_prices