# Conceptos: inventario con demanda incierta

Esta guía explica, desde cero, las ideas que usa el proyecto. Cada concepto parte por la
intuición, sigue con la fórmula (si la hay) y termina con una frase para explicarlo en una
entrevista. Todo se ilustra con el mismo ejemplo.

> **El detergente.** Una tienda vende un detergente. En promedio salen **4 unidades al
> día**, con una desviación estándar diaria de **3 unidades**: hay días de 0, días de 4 y
> días de 10. La tienda revisa el inventario **cada 7 días** y le pide al proveedor lo que
> falte. El pedido llega entre **2 y 5 días** después (3,5 en promedio). Si un cliente no
> encuentra detergente, se va: la venta se pierde.

## 1. Incertidumbre de la demanda

**Intuición.** Si supiéramos que mañana se venden exactamente 4 detergentes, bastaría con
tener 4. El problema es que no sabemos: puede ser 0 o 10. Todo el inventario "de más" que
se mantiene existe para cubrir esa incertidumbre. Con demanda perfectamente conocida, el
stock de seguridad sería cero.

**Fórmula.** Se resume la demanda diaria con su media μ (4) y su desviación estándar σ (3).
El coeficiente de variación σ/μ = 0,75 dice qué tan "ruidosa" es respecto de su tamaño.

**En una entrevista:** "El inventario de seguridad es el precio de no saber cuánto se va a
vender; si la demanda fuera conocida, no lo necesitaríamos."

## 2. Política de revisión periódica (R, S)

**Intuición.** Cada R días alguien mira cuánto detergente hay (en góndola más lo que ya viene
en camino) y pide lo necesario para "llenar hasta" un nivel S. Si hay 20 en tienda, 10 en
camino y S = 58, pide 28. La única decisión es S: muy bajo y hay quiebres; muy alto y se
inmoviliza dinero.

**Fórmula.** Pedido = S − (inventario disponible + pedidos en tránsito), cada R = 7 días.

**En una entrevista:** "Es la política típica de retail con reposición semanal: lo que se
decide es hasta dónde se llena cada vez."

## 3. Lead time y cobertura R + L

**Intuición.** El pedido de hoy no llega hoy: llega en L días. Y el siguiente pedido se
hará en R días y también tardará L en llegar. Entonces lo que pido hoy tiene que aguantar
desde ahora hasta que llegue el **próximo** pedido: R + L días. Para el detergente, 7 + 3,5
= 10,5 días.

**Fórmula.** Demanda esperada en la cobertura = μ · (R + L) = 4 · 10,5 = 42 unidades.

**En una entrevista:** "Con revisión periódica, el riesgo no dura solo el lead time sino la
revisión más el lead time, porque hasta la próxima revisión no puedo corregir."

## 4. Stock de seguridad y la fórmula clásica

**Intuición.** Si S fuera solo 42 (lo esperado), la mitad de los ciclos faltaría detergente.
Se agrega un colchón para los ciclos en que la demanda viene alta. El colchón crece con la
variabilidad (σ), con la raíz del horizonte (la variabilidad de varios días se compensa en
parte) y con lo exigente de la meta (z).

**Fórmula.**

S = μ·(R+L) + z·σ·√(R+L)

Con z = 1,645 (para 95%): 42 + 1,645 · 3 · √10,5 = 42 + 16,0 → **S = 58** (se redondea hacia
arriba). Los 16 son el stock de seguridad.

**Los supuestos escondidos.** La fórmula da por hecho dos cosas que no se ven a simple vista:

1. **Demanda normal:** la venta de 10,5 días tiene forma de campana. Con productos que venden
   pocas unidades y muchos días cero, esto es dudoso.
2. **Días independientes:** lo que se vende hoy no dice nada de lo que se venderá mañana.
   De ahí sale el √(R+L): la varianza de la suma de n días independientes es n·σ². Si los
   días buenos vienen en rachas o hay cambios lentos de nivel, ese supuesto subestima el riesgo.

También usa el lead time promedio, como si fuera fijo.

**En una entrevista:** "La fórmula es razonable, pero promete 95% solo si la demanda es
normal y cada día es independiente del anterior; en este proyecto medí cuál de los dos
supuestos pesa más."

