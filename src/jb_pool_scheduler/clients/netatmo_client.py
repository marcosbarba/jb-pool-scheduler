"""Cliente para consultar la temperatura del aire exterior en Netatmo Connect."""

import logging

import httpx

from jb_pool_scheduler.config import Settings, get_settings

logger = logging.getLogger(__name__)


class NetatmoClient:
    """Gestiona la autenticación OAuth2 y la lectura de temperatura exterior de Netatmo."""

    TOKEN_URL = "https://api.netatmo.com/oauth2/token"
    GET_STATIONS_URL = "https://api.netatmo.com/api/getstationsdata"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.access_token: str | None = None

    def _refresh_access_token(self) -> str:
        """Obtiene un access_token válido utilizando el refresh_token."""
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.settings.NETATMO_REFRESH_TOKEN,
            "client_id": self.settings.NETATMO_CLIENT_ID,
            "client_secret": self.settings.NETATMO_CLIENT_SECRET,
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(self.TOKEN_URL, data=payload)
            resp.raise_for_status()
            data = resp.json()
            self.access_token = data["access_token"]
            return self.access_token

    def get_outdoor_air_temperature(self) -> float:
        """Devuelve la temperatura actual del aire exterior registrada por Netatmo."""
        if not self.access_token:
            self._refresh_access_token()

        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"device_id": self.settings.NETATMO_STATION_MAC}

        with httpx.Client(timeout=10.0) as client:
            resp = client.get(self.GET_STATIONS_URL, headers=headers, params=params)
            
            # Si el token caducó (403/401), se renueva una vez y se reintenta
            if resp.status_code in (401, 403):
                self._refresh_access_token()
                headers["Authorization"] = f"Bearer {self.access_token}"
                resp = client.get(self.GET_STATIONS_URL, headers=headers, params=params)

            resp.raise_for_status()
            data = resp.json()

        devices = data.get("body", {}).get("devices", [])
        if not devices:
            raise RuntimeError("No se encontró la estación Netatmo configurada.")

        station = devices[0]
        # 1. Comprobar si la temperatura está en el módulo exterior auxiliar
        for module in station.get("modules", []):
            dashboard = module.get("dashboard_data", {})
            if "Temperature" in dashboard:
                return float(dashboard["Temperature"])

        # 2. Comprobar en el módulo base principal
        dashboard = station.get("dashboard_data", {})
        if "Temperature" in dashboard:
            return float(dashboard["Temperature"])

        raise KeyError("No se encontró lectura de temperatura en Netatmo.")