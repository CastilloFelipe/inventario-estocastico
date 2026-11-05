"""Pruebas del backtest y de las preguntas A y B con un DatosTienda sintético."""
import numpy as np
import pandas as pd
import pytest

from inventario.analisis import Config, curva_b, pregunta_a, resumen_a
from inventario.backtest import backtest
from inventario.datos import DatosTienda

N_CALIB = 210  # múltiplo de 7: la prueba empieza el mismo día de semana
N_PRUEBA = 140
ITEMS = ["SUAVE", "ERRATICA", "INTERMITENTE", "IRREGULAR", "SIN_VENTAS", "SIN_PRECIO"]


def _serie(rng, tipo, n):
    if tipo == "suave":
        return rng.poisson(20, n)
    if tipo == "erratica":  # vende casi todos los días, tamaños muy variables
        return np.where(rng.random(n) < 0.95, rng.choice([1, 2, 30], n), 0)
    if tipo == "intermitente":  # pocos días con venta, tamaño estable
        return np.where(rng.random(n) < 0.3, rng.choice([2, 3], n), 0)
    if tipo == "irregular":  # pocos días con venta, tamaño muy variable
        return np.where(rng.random(n) < 0.3, rng.choice([1, 20], n), 0)
    if tipo == "cero":
        return np.zeros(n, dtype=np.int64)
    return rng.poisson(5, n)


def _datos(semilla=0, prueba_igual=False):
    rng = np.random.default_rng(semilla)
    n = N_CALIB + N_PRUEBA
    tipos = ["suave", "erratica", "intermitente", "irregular", "cero", "poisson5"]
    ventas = np.column_stack([_serie(rng, t, n) for t in tipos]).astype(np.int64)
    if prueba_igual:
        ventas[N_CALIB:] = ventas[N_CALIB - N_PRUEBA:N_CALIB]
    fechas = pd.date_range("2015-01-05", periods=n)  # lunes
    return DatosTienda(
        item_ids=list(ITEMS),
        categorias=["FOODS", "FOODS", "HOBBIES", "HOBBIES", "HOUSEHOLD", "HOUSEHOLD"],
        fechas=fechas, dow=fechas.weekday.to_numpy(), ventas=ventas,
        precio=np.array([2.0, 3.0, 10.0, 5.0, 1.0, np.nan]), n_calib=N_CALIB)


CFG = Config(reps=20, dias_sim=112)


@pytest.fixture(scope="module")
def tabla_a():
    return pregunta_a(_datos(), CFG)


def test_backtest_demanda_cero_y_reproducible():
    cal = np.zeros((28, 2), dtype=np.int64)
    prueba = np.column_stack([np.zeros(70), np.full(70, 3)]).astype(np.int64)
    m1 = backtest(cal, prueba, np.array([0, 40]), 7, np.random.default_rng(1), reps=10)
    m2 = backtest(cal, prueba, np.array([0, 40]), 7, np.random.default_rng(1), reps=10)
    assert m1.fill_rate[0] == 1.0 and m1.inventario_prom[0] == 0.0
    assert m1.fill_rate[1] == 1.0  # S = 40 cubre 3/día durante R + L <= 12 días
    np.testing.assert_array_equal(m1.inventario_prom, m2.inventario_prom)


def test_columnas_y_clases_de_la_pregunta_a(tabla_a):
    cols = ["item_id", "categoria", "clase", "censura", "mejor_dist", "S_formula",
            "S_sim", "alcanzado", "alpha_formula", "alpha_sim", "fill_formula",
            "fill_sim", "inv_usd_formula", "inv_usd_sim", "S_bloques",
            "alcanzado_bloques", "alpha_bloques", "fill_bloques", "inv_usd_bloques",
            "demanda_prueba"]
    assert list(tabla_a.columns) == cols
    clases = dict(zip(tabla_a["item_id"], tabla_a["clase"]))
    assert clases["SUAVE"] == "suave" and clases["ERRATICA"] == "erratica"
    assert clases["INTERMITENTE"] == "intermitente"
    assert clases["IRREGULAR"] == "irregular"
    assert clases["SIN_VENTAS"] == "sin_ventas"


def test_producto_sin_ventas_excluido_y_contado(tabla_a):
    fila = tabla_a.set_index("item_id").loc["SIN_VENTAS"]
    assert pd.isna(fila["S_sim"]) and pd.isna(fila["alpha_sim"])
    res = resumen_a(tabla_a)
    excl = res[res["agrupacion"] == "excluidos"]
    assert len(excl) == 1 and excl["n"].iloc[0] == 1
    total = res[(res["agrupacion"] == "total")].iloc[0]
    assert total["n"] == 5
    por_clase = res[res["agrupacion"] == "clase"]
    assert "sin_ventas" not in set(por_clase["grupo"])
    assert por_clase["n"].sum() == 5


def test_producto_sin_precio_nan_y_fuera_de_las_sumas(tabla_a):
    t = tabla_a.set_index("item_id")
    assert pd.isna(t.loc["SIN_PRECIO", "inv_usd_formula"])
    assert pd.isna(t.loc["SIN_PRECIO", "inv_usd_sim"])
    assert t.loc["SIN_PRECIO", "alpha_sim"] > 0  # sí se simula
    res = resumen_a(tabla_a)
    total = res[res["agrupacion"] == "total"].iloc[0]
    con_precio = t.drop(index=["SIN_PRECIO", "SIN_VENTAS"])
    assert total["inv_usd_sim"] == pytest.approx(con_precio["inv_usd_sim"].sum())
    assert total["inv_usd_formula"] == pytest.approx(con_precio["inv_usd_formula"].sum())
    hh = res[(res["agrupacion"] == "categoria") & (res["grupo"] == "HOUSEHOLD")].iloc[0]
    assert hh["n"] == 1 and hh["inv_usd_sim"] == 0.0  # solo SIN_PRECIO, sin valor USD


