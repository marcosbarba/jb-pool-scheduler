from datetime import date, datetime
from zoneinfo import ZoneInfo

from jb_pool_scheduler.storage.repository import Repository

TZ = ZoneInfo("Europe/Madrid")


def test_temperature_extrema_separation_by_sensor_type(tmp_path):
    """Verifica que las lecturas de agua y aire no se mezclen al calcular min y max."""
    db_file = tmp_path / "test_extrema.db"
    repo = Repository(db_path=db_file, tz_name="Europe/Madrid")
    target_date = date(2026, 9, 29)

    # 1. Registrar lecturas de agua
    repo.record_temperature(22.0, sensor_type="water", dt=datetime(2026, 9, 29, 8, 0, tzinfo=TZ))
    repo.record_temperature(26.5, sensor_type="water", dt=datetime(2026, 9, 29, 15, 0, tzinfo=TZ))
    repo.record_temperature(24.0, sensor_type="water", dt=datetime(2026, 9, 29, 20, 0, tzinfo=TZ))

    # 2. Registrar lecturas de aire (con valores muy dispares)
    repo.record_temperature(12.0, sensor_type="air", dt=datetime(2026, 9, 29, 6, 0, tzinfo=TZ))
    repo.record_temperature(29.0, sensor_type="air", dt=datetime(2026, 9, 29, 14, 0, tzinfo=TZ))

    # 3. Comprobar extremos del agua
    w_min, w_max = repo.get_temperature_extrema_for_day(sensor_type="water", target_date=target_date)
    assert w_min == 22.0
    assert w_max == 26.5

    # 4. Comprobar extremos del aire
    a_min, a_max = repo.get_temperature_extrema_for_day(sensor_type="air", target_date=target_date)
    assert a_min == 12.0
    assert a_max == 29.0


def test_temperature_extrema_no_data_returns_none(tmp_path):
    """Comprueba que si no hay muestras registradas devuelva (None, None)."""
    db_file = tmp_path / "test_empty.db"
    repo = Repository(db_path=db_file, tz_name="Europe/Madrid")
    
    w_min, w_max = repo.get_temperature_extrema_for_day(sensor_type="water", target_date=date(2026, 9, 29))
    assert w_min is None
    assert w_max is None