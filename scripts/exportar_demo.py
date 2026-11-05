"""Prepara los datos de la app publicada (Streamlit Community Cloud).

    python scripts/exportar_demo.py

Copia los resultados ya calculados (outputs/) y un extracto comprimido con las ventas
diarias de la tienda analizada a app/datos_demo/. La app usa esa carpeta cuando no
encuentra outputs/ ni data/raw/.

Fuente de los datos: competencia "M5 Forecasting - Accuracy" (Kaggle). El extracto
contiene solo la tienda analizada y se incluye con fines de demostración, citando la fuente.
"""
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from inventario.datos import cargar_tienda, guardar_extracto  # noqa: E402

DESTINO = RAIZ / "app" / "datos_demo"
RESULTADOS = ("pregunta_a.csv", "resumen_a.csv", "curva_b.csv")


def main(tienda: str = "CA_1") -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nombre in RESULTADOS:
        origen = RAIZ / "outputs" / nombre
        if not origen.exists():
            sys.exit(f"Falta {origen}. Corre primero: python main.py --tienda {tienda}")
        shutil.copy2(origen, DESTINO / nombre)
    datos = cargar_tienda(RAIZ / "data" / "raw", tienda)
    guardar_extracto(datos, DESTINO / f"{tienda}.npz")
    total = sum(p.stat().st_size for p in DESTINO.iterdir()) / 1e6
    print(f"Listo: {DESTINO} ({total:.1f} MB)")


if __name__ == "__main__":
    main(*sys.argv[1:2])
