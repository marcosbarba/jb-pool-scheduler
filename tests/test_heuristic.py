"""Tests de propiedades de la heurística de horas según temperatura.

No fijan valores concretos de la tabla (se está ajustando), solo invariantes
que cualquier tabla razonable debe cumplir.
"""

import pytest

from jb_pool_scheduler.core.heuristic import (
    _FILTRATION_THRESHOLDS,
    calculate_filtration_hours,
)

TEMPS = [t / 10 for t in range(-50, 450)]  # -5.0 a 44.9 °C en pasos de 0.1


def test_hours_within_valid_range() -> None:
    assert all(1 <= calculate_filtration_hours(t) <= 24 for t in TEMPS)


def test_hours_never_decrease_with_temperature() -> None:
    hours = [calculate_filtration_hours(t) for t in TEMPS]
    assert hours == sorted(hours)


def test_extremes() -> None:
    assert calculate_filtration_hours(-10.0) == 1
    assert calculate_filtration_hours(60.0) == max(h for _, h in _FILTRATION_THRESHOLDS)


def test_thresholds_are_sorted_descending() -> None:
    bounds = [b for b, _ in _FILTRATION_THRESHOLDS]
    assert bounds == sorted(bounds, reverse=True)


@pytest.mark.parametrize(("bound", "hours"), _FILTRATION_THRESHOLDS)
def test_threshold_lower_bound_is_inclusive(bound: float, hours: int) -> None:
    """Cada umbral se alcanza justo en su límite inferior (intervalos [a, b))."""
    assert calculate_filtration_hours(bound) >= hours
    assert calculate_filtration_hours(bound - 0.01) <= hours
