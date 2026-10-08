"""Tests unitarios para validar la regla heurística de horas según temperatura."""

import pytest

from jb_pool_scheduler.core.heuristic import calculate_filtration_hours


@pytest.mark.parametrize(
    ("temp", "expected_hours"),
    [
        # Cada temperatura T cubre [T-0.5, T+0.5)
        (35.0, 12),
        (30.5, 12),  # límite inferior de ">30"
        (30.49, 11),
        (30.0, 11),
        (29.5, 11),
        (29.49, 10),
        (29.0, 10),
        (28.5, 10),
        (28.49, 8),
        (28.0, 8),
        (27.5, 8),
        (27.49, 7),
        (27.0, 7),
        (26.5, 7),
        (26.49, 6),
        (26.0, 6),
        (25.5, 6),
        (25.49, 5),
        (25.0, 5),
        (24.0, 5),
        (23.5, 5),
        (23.49, 4),
        (23.0, 4),
        (22.0, 4),
        (21.5, 4),
        (21.49, 3),
        (21.0, 3),
        (20.0, 3),
        (19.5, 3),
        (19.49, 2),
        (19.0, 2),
        (15.0, 2),
        (14.5, 2),  # límite inferior de la franja de 15 °C
        (14.49, 1),  # "<14" equivale a < 14.5
        (14.0, 1),
        (0.0, 1),
    ],
)
def test_calculate_filtration_hours_thresholds(temp: float, expected_hours: int) -> None:
    """Valida los límites exactos de cada intervalo [T-0.5, T+0.5)."""
    assert calculate_filtration_hours(temp) == expected_hours
