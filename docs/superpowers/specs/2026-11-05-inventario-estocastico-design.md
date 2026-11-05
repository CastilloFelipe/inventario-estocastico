# Diseño: Inventario estocástico con demanda real (M5 Walmart)

Fecha: 2026-11-05 · Autor: Felipe Castillo

## 1. Objetivo

Proyecto de portafolio (orientado a primer empleo en supply chain) que también sirve para
aprender modelos estocásticos de inventario. Responde dos preguntas de negocio con datos
reales de retail:

- **A (núcleo).** ¿La fórmula clásica de stock de seguridad entrega el servicio que promete
  con demanda real? Se compara, producto por producto, contra una política calibrada por
  simulación Monte Carlo, y ambas se prueban con demanda real que no se usó para calibrar.
- **B (vista gerencial).** ¿Cuánto inventario (USD) cuesta cada punto de fill rate, por
  categoría y para la tienda?

Criterio de éxito: resultados reproducibles (semilla fija), simulador validado contra casos
teóricos, conclusiones escritas solo después de correr el análisis, y una app que permita
explorar productos y la curva de la pregunta B.

## 2. Alcance acordado

| Decisión | Valor |
|---|---|
| Datos | M5 (Walmart): `sales_train_evaluation.csv`, `calendar.csv`, `sell_prices.csv` |
| Tienda | CA_1, sus 3.049 productos (3 categorías). La app muestra solo la tienda analizada (CA_1), porque los outputs precalculados son de una tienda; para otra: `python main.py --tienda X --salida otra_carpeta/` y apuntar `INVENTARIO_OUTPUTS` a esa carpeta |
| Calibración / prueba | Todo excepto los últimos 364 días / últimos 364 días |
| Política | Revisión periódica (R, S), R = 7 días (parámetro) |
| Lead time | Aleatorio, uniforme discreto en {2, 3, 4, 5} días (parámetro) |
| Quiebre | Ventas perdidas |
| Meta de servicio | Pregunta A: servicio por ciclo (α) de 95%, la métrica que promete la fórmula, para comparar con la misma vara; se reporta también el fill rate. Pregunta B: fill rate de 85% a 99% |
| Costo de mantener | 25% anual del precio (parámetro; solo escala USD) |

Fuera de alcance: varias tiendas simultáneas, pronóstico de demanda, costo de quiebre
explícito, política (s, S). Quedan como próximos pasos.

## 3. Conceptos (resumen)

- **(R, S):** cada R días se pide lo necesario para volver a S. Lo que se decide es S.
- **Cobertura R + L:** S debe cubrir la demanda hasta la próxima revisión más el lead time.
- **Fórmula clásica:** S = μ·(R+L) + z·σ·√(R+L), con μ y σ diarios y z según el servicio por
  ciclo objetivo. Supone demanda normal e independiente y lead time fijo (se usa su media).
- **Servicio por ciclo (α):** % de ciclos de revisión (R días) sin ningún día con demanda no atendida. **Fill rate (β):** % de
  unidades demandadas atendidas.
- **Monte Carlo con bootstrap:** se simulan muchos años posibles; cada día simulado toma la
  demanda de un día real del mismo día de la semana, elegido al azar (conserva el patrón
  semanal sin suponer distribución).
- **Syntetos-Boylan:** clasifica la demanda con ADI (días promedio entre ventas) y CV² (de las
  cantidades cuando hay venta) en suave, errática, intermitente e irregular (*lumpy*).
  Cortes estándar: ADI = 1,32 y CV² = 0,49.
- **Demanda censurada:** un 0 en ventas puede ser falta de stock; no se puede distinguir.

La explicación completa, con ejemplos, va en `docs/conceptos.md`.

## 4. Arquitectura

```
M5 ─► datos ─► demanda (diagnóstico) ─► politicas + simulador ─► backtest ─► analisis ─► reporte / app
```

| Módulo | Responsabilidad | Depende de |
|---|---|---|
| `scripts/descargar_m5.py` | Descarga los tres archivos a `data/raw/` (no versionado) | — |
| `src/inventario/datos.py` | Serie diaria por producto de una tienda, división calibración/prueba, precio por producto (último precio semanal conocido) | pandas |
| `src/inventario/demanda.py` | Estadísticos, clase Syntetos-Boylan, ajuste normal / Poisson / binomial negativa (mejor por AIC), marca de censura sospechosa | numpy, scipy |
| `src/inventario/simulador.py` | Simulación vectorizada (productos × réplicas) de (R, S) con ventas perdidas y lead time aleatorio; devuelve fill rate, servicio por ciclo e inventario promedio | numpy |
| `src/inventario/politicas.py` | S por fórmula; S por simulación (búsqueda binaria vectorizada del menor S entero que cumple una meta de α o de fill rate) | simulador |
| `src/inventario/backtest.py` | Reproduce la demanda real del período de prueba con un S dado (lead time aleatorio, varias réplicas solo sobre el lead time) | simulador |
| `src/inventario/analisis.py` | Tablas de la pregunta A por clase y categoría; curva de la pregunta B | todos los anteriores |
| `app/streamlit_app.py` | Explorar producto (demanda, clase, distribución, simulación con S ajustable) y curva B | analisis |
| `main.py` | Corre el análisis completo y guarda resultados en `outputs/` | analisis |

### Simulador: contrato

Entrada: matriz de demanda por día (réplicas × días × productos, o un muestreador), S por
producto, R, distribución de lead time, semilla. Salida por producto: fill rate, servicio por
ciclo, inventario promedio (unidades). No conoce M5.

Dinámica diaria (orden fijo y documentado): (1) llegan pedidos con fecha de hoy;
(2) si es día de revisión, al inicio del día se pide S − (inventario disponible + pedidos en
tránsito) y se sortea su lead time; (3) se atiende la demanda con el inventario disponible, lo
no atendido se pierde. Con este orden un pedido protege exactamente R + L días, la misma
convención que la fórmula clásica. El inventario inicial es S. Se descarta un período de calentamiento
de 4 semanas antes de medir.

### Búsqueda del S por simulación

El fill rate y el servicio por ciclo son no decrecientes en S, por eso se usa búsqueda binaria sobre S entero entre 0 y
un tope (p. ej. el S de la fórmula al 99,9% más un margen), para todos los productos a la vez.
Se usan números aleatorios comunes (misma semilla para cada S) para que la comparación entre
valores de S sea estable.

## 5. Resultados esperados

- **Pregunta A:** por clase de demanda y por categoría: α prometido (95%) vs α logrado en la
  prueba, para la fórmula (z = 1,645) y para el S calibrado por simulación con meta α = 95%;
  además el fill rate logrado y el inventario en USD de cada política.
- **Pregunta B:** para metas de 85% a 99%, inventario total en USD con S calibrado por
  simulación, y el fill rate efectivamente logrado en la prueba.
- `docs/resultados.md`: conclusiones en lenguaje de negocio, escritas con los números reales.

## 6. Validación y pruebas

Tests con datos sintéticos (no requieren M5):

1. Demanda Poisson, lead time fijo: servicio por ciclo simulado ≈ teórico (Poisson acumulada
   sobre R + L días), dentro de una tolerancia estadística.
2. Demanda normal de media alta: S por fórmula ≈ S por simulación.
3. Demanda siempre 0: fill rate 100% definido (sin división por cero), inventario sin pedidos.
4. Monotonía: más S nunca baja el fill rate; más lead time nunca lo sube (con igual S).
5. Reproducibilidad: misma semilla, mismos resultados.
6. Clasificación Syntetos-Boylan en series construidas para cada clase.
7. Datos: división calibración/prueba sin solapamiento; precios rellenados hacia adelante.

CI en GitHub Actions corre los tests.

## 7. Casos difíciles

- Producto sin ventas en calibración: se excluye y se informa la cantidad.
- Producto lanzado a mitad de la historia: se usa su historia desde la primera venta.
- Semanas sin precio: último precio conocido; si nunca tiene precio, se excluye del valor USD.
- Falla de descarga: mensaje con el archivo faltante y cómo obtenerlo.
- Demanda censurada: se marca (racha de ceros mucho más larga que lo esperable dada su tasa de
  venta) y se reporta su efecto, sin corregir los datos.

## 8. Entregables

Repositorio `CastilloFelipe/inventario-estocastico` con: código y tests, CI, `docs/conceptos.md`,
`docs/resultados.md`, app Streamlit, README con resultados y limitaciones, licencia MIT.
Los datos M5 no se versionan; se descargan con el script.