## 5. Servicio por ciclo (α) vs fill rate (β)

**Intuición.** Son dos maneras de medir "buen servicio" y pueden dar números muy distintos.

- **α (servicio por ciclo):** de cada 100 semanas, ¿en cuántas **no faltó** detergente ningún
  día? Una semana en que faltó una sola unidad cuenta como falla completa.
- **β (fill rate):** de cada 100 detergentes que los clientes quisieron comprar, ¿cuántos
  encontraron? Faltar una unidad casi no lo mueve.

La fórmula clásica con z = 1,645 promete α = 95%, no fill rate. Por eso el proyecto compara
las políticas con α (la misma vara) y reporta el fill rate aparte. En general el fill rate
es mayor que α.

**Fórmula.** α = ciclos sin faltante / ciclos totales. β = unidades vendidas / unidades
demandadas. Para un grupo de productos, el fill rate ponderado suma unidades de todos.

**En una entrevista:** "α cuenta semanas con algún quiebre; el fill rate cuenta unidades
vendidas. Para el cliente importa más el fill rate; para comparar con la fórmula hay que
usar α."

## 6. Ventas perdidas vs pedidos pendientes (backorders)

**Intuición.** Si un cliente no encuentra detergente en el supermercado, compra otra marca o
vuelve otro día: esa venta **se pierde**. En otros negocios (repuestos, B2B) el cliente
espera y la unidad se entrega después: es un **backorder**. Con ventas perdidas, el
inventario nunca queda negativo, y la demanda no atendida no se acumula para el ciclo
siguiente. El proyecto usa ventas perdidas porque es lo que pasa en retail.

**Fórmula.** Ventas del día = min(inventario disponible, demanda); lo que falta se pierde.

**En una entrevista:** "En retail el quiebre es venta perdida, no pedido pendiente; eso
cambia cómo se simula y cómo se mide el servicio."

## 7. Demanda intermitente y clasificación Syntetos-Boylan

**Intuición.** No todos los productos venden igual. Un detergente popular vende casi todos
los días; un repuesto de aspiradora vende una vez cada dos semanas. Tratar ambos con la
misma fórmula es arriesgado. Syntetos y Boylan propusieron clasificar con dos números:

- **ADI:** cada cuántos días, en promedio, hay una venta. ADI = 1 es vender todos los días.
- **CV²:** qué tan variable es la cantidad cuando sí hay venta.

**Fórmula.** Cortes estándar ADI = 1,32 y CV² = 0,49:

| | CV² < 0,49 | CV² ≥ 0,49 |
|---|---|---|
| ADI < 1,32 | Suave | Errática |
| ADI ≥ 1,32 | Intermitente | Irregular (*lumpy*) |

En la tienda CA_1, el 72% de los productos es intermitente.

**En una entrevista:** "Antes de elegir un método miro el tipo de demanda: la mayoría de los
productos de una tienda no vende todos los días, y eso rompe el supuesto de normalidad."

## 8. Monte Carlo y bootstrap

**Intuición.** En vez de confiar en una fórmula, se "juega" el año muchas veces en el
computador. Para cada día simulado se sortea una demanda, se aplica la política (pedir,
recibir, vender) y se cuenta qué pasó. Repitiendo 200 años posibles se estima α o el fill
rate de un S dado, y se busca el S más chico que cumple la meta.

¿De dónde sale la demanda sorteada? Del **bootstrap**: en vez de suponer una distribución,
se toma un día real de la historia al azar. Para conservar el patrón semanal, un lunes
simulado se copia de un lunes real.

**Fórmula.** No hay fórmula cerrada: α estimado = proporción de ciclos sin faltante en las
réplicas simuladas.

**En una entrevista:** "Simulo muchos años posibles reutilizando días reales, así no necesito
suponer que la demanda es normal."

## 9. Bootstrap por bloques y autocorrelación

**Intuición.** El bootstrap diario sortea cada día por separado, así que **también** supone
días independientes, igual que la fórmula. Pero en la realidad los días buenos vienen
juntos: una promoción, una ola de calor, el día de pago. Si el detergente vendió 10 hoy, es
algo más probable que mañana venda más de 4. Eso es **autocorrelación**.

