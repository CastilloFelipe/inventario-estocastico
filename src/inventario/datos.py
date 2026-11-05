"""Carga de datos M5 (Walmart) para una tienda."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ARCHIVOS = ("sales_train_evaluation.csv", "calendar.csv", "sell_prices.csv")


@dataclass
class DatosTienda:
    item_ids: list[str]
    categorias: list[str]
    fechas: pd.DatetimeIndex
    dow: np.ndarray        # (dias,) día de semana 0-6, lunes=0
    ventas: np.ndarray     # (dias, items) unidades
    precio: np.ndarray     # (items,) último precio de calibración, NaN si no hay
    n_calib: int

    @property
    def ventas_calib(self) -> np.ndarray:
        return self.ventas[: self.n_calib]

    @property
    def ventas_prueba(self) -> np.ndarray:
        return self.ventas[self.n_calib:]

    @property
    def dow_calib(self) -> np.ndarray:
        return self.dow[: self.n_calib]

    @property
    def dow_prueba(self) -> np.ndarray:
        return self.dow[self.n_calib:]


def _verificar_archivos(raw_dir: Path) -> None:
    for nombre in ARCHIVOS:
        if not (raw_dir / nombre).is_file():
            raise FileNotFoundError(
                f"Falta {nombre} en {raw_dir}. "
                "Descárgalo con: python scripts/descargar_m5.py")


def _leer_ventas_tienda(ruta: Path, tienda: str) -> pd.DataFrame:
    """Lee el CSV de ventas por bloques, conservando solo la tienda pedida."""
    cabecera = pd.read_csv(ruta, nrows=0).columns
    tipos = {c: np.int32 for c in cabecera if c.startswith("d_")}
    bloques = []
    for bloque in pd.read_csv(ruta, dtype=tipos, chunksize=5000):
        bloques.append(bloque[bloque["store_id"] == tienda])
    return pd.concat(bloques, ignore_index=True)


def cargar_tienda(raw_dir: Path, tienda: str = "CA_1",
                  dias_prueba: int = 364) -> DatosTienda:
    raw_dir = Path(raw_dir)
    _verificar_archivos(raw_dir)

    ventas_df = _leer_ventas_tienda(raw_dir / "sales_train_evaluation.csv", tienda)
    if ventas_df.empty:
        raise ValueError(f"La tienda {tienda!r} no aparece en sales_train_evaluation.csv")
    cols_d = [c for c in ventas_df.columns if c.startswith("d_")]
    ventas = ventas_df[cols_d].to_numpy().T  # (dias, items)

    cal = pd.read_csv(raw_dir / "calendar.csv", usecols=["date", "wm_yr_wk", "d"])
    cal = cal.set_index("d").loc[cols_d]
    fechas = pd.DatetimeIndex(pd.to_datetime(cal["date"]))
    dow = fechas.weekday.to_numpy()

    n_calib = len(cols_d) - dias_prueba
    if n_calib <= 0:
        raise ValueError(
            f"dias_prueba={dias_prueba} deja sin calibración ({len(cols_d)} días)")

    # Precio: último valor conocido en semanas cuyos días son TODOS de
    # calibración (una semana a caballo con la prueba se excluye: fuga).
    semanas_calib = np.setdiff1d(cal["wm_yr_wk"].iloc[:n_calib].unique(),
                                 cal["wm_yr_wk"].iloc[n_calib:].unique())
    tipos_p = {"store_id": "category", "item_id": "category",
               "wm_yr_wk": np.int32, "sell_price": np.float32}
    bloques = []
    for b in pd.read_csv(raw_dir / "sell_prices.csv", dtype=tipos_p,
                         chunksize=500_000):
        b = b[(b["store_id"] == tienda) & b["wm_yr_wk"].isin(semanas_calib)]
        bloques.append(b.astype({"store_id": str, "item_id": str}))
    precios = pd.concat(bloques, ignore_index=True)
    ultimo = (precios.sort_values("wm_yr_wk")
              .groupby("item_id")["sell_price"].last())
    item_ids = ventas_df["item_id"].tolist()
    precio = ultimo.reindex(item_ids).to_numpy(dtype=float)

    return DatosTienda(item_ids=item_ids,
                       categorias=ventas_df["cat_id"].tolist(),
                       fechas=fechas, dow=dow, ventas=ventas,
                       precio=precio, n_calib=n_calib)
