"""Preguntas A y B: fórmula vs simulación, y curva inventario vs fill rate.

La simulación se calibra con dos remuestreos de la demanda: bootstrap diario
por día de semana (días independientes) y bootstrap por bloques de días
consecutivos (conserva la autocorrelación). Ambos usan los mismos lead times.

Cada producto usa su propio generador aleatorio, derivado de
`(semilla, índice global del producto, etapa)`. Así el tamaño del lote solo
cambia cuántos productos se simulan juntos (memoria), nunca los resultados.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from inventario.backtest import backtest_con_lead_times, n_revisiones
from inventario.datos import DatosTienda
from inventario.demanda import (ajustar_distribuciones, censura_sospechosa,
                                clasificar, muestrear_demanda,
                                muestrear_demanda_bloques, primera_venta)
from inventario.politicas import s_formula, s_simulacion
from inventario.simulador import Metricas, muestrear_lead_times

# Etapas de la semilla por producto
ETAPA_CALIBRACION = 0  # demanda bootstrap y lead times de la calibración
ETAPA_BACKTEST = 1     # lead times del backtest
ETAPA_BLOQUES = 2      # demanda bootstrap por bloques de la calibración
Z_TOPE = 3.72          # 99,99%: base del tope de búsqueda s_max

Progreso = Callable[[int, int], None]


@dataclass
class Config:
    R: int = 7
    lead_times: tuple[int, ...] = (2, 3, 4, 5)
    reps: int = 200
    calentamiento: int = 28
    dias_sim: int = 364
    costo_anual: float = 0.25
    semilla: int = 2026
    lote: int = 250
    bloque: int = 28
    meta_a: float = 0.95
    metas_b: tuple[float, ...] = (0.85, 0.90, 0.95, 0.97, 0.98, 0.99)


@dataclass
class _Base:
    """Datos por producto comunes a ambas preguntas."""

    calib: np.ndarray      # (dias_calib, items) int64
    prueba: np.ndarray     # (dias_prueba, items) int64
    inicio: np.ndarray     # primera venta en calibración, -1 si nunca
    validos: np.ndarray    # índices de productos con ventas en calibración
    S_formula: np.ndarray  # (items,) int64
    s_max: np.ndarray      # (items,) int64


def _rng(cfg: Config, j: int, etapa: int) -> np.random.Generator:
    return np.random.default_rng([cfg.semilla, int(j), etapa])


def _base(datos: DatosTienda, cfg: Config) -> _Base:
    calib = np.rint(datos.ventas_calib).astype(np.int64)
    prueba = np.rint(datos.ventas_prueba).astype(np.int64)
    inicio = primera_venta(calib)
    items = calib.shape[1]
    mu, sigma = np.zeros(items), np.zeros(items)
    for j in np.flatnonzero(inicio >= 0):
        x = calib[inicio[j]:, j]
        mu[j] = x.mean()
        sigma[j] = x.std(ddof=1) if len(x) > 1 else 0.0
    L_media = float(np.mean(cfg.lead_times))
    z = round(float(stats.norm.ppf(cfg.meta_a)), 3)  # z tabulado: 1,645 para 95%
    S_f = s_formula(mu, sigma, cfg.R, L_media, z)
    s_max = s_formula(mu, sigma, cfg.R, L_media, Z_TOPE) * 2 + 10
    return _Base(calib, prueba, inicio, np.flatnonzero(inicio >= 0), S_f, s_max)


def _lotes(validos: np.ndarray, lote: int) -> list[np.ndarray]:
    return [validos[k:k + lote] for k in range(0, len(validos), max(1, lote))]


def _calibracion(datos: DatosTienda, cfg: Config, base: _Base,
                 idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Demanda bootstrap `(reps, calentamiento + dias_sim, lote)` y lead times."""
    n = cfg.calentamiento + cfg.dias_sim
    # Mismo calendario que el backtest: el día `calentamiento` es el 1.er día de prueba.
    dow_sim = (datos.dow_prueba[0] - cfg.calentamiento + np.arange(n)) % 7
    n_rev = n_revisiones(n, cfg.R)
    dem, lts = [], []
    for j in idx:
        rng = _rng(cfg, j, ETAPA_CALIBRACION)
        dem.append(muestrear_demanda(rng, base.calib[:, [j]], datos.dow_calib,
                                     dow_sim, cfg.reps, base.inicio[[j]]))
        lts.append(muestrear_lead_times(rng, cfg.reps, n_rev, 1, cfg.lead_times))
    return np.concatenate(dem, axis=2), np.concatenate(lts, axis=2)