Cuando hay rachas, la venta de una semana completa varía más de lo que predicen los días
sueltos. El **bootstrap por bloques** lo reduce copiando tramos de 28 días consecutivos de
la historia (en vez de días sueltos), así las rachas reales quedan dentro de la simulación.

**Fórmula.** Con días independientes, Var(suma de n días) = n·σ². Una forma simple de medir
la dependencia es el cociente

Var(suma de 10 días) / (10 · Var diaria)

que vale 1 si los días son independientes. En la tienda CA_1 la mediana es 1,94. Para el
detergente, si su cociente fuera 1,94, la desviación de los 10,5 días pasaría de 9,7 a
9,7 · √1,94 ≈ 13,5 unidades, y el colchón al 95% de 16 a unas 22.

La **autocorrelación de orden 1** es la correlación entre la venta de un día y la del día
siguiente: 0 sin dependencia, cercana a 1 con mucha.

**En una entrevista:** "La falla de la fórmula se asociaba más a que los días vienen en
rachas (o en cambios lentos de nivel) que a la forma de la demanda; simulando con bloques de días reales consecutivos el
servicio subió de 0,905 a 0,934, más cerca de la meta, aunque con más inventario. Parte de
esas rachas podría venir de quiebres o de cambios de nivel, y eso lo declaro."

## 10. Calibración vs prueba

**Intuición.** Si se ajusta S mirando un año y se mide el resultado en ese mismo año, el
resultado sale bueno "por construcción". Para saber si la política funciona, hay que
probarla con datos que no vio: se calibra con toda la historia salvo el último año y se
prueba con el último año (364 días). Es lo mismo que pasaría en la vida real: se decide con
el pasado y se vive el futuro.

**Fórmula.** Calibración = días 1 a N − 364; prueba = últimos 364 días. Ningún dato de prueba
entra en el cálculo de S (ni siquiera el precio).

**En una entrevista:** "Separé calibración y prueba para medir el servicio con demanda que la
política nunca vio, como un backtest."

## 11. Costo de mantener inventario

**Intuición.** Un detergente en bodega es dinero inmovilizado, ocupa espacio, se puede dañar
o quedar obsoleto. Se resume como un porcentaje anual del valor: con 25%, mantener 1.000 USD
de inventario durante un año cuesta 250 USD.

**Fórmula.** Costo anual = inventario promedio (unidades) × precio × 25%. Si el detergente
cuesta 5 USD y se mantienen en promedio 30 unidades, son 150 USD de inventario y 37,5 USD al
año.

**En una entrevista:** "Traduzco el inventario a dinero para que la discusión de servicio sea
una discusión de costo."

## 12. Curva inventario-servicio

**Intuición.** Cada meta de servicio implica un S para cada producto y, por lo tanto, un
inventario total. Al graficar inventario (USD) contra servicio logrado aparece una curva que
se aplana: los primeros puntos de servicio son baratos y los últimos son muy caros, porque
hay que cubrir días cada vez más raros. Esta curva es la herramienta para que la gerencia
elija el nivel de servicio sabiendo cuánto cuesta.

**Fórmula.** Para cada meta m: inventario(m) = Σ productos inventario promedio × precio;
servicio(m) = fill rate logrado en la prueba.

**En una entrevista:** "No le digo a la gerencia qué servicio elegir; le muestro cuánto
inventario cuesta cada punto adicional."

## 13. Demanda censurada

**Intuición.** Las ventas registradas no son la demanda: si no había detergente en la
góndola, el sistema anota 0 ventas aunque hubiera clientes buscándolo. Ese 0 está
"censurado". No se puede distinguir de un día realmente sin clientes. Una pista es una
racha de ceros demasiado larga: si el detergente vende casi todos los días, diez días
seguidos sin ventas probablemente fueron un quiebre.

**Fórmula.** Con p₀ = proporción de días sin venta, la probabilidad de una racha de k ceros
seguidos, si fueran al azar, es del orden de p₀ᵏ. Si (días de historia) × p₀ᵏ < 0,01 para la
racha más larga observada, el producto se marca como sospechoso (solo se evalúa en
productos que venden más de la mitad de los días). No se corrigen los datos;
se informa.

**En una entrevista:** "Las ventas son una cota inferior de la demanda; marqué los productos
con quiebres probables en la historia y lo declaro como limitación."
