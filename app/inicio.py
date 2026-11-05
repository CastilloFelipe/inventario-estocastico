"""Vista de inicio de la app: de qué se trata, conclusiones, conceptos y cómo leer cada vista.

Las cifras de las conclusiones se leen de los resultados (resumen_a.csv, curva_b.csv y,
si existe, diagnostico.csv), así el texto siempre coincide con lo que muestra la app.
"""
from __future__ import annotations

from typing import Callable

import pandas as pd
import streamlit as st

META_ALFA = 0.95


def _pct(x: float, dec: int = 1) -> str:
    return f"{x * 100:.{dec}f}".replace(".", ",") + "%"


def _usd(x: float) -> str:
    return f"USD {x:,.0f}".replace(",", ".")


def _num(x: float, dec: int = 2) -> str:
    return f"{x:.{dec}f}".replace(".", ",")


# ---------- guías cortas para cada vista ----------

GUIAS = {
    "curva": """
**Qué muestra:** cuánto inventario hace falta para cada nivel de servicio. A la simulación se
le pidió una meta de *fill rate* (85%, 90%, ... 99%) y se midió lo que realmente se logró en el
año de prueba.

- **Eje X:** inventario promedio en dólares. **Eje Y:** fill rate logrado.
- **Cada punto** es una meta; la etiqueta dice cuál.
- **Azul (diario)** sortea días sueltos; **naranjo (bloques)** sortea semanas reales seguidas.

**Cómo leerla:** compara la etiqueta de cada punto con su altura. Si el punto "95%" queda en
89%, el método prometió más de lo que cumplió. Si las dos curvas casi se superponen, los dos
métodos cuestan lo mismo por punto de servicio; la diferencia está en qué tan honesta es la meta.
""",
    "resumen": """
**Qué muestra:** las tres políticas con la misma meta, **95% de servicio por ciclo (α)**, la
promesa de la fórmula clásica. Todo se mide en el año de prueba, que ninguna política vio.

- **α logrado:** porcentaje de semanas sin ningún quiebre. La línea punteada es la meta.
- **Fill ponderado:** porcentaje de unidades demandadas que sí se vendieron, ponderado por la
  demanda de cada producto.
- **Inventario (USD):** cuánto dinero queda inmovilizado en promedio.

**Cómo leerla:** una barra bajo la línea es una promesa incumplida. Agrupa por *Clase* para ver
si la fórmula falla más en productos de baja rotación (intermitentes e irregulares).
""",
    "producto": """
**Qué muestra:** un producto real de la tienda: sus ventas diarias, cómo se clasifica su
demanda y una simulación en vivo de la política (R, S).

- **Clase:** tipo de demanda según Syntetos-Boylan (suave, errática, intermitente, irregular).
- **Mejor distribución:** la que mejor describe sus ventas diarias (por AIC).
- **Censura sospechosa:** rachas de ceros tan largas que probablemente fueron quiebres de stock.
- **S de cada política:** el nivel objetivo calculado por la fórmula y por las dos simulaciones.

**Cómo usarla:** mueve S y mira cómo cambian el servicio y el inventario. En el gráfico de abajo,
los días marcados son quiebres (demanda que no se pudo atender). Cambia el método de demanda para
ver cómo las rachas reales (bloques) cambian el riesgo comparado con días independientes.
""",
}


def guia(clave: str) -> None:
    with st.expander("¿Cómo leer esta vista?"):
        st.markdown(GUIAS[clave])


# ---------- conceptos ----------

