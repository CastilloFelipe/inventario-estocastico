"""Diagnóstico de dependencia temporal y deriva de la demanda por producto.

Mide, con la historia de calibración de cada producto (desde su primera venta):

- `ratio_var_10`: var(suma de ventanas de 10 días sin solapamiento) / (10 · var
  diaria). Con días independientes vale ~1; mayor que 1 indica que los días
  altos (o bajos) tienden a venir juntos y el riesgo de 10 días es mayor que
  el que supone la fórmula clásica.
- `autocorr_1`: autocorrelación de orden 1 de la serie diaria.
- `ratio_media`: media diaria en la prueba / media diaria de la historia de
  calibración desde la primera venta. Cerca de 1 indica que el nivel no se
  movió entre ambos períodos.

Solo entran productos con al menos 400 días desde su primera venta y varianza
diaria positiva. Guarda `outputs/diagnostico.csv` e imprime medianas y
percentiles. Si existe `outputs/pregunta_a.csv` (de main.py), cruza además el
α logrado por cada política según el tramo de `ratio_var_10` y lo guarda en
`outputs/diagnostico_cruce.csv`. Para revisar dos explicaciones alternativas
(rachas de ceros por quiebres y cambios de nivel por producto), repite ese cruce
separando por la marca de censura y por tercil de |log ratio_media| dentro de
cada tramo, y lo guarda en `outputs/diagnostico_confusores.csv`.

Uso: python scripts/diagnostico_dependencia.py --tienda CA_1
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from inventario.datos import cargar_tienda  # noqa: E402
from inventario.demanda import primera_venta  # noqa: E402

VENTANA = 10
MIN_DIAS = 400
TRAMOS = (0, 1.2, 2, 3, np.inf)
POLITICAS = ("formula", "sim", "bloques")


def diagnosticar(calib: np.ndarray, prueba: np.ndarray, item_ids: list[str],
                 categorias: list[str], ventana: int = VENTANA,
                 min_dias: int = MIN_DIAS) -> pd.DataFrame:
    """Una fila por producto elegible con los tres indicadores."""
    inicio = primera_venta(calib)
    filas = []
    for j in np.flatnonzero(inicio >= 0):
        x = calib[inicio[j]:, j].astype(float)
        if len(x) < min_dias:
            continue
        var_d = x.var(ddof=1)
        if var_d <= 0:
            continue
        n_v = len(x) // ventana
        sumas = x[len(x) - n_v * ventana:].reshape(n_v, ventana).sum(axis=1)
        filas.append({
            "item_id": item_ids[j],
            "categoria": categorias[j],
            "dias_historia": len(x),
            "ratio_var_10": sumas.var(ddof=1) / (ventana * var_d),
            "autocorr_1": float(np.corrcoef(x[:-1], x[1:])[0, 1]),
            "ratio_media": prueba[:, j].mean() / x.mean(),
        })
    return pd.DataFrame(filas)


def cruzar(diag: pd.DataFrame, pregunta_a: pd.DataFrame) -> pd.DataFrame:
    """α y fill medios por política según el tramo de `ratio_var_10`."""
    m = diag.merge(pregunta_a, on=["item_id", "categoria"])
    m["tramo"] = pd.cut(m["ratio_var_10"], TRAMOS)
    cols = {"n": ("item_id", "size")}
    cols.update({f"alpha_{p}": (f"alpha_{p}", "mean") for p in POLITICAS})
    cols.update({f"fill_{p}": (f"fill_{p}", "mean") for p in POLITICAS})
    out = m.groupby("tramo", observed=True).agg(**cols).reset_index()
    out["tramo"] = out["tramo"].astype(str)
    return out


def _agg(m: pd.DataFrame, por: list[str]) -> pd.DataFrame:
    cols = {"n": ("item_id", "size"),
            "mediana_ratio_var_10": ("ratio_var_10", "median"),
            "mediana_autocorr_1": ("autocorr_1", "median")}
    cols.update({f"alpha_{p}": (f"alpha_{p}", "mean") for p in POLITICAS})
    return m.groupby(por, observed=True).agg(**cols).reset_index()


def cruzar_confusores(diag: pd.DataFrame, pregunta_a: pd.DataFrame) -> pd.DataFrame:
    """α medio por política según tramo y un posible confusor.

    `factor` = "censura": `nivel` es la marca de censura sospechosa (True/False).
    `factor` = "deriva": `nivel` es el tercil (bajo/medio/alto) de
    |log ratio_media| calculado dentro de cada tramo de `ratio_var_10`.
    `tramo` = "todos" resume el nivel sin separar por tramo.
    """
    m = diag.merge(pregunta_a, on=["item_id", "categoria"])
    m["tramo"] = pd.cut(m["ratio_var_10"], TRAMOS).astype(str)
    m["censura"] = m["censura"].astype(str)
    with np.errstate(divide="ignore"):  # ratio_media 0 -> deriva infinita (alta)
        m["deriva"] = np.abs(np.log(m["ratio_media"].to_numpy(dtype=float)))
    pct = m.groupby("tramo")["deriva"].rank(pct=True, method="first")
    m["deriva"] = pd.cut(pct, [0, 1 / 3, 2 / 3, 1], labels=["bajo", "medio", "alto"])
    partes = []
    for factor in ("censura", "deriva"):
        t = _agg(m, [factor]).assign(tramo="todos")
        partes.append(pd.concat([t, _agg(m, [factor, "tramo"])])
                      .rename(columns={factor: "nivel"}).assign(factor=factor))
    out = pd.concat(partes, ignore_index=True)
    out["nivel"] = out["nivel"].astype(str)
    orden = ["factor", "nivel", "tramo", "n", "mediana_ratio_var_10",
             "mediana_autocorr_1"] + [f"alpha_{p}" for p in POLITICAS]
    return out[orden]


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--tienda", default="CA_1")
    p.add_argument("--raw", type=Path, default=RAIZ / "data" / "raw")
    p.add_argument("--salida", type=Path, default=RAIZ / "outputs")
    args = p.parse_args(argv)

    datos = cargar_tienda(args.raw, args.tienda)
    d = diagnosticar(datos.ventas_calib, datos.ventas_prueba, datos.item_ids,
                     datos.categorias)
    args.salida.mkdir(parents=True, exist_ok=True)
    d.to_csv(args.salida / "diagnostico.csv", index=False)

    print(f"Productos elegibles: {len(d)} de {len(datos.item_ids)} "
          f"(>= {MIN_DIAS} días desde la primera venta y varianza > 0)")
    q = [0.10, 0.25, 0.50, 0.75, 0.90]
    print(d[["ratio_var_10", "autocorr_1", "ratio_media"]].quantile(q).round(3)
          .rename(index=lambda v: f"p{int(v * 100)}").to_string())
    print(f"Proporción con ratio_var_10 > 1,2: {(d['ratio_var_10'] > 1.2).mean():.3f}")
    print(f"Proporción con autocorr_1 > 0: {(d['autocorr_1'] > 0).mean():.3f}")
    print("Medianas por categoría:")
    print(d.groupby("categoria")[["ratio_var_10", "autocorr_1", "ratio_media"]]
          .median().round(3).to_string())
    print(f"Archivo: {args.salida / 'diagnostico.csv'}")

    ruta_a = args.salida / "pregunta_a.csv"
    if ruta_a.is_file():
        cruce = cruzar(d, pd.read_csv(ruta_a))
        cruce.to_csv(args.salida / "diagnostico_cruce.csv", index=False)
        print("\nα y fill logrados en la prueba según ratio_var_10:")
        print(cruce.round(3).to_string(index=False))
        print(f"Archivo: {args.salida / 'diagnostico_cruce.csv'}")
        conf = cruzar_confusores(d, pd.read_csv(ruta_a))
        conf.to_csv(args.salida / "diagnostico_confusores.csv", index=False)
        print("\nMismo cruce separando por censura y por deriva de nivel:")
        print(conf.round(3).to_string(index=False))
        print(f"Archivo: {args.salida / 'diagnostico_confusores.csv'}")


if __name__ == "__main__":
    main()
