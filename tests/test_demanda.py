"""Pruebas del diagnóstico y muestreo de la demanda."""
import numpy as np

from inventario.demanda import (
    ajustar_distribuciones,
    censura_sospechosa,
    clasificar,
    muestrear_demanda,
    primera_venta,
)


def _clasifica_una(x):
    v = np.asarray(x, dtype=float).reshape(-1, 1)
    return clasificar(v, primera_venta(v))[0]


def test_primera_venta_indice_y_menos_uno_si_nunca_vende():
    v = np.array([[0, 0, 0], [0, 0, 0], [4, 0, 0], [1, 0, 2]])
    assert primera_venta(v).tolist() == [2, -1, 3]


def test_clasifica_suave():
    assert _clasifica_una([5, 6, 5, 6] * 10) == "suave"


def test_clasifica_erratica():
    # vende todos los días pero con cantidades muy variables
    assert _clasifica_una([1, 20, 1, 20] * 10) == "erratica"


def test_clasifica_intermitente():
    # vende 1 de cada 4 días, cantidad constante
    assert _clasifica_una([0, 0, 0, 5] * 10) == "intermitente"


def test_clasifica_irregular():
    assert _clasifica_una([0, 0, 0, 1, 0, 0, 0, 20] * 5) == "irregular"


def test_clasifica_sin_ventas():
    assert _clasifica_una([0] * 30) == "sin_ventas"


def test_clasifica_usa_solo_dias_desde_inicio():
    # los ceros iniciales no cuentan para el ADI
    v = np.array([0] * 50 + [5, 6] * 20, dtype=float).reshape(-1, 1)
    assert clasificar(v, primera_venta(v))[0] == "suave"


def test_ajuste_serie_en_cero_es_sin_ventas():
    assert ajustar_distribuciones(np.zeros(50)) == {"mejor": "sin_ventas", "aic": {}}


def test_ajuste_poisson_gana_con_datos_poisson():
    x = np.random.default_rng(1).poisson(3, 2000)
    res = ajustar_distribuciones(x)
    assert res["mejor"] == "poisson"
    assert set(res["aic"]) == {"normal", "poisson", "binomial_negativa"} or set(
        res["aic"]
    ) == {"normal", "poisson"}


def test_ajuste_binomial_negativa_gana_con_sobredispersion():
    x = np.random.default_rng(2).negative_binomial(2, 0.2, 2000)
    res = ajustar_distribuciones(x)
    assert res["mejor"] == "binomial_negativa"
    assert "binomial_negativa" in res["aic"]


def test_ajuste_sin_sobredispersion_omite_binomial_negativa():
    res = ajustar_distribuciones(np.array([3, 3, 3, 4, 2, 3, 3]))
    assert "binomial_negativa" not in res["aic"]


def test_censura_sospechosa_con_racha_larga_en_producto_que_vende_mucho():
    rng = np.random.default_rng(3)
    x = (rng.random(1000) < 0.9).astype(float)
    x[300:360] = 0
    assert censura_sospechosa(x) is True


def test_censura_no_sospechosa_en_poisson():
    x = np.random.default_rng(4).poisson(3, 365)
    assert censura_sospechosa(x) is False


def test_muestreo_nunca_usa_dias_anteriores_a_inicio():
    historia = np.full((70, 1), 999.0)
    historia[35:, 0] = 1.0
    dow_h = np.arange(70) % 7
    dow_s = np.arange(14) % 7
    out = muestrear_demanda(
        np.random.default_rng(0), historia, dow_h, dow_s, 50, np.array([35])
    )
    assert out.shape == (50, 14, 1)
    assert out.dtype == np.int64
    assert (out == 1).all()


def test_muestreo_respeta_el_dia_de_semana():
    dow_h = np.arange(70) % 7
    historia = np.where(dow_h == 5, 7, 0).reshape(-1, 1).astype(float)
    dow_s = np.arange(21) % 7
    out = muestrear_demanda(
        np.random.default_rng(0), historia, dow_h, dow_s, 20, np.array([0])
    )
    esperado = np.where(dow_s == 5, 7, 0)
    assert (out[:, :, 0] == esperado).all()


def test_muestreo_item_sin_ventas_da_ceros():
    historia = np.zeros((14, 2))
    historia[:, 1] = 2
    dow_h = np.arange(14) % 7
    out = muestrear_demanda(
        np.random.default_rng(0), historia, dow_h, np.arange(7), 5, np.array([-1, 0])
    )
    assert (out[:, :, 0] == 0).all()
    assert (out[:, :, 1] == 2).all()


def test_muestreo_historia_corta_usa_todos_los_dias_validos():
    # inicio en el día 5 de 7: solo hay un día válido de algunos weekdays
    historia = np.full((7, 1), 3.0)
    dow_h = np.arange(7)
    out = muestrear_demanda(
        np.random.default_rng(0), historia, dow_h, np.arange(7), 4, np.array([5])
    )
    assert (out == 3).all()
