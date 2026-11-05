import importlib.util
import io
from pathlib import Path

import pytest

_ruta = Path(__file__).resolve().parents[1] / "scripts" / "descargar_m5.py"
_spec = importlib.util.spec_from_file_location("descargar_m5", _ruta)
descargar_m5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(descargar_m5)


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_contenido_invalido_se_borra_y_el_error_es_claro(tmp_path, monkeypatch):
    pointer = b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\n"
    monkeypatch.setattr(descargar_m5.urllib.request, "urlopen",
                        lambda *a, **k: _Resp(pointer))
    with pytest.raises(RuntimeError) as e:
        descargar_m5.descargar("calendar.csv", "http://falso/", tmp_path)
    assert "calendar.csv" in str(e.value) and "Kaggle" in str(e.value)
    assert list(tmp_path.iterdir()) == []


def test_contenido_valido_se_guarda(tmp_path, monkeypatch):
    monkeypatch.setattr(descargar_m5.urllib.request, "urlopen",
                        lambda *a, **k: _Resp(b"date,wm_yr_wk,x\n2011-01-29,11101,1\n"))
    assert descargar_m5.descargar("calendar.csv", "http://falso/", tmp_path)
    assert (tmp_path / "calendar.csv").exists()
