"""Pruebas de la carga de datos M5 con CSV sintéticos."""
import numpy as np
import pandas as pd
import pytest

from conftest import escribir_m5_sintetico
from inventario.datos import cargar_tienda


@pytest.fixture
def raw(tmp_path):
    esperado = escribir_m5_sintetico(tmp_path)
    return tmp_path, esperado


def test_filtra_la_tienda_pedida(raw):
    d, esperado = raw
    datos = cargar_tienda(d, "CA_1", dias_prueba=7)
    assert datos.item_ids == ["FOODS_1_001", "FOODS_1_002", "HOBBIES_1_001"]
    assert datos.categorias == ["FOODS", "FOODS", "HOBBIES"]
    assert datos.ventas.shape == (28, 3)
    for j, item in enumerate(datos.item_ids):
        assert datos.ventas[:, j].tolist() == esperado[("CA_1", item)]
    otra = cargar_tienda(d, "TX_1", dias_prueba=7)
    assert otra.ventas[:, 0].tolist() == esperado[("TX_1", "FOODS_1_001")]


def test_calibracion_y_prueba_no_se_solapan_y_suman_todo(raw):
    d, _ = raw
    datos = cargar_tienda(d, dias_prueba=7)
    assert datos.n_calib == 21
    assert len(datos.ventas_calib) == 21 and len(datos.ventas_prueba) == 7
    assert len(datos.dow_calib) + len(datos.dow_prueba) == len(datos.fechas) == 28
    np.testing.assert_array_equal(
        np.vstack([datos.ventas_calib, datos.ventas_prueba]), datos.ventas)
    np.testing.assert_array_equal(
        np.concatenate([datos.dow_calib, datos.dow_prueba]), datos.dow)


def test_dow_coincide_con_el_calendario(raw):
    d, _ = raw
    datos = cargar_tienda(d, dias_prueba=7)
    cal = pd.read_csv(d / "calendar.csv").iloc[:28]
    esperado = pd.to_datetime(cal["date"]).dt.weekday.to_numpy()
    np.testing.assert_array_equal(datos.dow, esperado)
    assert datos.dow[0] == 5  # 2011-01-29 fue sábado
    assert set(datos.dow) <= set(range(7))
    assert isinstance(datos.fechas, pd.DatetimeIndex)
    assert datos.fechas[0] == pd.Timestamp("2011-01-29")


def test_precio_es_el_ultimo_de_calibracion_e_ignora_la_prueba(raw):
    d, _ = raw
    datos = cargar_tienda(d, dias_prueba=7)
    # FOODS_1_001 vale 9.0 en la semana de prueba, pero debe tomarse 3.0
    assert datos.precio[0] == 3.0
    assert datos.precio[1] == 6.0


def test_producto_sin_precio_es_nan(raw):
    d, _ = raw
    datos = cargar_tienda(d, dias_prueba=7)
    assert np.isnan(datos.precio[2])


def test_precio_con_calibracion_corta_usa_solo_esa_ventana(raw):
    d, _ = raw
    # con 21 días de prueba la calibración es solo la semana 0 (precio 1.0)
    datos = cargar_tienda(d, dias_prueba=21)
    assert datos.precio[0] == 1.0


@pytest.mark.parametrize("archivo", ["sales_train_evaluation.csv",
                                     "calendar.csv", "sell_prices.csv"])
def test_archivo_faltante_nombra_archivo_y_script(raw, archivo):
    d, _ = raw
    (d / archivo).unlink()
    with pytest.raises(FileNotFoundError) as exc:
        cargar_tienda(d, dias_prueba=7)
    assert archivo in str(exc.value)
    assert "scripts/descargar_m5.py" in str(exc.value)


def test_tienda_inexistente_da_error_claro(raw):
    d, _ = raw
    with pytest.raises(ValueError, match="ZZ_9"):
        cargar_tienda(d, "ZZ_9", dias_prueba=7)
