"""Gráfico de la pregunta B: inventario (USD) vs fill rate logrado en la prueba.

Lee `outputs/curva_b.csv` (generado por main.py) y guarda `docs/curva_b.png`.

Uso: python scripts/grafico_curva_b.py
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
GRILLA = "#e4e3df"
SERIES = {  # paleta categórica en orden fijo: azul, naranja
    "diario": ("#2a78d6", "o", "Bootstrap diario (días independientes)", (-8, 4), "right"),
    "bloques": ("#eb6834", "s", "Bootstrap por bloques de 28 días", (8, -12), "left"),
}


def graficar(curva: pd.DataFrame, destino: Path) -> None:
    total = curva[curva["categoria"] == "TOTAL"]
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor(SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)
    for metodo, (color, marca, etiqueta, desfase, alineacion) in SERIES.items():
        d = total[total["metodo"] == metodo].sort_values("meta")
        x = d["inventario_usd"] / 1000
        y = d["fill_logrado"] * 100
        ax.plot(x, y, color=color, lw=2, marker=marca, ms=7, label=etiqueta,
                markeredgecolor=SUPERFICIE, markeredgewidth=1.5)
        for xi, yi, meta in zip(x, y, d["meta"]):
            ax.annotate(f"meta {meta * 100:.0f}%", (xi, yi), xytext=desfase,
                        textcoords="offset points", ha=alineacion, fontsize=7.5, color=TEXTO_2)
    ax.set_xlabel("Inventario promedio en la prueba (miles de USD)", color=TEXTO)
    ax.set_ylabel("Fill rate logrado en la prueba (%)", color=TEXTO)
    fig.text(0.02, 0.965, "Tienda CA_1: inventario necesario vs fill rate logrado",
             color=TEXTO, fontsize=12, va="top")
    fig.text(0.02, 0.915, "Cada punto es una meta de fill rate fijada en la calibración; "
             "el eje vertical es lo que se logró con la demanda real (364 días)",
             fontsize=8, color=TEXTO_2, va="top")
    ax.grid(True, color=GRILLA, lw=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(TEXTO_2)
    ax.tick_params(colors=TEXTO_2)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, facecolor=SUPERFICIE)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--entrada", type=Path, default=RAIZ / "outputs" / "curva_b.csv")
    p.add_argument("--salida", type=Path, default=RAIZ / "docs" / "curva_b.png")
    args = p.parse_args(argv)
    graficar(pd.read_csv(args.entrada), args.salida)
    print(f"Gráfico: {args.salida}")


if __name__ == "__main__":
    main()
