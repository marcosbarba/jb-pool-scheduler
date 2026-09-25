import pytest
from jb_pool_scheduler.core.heuristic import calculate_filtration_hours


@pytest.mark.parametrize(
    "temp,expected_hours",
    [
        (33.0, 12),
        (30.0, 12),
        (29.8, 11),
        (29.0, 11),
        (28.5, 10),
        (28.0, 10),
        (27.1, 9),
        (27.0, 9),
        (26.9, 8),
        (26.0, 8),
        (25.4, 7),
        (25.0, 7),
        (24.3, 6),
        (24.0, 6),
        (23.8, 5),
        (22.0, 5),
        (21.5, 5),
        (20.0, 5),
        (19.2, 4),
        (19.0, 4),
        (18.5, 3),
        (18.0, 3),
        (17.7, 2),
        (17.0, 2),
        (16.3, 1),
        (16.0, 1),
        (15.9, 0),
        (15.0, 0),
        (8.0, 0),
    ],
)
def test_calculate_filtration_hours_table(temp: float, expected_hours: int) -> None:
    assert calculate_filtration_hours(temp) == expected_hours