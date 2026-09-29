"""Tests unitarios para validar la regla heurística de horas según temperatura."""

import pytest

from jb_pool_scheduler.core.heuristic import calculate_filtration_hours


@pytest.mark.parametrize(
    ("temp", "expected_hours"),
    [
        (32.0, 12),
        (30.0, 12),
        (29.5, 11),
        (29.0, 11),
        (28.0, 10),
        (27.0, 9),
        (26.0, 8),
        (25.0, 7),
        (24.0, 6),
        (23.5, 5),
        (20.0, 5),  # 20 a 23 °C asignan 5 h
        (19.0, 4),
        (18.0, 3),
        (17.0, 2),
        (16.5, 1),
        (15.9, 1),  # Límite inferior: por debajo de 16 °C no filtra
        (12.0, 1),
        (0.0, 1),
    ],
)
def test_calculate_filtration_hours_thresholds(temp: float, expected_hours: int) -> None:
    """Valida los límites exactos y franjas intermedias de la escala térmica."""
    assert calculate_filtration_hours(temp) == expected_hours