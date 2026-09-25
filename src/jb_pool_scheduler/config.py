"""Configuración global y validación de variables de entorno mediante Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Entorno y persistencia
    TZ: str = Field(default="Europe/Madrid")
    SQLITE_DB_PATH: Path = Field(default=Path("data/pool_schedule.db"))

    # REE / ESIOS API
    ESIOS_API_TOKEN: str = Field(..., description="Token personal para api.esios.ree.es")

    # Tuya / Smart Life Cloud API (Credenciales globales)
    TUYA_ACCESS_ID: str = Field(..., description="Access ID / Client ID de Tuya Cloud")
    TUYA_ACCESS_SECRET: str = Field(..., description="Access Secret de Tuya Cloud")
    TUYA_ENDPOINT: str = Field(
        default="https://openapi.tuyaeu.com",
        description="Endpoint regional de Tuya (Central Europe Data Center)",
    )

    # Dispositivos Tuya
    TUYA_PUMP_DEVICE_ID: str = Field(
        ..., description="Device ID del interruptor/magnetotérmico DIN de la depuradora"
    )
    TUYA_TEMP_DEVICE_ID: str = Field(
        ..., description="Device ID de la sonda de temperatura del agua"
    )

    # Netatmo
    NETATMO_CLIENT_ID: str = Field(..., description="Client ID de Netatmo")
    NETATMO_CLIENT_SECRET: str = Field(..., description="Client Secret de Netatmo")
    NETATMO_REFRESH_TOKEN: str = Field(..., description="Refresh token de Netatmo")
    NETATMO_STATION_MAC: str = Field(..., description="MAC de la estación exterior Netatmo")

    # Antihielo
    ANTIFREEZE_TEMP_THRESHOLD: float = Field(default=1.0)
    ANTIFREEZE_TEMP_HYSTERESIS: float = Field(default=2.0)

    TELEGRAM_BOT_TOKEN: str = Field(..., description="Token del bot generado por @BotFather")
    TELEGRAM_CHAT_ID: str = Field(..., description="IDs de chats separados por comas")
    TELEGRAM_NOTIFY_SWITCH_EVENTS: bool = Field(
        default=True,
        description="Emitir mensaje al encender y apagar la bomba",
    )

    @property
    def telegram_chat_ids(self) -> list[str]:
        """Devuelve la lista de chat_ids parseados sin espacios en blanco."""
        return [cid.strip() for cid in self.TELEGRAM_CHAT_ID.split(",") if cid.strip()]


@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia cacheada de la configuración validada."""
    return Settings()