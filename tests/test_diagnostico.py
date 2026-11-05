"""Tests del diagnóstico de dependencia (scripts/diagnostico_dependencia.py)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_RUTA = Path(__file__).resolve().parents[1] / "scripts" / "diagnostico_dependencia.py"
_spec = importlib.util.spec_from_file_location("diagnostico_dependencia", _RUTA)
diag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(diag)


def _series():
    rng = np.random.default_rng(0)
    dias = 2000
    iid = rng.poisson(5, dias)
    # Nivel que cambia cada 30 días: días consecutivos parecidos
    nivel = np.repeat(rng.choice([1, 9], dias // 30 + 1), 30)[:dias]
    persistente = rng.poisson(nivel)
    corta = np.r_[np.zeros(dias - 100), rng.poisson(5, 100)]  # pocos días de historia
    constante = np.full(dias, 3)                              # varianza cero
    calib = np.c_[iid, persistente, corta, constante]
    prueba = np.c_[rng.poisson(5, 364), rng.poisson(5, 364),
                   rng.poisson(5, 364), np.full(364, 3)]
    return calib, prueba


def test_independiente_vs_persistente_y_filtros():
    calib, prueba = _series()
    d = diag.diagnosticar(calib, prueba, ["iid", "pers", "corta", "const"],
                          ["A"] * 4).set_index("item_id")
    assert list(d.index) == ["iid", "pers"]  # corta y constante quedan fuera
    assert 0.7 < d.loc["iid", "ratio_var_10"] < 1.3
    assert abs(d.loc["iid", "autocorr_1"]) < 0.1
    assert d.loc["pers", "ratio_var_10"] > 3
    assert d.loc["pers", "autocorr_1"] > 0.3
    assert abs(d.loc["iid", "ratio_media"] - 1) < 0.1


def test_cruzar_agrupa_por_tramo():
    diag_df = pd.DataFrame({"item_id": ["a", "b", "c"], "categoria": ["X"] * 3,
                            "ratio_var_10": [1.0, 1.5, 5.0]})
    a = pd.DataFrame({"item_id": ["a", "b", "c"], "categoria": ["X"] * 3,
                      **{f"{m}_{p}": [0.9, 0.8, 0.7] for m in ("alpha", "fill")
                         for p in diag.POLITICAS}})
    c = diag.cruzar(diag_df, a)
    assert c["n"].tolist() == [1, 1, 1]
    assert c["alpha_formula"].tolist() == [0.9, 0.8, 0.7]


def test_cruzar_confusores_separa_por_censura_y_deriva():
    n = 6
    diag_df = pd.DataFrame({"item_id": list("abcdef"), "categoria": ["X"] * n,
                            "ratio_var_10": [1.0] * 3 + [5.0] * 3,
                            "autocorr_1": [0.0] * n,
                            "ratio_media": [1.0, 1.5, 0.0, 1.0, 0.5, 3.0]})
    a = pd.DataFrame({"item_id": list("abcdef"), "categoria": ["X"] * n,
                      "censura": [False, True, False, True, False, True],
                      **{f"alpha_{p}": [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]
                         for p in diag.POLITICAS}})
    c = diag.cruzar_confusores(diag_df, a)
    cen = c[(c["factor"] == "censura") & (c["tramo"] == "todos")].set_index("nivel")
    assert cen.loc["True", "n"] == 3 and cen.loc["False", "n"] == 3
    der = c[(c["factor"] == "deriva") & (c["tramo"] != "todos")]
    assert der["n"].tolist() == [1] * 6  # un producto por tercil en cada tramo
    # en el tramo bajo: |log| 0 (a) < log 1,5 (b) < inf (c, ratio 0)
    bajo = der[der["tramo"] == "(0.0, 1.2]"].set_index("nivel")["alpha_formula"]
    assert bajo.to_dict() == {"bajo": 0.9, "medio": 0.8, "alto": 0.7}
