"""Capa de persistencia con SQLite para registros de temperatura y planes de filtración."""

import sqlite3
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jb_pool_scheduler.config import Settings, get_settings
from jb_pool_scheduler.core.optimizer import TimeInterval


class Repository:
    """Gestiona las lecturas térmicas y los intervalos programados en SQLite."""

    def __init__(self, db_path: Path | None = None, tz_name: str | None = None) -> None:
        settings: Settings = get_settings()
        self.db_path = db_path or settings.SQLITE_DB_PATH
        self.tz = ZoneInfo(tz_name or settings.TZ)
        self._ensure_db_dir()
        self._init_schema()

    def _ensure_db_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            # 1. Crear tablas si no existen
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS temperature_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_at TEXT NOT NULL,
                    temperature REAL NOT NULL,
                    sensor_type TEXT NOT NULL DEFAULT 'water'
                );

                CREATE TABLE IF NOT EXISTS daily_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_date TEXT NOT NULL,
                    start_hour INTEGER NOT NULL,
                    end_hour INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(schedule_date, start_hour, end_hour)
                );

                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )

            # 2. Migración: agregar la columna si la tabla ya existía de antes
            columns = [
                row["name"]
                for row in conn.execute("PRAGMA table_info(temperature_samples)").fetchall()
            ]
            if "sensor_type" not in columns:
                conn.execute(
                    "ALTER TABLE temperature_samples ADD COLUMN sensor_type TEXT NOT NULL DEFAULT 'water'"
                )

            # 3. Crear índices una vez asegurada la presencia de sensor_type
            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_temp_query 
                ON temperature_samples(sensor_type, recorded_at);

                CREATE INDEX IF NOT EXISTS idx_schedule_date 
                ON daily_schedules(schedule_date);
                """
            )

    def record_temperature(self, temp: float, sensor_type: str = "water", dt: datetime | None = None) -> None:
        """Registra una lectura térmica indicando si proviene de 'water' o 'air'."""
        now = dt or datetime.now(self.tz)
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO temperature_samples (recorded_at, temperature, sensor_type) VALUES (?, ?, ?)",
                (now.isoformat(), round(temp, 2), sensor_type),
            )

    def get_temperature_extrema_for_day(
        self, sensor_type: str = "water", target_date: date | None = None
    ) -> tuple[float | None, float | None]:
        """Devuelve (min, max) de un tipo de sensor para una fecha concreta (00:00 a 23:59)."""
        day = target_date or datetime.now(self.tz).date()
        day_str = day.isoformat()
        start_iso = f"{day_str}T00:00:00"
        end_iso = f"{day_str}T23:59:59"

        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT MIN(temperature) AS min_val, MAX(temperature) AS max_val
                FROM temperature_samples
                WHERE sensor_type = ? AND recorded_at BETWEEN ? AND ?
                """,
                (sensor_type, start_iso, end_iso),
            ).fetchone()

        if row and row["min_val"] is not None:
            return float(row["min_val"]), float(row["max_val"])
        return None, None

    def get_min_temperature_for_day(self, target_date: date | None = None) -> float | None:
        """Compatibilidad retroactiva: devuelve la mínima de agua registrada."""
        min_temp, _ = self.get_temperature_extrema_for_day("water", target_date)
        return min_temp

    def save_daily_schedule(self, target_date: date, intervals: list[TimeInterval]) -> None:
        date_str = target_date.isoformat()
        now_str = datetime.now(self.tz).isoformat()
        with self._get_connection() as conn:
            conn.execute("DELETE FROM daily_schedules WHERE schedule_date = ?", (date_str,))
            conn.executemany(
                """
                INSERT INTO daily_schedules (schedule_date, start_hour, end_hour, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [(date_str, i.start_hour, i.end_hour, now_str) for i in intervals],
            )

    def get_schedule_for_date(self, target_date: date) -> list[TimeInterval]:
        date_str = target_date.isoformat()
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT start_hour, end_hour FROM daily_schedules WHERE schedule_date = ? ORDER BY start_hour ASC",
                (date_str,),
            ).fetchall()
        return [TimeInterval(start_hour=r["start_hour"], end_hour=r["end_hour"]) for r in rows]

    def is_pump_scheduled(self, dt: datetime | None = None) -> bool:
        current_dt = dt or datetime.now(self.tz)
        date_str = current_dt.date().isoformat()
        current_hour = current_dt.hour
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM daily_schedules
                WHERE schedule_date = ? AND ? >= start_hour AND ? < end_hour
                LIMIT 1
                """,
                (date_str, current_hour, current_hour),
            ).fetchone()
        return row is not None

    def get_system_state(self, key: str, default: str = "") -> str:
        with self._get_connection() as conn:
            row = conn.execute("SELECT value FROM system_state WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_system_state(self, key: str, value: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO system_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )