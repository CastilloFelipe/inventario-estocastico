# Inventario estocástico (M5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Comparar la fórmula clásica de stock de seguridad contra una política (R, S) calibrada por Monte Carlo con demanda real de M5 (tienda CA_1), y construir la curva inventario–fill rate.

**Architecture:** Paquete `src/inventario/` con módulos independientes: datos → demanda → simulador → políticas → backtest → análisis. El simulador es NumPy vectorizado (réplicas × días × productos) y no conoce M5; el análisis procesa los productos por lotes para acotar memoria.

**Tech Stack:** Python 3.12, numpy, pandas, scipy, streamlit, plotly, pytest.

**Spec:** `docs/superpowers/specs/2026-11-05-inventario-estocastico-design.md`

## Global Constraints

- Tienda por defecto `CA_1`; prueba = últimos 364 días; calibración = el resto.
- R = 7 días; lead time uniforme discreto en {2, 3, 4, 5}; ventas perdidas; inventario inicial S; calentamiento 28 días.
- Pregunta A: meta α = 0,95 (z = 1,645) para fórmula y simulación. Pregunta B: metas de fill rate 0,85; 0,90; 0,95; 0,97; 0,98; 0,99.
- Costo de mantener 25% anual del precio. Semilla por defecto 2026.
- Syntetos-Boylan: ADI ≥ 1,32 → intermitente/irregular; CV² ≥ 0,49 → errática/irregular.
- Datos M5 nunca se versionan (`data/raw/` en `.gitignore`); tests solo con datos sintéticos.
- Autor de commits: `Felipe Castillo <felipecastilloriq@gmail.com>`; textos en español.

## Review Focus

1. Producto sin ventas en calibración: queda fuera del análisis, contado en el resumen, sin errores (test en Task 5).
2. Producto lanzado tarde: el bootstrap solo toma días desde su primera venta (test en Task 3).
3. Producto sin precio: su inventario en USD es NaN y no entra en las sumas (tests en Tasks 4 y 5).
4. Meta inalcanzable dentro de `s_max` (p. ej. α = 0,999 con demanda irregular): devuelve `s_max` y `alcanzado=False`, no un bucle infinito (test en Task 2).
5. Procesar por lotes no cambia resultados: `lote=2` y `lote=1000` dan lo mismo con igual semilla (test en Task 5).

---

### Task 1: Proyecto base y simulador (R, S)

**Files:**
- Create: `requirements.txt` (numpy, pandas, scipy, streamlit, plotly, pytest), `.gitignore` (`data/raw/`, `outputs/`, caches), `LICENSE` (MIT, Felipe Castillo Riquelme, 2026), `.github/workflows/tests.yml` (Python 3.12, `pip install -r requirements.txt`, `pytest -q`), `tests/conftest.py` (agrega `src/` al path)
- Create: `src/inventario/__init__.py`, `src/inventario/simulador.py`
- Test: `tests/test_simulador.py`

**Interfaces:**
- Produces:
  - `@dataclass Metricas: fill_rate: np.ndarray; servicio_ciclo: np.ndarray; inventario_prom: np.ndarray` (todas de forma `(items,)`)
  - `muestrear_lead_times(rng: np.random.Generator, reps: int, n_revisiones: int, items: int, valores: tuple[int, ...] = (2, 3, 4, 5)) -> np.ndarray` int, forma `(reps, n_revisiones, items)`
  - `simular(demanda: np.ndarray, S: np.ndarray, R: int, lead_times: np.ndarray, calentamiento: int = 28) -> Metricas`; `demanda` forma `(reps, dias, items)`

Dinámica por día t (fija): (1) sumar pedidos que llegan en t; (2) vender `min(inv, demanda)`, el resto se pierde; (3) si `t % R == 0`, pedir `max(0, S − inv − en_tránsito)` con el lead time de esa revisión (llega en t + L). Inventario inicial = S. Métricas solo desde `calentamiento`: fill = vendido/demandado (1,0 si demandado = 0); α = fracción de ventanas `[t, t+R)` alineadas a revisiones sin ningún día con venta perdida; inventario_prom = media del inventario al cierre del día, promediado sobre réplicas.

- [ ] **Step 1: Tests que fallan**

```python
def test_demanda_cero_da_servicio_total_sin_error():
    d = np.zeros((5, 100, 3), dtype=np.int64)
    m = simular(d, np.array([0, 5, 10]), 7, np.full((5, 15, 3), 3))
    assert np.allclose(m.fill_rate, 1.0) and np.allclose(m.servicio_ciclo, 1.0)

def test_mas_S_nunca_baja_el_servicio():  # Poisson(4), 300 réplicas, 364 días, misma demanda y lead times
    assert np.all(np.diff([simular(d, np.array([s]), 7, lt).fill_rate[0] for s in range(20, 80, 5)]) >= -1e-12)

def test_mas_lead_time_nunca_sube_el_servicio():  # S fijo, lead time fijo 2 vs 5
    assert m5.fill_rate[0] <= m2.fill_rate[0] and m5.servicio_ciclo[0] <= m2.servicio_ciclo[0]

def test_misma_semilla_mismo_resultado(): ...

def test_poisson_lead_time_fijo_coincide_con_teoria():
    # λ = 4/día, R = 7, L = 3 fijo; S = poisson.ppf(0.95, 4 * 10); 2000 réplicas × 364 días
    assert abs(m.servicio_ciclo[0] - poisson.cdf(S, 40)) < 0.02
```

- [ ] **Step 2:** `pytest tests/test_simulador.py -v` → FAIL (import error).
- [ ] **Step 3:** Implementar `muestrear_lead_times`, `Metricas`, `simular`. Bucle sobre días con operaciones vectorizadas sobre `(reps, items)`; pedidos en tránsito en un arreglo circular `(reps, max_L + 1, items)`.
- [ ] **Step 4:** `pytest tests/test_simulador.py -v` → PASS.
- [ ] **Step 5:** Commit `"Simulador (R, S) con ventas perdidas y lead time aleatorio"`.

### Task 2: Políticas (fórmula y búsqueda por simulación)

**Files:** Create `src/inventario/politicas.py` · Test `tests/test_politicas.py`

**Interfaces:**
- Consumes: `simular`, `Metricas` (Task 1)
- Produces:
  - `s_formula(mu: np.ndarray, sigma: np.ndarray, R: int, L_media: float, z: float) -> np.ndarray` int = `ceil(mu*(R+L) + z*sigma*sqrt(R+L))`, mínimo 0
  - `s_simulacion(demanda: np.ndarray, lead_times: np.ndarray, R: int, meta: float, metrica: Literal["ciclo", "fill"], s_max: np.ndarray, calentamiento: int = 28) -> tuple[np.ndarray, np.ndarray]` → `(S, alcanzado)`; búsqueda binaria entera vectorizada en `[0, s_max]` del menor S que cumple la meta, reutilizando la misma demanda y lead times (números aleatorios comunes)

- [ ] **Step 1: Tests que fallan**

```python
def test_formula_valores_conocidos():
    assert s_formula(np.array([4.0]), np.array([2.0]), 7, 3.0, 1.645)[0] == math.ceil(40 + 1.645 * 2 * math.sqrt(10))

def test_normal_media_alta_formula_y_simulacion_coinciden():
    # demanda ~ round(N(100, 20)) >= 0, L fijo 3, meta α = 0.95, 1000 réplicas
    assert abs(S_sim[0] - S_f[0]) / S_f[0] < 0.03

def test_S_encontrado_es_el_minimo():
    # simular(S) cumple la meta y simular(S - 1) no

def test_meta_inalcanzable_devuelve_s_max():
    S, ok = s_simulacion(d, lt, 7, 0.999, "fill", s_max=np.array([3]))
    assert S[0] == 3 and not ok[0]
```

- [ ] **Step 2:** `pytest tests/test_politicas.py -v` → FAIL.
- [ ] **Step 3:** Implementar ambas funciones.
- [ ] **Step 4:** `pytest tests/test_politicas.py -v` → PASS.
- [ ] **Step 5:** Commit `"Políticas: fórmula clásica y búsqueda de S por simulación"`.

### Task 3: Diagnóstico y muestreo de la demanda

**Files:** Create `src/inventario/demanda.py` · Test `tests/test_demanda.py`

**Interfaces:**
- Produces:
  - `primera_venta(ventas: np.ndarray) -> np.ndarray` índice del primer día con venta por producto (`-1` si nunca vende); `ventas` forma `(dias, items)`
  - `clasificar(ventas: np.ndarray, inicio: np.ndarray) -> np.ndarray` de str en {`"suave"`, `"erratica"`, `"intermitente"`, `"irregular"`, `"sin_ventas"`}; ADI = días desde `inicio` / días con venta; CV² de las cantidades > 0
  - `ajustar_distribuciones(x: np.ndarray) -> dict` con claves `"mejor"` y `"aic"` (normal, poisson, binomial_negativa; la binomial negativa solo si var > media, por momentos)
  - `censura_sospechosa(x: np.ndarray) -> bool`: con p0 = fracción de ceros y Lmax = racha de ceros más larga, sospechosa si `len(x) * p0**Lmax < 0.01` y p0 < 0.5
  - `muestrear_demanda(rng, historia: np.ndarray, dow_hist: np.ndarray, dow_sim: np.ndarray, reps: int, inicio: np.ndarray) -> np.ndarray` `(reps, len(dow_sim), items)`; para cada día simulado toma un día histórico al azar del mismo día de semana y ≥ `inicio` del producto

- [ ] **Step 1: Tests que fallan:** una serie construida para cada clase da su etiqueta; serie toda en cero → `"sin_ventas"`; Poisson(3) → mejor = poisson; datos sobredispersos → binomial_negativa; serie con 60 ceros seguidos en un producto que vende el 90% de los días → censura `True`, Poisson(3) → `False`; `muestrear_demanda` nunca devuelve valores de días anteriores a `inicio` (historia con 999 antes de `inicio`) y respeta el día de semana (historia donde el sábado vale 7 y el resto 0).
- [ ] **Step 2:** `pytest tests/test_demanda.py -v` → FAIL.
- [ ] **Step 3:** Implementar. `muestrear_demanda`: por día de semana, índices válidos de cada producto = sufijo de los días de ese weekday con índice ≥ `inicio`; índice = `inicio_w + floor(u * k_w)`.
- [ ] **Step 4:** `pytest tests/test_demanda.py -v` → PASS.
- [ ] **Step 5:** Commit `"Diagnóstico de demanda: Syntetos-Boylan, distribuciones, censura y bootstrap por día de semana"`.

### Task 4: Carga de datos M5

**Files:** Create `scripts/descargar_m5.py`, `src/inventario/datos.py` · Test `tests/test_datos.py` (con CSV mínimos escritos en `tmp_path` con el mismo formato que M5)

**Interfaces:**
- Produces:
  - `@dataclass DatosTienda: item_ids: list[str]; categorias: list[str]; fechas: pd.DatetimeIndex; dow: np.ndarray; ventas: np.ndarray (dias, items) int; precio: np.ndarray (items,) float; n_calib: int` con propiedades `ventas_calib`, `ventas_prueba`, `dow_calib`, `dow_prueba`
  - `cargar_tienda(raw_dir: Path, tienda: str = "CA_1", dias_prueba: int = 364) -> DatosTienda`; precio = último `sell_price` conocido dentro de la calibración (NaN si no hay)
- `descargar_m5.py`: baja `sales_train_evaluation.csv` y `sell_prices.csv` de `https://media.githubusercontent.com/media/shrutidoshi94/M5Forecasting/main/` y `calendar.csv` de `https://raw.githubusercontent.com/shrutidoshi94/M5Forecasting/main/` a `data/raw/`; omite archivos ya presentes; ante error indica el archivo y la fuente original (Kaggle, competencia M5).

- [ ] **Step 1: Tests que fallan:** filtra la tienda pedida; calibración y prueba no se solapan y suman todos los días; `dow` coincide con el calendario; precio toma el último valor de calibración e ignora precios del período de prueba; producto sin precio → NaN; si falta un archivo, `FileNotFoundError` cuyo mensaje nombra el archivo y `scripts/descargar_m5.py`.
- [ ] **Step 2:** `pytest tests/test_datos.py -v` → FAIL.
- [ ] **Step 3:** Implementar `cargar_tienda` y el script.
- [ ] **Step 4:** `pytest tests/test_datos.py -v` → PASS.
- [ ] **Step 5:** Commit `"Carga de datos M5 por tienda y script de descarga"`.

### Task 5: Backtest, análisis de las preguntas A y B y CLI

**Files:** Create `src/inventario/backtest.py`, `src/inventario/analisis.py`, `main.py` · Test `tests/test_analisis.py` (con un `DatosTienda` sintético de 6 productos: suave, errática, intermitente, irregular, sin ventas y sin precio)

**Interfaces:**
- Consumes: Tasks 1–4
- Produces:
  - `backtest(calentamiento_demanda: np.ndarray (28, items), ventas_prueba: np.ndarray, S: np.ndarray, R: int, rng, reps: int = 50, valores_lt=(2, 3, 4, 5)) -> Metricas` (demanda real fija, solo el lead time es aleatorio)
  - `@dataclass Config: R=7; lead_times=(2,3,4,5); reps=200; calentamiento=28; dias_sim=364; costo_anual=0.25; semilla=2026; lote=250; meta_a=0.95; metas_b=(0.85,0.90,0.95,0.97,0.98,0.99)`
  - `pregunta_a(datos: DatosTienda, cfg: Config) -> pd.DataFrame` por producto: `item_id, categoria, clase, censura, mejor_dist, S_formula, S_sim, alcanzado, alpha_formula, alpha_sim, fill_formula, fill_sim, inv_usd_formula, inv_usd_sim`
  - `resumen_a(df: pd.DataFrame) -> pd.DataFrame` por `clase` y por `categoria`: n, medias de α y fill logrados, suma de inventario USD; reporta excluidos
  - `curva_b(datos: DatosTienda, cfg: Config) -> pd.DataFrame`: `meta, categoria` (incluye `"TOTAL"`), `inventario_usd, costo_anual_usd, fill_logrado` (ponderado por demanda de prueba)
  - `main.py --tienda CA_1 --reps 200 --salida outputs/`: guarda `pregunta_a.csv`, `resumen_a.csv`, `curva_b.csv`

- [ ] **Step 1: Tests que fallan:** producto sin ventas excluido y contado; producto sin precio con `inv_usd_*` NaN y fuera de las sumas; `lote=2` y `lote=1000` producen el mismo DataFrame; curva B con inventario no decreciente en la meta; con demanda de prueba idéntica a la calibración y Poisson alta, `alpha_sim` ≥ 0,9.
- [ ] **Step 2:** `pytest tests/test_analisis.py -v` → FAIL.
- [ ] **Step 3:** Implementar. Simulación de calibración con `muestrear_demanda` sobre `dias_sim + calentamiento` días; `s_max` = `s_formula` con z = 3,72 (99,99%) × 2 + 10; semilla derivada por lote (`semilla + índice de lote`) pero con el mismo orden de productos para reproducibilidad.
- [ ] **Step 4:** `pytest -q` → todo PASS.
- [ ] **Step 5:** Commit `"Backtest, preguntas A y B y CLI"`.

### Task 6: Análisis real y documentación

**Files:** Create `docs/conceptos.md`, `docs/resultados.md`, `README.md`

- [ ] **Step 1:** `python scripts/descargar_m5.py && python main.py --tienda CA_1` → existen los tres CSV en `outputs/`.
- [ ] **Step 2:** Escribir `docs/resultados.md` solo con cifras de esos CSV: tabla A por clase y categoría, curva B (gráfico PNG en `docs/`), número de excluidos y sospechosos de censura, limitaciones (lead time supuesto, demanda censurada, una tienda).
- [ ] **Step 3:** Escribir `docs/conceptos.md` (los 12 conceptos acordados, con el ejemplo del detergente) y el README (objetivo, resultados clave, cómo reproducir, estructura, licencia y fuente de datos M5).
- [ ] **Step 4:** Commit `"Resultados con M5 (CA_1), guía de conceptos y README"`.

### Task 7: App Streamlit

**Files:** Create `app/streamlit_app.py` · Test `tests/test_app.py` (AppTest con `outputs/` sintético en `tmp_path`, sin M5)

**Interfaces:** Consumes los CSV de Task 5 y `simular`/`muestrear_demanda` para la vista de producto.

- [ ] **Step 1: Test que falla:** la app carga con CSV sintéticos, muestra la curva B y una vista de producto sin excepciones; sin `outputs/` muestra un mensaje con el comando a correr.
- [ ] **Step 2:** `pytest tests/test_app.py -v` → FAIL.
- [ ] **Step 3:** Implementar tres vistas: curva B con filtro por categoría; resultados A por clase; producto (serie, clase, mejor distribución y simulación con S en un deslizador mostrando inventario diario y quiebres).
- [ ] **Step 4:** `pytest -q` → PASS; captura de pantalla en `docs/`.
- [ ] **Step 5:** Commit `"App Streamlit"`.
