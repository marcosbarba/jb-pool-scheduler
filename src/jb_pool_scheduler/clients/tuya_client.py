"""Cliente para interactuar con la OpenAPI de Tuya / Smart Life."""

import logging
from typing import Any

from tuya_connector import TuyaOpenAPI

from jb_pool_scheduler.config import Settings, get_settings

logger = logging.getLogger(__name__)


class TuyaClient:
    """Encapsula la comunicación con la plataforma Tuya Cloud."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.api = TuyaOpenAPI(
            endpoint=self.settings.TUYA_ENDPOINT,
            access_id=self.settings.TUYA_ACCESS_ID,
            access_secret=self.settings.TUYA_ACCESS_SECRET,
        )
        self.api.connect()

    def get_device_status(self, device_id: str) -> list[dict[str, Any]]:
        """Obtiene la lista de estados y DPs brutos del dispositivo."""
        response = self.api.get(f"/v1.0/iot-03/devices/{device_id}/status")
        if not response.get("success", False):
            msg = f"Error al consultar estado en Tuya ({device_id}): {response.get('msg')}"
            logger.error(msg)
            raise RuntimeError(msg)
        return response.get("result", [])

    def get_water_temperature(self) -> float:
            """Consulta la sonda y devuelve la temperatura medida por el sensor interno (temp_current)."""
            statuses = self.get_device_status(self.settings.TUYA_TEMP_DEVICE_ID)
            status_map = {item.get("code"): item.get("value") for item in statuses}

            if "temp_current" not in status_map or status_map["temp_current"] is None:
                raise KeyError(
                    f"No se encontró 'temp_current' en los datos de la sonda: {statuses}"
                )

            # El dispositivo devuelve enteros multiplicados por 10 (ej: 250 -> 25.0 °C)
            return float(status_map["temp_current_external"]) / 10.0

    def get_pump_status(self) -> bool:
        """Devuelve True si el interruptor de la depuradora está encendido, False si está apagado."""
        statuses = self.get_device_status(self.settings.TUYA_PUMP_DEVICE_ID)
        switch_keys = ("switch_1", "switch", "relay")
        for item in statuses:
            if item.get("code") in switch_keys:
                return bool(item["value"])
        raise KeyError(
            f"No se encontró código de conmutador en el interruptor DIN: {statuses}"
        )

    def set_pump_status(self, target_state: bool, switch_code: str = "switch_1") -> bool:
        """Conmuta el interruptor de la depuradora solo si su estado difiere del deseado (idempotente)."""
        current_state = self.get_pump_status()
        if current_state == target_state:
            logger.info("La depuradora ya está en el estado deseado: %s", target_state)
            return False

        payload = {
            "commands": [
                {
                    "code": switch_code,
                    "value": target_state,
                }
            ]
        }
        response = self.api.post(
            f"/v1.0/iot-03/devices/{self.settings.TUYA_PUMP_DEVICE_ID}/commands",
            body=payload,
        )
        if not response.get("success", False):
            msg = f"Fallo al enviar comando a Tuya: {response.get('msg')}"
            logger.error(msg)
            raise RuntimeError(msg)

        logger.info("Depuradora conmutada a: %s", target_state)
        return True