def _calibracion_bloques(datos: DatosTienda, cfg: Config, base: _Base,
                         idx: np.ndarray) -> np.ndarray:
    """Demanda bootstrap por bloques `(reps, calentamiento + dias_sim, lote)`.

    Mismo calendario que `_calibracion`; los lead times se reutilizan de ahí.
    """
    n = cfg.calentamiento + cfg.dias_sim
    dow_inicio = int((datos.dow_prueba[0] - cfg.calentamiento) % 7)
    return np.concatenate([
        muestrear_demanda_bloques(_rng(cfg, j, ETAPA_BLOQUES), base.calib[:, [j]],
                                  datos.dow_calib, dow_inicio, n, cfg.reps,
                                  base.inicio[[j]], cfg.bloque)
        for j in idx], axis=2)


def _backtests(cfg: Config, base: _Base, idx: np.ndarray,
               niveles: list[np.ndarray]) -> list[Metricas]:
    """Backtest de cada vector S en `niveles` con los mismos lead times."""
    cal = base.calib[-cfg.calentamiento:, idx]
    prueba = base.prueba[:, idx]
    n_rev = n_revisiones(len(cal) + len(prueba), cfg.R)
    lt = np.concatenate([
        muestrear_lead_times(_rng(cfg, j, ETAPA_BACKTEST), cfg.reps, n_rev, 1,
                             cfg.lead_times)
        for j in idx], axis=2)
    return [backtest_con_lead_times(cal, prueba, S, cfg.R, lt) for S in niveles]


def _con_vacios(valores: np.ndarray, valido: np.ndarray, tipo: str) -> pd.Series:
    """Serie de tipo anulable con NA donde `valido` es False."""
    return pd.Series(valores).astype(tipo).mask(~valido)


