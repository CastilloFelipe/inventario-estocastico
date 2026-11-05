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
DESTINO = Path(__file__).resolve().parents[1] / "data" / "raw"


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
