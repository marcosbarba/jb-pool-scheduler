"""Cliente para el envío de notificaciones y reportes a través de Telegram Bot API."""

import logging
from datetime import date
import httpx
from jb_pool_scheduler.config import Settings, get_settings
from jb_pool_scheduler.core.optimizer import TimeInterval

logger = logging.getLogger(__name__)


class TelegramClient:
    """Gestiona el despacho de mensajes formateados hacia Telegram."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = (
            f"https://api.telegram.org/bot{self.settings.TELEGRAM_BOT_TOKEN}"
        )

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Envía un mensaje de texto a todos los chats configurados."""
        url = f"{self.base_url}/sendMessage"
        any_success = False

        with httpx.Client(timeout=10.0) as client:
            for chat_id in self.settings.telegram_chat_ids:
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                }
                try:
                    response = client.post(url, json=payload)
                    data = response.json()
                    if not data.get("ok", False):
                        logger.error(
                            "Error enviando a Telegram (chat_id: %s): %s",
                            chat_id,
                            data.get("description", response.text),
                        )
                    else:
                        any_success = True
                except Exception as exc:
                    logger.error("Fallo de red al enviar a Telegram (chat_id: %s): %s", chat_id, exc)

        return any_success

    def send_planning_report(
        self,
        schedule_date: date,
        min_water_temp: float,
        target_hours: int,
        intervals: list[TimeInterval],
    ) -> bool:
        """Formatea y envía el reporte diario con la mínima y los tramos asignados."""
        date_str = schedule_date.strftime("%d/%m/%Y")

        if intervals:
            lines = [f"• {i.format_range()} ({i.duration_hours}h)" for i in intervals]
            intervals_formatted = "\n".join(lines)
        else:
            intervals_formatted = "• Sin tramos programados"

        message = (
            f"📋 <b>Plan de Depuración — {date_str}</b>\n\n"
            f"🌡️ <b>Mínima agua registrada:</b> {min_water_temp:.1f} °C\n"
            f"⏱️ <b>Tiempo asignado:</b> {target_hours} horas\n\n"
            f"⚡ <b>Intervalos optimizados (ESIOS PVPC):</b>\n"
            f"{intervals_formatted}"
        )
        return self.send_message(message, parse_mode="HTML")

    def send_switch_event(self, is_on: bool, details: str = "") -> bool:
        """Notifica el encendido o apagado de la depuradora si la opción está activada."""
        if not self.settings.TELEGRAM_NOTIFY_SWITCH_EVENTS:
            return False

        header = "🟢 <b>Depuradora ENCENDIDA</b>" if is_on else "🔴 <b>Depuradora APAGADA</b>"
        text = f"{header}\n{details}".strip()
        return self.send_message(text, parse_mode="HTML")

    def send_antifreeze_alert(self, air_temp: float, threshold: float) -> bool:
        """Alerta de activación del modo antihielo cuando la temperatura desciende del umbral."""
        message = (
            f"❄️ <b>ALERTA ANTIHIELO ACTIVADA</b>\n\n"
            f"🌡️ <b>Temperatura exterior:</b> {air_temp:.1f} °C (Umbral: ≤ {threshold:.1f} °C)\n"
            f"⚙️ <b>Acción:</b> El plan horario queda anulado. La depuradora permanecerá "
            f"<b>ENCENDIDA</b> continuamente para evitar la congelación de tuberías."
        )
        return self.send_message(message, parse_mode="HTML")

    def send_antifreeze_recovery(self, air_temp: float, hysteresis: float) -> bool:
        """Alerta de desactivación del modo antihielo cuando la temperatura sube por encima de la histéresis."""
        message = (
            f"☀️ <b>ALERTA ANTIHIELO FINALIZADA</b>\n\n"
            f"🌡️ <b>Temperatura exterior:</b> {air_temp:.1f} °C (Histéresis: ≥ {hysteresis:.1f} °C)\n"
            f"⚙️ <b>Acción:</b> Se restablece el funcionamiento habitual conforme al "
            f"<b>plan horario programado</b>."
        )
        return self.send_message(message, parse_mode="HTML")