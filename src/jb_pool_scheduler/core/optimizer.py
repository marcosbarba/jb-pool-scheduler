"""Módulo de optimización económica y consolidación de franjas horarias."""

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TimeInterval:
    """Representa un intervalo de filtración continuo."""

    start_hour: int
    end_hour: int

    @property
    def duration_hours(self) -> int:
        return self.end_hour - self.start_hour

    def format_range(self) -> str:
        return f"{self.start_hour:02d}:00 - {self.end_hour:02d}:00"

    def __str__(self) -> str:
        return f"({self.start_hour}-{self.end_hour})"


def consolidate_contiguous_hours(hours: Sequence[int]) -> list[TimeInterval]:
    """Agrupa horas consecutivas individuales en tramos continuos.

    Ejemplo: [2, 3, 4, 14, 15] -> [(2, 5), (14, 16)]
    """
    if not hours:
        return []

    sorted_hours = sorted(set(hours))
    intervals: list[TimeInterval] = []

    start = sorted_hours[0]
    end = start + 1

    for h in sorted_hours[1:]:
        if h == end:
            end += 1
        else:
            intervals.append(TimeInterval(start_hour=start, end_hour=end))
            start = h
            end = h + 1

    intervals.append(TimeInterval(start_hour=start, end_hour=end))
    return intervals


def get_cheapest_intervals(
    hourly_prices: dict[int, float], target_hours: int
) -> list[TimeInterval]:
    """Selecciona las N horas de menor precio y genera los tramos consolidados.

    :param hourly_prices: Diccionario con la hora (0-23) y el precio en €/MWh o €/kWh.
    :param target_hours: Número de horas requeridas de depuración.
    :return: Lista de objetos TimeInterval agrupados y cronológicos.
    """
    if target_hours <= 0:
        return []

    # Limitar el objetivo a un máximo de 24 horas
    target_hours = min(target_hours, len(hourly_prices))

    # Ordenar por precio ascendente y tomar las N más baratas
    cheapest = sorted(hourly_prices.items(), key=lambda item: item[1])[:target_hours]

    # Extraer las horas y agruparlas de forma cronológica
    selected_hours = [hour for hour, _ in cheapest]
    return consolidate_contiguous_hours(selected_hours)