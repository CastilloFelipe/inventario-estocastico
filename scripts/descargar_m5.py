"""Descarga los CSV del dataset M5 a data/raw/ (solo biblioteca estándar).

Fuente original: Kaggle, competencia M5 "M5 Forecasting - Accuracy".
Los archivos se bajan de un espejo en GitHub (shrutidoshi94/M5Forecasting).
"""
import shutil
import sys
import urllib.request
from pathlib import Path

MEDIA = "https://media.githubusercontent.com/media/shrutidoshi94/M5Forecasting/main/"
RAW = "https://raw.githubusercontent.com/shrutidoshi94/M5Forecasting/main/"
ARCHIVOS = {
    "sales_train_evaluation.csv": MEDIA,
    "sell_prices.csv": MEDIA,
    "calendar.csv": RAW,
}
ENCABEZADOS = {
    "sales_train_evaluation.csv": "id,item_id",
    "calendar.csv": "date,wm_yr_wk",
    "sell_prices.csv": "store_id,item_id",
}
DESTINO = Path(__file__).resolve().parents[1] / "data" / "raw"


def _verificar_encabezado(ruta: Path, nombre: str, base: str) -> None:
    """Falla si la primera línea no es la esperada (puntero LFS, HTML, etc.)."""
    with open(ruta, "rb") as f:
        primera = f.readline().decode("utf-8", errors="replace").strip()
    esperado = ENCABEZADOS.get(nombre)
    if esperado and not primera.startswith(esperado):
        raise ValueError(
            f"contenido inválido en {nombre} (primera línea {primera[:60]!r}, se esperaba "
            f"que empezara con {esperado!r}); puede ser un puntero de Git LFS o una página HTML"
        )


def descargar(nombre: str, base: str, destino: Path = DESTINO) -> bool:
    """Baja un archivo en streaming; devuelve False si ya existía."""
    ruta = destino / nombre
    if ruta.exists():
        print(f"Omitido (ya existe): {ruta}")
        return False
    destino.mkdir(parents=True, exist_ok=True)
    parcial = ruta.with_suffix(ruta.suffix + ".part")
    try:
        with urllib.request.urlopen(base + nombre, timeout=60) as r, \
                open(parcial, "wb") as f:
            shutil.copyfileobj(r, f)
        _verificar_encabezado(parcial, nombre, base)
        parcial.replace(ruta)
    except Exception as e:
        parcial.unlink(missing_ok=True)
        raise RuntimeError(
            f"No se pudo descargar {nombre} desde {base + nombre}: {e}. "
            "Fuente original: Kaggle, competencia M5 'M5 Forecasting - Accuracy' "
            "(https://www.kaggle.com/c/m5-forecasting-accuracy/data)."
        ) from e
    print(f"Descargado: {ruta}")
    return True


def main() -> int:
    try:
        for nombre, base in ARCHIVOS.items():
            descargar(nombre, base)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
