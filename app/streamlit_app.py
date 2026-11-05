"""App Streamlit: curva inventario-servicio, fórmula vs simulación y vista por producto.

Uso: streamlit run app/streamlit_app.py
Rutas configurables con INVENTARIO_OUTPUTS (por defecto outputs/) e
INVENTARIO_RAW (por defecto data/raw/).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from inventario.analisis import Config  # noqa: E402
from inventario.datos import cargar_tienda  # noqa: E402
from inventario.demanda import muestrear_demanda, muestrear_demanda_bloques, primera_venta  # noqa: E402
from inventario.simulador import muestrear_lead_times, simular  # noqa: E402

TIENDA = "CA_1"
COLORES = ["#2a78d6", "#eb6834", "#1baf7a"]
POLITICAS = [("formula", "Fórmula"), ("sim", "Simulación diaria"), ("bloques", "Simulación por bloques")]
SEMILLA_APP = 2026
REPS_APP = 200
VISTAS = ["Curva inventario–servicio", "Fórmula vs simulación", "Producto"]


def ruta_outputs() -> Path:
    return Path(os.environ.get("INVENTARIO_OUTPUTS", RAIZ / "outputs"))


def ruta_raw() -> Path:
    return Path(os.environ.get("INVENTARIO_RAW", RAIZ / "data" / "raw"))


def trayectoria(demanda: np.ndarray, S: int, R: int, lead_times: np.ndarray,
                calentamiento: int) -> tuple[np.ndarray, np.ndarray]:
    """Inventario diario al cierre y días con quiebre de una réplica (misma dinámica que `simular`).

    demanda: (dias,); lead_times: (n_rev,). Devuelve solo los días posteriores al calentamiento.
    """
    n = int(lead_times.max()) + 1
    inv, en_transito = int(S), 0
    pipeline = np.zeros(n, dtype=np.int64)
    inventario, quiebre = [], []
    for t in range(len(demanda)):
        llega = pipeline[t % n]
        inv += llega
        en_transito -= llega
        pipeline[t % n] = 0
        if t % R == 0:
            pedido = max(0, S - inv - en_transito)
            pipeline[(t + int(lead_times[t // R])) % n] += pedido
            en_transito += pedido
        v = min(inv, int(demanda[t]))
        inv -= v
        inventario.append(inv)
        quiebre.append(demanda[t] > v)
    return np.array(inventario)[calentamiento:], np.array(quiebre)[calentamiento:]


def simular_producto(historia: np.ndarray, dow_calib: np.ndarray, dow_prueba0: int,
                     S: int, metodo: str, j: int, cfg: Config) -> dict:
    """Simulación en vivo de un producto: métricas con `reps` réplicas y una trayectoria."""
    historia = historia.reshape(-1, 1)
    inicio = primera_venta(historia)
    n = cfg.calentamiento + cfg.dias_sim
    rng = np.random.default_rng([cfg.semilla, int(j), 9])
    if metodo == "bloques":
        dem = muestrear_demanda_bloques(rng, historia, dow_calib,
                                        int((dow_prueba0 - cfg.calentamiento) % 7), n,
                                        cfg.reps, inicio, cfg.bloque)
    else:
        dow_sim = (dow_prueba0 - cfg.calentamiento + np.arange(n)) % 7
        dem = muestrear_demanda(rng, historia, dow_calib, dow_sim, cfg.reps, inicio)
    n_rev = -(-n // cfg.R) + 1
    lt = muestrear_lead_times(rng, cfg.reps, n_rev, 1, cfg.lead_times)
    m = simular(dem, np.array([S]), cfg.R, lt, calentamiento=cfg.calentamiento)
    inv, quiebre = trayectoria(dem[0, :, 0], S, cfg.R, lt[0, :, 0], cfg.calentamiento)
    return {"alpha": float(m.servicio_ciclo[0]), "fill": float(m.fill_rate[0]),
            "inv_prom": float(m.inventario_prom[0]), "inv": inv, "quiebre": quiebre}


# ---------- carga con caché ----------

@st.cache_data(show_spinner=False)
def leer_csv(ruta: str, firma: float) -> pd.DataFrame:
    return pd.read_csv(ruta)


def cargar_salida(nombre: str) -> pd.DataFrame | None:
    ruta = ruta_outputs() / nombre
    return leer_csv(str(ruta), ruta.stat().st_mtime) if ruta.exists() else None


@st.cache_resource(show_spinner="Cargando datos M5...")
def cargar_datos(raw: str):
    return cargar_tienda(Path(raw), TIENDA)


def aviso_sin_outputs() -> None:
    st.warning("No se encontraron los resultados del análisis en "
               f"`{ruta_outputs()}`. Genéralos con:")
    st.code("python main.py", language="bash")


def aviso_sin_raw() -> None:
    st.warning(f"No se encontraron los datos M5 en `{ruta_raw()}`. Descárgalos con:")
    st.code("python scripts/descargar_m5.py", language="bash")


def layout_base(fig: go.Figure, x: str, y: str, formato_y: str | None = None) -> go.Figure:
    fig.update_layout(xaxis_title=x, yaxis_title=y, margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h", y=-0.2), height=440)
    if formato_y:
        fig.update_yaxes(tickformat=formato_y)
    return fig


# ---------- vistas ----------

def vista_curva() -> None:
    st.header("Curva inventario–servicio")
    st.caption("Cada punto es una meta de fill rate pedida a la simulación; el eje Y es el fill "
               "rate logrado en el año de prueba y el eje X el inventario promedio valorizado.")
    b = cargar_salida("curva_b.csv")
    if b is None:
        return aviso_sin_outputs()
    cats = list(b["categoria"].unique())
    sel = st.multiselect("Categoría", cats, default=["TOTAL"] if "TOTAL" in cats else cats[:1])
    c1, c2 = st.columns(2)
    ver_diario = c1.checkbox("Simulación diaria", value=True)
    ver_bloques = c2.checkbox("Simulación por bloques", value=True)
    metodos = [m for m, v in (("diario", ver_diario), ("bloques", ver_bloques)) if v]
    if not sel or not metodos:
        st.info("Elige al menos una categoría y un método.")
        return
    color = {"diario": COLORES[0], "bloques": COLORES[1]}
    dash = dict(zip(sel, ["solid", "dash", "dot", "dashdot"] * 3))
    fig = go.Figure()
    for cat in sel:
        for met in metodos:
            d = b[(b["categoria"] == cat) & (b["metodo"] == met)].sort_values("meta")
            fig.add_trace(go.Scatter(
                x=d["inventario_usd"], y=d["fill_logrado"], mode="lines+markers+text",
                name=f"{cat} · {met}", text=[f"{m:.0%}" for m in d["meta"]],
                textposition="top center", line=dict(color=color[met], dash=dash[cat]),
                hovertemplate="Meta %{text}<br>Inventario %{x:,.0f} USD<br>Fill %{y:.1%}<extra></extra>"))
    layout_base(fig, "Inventario promedio (USD)", "Fill rate logrado", ".0%")
    st.plotly_chart(fig, width="stretch")
    tabla = b[b["categoria"].isin(sel) & b["metodo"].isin(metodos)].rename(columns={
        "metodo": "Método", "meta": "Meta fill", "categoria": "Categoría",
        "inventario_usd": "Inventario (USD)", "costo_anual_usd": "Costo anual (USD)",
        "fill_logrado": "Fill logrado", "n_no_alcanzado": "Sin alcanzar"})
    st.dataframe(tabla, hide_index=True, width="stretch")


def vista_resumen() -> None:
    st.header("Fórmula vs simulación")
    st.caption("Meta de servicio por ciclo α = 0,95. Se compara lo logrado en el año de prueba.")
    r = cargar_salida("resumen_a.csv")
    if r is None:
        return aviso_sin_outputs()
    agr = st.radio("Agrupar por", ["clase", "categoria", "total"], horizontal=True,
                   format_func=lambda x: {"clase": "Clase", "categoria": "Categoría",
                                          "total": "Total"}[x])
    g = r[r["agrupacion"] == agr]
    filas = []
    for _, f in g.iterrows():
        for p, nombre in POLITICAS:
            filas.append({"Grupo": f["grupo"], "Política": nombre, "Productos": f["n"],
                          "α logrado": f[f"alpha_{p}"], "Fill ponderado": f[f"fill_pond_{p}"],
                          "Inventario (USD)": f[f"inv_usd_{p}"]})
    tabla = pd.DataFrame(filas)
    fig = go.Figure()
    for (p, nombre), col in zip(POLITICAS, COLORES):
        d = tabla[tabla["Política"] == nombre]
        fig.add_trace(go.Bar(x=d["Grupo"], y=d["α logrado"], name=nombre, marker_color=col,
                             text=[f"{v:.3f}".replace(".", ",") for v in d["α logrado"]],
                             textposition="outside"))
    fig.add_hline(y=0.95, line_dash="dash", line_color="#666",
                  annotation_text="Meta 0,95", annotation_position="top left")
    layout_base(fig, "Grupo", "α logrado (media)")
    fig.update_layout(barmode="group")
    fig.update_yaxes(range=[0.7, 1.02])
    st.plotly_chart(fig, width="stretch")
    st.dataframe(tabla, hide_index=True, width="stretch", column_config={
        "α logrado": st.column_config.NumberColumn(format="%.3f"),
        "Fill ponderado": st.column_config.NumberColumn(format="%.3f"),
        "Inventario (USD)": st.column_config.NumberColumn(format="%,.0f")})


def vista_producto() -> None:
    st.header("Producto")
    a = cargar_salida("pregunta_a.csv")
    if a is None:
        return aviso_sin_outputs()
    if not (ruta_raw() / "sales_train_evaluation.csv").exists():
        return aviso_sin_raw()
    datos = cargar_datos(str(ruta_raw()))
    a = a[a["item_id"].isin(datos.item_ids) & (a["clase"] != "sin_ventas")]
    busca = st.text_input("Buscar producto", placeholder="p. ej. FOODS_1_001")
    opciones = [i for i in a["item_id"] if busca.strip().lower() in i.lower()]
    if not opciones:
        st.info("Ningún producto coincide con la búsqueda.")
        return
    item = st.selectbox("Producto", opciones)
    f = a[a["item_id"] == item].iloc[0]
    j = datos.item_ids.index(item)

    serie = pd.Series(datos.ventas[:, j], index=datos.fechas)
    fig = go.Figure(go.Scatter(x=serie.index, y=serie.values, mode="lines",
                               line=dict(color=COLORES[0], width=1), name="Ventas diarias"))
    fig.add_vline(x=datos.fechas[datos.n_calib].timestamp() * 1000, line_dash="dash",
                  line_color="#666", annotation_text="Inicio de la prueba")
    layout_base(fig, "Fecha", "Unidades vendidas por día")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, width="stretch")

    c = st.columns(4)
    c[0].metric("Clase", str(f["clase"]).capitalize())
    c[1].metric("Mejor distribución", str(f["mejor_dist"]).replace("_", " "))
    c[2].metric("Censura sospechosa", "Sí" if f["censura"] is True or f["censura"] == True else "No")  # noqa: E712
    c[3].metric("Categoría", str(f["categoria"]))
    s = st.columns(3)
    for col, (p, nombre) in zip(s, POLITICAS):
        col.metric(f"S · {nombre}", f"{int(f[f'S_{p}'])} unidades")

    st.subheader("Simulación en vivo")
    cfg = Config(reps=REPS_APP, semilla=SEMILLA_APP)
    s_max = int(max(f["S_formula"], f["S_sim"], f["S_bloques"], 1) * 2 + 5)
    c1, c2 = st.columns([2, 1])
    S = c1.slider("Nivel S (unidades)", 0, s_max, int(f["S_bloques"]))
    metodo = c2.radio("Método de demanda", ["diario", "bloques"], horizontal=True)
    r = simular_producto(datos.ventas_calib[:, j], datos.dow_calib, int(datos.dow_prueba[0]),
                         S, metodo, j, cfg)
    precio = datos.precio[j]
    m = st.columns(4)
    m[0].metric("α (servicio por ciclo)", f"{r['alpha']:.3f}".replace(".", ","))
    m[1].metric("Fill rate", f"{r['fill']:.3f}".replace(".", ","))
    m[2].metric("Inventario promedio", f"{r['inv_prom']:.1f} unid.".replace(".", ","))
    m[3].metric("Inventario promedio (USD)",
                "s/d" if np.isnan(precio) else f"{r['inv_prom'] * precio:,.0f}")
    dias = np.arange(1, len(r["inv"]) + 1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dias, y=r["inv"], mode="lines", name="Inventario al cierre",
                             line=dict(color=COLORES[0], width=1.5)))
    q = r["quiebre"]
    fig.add_trace(go.Scatter(x=dias[q], y=r["inv"][q], mode="markers", name="Día con quiebre",
                             marker=dict(color=COLORES[1], size=8, symbol="x")))
    layout_base(fig, "Día de la simulación", "Inventario (unidades)")
    st.plotly_chart(fig, width="stretch")
    st.caption(f"Una réplica de {REPS_APP}; {int(q.sum())} días con quiebre de {len(q)}. "
               "Semilla fija: 2026.")


def main() -> None:
    st.set_page_config(page_title="Inventario estocástico", layout="wide")
    st.title("Inventario estocástico · Walmart M5 (CA_1)")
    vista = st.sidebar.radio("Vista", VISTAS)
    {VISTAS[0]: vista_curva, VISTAS[1]: vista_resumen, VISTAS[2]: vista_producto}[vista]()


main()
