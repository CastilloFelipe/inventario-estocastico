"""Backtest: reproduce la demanda real del período de prueba con un S dado.

La demanda es fija (la real); solo el lead time es aleatorio, con varias réplicas.
"""
import math

import numpy as np

from inventario.simulador import Metricas, muestrear_lead_times, simular


def n_revisiones(dias: int, R: int) -> int:
    """Revisiones necesarias para cubrir `dias` días (con holgura de una)."""
    return math.ceil(dias / R) + 1


def backtest_con_lead_times(
    calentamiento_demanda: np.ndarray,
    ventas_prueba: np.ndarray,
    S: np.ndarray,
    R: int,
    lead_times: np.ndarray,
) -> Metricas:
    """Backtest con lead times ya muestreados `(reps, n_rev, items)`.

    Antepone `calentamiento_demanda` (últimos días de calibración) a la prueba;
    el simulador los descarta de las métricas. La demanda real se replica en
    todas las réplicas sin copiarla.
    """
    real = np.rint(np.vstack([calentamiento_demanda, ventas_prueba])).astype(np.int64)
    reps = lead_times.shape[0]
    demanda = np.broadcast_to(real[None], (reps, *real.shape))
    return simular(demanda, S, R, lead_times, calentamiento=len(calentamiento_demanda))


def backtest(
    calentamiento_demanda: np.ndarray,
    ventas_prueba: np.ndarray,
    S: np.ndarray,
    R: int,
    rng: np.random.Generator,
    reps: int = 50,
    valores_lt: tuple[int, ...] = (2, 3, 4, 5),
) -> Metricas:
    """Backtest con demanda real fija y `reps` réplicas del lead time aleatorio."""
    dias = len(calentamiento_demanda) + len(ventas_prueba)
    items = np.asarray(ventas_prueba).shape[1]
    lt = muestrear_lead_times(rng, reps, n_revisiones(dias, R), items, valores_lt)
    return backtest_con_lead_times(calentamiento_demanda, ventas_prueba, S, R, lt)
