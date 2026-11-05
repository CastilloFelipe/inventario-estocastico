"""Políticas de reposición (R, S): fórmula clásica y búsqueda por simulación."""
from typing import Literal

import numpy as np

from inventario.simulador import simular


def s_formula(
    mu: np.ndarray, sigma: np.ndarray, R: int, L_media: float, z: float
) -> np.ndarray:
    """S = ceil(mu*(R+L) + z*sigma*sqrt(R+L)), con mínimo 0."""
    horizonte = R + L_media
    S = np.ceil(np.asarray(mu) * horizonte + z * np.asarray(sigma) * np.sqrt(horizonte))
    return np.maximum(0, S).astype(np.int64)


def s_simulacion(
    demanda: np.ndarray,
    lead_times: np.ndarray,
    R: int,
    meta: float,
    metrica: Literal["ciclo", "fill"],
    s_max: np.ndarray,
    calentamiento: int = 28,
) -> tuple[np.ndarray, np.ndarray]:
    """Menor S entero en [0, s_max] que cumple la meta, por ítem.

    Búsqueda binaria vectorizada: una llamada a `simular` por paso para todos los
    ítems a la vez, con la misma demanda y lead times (números aleatorios comunes).
    Devuelve `(S, alcanzado)`; si ni s_max cumple, S = s_max y alcanzado = False.
    """
    if metrica not in ("ciclo", "fill"):
        raise ValueError(f"métrica desconocida: {metrica!r}")
    atributo = "servicio_ciclo" if metrica == "ciclo" else "fill_rate"

    # Supone que el servicio es monótono creciente en S con números aleatorios comunes.
    def cumple(S: np.ndarray) -> np.ndarray:
        m = simular(demanda, S, R, lead_times, calentamiento)
        return getattr(m, atributo) >= meta

    hi = np.asarray(s_max, dtype=np.int64).copy()
    lo = np.zeros_like(hi)
    alcanzado = cumple(hi)

    # Invariante: el mínimo (o s_max si es inalcanzable) está en [lo, hi].
    while (lo < hi).any():
        mid = (lo + hi) // 2
        ok = cumple(mid)
        hi = np.where(ok, mid, hi)
        lo = np.where(ok, lo, np.minimum(mid + 1, hi))
    return lo, alcanzado