def test_lote_no_cambia_el_resultado():
    datos = _datos()
    a = pregunta_a(datos, Config(reps=20, dias_sim=112, lote=2))
    b = pregunta_a(datos, Config(reps=20, dias_sim=112, lote=1000))
    pd.testing.assert_frame_equal(a, b)
    ca = curva_b(datos, Config(reps=10, dias_sim=56, lote=2, metas_b=(0.9, 0.97)))
    cb = curva_b(datos, Config(reps=10, dias_sim=56, lote=1000, metas_b=(0.9, 0.97)))
    pd.testing.assert_frame_equal(ca, cb)


def test_curva_b_inventario_no_decreciente_en_la_meta():
    curva = curva_b(_datos(), CFG)
    assert list(curva.columns) == ["metodo", "meta", "categoria", "inventario_usd",
                                   "costo_anual_usd", "fill_logrado", "n_no_alcanzado"]
    assert set(curva["metodo"]) == {"diario", "bloques"}
    assert set(curva["categoria"]) == {"FOODS", "HOBBIES", "HOUSEHOLD", "TOTAL"}
    for metodo in ("diario", "bloques"):
        total = curva[(curva["categoria"] == "TOTAL")
                      & (curva["metodo"] == metodo)].sort_values("meta")
        assert list(total["meta"]) == list(CFG.metas_b)
        assert np.all(np.diff(total["inventario_usd"].to_numpy()) >= -1e-9)
        np.testing.assert_allclose(total["costo_anual_usd"],
                                   total["inventario_usd"] * CFG.costo_anual)
        assert total["fill_logrado"].between(0, 1).all()
        assert total["fill_logrado"].iloc[-1] >= total["fill_logrado"].iloc[0]
        assert total["n_no_alcanzado"].between(0, 5).all()


def test_prueba_identica_y_poisson_alta_logra_alpha():
    tabla = pregunta_a(_datos(semilla=3, prueba_igual=True), CFG)
    fila = tabla.set_index("item_id").loc["SUAVE"]
    assert fila["alcanzado"]
    assert fila["alpha_sim"] >= 0.9


def test_columnas_nuevas_de_bloques_y_demanda_prueba(tabla_a):
    datos = _datos()
    t = tabla_a.set_index("item_id")
    np.testing.assert_array_equal(t["demanda_prueba"].to_numpy(),
                                  datos.ventas_prueba.sum(axis=0))
    assert pd.isna(t.loc["SIN_VENTAS", "S_bloques"])
    assert pd.isna(t.loc["SIN_PRECIO", "inv_usd_bloques"])
    ok = t.drop(index="SIN_VENTAS")
    assert ok["alpha_bloques"].between(0, 1).all()
    assert ok["fill_bloques"].between(0, 1).all()
    assert (ok["S_bloques"] >= 0).all()


def _datos_ar1(n_items=8, phi=0.9, semilla=11):
    rng = np.random.default_rng(semilla)
    n = N_CALIB * 3 + N_PRUEBA
    cols = []
    for _ in range(n_items):
        e = rng.normal(0, 6, n)
        x = np.empty(n)
        x[0] = e[0]
        for t in range(1, n):
            x[t] = phi * x[t - 1] + e[t]
        cols.append(np.maximum(0, np.rint(15 + x)))
    ventas = np.column_stack(cols).astype(np.int64)
    fechas = pd.date_range("2015-01-05", periods=n)
    return DatosTienda(
        item_ids=[f"AR_{i}" for i in range(n_items)], categorias=["FOODS"] * n_items,
        fechas=fechas, dow=fechas.weekday.to_numpy(), ventas=ventas,
        precio=np.ones(n_items), n_calib=N_CALIB * 3)


def test_bloques_logran_mas_alpha_que_el_diario_con_demanda_ar1():
    tabla = pregunta_a(_datos_ar1(), Config(reps=20, dias_sim=112))
    assert tabla["alpha_bloques"].mean() > tabla["alpha_sim"].mean()
    assert (tabla["S_bloques"] >= tabla["S_sim"]).mean() >= 0.75


def test_fill_ponderado_por_demanda_de_prueba():
    df = pd.DataFrame({
        "item_id": ["A", "B"], "categoria": ["FOODS", "FOODS"],
        "clase": ["suave", "suave"], "alcanzado": [True, False],
        "alcanzado_bloques": [True, True],
        "alpha_formula": [0.9, 0.8], "alpha_sim": [0.9, 0.8],
        "alpha_bloques": [0.95, 0.9],
        "fill_formula": [0.9, 0.5], "fill_sim": [1.0, 0.6],
        "fill_bloques": [0.8, 0.7],
        "inv_usd_formula": [1.0, 2.0], "inv_usd_sim": [1.0, 2.0],
        "inv_usd_bloques": [3.0, 4.0],
        "demanda_prueba": [300, 100],
    })
    total = resumen_a(df).set_index("agrupacion").loc["total"]
    assert total["fill_pond_formula"] == pytest.approx((0.9 * 300 + 0.5 * 100) / 400)
    assert total["fill_pond_sim"] == pytest.approx((1.0 * 300 + 0.6 * 100) / 400)
    assert total["fill_pond_bloques"] == pytest.approx((0.8 * 300 + 0.7 * 100) / 400)
    assert total["fill_bloques"] == pytest.approx(0.75)
    assert total["alpha_bloques"] == pytest.approx(0.925)
    assert total["inv_usd_bloques"] == pytest.approx(7.0)
