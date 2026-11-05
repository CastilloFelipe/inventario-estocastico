"""Configuración de pytest: agrega `src/` al path de importación."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# Precios sintéticos de CA_1: {item: {semana_indice (0-based): precio}}.
# La semana 3 (días 22-28) cae en la prueba cuando dias_prueba=7.
PRECIOS_CA1 = {
    "FOODS_1_001": {0: 1.0, 1: 2.0, 2: 3.0, 3: 9.0},  # último de calibración: 3.0
    "FOODS_1_002": {0: 5.0, 1: 6.0},                   # termina antes de la prueba: 6.0
    "HOBBIES_1_001": {},                               # sin precio alguno
}


def escribir_m5_sintetico(directorio, n_dias_ventas=28, n_dias_calendario=30):
    """Escribe sales_train_evaluation.csv, calendar.csv y sell_prices.csv mínimos.

    Mismo formato que M5: 2 tiendas (CA_1, TX_1), 3 productos, calendario con
    más días que ventas. Devuelve el diccionario de ventas esperado por
    (tienda, item) como lista de enteros por día.
    """
    import numpy as np
    import pandas as pd

    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)

    items = [("FOODS_1_001", "FOODS_1", "FOODS"),
             ("FOODS_1_002", "FOODS_1", "FOODS"),
             ("HOBBIES_1_001", "HOBBIES_1", "HOBBIES")]
    filas, esperado = [], {}
    for tienda, estado in (("CA_1", "CA"), ("TX_1", "TX")):
        for item, dept, cat in items:
            v = rng.integers(0, 6, n_dias_ventas)
            esperado[(tienda, item)] = v.tolist()
            fila = {"id": f"{item}_{tienda}_evaluation", "item_id": item,
                    "dept_id": dept, "cat_id": cat, "store_id": tienda,
                    "state_id": estado}
            fila.update({f"d_{i + 1}": int(v[i]) for i in range(n_dias_ventas)})
            filas.append(fila)
    pd.DataFrame(filas).to_csv(directorio / "sales_train_evaluation.csv", index=False)

    fechas = pd.date_range("2011-01-29", periods=n_dias_calendario)
    cal = pd.DataFrame({
        "date": fechas.strftime("%Y-%m-%d"),
        "wm_yr_wk": 11101 + np.arange(n_dias_calendario) // 7,
        "weekday": fechas.day_name().str.lower(),
        "wday": (fechas.weekday + 2) % 7 + 1,  # convención M5 (sábado=1)
        "month": fechas.month, "year": fechas.year,
        "d": [f"d_{i + 1}" for i in range(n_dias_calendario)],
        "event_name_1": "", "event_type_1": "", "event_name_2": "",
        "event_type_2": "", "snap_CA": 0, "snap_TX": 0, "snap_WI": 0,
    })
    cal.to_csv(directorio / "calendar.csv", index=False)

    precios = []
    for item, por_semana in PRECIOS_CA1.items():
        for s, p in por_semana.items():
            precios.append(("CA_1", item, 11101 + s, p))
            precios.append(("TX_1", item, 11101 + s, p + 100.0))  # distinta tienda
    pd.DataFrame(precios, columns=["store_id", "item_id", "wm_yr_wk", "sell_price"]
                 ).to_csv(directorio / "sell_prices.csv", index=False)
    return esperado
