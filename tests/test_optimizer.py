"""Tests unitarios para la ordenación de precios PVPC y consolidación de franjas."""

from jb_pool_scheduler.core.optimizer import (
    TimeInterval,
    consolidate_contiguous_hours,
    get_cheapest_intervals,
)


def test_consolidate_contiguous_hours_blocks():
    """Agrupa secuencias consecutivas en tramos cerrados."""
    hours = [1, 2, 3, 10, 11, 23]
    intervals = consolidate_contiguous_hours(hours)

    assert intervals == [
        TimeInterval(start_hour=1, end_hour=4),
        TimeInterval(start_hour=10, end_hour=12),
        TimeInterval(start_hour=23, end_hour=24),
    ]


def test_consolidate_unsorted_or_empty():
    """Tolera entradas desordenadas, duplicadas o vacías."""
    assert consolidate_contiguous_hours([]) == []
    assert consolidate_contiguous_hours([4, 2, 3, 2]) == [TimeInterval(start_hour=2, end_hour=5)]


def test_get_cheapest_intervals_target_zero():
    """Si el objetivo es 0 horas (invernaje), devuelve una lista vacía."""
    mock_prices = {h: 50.0 + h for h in range(24)}
    assert get_cheapest_intervals(mock_prices, target_hours=0) == []


def test_get_cheapest_intervals_exact_selection():
    """Valida que escoja exactamente las horas con menor coste numérico."""
    mock_prices = {
        0: 100.0, 1: 90.0, 2: 20.0, 3: 15.0, 4: 10.0, 5: 30.0,
        6: 80.0, 7: 85.0, 8: 95.0, 9: 110.0, 10: 40.0, 11: 35.0,
        12: 50.0, 13: 60.0, 14: 70.0, 15: 65.0, 16: 55.0, 17: 85.0,
        18: 120.0, 19: 130.0, 20: 115.0, 21: 105.0, 22: 95.0, 23: 75.0,
    }

    # Las 4 más baratas son: hora 4 (10), hora 3 (15), hora 2 (20), hora 5 (30)
    intervals = get_cheapest_intervals(mock_prices, target_hours=4)

    assert intervals == [TimeInterval(start_hour=2, end_hour=6)]
    assert sum(i.duration_hours for i in intervals) == 4