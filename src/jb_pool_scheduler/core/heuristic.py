"""Regla heurística para calcular las horas de filtración según la temperatura del agua."""

# Cada temperatura entera T de la tabla original representa el intervalo [T-0.5, T+0.5).
# (umbral inferior inclusivo en °C, horas), de mayor a menor temperatura.
_FILTRATION_THRESHOLDS: tuple[tuple[float, int], ...] = (
    (30.5, 12),  # > 30
    (29.5, 11),  # 30
    (28.5, 10),  # 29
    (27.5, 8),  # 28
    (26.5, 7),  # 27
    (25.5, 6),  # 26
    (23.5, 5),  # 24 y 25
    (21.5, 4),  # 22 y 23
    (19.5, 3),  # 20 y 21
    (14.5, 2),  # 15 a 19
)


def calculate_filtration_hours(water_temp: float) -> int:
    """Calcula las horas diarias de depuración según la temperatura del agua (media de mínima y máxima del día).

    Tabla (temperatura redondeada -> horas), donde cada valor cubre [T-0.5, T+0.5):
    - > 30: 12 h | 30: 11 h | 29: 10 h | 28: 8 h | 27: 7 h | 26: 6 h
    - 24-25: 5 h | 22-23: 4 h | 20-21: 3 h | 15-19: 2 h | < 14.5 (<14): 1 h
    """
    for lower_bound, hours in _FILTRATION_THRESHOLDS:
        if water_temp >= lower_bound:
            return hours
    return 1
