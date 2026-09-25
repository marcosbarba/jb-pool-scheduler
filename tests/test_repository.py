from datetime import date, datetime
from zoneinfo import ZoneInfo
from jb_pool_scheduler.core.optimizer import TimeInterval
from jb_pool_scheduler.storage.repository import Repository

TZ = ZoneInfo("Europe/Madrid")


def test_temperature_recording_and_min(tmp_path):
    db_file = tmp_path / "test.db"
    repo = Repository(db_path=db_file, tz_name="Europe/Madrid")

    day = date(2026, 9, 24)
    # Registrar varias temperaturas del día
    repo.record_temperature(24.5, dt=datetime(2026, 9, 24, 8, 0, tzinfo=TZ))
    repo.record_temperature(21.2, dt=datetime(2026, 9, 24, 6, 30, tzinfo=TZ))  # Mínima
    repo.record_temperature(26.0, dt=datetime(2026, 9, 24, 15, 0, tzinfo=TZ))

    # Lectura de otro día diferente
    repo.record_temperature(19.0, dt=datetime(2026, 9, 23, 5, 0, tzinfo=TZ))

    min_temp = repo.get_min_temperature_for_day(day)
    assert min_temp == 21.2


def test_save_and_retrieve_schedule(tmp_path):
    db_file = tmp_path / "test.db"
    repo = Repository(db_path=db_file, tz_name="Europe/Madrid")

    target_date = date(2026, 9, 25)
    intervals = [
        TimeInterval(start_hour=2, end_hour=6),
        TimeInterval(start_hour=14, end_hour=16),
    ]

    repo.save_daily_schedule(target_date, intervals)
    retrieved = repo.get_schedule_for_date(target_date)
    assert retrieved == intervals

    # Comprobación de encendido según la hora
    # A las 03:30 debe estar ENCENDIDA (dentro de 2 a 6)
    assert repo.is_pump_scheduled(datetime(2026, 9, 25, 3, 30, tzinfo=TZ)) is True
    # A las 06:00 ya debe estar APAGADA (fin de tramo a las 6)
    assert repo.is_pump_scheduled(datetime(2026, 9, 25, 6, 0, tzinfo=TZ)) is False
    # A las 10:00 debe estar APAGADA
    assert repo.is_pump_scheduled(datetime(2026, 9, 25, 10, 0, tzinfo=TZ)) is False