def pregunta_a(datos: DatosTienda, cfg: Config,
               progreso: Progreso | None = None) -> pd.DataFrame:
    """Fórmula (z de meta_a) vs S calibrado por simulación (α = meta_a), por producto.

    La simulación se calibra con bootstrap diario (`*_sim`) y por bloques
    (`*_bloques`); las tres políticas se evalúan en el mismo backtest.

    Los productos sin ventas en calibración quedan con clase "sin_ventas" y
    métricas vacías; `resumen_a` los excluye y los cuenta.
    """
    base = _base(datos, cfg)
    items = base.calib.shape[1]
    clase = clasificar(base.calib, base.inicio)
    censura = pd.array([pd.NA] * items, dtype="boolean")
    mejor = np.full(items, "sin_ventas", dtype=object)
    for j in base.validos:
        x = base.calib[base.inicio[j]:, j]
        censura[j] = censura_sospechosa(x)
        mejor[j] = ajustar_distribuciones(x)["mejor"]

    S_sim = np.zeros(items, dtype=np.int64)
    S_bl = np.zeros(items, dtype=np.int64)
    alcanzado = np.zeros(items, dtype=bool)
    alcanzado_bl = np.zeros(items, dtype=bool)
    met = {f"{m}_{p}": np.full(items, np.nan) for m in ("alpha", "fill", "inv")
           for p in ("formula", "sim", "bloques")}
    lotes = _lotes(base.validos, cfg.lote)
    for k, idx in enumerate(lotes):
        dem, lt = _calibracion(datos, cfg, base, idx)
        S, ok = s_simulacion(dem, lt, cfg.R, cfg.meta_a, "ciclo", base.s_max[idx],
                             cfg.calentamiento)
        del dem
        S_sim[idx], alcanzado[idx] = S, ok
        dem_bl = _calibracion_bloques(datos, cfg, base, idx)
        S_b, ok_b = s_simulacion(dem_bl, lt, cfg.R, cfg.meta_a, "ciclo",
                                 base.s_max[idx], cfg.calentamiento)
        del dem_bl
        S_bl[idx], alcanzado_bl[idx] = S_b, ok_b
        mf, ms, mb = _backtests(cfg, base, idx, [base.S_formula[idx], S, S_b])
        for nombre, m in (("formula", mf), ("sim", ms), ("bloques", mb)):
            met[f"alpha_{nombre}"][idx] = m.servicio_ciclo
            met[f"fill_{nombre}"][idx] = m.fill_rate
            met[f"inv_{nombre}"][idx] = m.inventario_prom
        if progreso:
            progreso(k + 1, len(lotes))

    valido = base.inicio >= 0
    precio = np.asarray(datos.precio, dtype=float)
    return pd.DataFrame({
        "item_id": list(datos.item_ids),
        "categoria": list(datos.categorias),
        "clase": clase,
        "censura": censura,
        "mejor_dist": mejor,
        "S_formula": _con_vacios(base.S_formula, valido, "Int64"),
        "S_sim": _con_vacios(S_sim, valido, "Int64"),
        "alcanzado": _con_vacios(alcanzado, valido, "boolean"),
        "alpha_formula": met["alpha_formula"],
        "alpha_sim": met["alpha_sim"],
        "fill_formula": met["fill_formula"],
        "fill_sim": met["fill_sim"],
        "inv_usd_formula": met["inv_formula"] * precio,
        "inv_usd_sim": met["inv_sim"] * precio,
        "S_bloques": _con_vacios(S_bl, valido, "Int64"),
        "alcanzado_bloques": _con_vacios(alcanzado_bl, valido, "boolean"),
        "alpha_bloques": met["alpha_bloques"],
        "fill_bloques": met["fill_bloques"],
        "inv_usd_bloques": met["inv_bloques"] * precio,
        "demanda_prueba": base.prueba.sum(axis=0).astype(np.int64),
    })


def _fill_ponderado(fill: np.ndarray, demanda: np.ndarray) -> float:
    """Fill rate agregado: media de fill ponderada por la demanda de prueba."""
    con_fill = ~np.isnan(fill)
    peso = demanda[con_fill].sum()
    return float((fill[con_fill] * demanda[con_fill]).sum() / peso) if peso > 0 else 1.0


def _agregar(g: pd.DataFrame) -> dict:
    demanda = g["demanda_prueba"].to_numpy(dtype=float)
    return {
        "n": len(g),
        "alpha_formula": g["alpha_formula"].mean(),
        "alpha_sim": g["alpha_sim"].mean(),
        "fill_formula": g["fill_formula"].mean(),
        "fill_sim": g["fill_sim"].mean(),
        "inv_usd_formula": g["inv_usd_formula"].sum(),  # NaN (sin precio) fuera
        "inv_usd_sim": g["inv_usd_sim"].sum(),
        "n_sin_precio": int(g["inv_usd_sim"].isna().sum()),
        "n_no_alcanzado": int((~g["alcanzado"].astype(bool)).sum()),
        "alpha_bloques": g["alpha_bloques"].mean(),
        "fill_bloques": g["fill_bloques"].mean(),
        "inv_usd_bloques": g["inv_usd_bloques"].sum(),
        **{f"fill_pond_{p}": _fill_ponderado(g[f"fill_{p}"].to_numpy(dtype=float),
                                              demanda)
           for p in ("formula", "sim", "bloques")},
    }


