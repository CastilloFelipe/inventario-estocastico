import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from conftest import escribir_m5_sintetico

from pathlib import Path

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
ITEMS = ["FOODS_1_001", "FOODS_1_002", "HOBBIES_1_001"]


def _escribir_outputs(d):
    d.mkdir(parents=True, exist_ok=True)
    filas = [{"metodo": m, "meta": meta, "categoria": c, "inventario_usd": 1000 * meta * k,
              "costo_anual_usd": 250 * meta, "fill_logrado": meta - 0.05 * k,
              "n_no_alcanzado": 0}
             for k, m in ((1, "diario"), (2, "bloques"))
             for meta in (0.85, 0.95) for c in ("FOODS", "TOTAL")]
    pd.DataFrame(filas).to_csv(d / "curva_b.csv", index=False)
    res = []
    for agr, grupos in (("clase", ["suave", "intermitente"]), ("categoria", ["FOODS", "HOBBIES"]),
                        ("total", ["TOTAL"])):
        for g in grupos:
            f = {"agrupacion": agr, "grupo": g, "n": 3, "n_sin_precio": 0, "n_no_alcanzado": 0}
            for p in ("formula", "sim", "bloques"):
                f.update({f"alpha_{p}": 0.9, f"fill_{p}": 0.95, f"inv_usd_{p}": 500.0,
                          f"fill_pond_{p}": 0.96})
            res.append(f)
    pd.DataFrame(res).to_csv(d / "resumen_a.csv", index=False)
    a = pd.DataFrame({
        "item_id": ITEMS, "categoria": ["FOODS", "FOODS", "HOBBIES"],
        "clase": ["suave", "intermitente", "intermitente"], "censura": [False, True, False],
        "mejor_dist": ["poisson", "binomial_negativa", "poisson"],
        "S_formula": [30, 20, 25], "S_sim": [31, 22, 26], "S_bloques": [33, 24, 28],
        "demanda_prueba": [10, 20, 30]})
    a.to_csv(d / "pregunta_a.csv", index=False)


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    out, raw = tmp_path / "outputs", tmp_path / "raw"
    _escribir_outputs(out)
    escribir_m5_sintetico(raw, n_dias_ventas=420, n_dias_calendario=430)
    monkeypatch.setenv("INVENTARIO_OUTPUTS", str(out))
    monkeypatch.setenv("INVENTARIO_RAW", str(raw))
    return out, raw


def _app(vista=None):
    at = AppTest.from_file(APP, default_timeout=60).run()
    if vista:
        at.sidebar.radio[0].set_value(vista).run()
    return at


def test_inicio_es_la_vista_por_defecto_y_muestra_conclusiones(entorno):
    at = _app()
    assert not at.exception
    assert at.header[0].value == "¿De qué se trata?"
    textos = " ".join(m.value for m in at.markdown)
    # Las cifras salen de resumen_a.csv (α 0,9 en las tres políticas) y de curva_b.csv
    assert "90,0%" in textos and "La fórmula no cumple su promesa" in textos
    assert "pidiendo 95% de fill rate" in textos
    assert len(at.metric) == 3
    assert len(at.expander) >= 11  # limitaciones + conceptos


def test_inicio_sin_outputs_no_falla(entorno):
    out, _ = entorno
    for f in out.iterdir():
        f.unlink()
    at = _app()
    assert not at.exception
    assert any("python main.py" in i.value for i in at.info)


def test_curva_carga_y_filtra(entorno):
    at = _app("Curva inventario–servicio")
    assert not at.exception
    assert at.header[0].value == "Curva inventario–servicio"
    at.multiselect[0].set_value(["FOODS", "TOTAL"]).run()
    assert not at.exception


def test_resumen_renderiza(entorno):
    at = _app("Fórmula vs simulación")
    assert not at.exception
    assert at.header[0].value == "Fórmula vs simulación"
    at.radio[0].set_value("Categoría").run()
    assert not at.exception


@pytest.mark.parametrize("metodo", ["diario", "bloques"])
def test_producto_simula(entorno, metodo):
    at = _app("Producto")
    assert not at.exception
    at.radio[0].set_value(metodo).run()
    at.slider[0].set_value(10).run()
    assert not at.exception
    etiquetas = [m.label for m in at.metric]
    assert "Fill rate" in etiquetas and "Clase" in etiquetas


def test_sin_outputs_muestra_comando(entorno):
    out, _ = entorno
    for f in out.iterdir():
        f.unlink()
    for vista in ("Curva inventario–servicio", "Fórmula vs simulación", "Producto"):
        at = _app(vista)
        assert not at.exception
        assert any("python main.py" in c.value for c in at.code), vista


def test_sin_raw_muestra_comando(entorno):
    _, raw = entorno
    for f in raw.iterdir():
        f.unlink()
    at = _app("Producto")
    assert not at.exception
    assert any("python scripts/descargar_m5.py" in c.value for c in at.code)