CONCEPTOS = [
    ("Política de inventario (R, S)",
     "Cada **R = 7 días** se revisa el inventario y se pide lo necesario para volver a un nivel "
     "objetivo **S**. Lo que se decide por producto es S: muy bajo genera quiebres, muy alto "
     "inmoviliza dinero."),
    ("Lead time y cobertura R + L",
     "El **lead time (L)** es lo que demora el pedido en llegar; aquí es aleatorio entre 2 y 5 "
     "días. Por eso S debe alcanzar para la demanda de **R + L días**: hasta la próxima revisión "
     "más lo que tarda ese pedido."),
    ("Stock de seguridad y fórmula clásica",
     "La fórmula de los libros es **S = μ·(R+L) + z·σ·√(R+L)**: la demanda esperada más un colchón. "
     "Con z = 1,645 promete 95% de servicio por ciclo. Supone dos cosas: que la demanda diaria es "
     "**normal** y que los días son **independientes** entre sí."),
    ("Servicio por ciclo (α) vs fill rate (β)",
     "**α:** porcentaje de semanas (ciclos de revisión) sin ningún quiebre; es lo que promete la "
     "fórmula. **β (fill rate):** porcentaje de unidades demandadas que se vendieron; es lo que "
     "importa comercialmente. Un ciclo con 1 unidad faltante de 40 es un fracaso para α y un "
     "97,5% para β."),
    ("Ventas perdidas",
     "Si no hay stock, el cliente se va (como en un supermercado). La venta no se recupera "
     "después, a diferencia de un pedido pendiente."),
    ("Monte Carlo y bootstrap",
     "En vez de una fórmula, se **simulan cientos de años posibles** de la tienda y se cuentan "
     "los quiebres. La demanda de cada día simulado se saca al azar de días reales del producto "
     "(**bootstrap**), sin suponer ninguna distribución."),
    ("Bootstrap por bloques",
     "El bootstrap diario sortea días sueltos, así que también supone días independientes. El "
     "**bootstrap por bloques** sortea **28 días reales seguidos**, y con eso conserva las rachas "
     "(promociones, temporadas, cambios de nivel)."),
    ("Clases de demanda (Syntetos-Boylan)",
     "Se clasifica cada producto con **ADI** (cada cuántos días vende, corte 1,32) y **CV²** (qué "
     "tan variables son las cantidades, corte 0,49): **suave** (vende casi todos los días, "
     "parecido), **errática** (casi todos los días, muy variable), **intermitente** (pocos días, "
     "parecido) e **irregular** (pocos días, muy variable)."),
    ("Calibración y prueba",
     "Las políticas se calibran con los primeros años de datos y se evalúan con el **último año "
     "(364 días)**, que ninguna vio. Es la forma honesta de medir: decidir con el pasado y "
     "vivirlo con el futuro."),
    ("Demanda censurada",
     "Los datos muestran ventas, no demanda. Un día con 0 ventas puede ser falta de clientes o "
     "falta de producto. No se puede corregir del todo; se marcan las rachas de ceros sospechosas."),
    ("Costo de mantener inventario",
     "Tener producto en bodega cuesta: capital, espacio, mermas. Se usa **25% anual del precio**. "
     "Solo escala los dólares; no cambia qué política es mejor."),
]


# ---------- conclusiones con cifras reales ----------

def _conclusiones(r: pd.DataFrame, b: pd.DataFrame | None, d: pd.DataFrame | None) -> None:
    tot = r[r["agrupacion"] == "total"].iloc[0]
    st.subheader("Conclusiones")

    c1, c2, c3 = st.columns(3)
    for col, (p, nombre) in zip((c1, c2, c3), (("formula", "Fórmula clásica"),
                                                ("sim", "Simulación diaria"),
                                                ("bloques", "Simulación por bloques"))):
        col.metric(f"{nombre} · α logrado", _pct(tot[f"alpha_{p}"]),
                   delta=f"{(tot[f'alpha_{p}'] - META_ALFA) * 100:+.1f} pts vs meta".replace(".", ","),
                   delta_color="normal")
        col.caption(f"Fill ponderado {_pct(tot[f'fill_pond_{p}'])} · inventario "
                    f"{_usd(tot[f'inv_usd_{p}'])}")

    brecha = META_ALFA - tot["alpha_formula"]
    cierre = (tot["alpha_bloques"] - tot["alpha_formula"]) / brecha if brecha > 0 else float("nan")
    extra_inv = tot["inv_usd_bloques"] / tot["inv_usd_sim"] - 1

    puntos = [
        f"**La fórmula no cumple su promesa.** Prometía {_pct(META_ALFA, 0)} de servicio por "
        f"ciclo y en el año de prueba logró {_pct(tot['alpha_formula'])}. La simulación con días "
        f"independientes tampoco: {_pct(tot['alpha_sim'])}.",
    ]
    if d is not None and len(d):
        mediana = d["ratio_var_10"].median()
        sobre = (d["ratio_var_10"] > 1.2).mean()
        puntos.append(
            f"**La brecha se asocia a que la demanda tiene memoria.** En el {_pct(sobre, 0)} de los "
            f"productos, las ventas de 10 días seguidos varían más de lo que supone la "
            f"independencia (en la mediana, {_num(mediana)} veces). Tanto la fórmula como el "
            f"bootstrap diario suponen días independientes.")
    else:
        puntos.append("**La brecha se asocia a que la demanda tiene memoria**: las ventas de días "
                      "cercanos se parecen más de lo que suponen la fórmula y el bootstrap diario.")
    puntos.append(
        f"**El bootstrap por bloques acerca la promesa a la realidad.** Llega a "
        f"{_pct(tot['alpha_bloques'])} de servicio (cerca de {_pct(cierre, 0)} de la brecha de la "
        f"fórmula), pero necesita {_pct(extra_inv, 0)} más inventario que la simulación diaria y "
        f"todavía queda bajo la meta.")
    if b is not None:
        t = b[(b["categoria"] == "TOTAL") & (b["meta"].round(2) == 0.95)]
        if set(t["metodo"]) >= {"diario", "bloques"}:
            dia = t[t["metodo"] == "diario"].iloc[0]
            blo = t[t["metodo"] == "bloques"].iloc[0]
            puntos.append(
                f"**En la curva inventario–servicio**, pidiendo 95% de fill rate, la simulación "
                f"diaria logra {_pct(dia['fill_logrado'])} y la de bloques {_pct(blo['fill_logrado'])}. "
                f"Las dos curvas casi se superponen: los bloques no hacen el inventario más "
                f"eficiente, hacen que la meta que se pide sea la que se cumple.")
    puntos.append(
        "**Lección práctica:** antes de confiar en un nivel de servicio calculado con una "
        "fórmula, conviene probarlo contra demanda real que no se usó para calcularlo.")
    st.markdown("\n".join(f"- {p}" for p in puntos))

    with st.expander("Limitaciones (léelas antes de sacar conclusiones generales)"):
        st.markdown("""
- **Una sola tienda** (CA_1) y un solo año de prueba.
- **El lead time es un supuesto** (2 a 5 días): M5 no trae datos de reposición.
- **Demanda censurada:** parte de las rachas de ceros pueden ser quiebres, que inflan la medida
  de dependencia entre días.
- **Cambios de nivel por producto:** la demanda promedio de la tienda no cambió, pero algunos
  productos subieron o bajaron mucho; eso también baja el servicio y no se separó del todo de la
  dependencia.
- **Ventana de calibración larga:** μ, σ y el bootstrap usan toda la historia desde la primera
  venta. Una ventana reciente podría cambiar los resultados; no se probó.
- **El bloque de 28 días se eligió, no se optimizó.**
""")


