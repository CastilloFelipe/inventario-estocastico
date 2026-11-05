"""Simulador vectorizado de inventario con política de revisión periódica (R, S).

Ventas perdidas, lead time aleatorio por pedido. No depende de ningún conjunto
de datos: recibe demanda, niveles S y lead times ya muestreados.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class Trayectoria:
    """Réplica 0 tras el calentamiento, todas de forma `(dias_medidos, items)`."""

    inventario: np.ndarray  # al cierre de cada día
    perdidas: np.ndarray    # unidades de demanda no atendidas


@dataclass
class Metricas:
    """Métricas por ítem, todas de forma `(items,)`."""

    fill_rate: np.ndarray
    servicio_ciclo: np.ndarray
    inventario_prom: np.ndarray


def muestrear_lead_times(
    rng: np.random.Generator,
    reps: int,
    n_revisiones: int,
    items: int,
    valores: tuple[int, ...] = (2, 3, 4, 5),
) -> np.ndarray:
    """Lead times uniformes discretos, forma `(reps, n_revisiones, items)`."""
    return rng.choice(np.asarray(valores, dtype=np.int64), size=(reps, n_revisiones, items))


def simular(
    demanda: np.ndarray,
    S: np.ndarray,
    R: int,
    lead_times: np.ndarray,
    calentamiento: int = 28,
    devolver_trayectoria: bool = False,
) -> "Metricas | tuple[Metricas, Trayectoria]":
    """Simula la política (R, S) y devuelve métricas por ítem.

    demanda: `(reps, dias, items)`; S: `(items,)`; lead_times: `(reps, n_rev, items)`
    con una entrada por revisión (la k-ésima revisión ocurre en el día k * R).

    Dinámica diaria: (1) llegan pedidos; (2) si t % R == 0, al inicio del día se
    pide max(0, S - inv - en_tránsito), que llega en t + L; (3) se vende
    min(inv, demanda) y el resto se pierde. Un pedido protege exactamente R + L días.
    Inventario inicial = S. Las métricas se acumulan solo desde `calentamiento`.

    Con `devolver_trayectoria=True` devuelve `(Metricas, Trayectoria)`, con la
    trayectoria diaria de la réplica 0 posterior al calentamiento. Las métricas
    no cambian.
    """
    demanda = np.asarray(demanda)
    reps, dias, items = demanda.shape
    S = np.asarray(S, dtype=np.int64)
    max_l = int(lead_times.max()) if lead_times.size else 1
    n = max_l + 1  # tamaño del arreglo circular de pedidos en tránsito

    inv = np.broadcast_to(S, (reps, items)).copy()
    pipeline = np.zeros((reps, n, items), dtype=np.int64)
    en_transito = np.zeros((reps, items), dtype=np.int64)
    idx_reps = np.arange(reps)[:, None]
    idx_items = np.arange(items)[None, :]

    vendido = np.zeros((reps, items))
    demandado = np.zeros((reps, items))
    suma_inv = np.zeros((reps, items))
    dias_medidos = 0
    perdida_ventana = np.zeros((reps, items), dtype=bool)
    ventanas_ok = np.zeros((reps, items))
    n_ventanas = 0
    inv_dia, perdida_dia = [], []

    for t in range(dias):
        # (1) llegadas
        llega = pipeline[:, t % n, :]
        inv += llega
        en_transito -= llega
        pipeline[:, t % n, :] = 0

        # (2) revisión y pedido al inicio del día
        if t % R == 0:
            pedido = np.maximum(0, S - inv - en_transito)
            L = lead_times[:, t // R, :]
            pipeline[idx_reps, (t + L) % n, idx_items] += pedido
            en_transito += pedido

        # (3) ventas; lo no atendido se pierde
        d = demanda[:, t, :]
        v = np.minimum(inv, d)
        inv -= v

        if t >= calentamiento:
            vendido += v
            demandado += d
            suma_inv += inv
            dias_medidos += 1
            if devolver_trayectoria:
                inv_dia.append(inv[0].copy())
                perdida_dia.append((d[0] - v[0]).copy())

        # ventanas [k*R, (k+1)*R) completas que empiezan tras el calentamiento
        ini = t - t % R
        if ini >= calentamiento:
            if t % R == 0:
                perdida_ventana[:] = False
            perdida_ventana |= d > v
            if t % R == R - 1:
                ventanas_ok += ~perdida_ventana
                n_ventanas += 1

    vend = vendido.sum(axis=0)
    dem = demandado.sum(axis=0)
    fill = np.where(dem > 0, vend / np.where(dem > 0, dem, 1), 1.0)
    alfa = ventanas_ok.mean(axis=0) / n_ventanas if n_ventanas else np.ones(items)
    inv_prom = (suma_inv / max(dias_medidos, 1)).mean(axis=0)
    m = Metricas(fill_rate=fill, servicio_ciclo=alfa, inventario_prom=inv_prom)
    if not devolver_trayectoria:
        return m
    shape = (0, items)
    return m, Trayectoria(
        inventario=np.array(inv_dia, dtype=np.int64).reshape(-1, items) if inv_dia else np.zeros(shape, np.int64),
        perdidas=np.array(perdida_dia, dtype=np.int64).reshape(-1, items) if perdida_dia else np.zeros(shape, np.int64))
