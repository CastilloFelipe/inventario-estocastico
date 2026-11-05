import math

import numpy as np

from inventario.politicas import s_formula, s_simulacion
from inventario.simulador import muestrear_lead_times, simular


def _poisson(reps=200, dias=120, items=3, seed=0):
    rng = np.random.default_rng(seed)
    d = rng.poisson([3, 6, 10][:items], size=(reps, dias, items)).astype(np.int64)
    lt = muestrear_lead_times(rng, reps, dias // 7 + 1, items)
    return d, lt


def test_formula_valores_conocidos():
    S = s_formula(np.array([4.0]), np.array([2.0]), 7, 3.0, 1.645)
    assert S[0] == math.ceil(40 + 1.645 * 2 * math.sqrt(10))


def test_formula_minimo_cero():
    S = s_formula(np.array([0.0]), np.array([0.0]), 7, 3.0, 1.645)
    assert S[0] == 0 and np.issubdtype(S.dtype, np.integer)


def test_normal_media_alta_formula_y_simulacion_coinciden():
    rng = np.random.default_rng(1)
    reps, dias = 1000, 150
    d = np.maximum(0, np.round(rng.normal(100, 20, (reps, dias, 1)))).astype(np.int64)
    lt = np.full((reps, dias // 7 + 1, 1), 3, dtype=np.int64)
    S_f = s_formula(np.array([100.0]), np.array([20.0]), 7, 3.0, 1.645)
    S_sim, ok = s_simulacion(d, lt, 7, 0.95, "ciclo", s_max=np.array([3000]))
    assert ok[0]
    assert abs(S_sim[0] - S_f[0]) / S_f[0] < 0.03


def test_S_encontrado_es_el_minimo():
    d, lt = _poisson()
    s_max = np.array([400, 400, 400])
    for metrica, meta in (("ciclo", 0.9), ("fill", 0.97)):
        S, ok = s_simulacion(d, lt, 7, meta, metrica, s_max=s_max)
        assert ok.all()
        attr = "servicio_ciclo" if metrica == "ciclo" else "fill_rate"
        assert (getattr(simular(d, S, 7, lt), attr) >= meta).all()
        menor = getattr(simular(d, S - 1, 7, lt), attr)
        assert (menor < meta).all()


def test_meta_inalcanzable_devuelve_s_max():
    d, lt = _poisson(items=1)
    S, ok = s_simulacion(d, lt, 7, 0.999, "fill", s_max=np.array([3]))
    assert S[0] == 3 and not ok[0]


def test_items_mezclados_alcanzable_e_inalcanzable():
    d, lt = _poisson()
    S, ok = s_simulacion(d, lt, 7, 0.95, "fill", s_max=np.array([400, 2, 400]))
    assert list(ok) == [True, False, True]
    assert S[1] == 2
