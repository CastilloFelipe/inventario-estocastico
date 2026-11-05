"""Corre las preguntas A y B sobre una tienda M5 y guarda los CSV de resultados.

Uso: python main.py --tienda CA_1 --reps 200 --salida outputs/
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from inventario.analisis import Config, curva_b, pregunta_a, resumen_a  # noqa: E402
from inventario.datos import cargar_tienda  # noqa: E402


def _progreso(etiqueta: str, inicio: float):
    def avisar(k: int, total: int) -> None:
        print(f"  {etiqueta}: lote {k}/{total} ({time.time() - inicio:.0f} s)", flush=True)
    return avisar


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--tienda", default="CA_1")
    p.add_argument("--reps", type=int, default=200)
    p.add_argument("--salida", type=Path, default=Path("outputs"))
    p.add_argument("--raw", type=Path, default=Path("data/raw"))
    p.add_argument("--lote", type=int, default=250)
    args = p.parse_args(argv)

    cfg = Config(reps=args.reps, lote=args.lote)
    inicio = time.time()
    print(f"Cargando {args.tienda} desde {args.raw} ...", flush=True)
    datos = cargar_tienda(args.raw, args.tienda)
    print(f"  {len(datos.item_ids)} productos, {datos.n_calib} días de calibración, "
          f"{len(datos.ventas_prueba)} de prueba", flush=True)

    print("Pregunta A: fórmula vs simulación (α = 95%)", flush=True)
    a = pregunta_a(datos, cfg, progreso=_progreso("A", inicio))
    res = resumen_a(a)
    print("Pregunta B: curva inventario vs fill rate", flush=True)
    b = curva_b(datos, cfg, progreso=_progreso("B", inicio))

    args.salida.mkdir(parents=True, exist_ok=True)
    a.to_csv(args.salida / "pregunta_a.csv", index=False)
    res.to_csv(args.salida / "resumen_a.csv", index=False)
    b.to_csv(args.salida / "curva_b.csv", index=False)

    total = res[res["agrupacion"] == "total"].iloc[0]
    excluidos = int(res.loc[res["agrupacion"] == "excluidos", "n"].iloc[0])
    print("\nResumen")
    print(f"  Productos analizados: {total['n']} (excluidos sin ventas: {excluidos}, "
          f"sin precio: {total['n_sin_precio']})")
    print(f"  {'':16}{'fórmula':>12}{'sim. diaria':>14}{'sim. bloques':>14}")
    filas = [("α logrado (media)", "alpha", "{:.3f}"),
             ("Fill (media)", "fill", "{:.3f}"),
             ("Fill (ponderado)", "fill_pond", "{:.3f}"),
             ("Inventario USD", "inv_usd", "{:,.0f}")]
    for etiqueta, col, fmt in filas:
        valores = [fmt.format(total[f"{col}_{p}"]) for p in ("formula", "sim", "bloques")]
        print(f"  {etiqueta:16}{valores[0]:>12}{valores[1]:>14}{valores[2]:>14}")
    no_alc_bl = int((~a["alcanzado_bloques"].fillna(True)).sum())
    print(f"  Meta α {cfg.meta_a}; sin alcanzar con s_max: diaria {total['n_no_alcanzado']}, "
          f"bloques {no_alc_bl}")
    print("  Curva B (TOTAL):")
    for _, f in b[b["categoria"] == "TOTAL"].iterrows():
        print(f"    {f['metodo']:>7} meta {f['meta']:.2f}: inventario "
              f"{f['inventario_usd']:>12,.0f} USD, fill logrado {f['fill_logrado']:.3f}, "
              f"sin alcanzar {f['n_no_alcanzado']}")
    print(f"Archivos en {args.salida}/ ({time.time() - inicio:.0f} s)")


if __name__ == "__main__":
    main()
