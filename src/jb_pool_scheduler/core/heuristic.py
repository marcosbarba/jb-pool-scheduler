"""Regla heurística para calcular las horas de filtración según la temperatura del agua."""


def calculate_filtration_hours(min_temp: float) -> int:
    """Calcula las horas diarias de depuración según la temperatura mínima registrada.

    Tabla de correspondencia:
    - >= 30 °C: 12 h
    - >= 29 °C: 11 h
    - >= 28 °C: 10 h
    - >= 27 °C: 9 h
    - >= 26 °C: 8 h
    - >= 25 °C: 7 h
    - >= 24 °C: 6 h
    - >= 20 °C: 5 h (cubre 20, 21, 22 y 23 °C)
    - >= 19 °C: 4 h
    - >= 18 °C: 3 h
    - >= 17 °C: 2 h
    - <  17 °C: 1 h
    """
    if min_temp >= 30.0:
        return 12
    if min_temp >= 29.0:
        return 11
    if min_temp >= 28.0:
        return 10
    if min_temp >= 27.0:
        return 9
    if min_temp >= 26.0:
        return 8
    if min_temp >= 25.0:
        return 7
    if min_temp >= 24.0:
        return 6
    if min_temp >= 20.0:
        return 5
    if min_temp >= 19.0:
        return 4
    if min_temp >= 18.0:
        return 3
    if min_temp >= 17.0:
        return 2
    return 1