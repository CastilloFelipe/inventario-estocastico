import numpy as np
from scipy.stats import poisson

from inventario.simulador import muestrear_lead_times, simular

REPS, DIAS, R = 300, 364, 7
N_REV = -(-DIAS // R)


def _demanda_y_lt(reps=REPS, seed=0, media=4.0):
    rng = np.random.default_rng(seed)
    d = rng.poisson(media, size=(reps, DIAS, 1))
    lt = muestrear_lead_times(rng, reps, N_REV, 1)
    return d, lt


def test_demanda_cero_da_servicio_total_sin_error():
    d = np.zeros((5, 100, 3), dtype=np.int64)
    m = simular(d, np.array([0, 5, 10]), 7, np.full((5, 15, 3), 3))
    assert np.allclose(m.fill_rate, 1.0) and np.allclose(m.servicio_ciclo, 1.0)


def test_muestrear_lead_times_forma_y_valores():
    lt = muestrear_lead_times(np.random.default_rng(1), 4, 6, 3)
    assert lt.shape == (4, 6, 3)
    assert set(np.unique(lt)) <= {2, 3, 4, 5}


def test_mas_S_nunca_baja_el_servicio():
    d, lt = _demanda_y_lt()
    fills = [simular(d, np.array([s]), 7, lt).fill_rate[0] for s in range(20, 80, 5)]
    assert np.all(np.diff(fills) >= -1e-12)


def test_mas_lead_time_nunca_sube_el_servicio():
    d, _ = _demanda_y_lt()
    S = np.array([45])
    m2 = simular(d, S, 7, np.full((REPS, N_REV, 1), 2))
    m5 = simular(d, S, 7, np.full((REPS, N_REV, 1), 5))
    assert m5.fill_rate[0] <= m2.fill_rate[0]
    assert m5.servicio_ciclo[0] <= m2.servicio_ciclo[0]


def test_misma_semilla_mismo_resultado():
    S = np.array([40, 50])
    res = []
    for _ in range(2):
        rng = np.random.default_rng(123)
        d = rng.poisson(4.0, size=(50, DIAS, 2))
        lt = muestrear_lead_times(rng, 50, N_REV, 2)
        res.append(simular(d, S, 7, lt))
    for campo in ("fill_rate", "servicio_ciclo", "inventario_prom"):
        assert np.array_equal(getattr(res[0], campo), getattr(res[1], campo))


def test_poisson_lead_time_fijo_coincide_con_teoria():
    # λ = 4/día, R = 7, L = 3 fijo: el pedido protege R + L = 10 días
    reps = 2000
    S = int(poisson.ppf(0.95, 4 * 10))
    d = np.random.default_rng(7).poisson(4.0, size=(reps, DIAS, 1))
    m = simular(d, np.array([S]), 7, np.full((reps, N_REV, 1), 3))
    assert abs(m.servicio_ciclo[0] - poisson.cdf(S, 40)) < 0.02
