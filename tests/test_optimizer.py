from jb_pool_scheduler.core.optimizer import (
    TimeInterval,
    consolidate_contiguous_hours,
    get_cheapest_intervals,
)


def test_consolidate_contiguous_hours():
    # Caso clásico: bloques contiguos separados
    hours = [2, 3, 4, 14, 15]
    intervals = consolidate_contiguous_hours(hours)
    assert intervals == [
        TimeInterval(start_hour=2, end_hour=5),
        TimeInterval(start_hour=14, end_hour=16),
    ]


def test_consolidate_single_hours():
    # Franjas sin horas adyacentes
    hours = [1, 5, 9]
    intervals = consolidate_contiguous_hours(hours)
    assert intervals == [
        TimeInterval(start_hour=1, end_hour=2),
        TimeInterval(start_hour=5, end_hour=6),
        TimeInterval(start_hour=9, end_hour=10),
    ]


def test_consolidate_empty():
    assert consolidate_contiguous_hours([]) == []


def test_get_cheapest_intervals():
    # Simular 24 horas con precios variados
    mock_prices = {
        0: 0.15, 1: 0.12, 2: 0.08, 3: 0.05, 4: 0.04, 5: 0.06,
        6: 0.10, 7: 0.18, 8: 0.22, 9: 0.20, 10: 0.19, 11: 0.17,
        12: 0.14, 13: 0.11, 14: 0.07, 15: 0.09, 16: 0.13, 17: 0.16,
        18: 0.21, 19: 0.25, 20: 0.24, 21: 0.23, 22: 0.18, 23: 0.16,
    }

    # Pedimos las 5 horas más baratas: deben ser 4 (0.04), 3 (0.05), 5 (0.06), 14 (0.07), 2 (0.08)
    intervals = get_cheapest_intervals(mock_prices, target_hours=5)

    # Ordenadas cronológicamente y fusionadas: [2, 3, 4, 5] -> (2-6) y [14] -> (14-15)
    assert intervals == [
        TimeInterval(start_hour=2, end_hour=6),
        TimeInterval(start_hour=14, end_hour=15),
    ]
    assert sum(i.duration_hours for i in intervals) == 5