def resumen_a(df: pd.DataFrame) -> pd.DataFrame:
    """Medias de α y fill logrados y suma de inventario USD por clase y categoría.

    Filas con `agrupacion` en {"clase", "categoria", "total", "excluidos"}; la
    fila "excluidos" cuenta los productos sin ventas en calibración.
    """
    ok = df[df["clase"] != "sin_ventas"]
    filas = []
    for agrupacion in ("clase", "categoria"):
        for grupo, g in ok.groupby(agrupacion, sort=True):
            filas.append({"agrupacion": agrupacion, "grupo": grupo, **_agregar(g)})
    filas.append({"agrupacion": "total", "grupo": "TOTAL", **_agregar(ok)})
    filas.append({"agrupacion": "excluidos", "grupo": "sin_ventas",
                  "n": int((df["clase"] == "sin_ventas").sum())})
    res = pd.DataFrame(filas)
    return res.astype({c: "Int64" for c in ("n", "n_sin_precio", "n_no_alcanzado")})


def curva_b(datos: DatosTienda, cfg: Config,
            progreso: Progreso | None = None) -> pd.DataFrame:
    """Inventario USD y fill logrado en la prueba con S calibrado por fill rate.

    Una curva por método de calibración (`metodo` "diario" o "bloques"). Todas
    las metas y ambos métodos usan los mismos lead times de calibración y de
    backtest (números aleatorios comunes), así S crece con la meta.
    `n_no_alcanzado` cuenta los productos cuya meta no se alcanzó ni con s_max.
    """
    base = _base(datos, cfg)
    items = base.calib.shape[1]
    claves = [(metodo, meta) for metodo in ("diario", "bloques") for meta in cfg.metas_b]
    inv = {c: np.full(items, np.nan) for c in claves}
    fill = {c: np.full(items, np.nan) for c in claves}
    no_ok = {c: np.zeros(items, dtype=bool) for c in claves}
    lotes = _lotes(base.validos, cfg.lote)
    for k, idx in enumerate(lotes):
        dem, lt = _calibracion(datos, cfg, base, idx)
        res = [s_simulacion(dem, lt, cfg.R, meta, "fill", base.s_max[idx],
                            cfg.calentamiento) for meta in cfg.metas_b]
        del dem
        dem = _calibracion_bloques(datos, cfg, base, idx)
        res += [s_simulacion(dem, lt, cfg.R, meta, "fill", base.s_max[idx],
                             cfg.calentamiento) for meta in cfg.metas_b]
        del dem
        metricas = _backtests(cfg, base, idx, [S for S, _ in res])
        for c, (_, ok), m in zip(claves, res, metricas):
            inv[c][idx] = m.inventario_prom
            fill[c][idx] = m.fill_rate
            no_ok[c][idx] = ~ok
        if progreso:
            progreso(k + 1, len(lotes))

    precio = np.asarray(datos.precio, dtype=float)
    demanda_prueba = base.prueba.sum(axis=0).astype(float)
    categorias = np.asarray(datos.categorias, dtype=object)
    grupos = [(c, categorias == c) for c in sorted(set(datos.categorias))]
    grupos.append(("TOTAL", np.ones(items, dtype=bool)))
    filas = []
    for metodo, meta in claves:
        c = (metodo, meta)
        usd = inv[c] * precio
        for nombre, mascara in grupos:
            inventario = float(np.nansum(usd[mascara]))
            filas.append({"metodo": metodo, "meta": meta, "categoria": nombre,
                          "inventario_usd": inventario,
                          "costo_anual_usd": inventario * cfg.costo_anual,
                          "fill_logrado": _fill_ponderado(fill[c][mascara],
                                                          demanda_prueba[mascara]),
                          "n_no_alcanzado": int(no_ok[c][mascara].sum())})
    return pd.DataFrame(filas)