def vista_inicio(cargar_salida: Callable[[str], pd.DataFrame | None]) -> None:
    st.header("¿De qué se trata?")
    st.markdown("""
Una tienda tiene que decidir **cuánto stock mantener de cada producto** sin saber cuánto va a
vender. La herramienta clásica es una **fórmula de stock de seguridad** que promete un nivel de
servicio, por ejemplo "95% de las semanas sin quiebres".

Este proyecto pone a prueba esa promesa con **datos reales de Walmart** (competencia M5): los
**3.049 productos de la tienda CA_1** (California), con ventas diarias de 2011 a 2016. Se
comparan tres formas de fijar el nivel de inventario de cada producto:

1. **Fórmula clásica**, la de los libros, que supone demanda normal y días independientes.
2. **Simulación Monte Carlo con días independientes**: sortea días reales del producto.
3. **Simulación Monte Carlo por bloques**: sortea semanas reales seguidas, conservando las rachas.

Las tres se calibran con los primeros años y se ponen a prueba con el **último año**, día por
día, con la demanda que realmente ocurrió.
""")

    r = cargar_salida("resumen_a.csv")
    if r is None or "alpha_bloques" not in r.columns:
        st.info("Las conclusiones aparecen cuando están los resultados del análisis "
                "(`python main.py`).")
    else:
        _conclusiones(r, cargar_salida("curva_b.csv"), cargar_salida("diagnostico.csv"))

    st.subheader("Conceptos clave")
    for titulo, texto in CONCEPTOS:
        with st.expander(titulo):
            st.markdown(texto)

    st.subheader("Cómo usar la app")
    st.markdown("""
- **Curva inventario–servicio:** cuánto inventario cuesta cada punto de servicio, y si la meta
  pedida se cumple.
- **Fórmula vs simulación:** las tres políticas lado a lado, por clase de demanda y categoría.
- **Producto:** elige un producto, mueve su nivel S y mira la simulación en vivo.

Cada vista tiene una guía **"¿Cómo leer esta vista?"** arriba. El detalle completo está en el
[reporte de resultados](https://github.com/CastilloFelipe/inventario-estocastico/blob/main/docs/resultados.md)
y la [guía de conceptos](https://github.com/CastilloFelipe/inventario-estocastico/blob/main/docs/conceptos.md).
""")
