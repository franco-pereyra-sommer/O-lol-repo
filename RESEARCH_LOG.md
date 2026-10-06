# Registro de investigación

Objetivo: encontrar condiciones de entrada que, después de costos, tengan
retorno esperado positivo **fuera de muestra** y de forma **consistente** en
distintos períodos del mercado. Encontrar "algo que funcionó en el pasado" no
alcanza: con miles de pruebas, siempre aparece algo por azar.

Este archivo tiene cuatro partes (empezá por la 0 si no seguiste el trabajo):
0. Estado actual y guía de lectura: qué se hizo, qué resultó y qué sigue, sin jerga.
1. Glosario: qué significa cada valor de los resultados y cómo se calcula.
2. Reglas de decisión, fijadas ANTES de ver resultados.
3. Bitácora de experimentos: qué se probó, qué dio, qué se decidió y qué sigue.

---

## 0. Estado actual y guía de lectura

*Esta sección es el punto de entrada para quien no siguió el trabajo. Se actualiza al cerrar cada experimento. Última actualización: 2026-10-06, tras cerrar EXP-012b. El detalle de cada experimento está en la sección 3 (bitácora); acá sólo se resume y se señala dónde mirar.*

### 0.1 En pocas palabras
- **Qué se busca:** reglas de entrada (por ejemplo "RSI cruza tal valor y la media corta supera a la larga") que den ganancia **después de costos**, en datos que la regla **no vio** al elegirse, y de forma repetible en distintos períodos del mercado.
- **Dónde estamos:** con BTCUSDT 1h (2017-2026) **ninguna variante probada gana dinero fuera de muestra** (EXP-001, 002, 005). No hay "candidato" y el tramo final de datos reservado (holdout) **sigue sin abrirse**.
- **Qué se hizo además:** una buena parte del trabajo fue **comprobar que las mediciones son honestas** (que no se "espíe" el futuro, que no se confunda suerte con señal, que los números de confianza no estén inflados). Eso es lo que cubren EXP-003 a EXP-007 (todas terminadas); EXP-008 a EXP-012b usaron esa infraestructura para probar cinco ideas nuevas (más información de contexto; búsqueda estructurada; otra geometría de salida; otra escala temporal; objetivos mayores), todas sin mejora. Esa infraestructura es la que permitirá creer en un resultado positivo si algún día aparece.

### 0.2 Experimentos: estado y conclusión (una línea cada uno)
| Experimento | Qué fue | Estado | Conclusión |
|---|---|---|---|
| EXP-000 | Punto de partida con datos de Yahoo (2 años) | Cerrado | Con 2 años no se distingue señal de régimen de mercado; pasar a historia larga. |
| EXP-001 | Línea base con 9 años de Binance, walk-forward de 10 folds, LONG y SHORT | Cerrado | LONG −0,14 % y SHORT −0,61 % por operación fuera de muestra: sin candidato. |
| EXP-002 | Re-buscar cada mes (TRAIN de 3,5 meses, 90 folds) | Cerrado | No mejora (LONG −0,19 %, SHORT −0,15 %); la idea "ventanas cortas" sola no ayuda. |
| EXP-003 | ¿Hay filtración de información entre TRAIN y VALIDATION? (purga/embargo) | Cerrado | **No hay filtración.** El problema era otro: un número de confianza inflado. Se corrigió el estadístico. |
| EXP-004 | Cómo corregir por probar miles de condiciones (Reality Check y PBO) | Cerrado | Se implementaron y validaron con simulaciones; se midió que "la mejor condición" se degrada fuera de muestra. |
| EXP-005 | Reality Check sobre las 4 variantes ya corridas | Cerrado | p ≈ 0,9–1,0: ninguna es distinguible de cero ni de la línea base. |
| EXP-006 | Segunda prueba de look-ahead (que ninguna señal use datos futuros) | Cerrado | 0 fugas en 5.000 condiciones. Un look-ahead leve en el costo del escenario `conservative` fue corregido. |
| EXP-007 | Operaciones superpuestas: qué estadístico es válido y qué cooldown conviene | Cerrado | El t entre operaciones es inútil (bajo ruido "pasa" t ≥ 3 el 24 % de las veces); valen el t entre folds y el HAC. Cooldown estándar: `until_exit`. |
| EXP-008 | Features de régimen (tendencia 4h, tendencia diaria, volatilidad relativa) vs baseline, misma metodología | Cerrado | **No mejoran la generalización fuera de muestra** (t pareado +1,29 LONG, −1,14 SHORT; Reality Check p ≥ 0,79). Sólo inflan lo "mejor in-sample" (PBO). Resultado negativo registrado. |
| EXP-009 | Búsqueda estructurada "contexto + disparador" vs búsqueda aleatoria (mismo presupuesto de 7.500 condiciones por fold) | Cerrado | **No es mejor**: t pareado +0,93 (LONG) y +0,30 (SHORT) contra la aleatoria con las mismas features; Reality Check p ≥ 0,87. Opera entre 9 y 16 veces menos, pero el lift por fold no cambia; ningún procedimiento es rentable. |
| EXP-010 | Salidas TP/SL proporcionales al ATR (4 variantes pre-fijadas) vs TP 5 % / SL 3 %, mismas entradas | Cerrado | **Caso A (negativo)**: ninguna variante mejora al baseline (R1 = NO en las 8; Reality Check p ≥ 0,81). Con cualquier geometría el TP se alcanza con la frecuencia de una caminata sin ventaja y el neto ≈ −costo: el problema no es la salida. H = 100 no resulta corto (NONE ≤ 15 %). |
| EXP-011 | Escala temporal: BTCUSDT 4h vs 1h con la misma duración de operación (H = 25 barras de 4h = 100 h), mismo TP/SL, misma búsqueda | Cerrado | **Escenario A (4h no mejora)**: costos por operación, operaciones por condición y ventana (≈ 11,3) y retorno bruto (≈ 0) son iguales en 1h y 4h; la diferencia 4h − 1h no es significativa (t pareado −0,6 y −0,3; Reality Check p ≥ 0,86). Con exits en % y horizonte en horas, cambiar la escala de las barras no cambia el cociente costo/movimiento capturado. |
| EXP-012 | Escala del objetivo: TP/SL y horizonte ×2, ×3 y ×4 (TRAIN/VAL escalados) | Cerrado (**no concluyente**) | Escenario formal A (sin evidencia de predictibilidad: lift bruto +0,26 %/fold con t = 1,26 en V1 LONG, nada significativo), pero **V2 y V3 casi no seleccionaron condiciones** (1 y 0 folds con operaciones) porque el mínimo efectivo de operaciones en TRAIN subió a 50/75/100 en vez de 30 (error de Claude: `MIN_CASES_FRACTION` escala con el TRAIN). A escalas grandes la línea base sin condición ya gana en LONG por la deriva de BTC: sólo el lift es interpretable. |
| EXP-012b | Repetición de EXP-012 con el mínimo efectivo de 30 operaciones (corrige la desviación) | Cerrado | **Escenario A informativo**: con selección suficiente (41/29, 25/17 y 14/10 folds con operaciones), el lift bruto por fold va de −0,22 % a +0,25 % con t entre −0,84 y +1,44 (umbrales 3,11–3,35); Reality Check de predictibilidad p = 0,97. El bruto/neto positivo en LONG a escalas grandes es la deriva de BTC (la línea base sin condición lo reproduce); sólo el lift es interpretable. |
| EXP-013 | Rama a2: regla diaria "comprado o en efectivo" (3 reglas fijas: tendencia 20 y 100 días, calma) contra exposición constante igualada | **Preregistrado** (en curso) | Diseño y criterio de candidato adaptado fijados antes de correr; K 30 → 33. |

### 0.3 Respuestas a las preguntas de revisión

**1. EXP-003 (purga y embargo).** Detalle en la entrada EXP-003.
- *Qué se entendió:* **purga** = sacar del TRAIN toda observación cuyo resultado depende de precios del período evaluado; **embargo** = además dejar un margen de TRAIN **posterior** al período evaluado. Éste sólo existe si se entrena con datos posteriores al test (K-fold, CPCV); en un walk-forward que sólo avanza hacia adelante no corresponde.
- *Sobre `n_dropped_horizon`:* resultó que **sí resuelve la filtración entre segmentos**: descartar toda señal cuyo horizonte se sale del segmento es exactamente una purga. Lo que **no** resuelve (ni debe) es el **solapamiento entre operaciones**, que es otro problema: no es filtración sino dependencia estadística (varias operaciones comparten las mismas velas) y hace que el número "t" parezca mejor de lo que es.
- *Qué cambió en el código:* `trade_intervals` y `fits_in_segment` (hacen explícita la regla de purga; el comportamiento no cambió) y `fold_level_t` (nuevo estadístico entre folds), en `entry_detector.py` y `walk_forward.py`.
- *Tests agregados:* la ventana de cada operación cae dentro de su segmento (verificado que el test falla si se rompe la purga); cambiar todos los precios posteriores al TRAIN no altera ninguna métrica de TRAIN; simulación de que el solapamiento infla el t; test del t entre folds.
- *¿Cambió resultados?* **No cambió ningún resultado de EXP-001/002** (el walk-forward estaba bien). Sí se **enmendó el criterio de candidato** (regla 4): pasó de "t ≥ 3 entre todas las entradas" a "t ≥ 3 **entre folds**", que es más exigente.

**2. EXP-004 (Reality Check y PBO).** Detalle en la entrada EXP-004.
- *¿Análisis serio o versión simplificada?* Análisis completo (qué es una hipótesis, universo, benchmark, estadístico, bootstrap respetando el tiempo, costos, relación con el walk-forward, límites) **y** una implementación real, no simplificada, de las dos herramientas, validada con simulaciones: con ruido puro el Reality Check rechaza ≈ 5 % (el "mejor de 200 reglas" parece significativo el 100 % de las veces si no se corrige) y detecta una ventaja real; la PBO da ≈ 0,5 con ruido y ≈ 0 con ventaja estable.
- *Universo de hipótesis:* tres niveles (condición; procedimiento completo; programa de investigación = todas las variantes probadas contra los mismos datos). Se corrige por el tercero, porque dentro de un fold la selección ya se hace en TRAIN y se mide en VALIDATION.
- *¿Faltaba infraestructura?* Sí, para aplicar el Reality Check a datos reales: faltaba la serie de resultados fuera de muestra por procedimiento. **Se construyó y se aplicó en EXP-005.** Siguen sin implementar: SPA (variante del Reality Check), Deflated Sharpe Ratio, CPCV, PBO sobre el lift. Están en el Plan (ítem 11).
- *Qué recomendó:* el listado de 8 evidencias necesarias para poder decir "probablemente no es azar" (final de EXP-004), una cuenta K de variantes (regla 7) y volver recién después a ampliar la búsqueda.

**3. Estado del roadmap.**
- EXP-001/002 están **cerrados y reproducidos** (se repitieron en EXP-005 y dieron los mismos números al dígito).
- Terminados: EXP-000 a EXP-012b (ver 0.2). En curso: ninguno.
- **Pendiente de la tabla original** (sección 4, Plan): volumen y hora del día; periodicidad de re-búsqueda; modelos de costo dinámicos; comparación con Genetic Programming; CPCV, PBO sobre el lift y Deflated Sharpe. Nada de esto se descartó; cada uno se evalúa como experimento separado.
- La numeración vieja (EXP-003 = régimen, EXP-004 = contexto+disparador) **ya fue reemplazada** en la sección 4. Las features de régimen (la "EXP-003 original") se probaron en EXP-008 y la estructura "contexto + disparador" (la "EXP-004 original") en EXP-009: ninguna mejoró.

**4. Próximo experimento (propuesta, la decisión es tuya).**
1. ~~Cerrar EXP-007~~ (hecho: cooldown `until_exit`; deciden el t entre folds y el HAC, nunca el t entre operaciones).
2. ~~Features de régimen~~ (hecho en EXP-008: no mejoran la generalización; quedan implementadas y apagadas por defecto).
3. ~~Contexto + disparador~~ (hecho en EXP-009: no mejora; el generador queda implementado y apagado por defecto).
4. ~~TP/SL proporcionales al ATR~~ (hecho en EXP-010: no mejora; el modo `atr` queda implementado y apagado por defecto).
5. ~~Temporalidad más lenta (4h con la misma duración de operación)~~ (hecho en EXP-011: no mejora; la agregación estricta 1h→4h queda implementada).
6. ~~Escala del objetivo (TP/SL/H ×2, ×3, ×4)~~ (hecho en EXP-012, que fue no concluyente por un error de Claude en el mínimo de operaciones, y repetido en EXP-012b: sin lift detectable).
7. **Lo que sigue lo decidís vos.** Hay 8 experimentos de búsqueda seguidos sin avance (EXP-001, 002, 008, 009, 010, 011, 012, 012b; CLAUDE.md pide revisar el rumbo a los 10). EXP-011 mostró por qué pasar a 4h no cambió nada: con TP/SL en % y horizonte en horas, la operación dura lo mismo (≈ 36–41 h), se repite el mismo número de veces por mes y paga el mismo costo; y el retorno bruto es ≈ 0 en todos los diseños. Lo que cambiaría el cociente costo/movimiento es la escala del *objetivo*. Opciones (cada una suma variantes a K): (a) objetivos más grandes frente al costo (TP/SL y horizonte escalados, con o sin temporalidad más lenta), sabiendo que con bruto ≈ 0 se espera "perder menos" y no ganar; (b) otros activos/mercados (otra estructura de costos, más historia independiente); (c) revisar el objetivo del proyecto, porque en seis experimentos las entradas seleccionadas no superan a una caminata sin ventaja; (d) más validez estadística (CPCV, PBO sobre el lift).
- **Estado tras EXP-012b (propuesta; decide el usuario):** ocho experimentos de búsqueda de entradas técnicas aleatorias sobre BTCUSDT (más información, más estructura, otra salida, otra temporalidad, otra escala del objetivo) no muestran lift bruto detectable. Estamos a dos del umbral de CLAUDE.md (10) para revisar el rumbo; conviene hacerlo ahora. Opciones: (a) cambiar el objeto de estudio y no la búsqueda: otros activos/mercados con historia independiente, o reglas que no sean de entrada (tamaño/gestión, filtros de régimen como "no operar"); (b) una prueba de "techo de información" sin selección (¿existe predictibilidad de la dirección con modelos simples sobre las mismas features, medida por lift OOS?); (c) más validez (CPCV, PBO sobre el lift); (d) dar por cerrada la línea de entradas técnicas simples en BTC. Nada se ejecuta sin autorización.
- **Decisión del usuario (2026-10-06): se elige la opción (a), cambiar el objeto de estudio.** Todavía **no se definió cuál de las dos ramas** (otros activos/mercados, o reglas que no son de entrada como filtros "no operar" o tamaño/gestión) ni el diseño; eso se decide al arrancar la conversación siguiente, y cualquier descarga de datos de otros activos o costos distintos requiere autorización explícita. Contexto para retomar: `HANDOFF.md`.
- **Decisión del usuario (2026-10-06, conversación siguiente): rama a2** (reglas que no son de entrada), frente a a1 (el mismo método en ETH, XRP y BNB; K 30 → 36, ≈ 3,9 M hipótesis, descarga de datos). Se diseñó como **EXP-013**: tres reglas fijas de "comprado o en efectivo" revisadas una vez por día, comparadas contra mantener siempre la misma exposición promedio (así la suba de BTC no cuenta como mérito). El usuario autorizó el criterio de candidato adaptado (incluido el mínimo de 30 entradas) y **reiniciar en 0 el contador de experimentos seguidos sin avance** (los 8 de la línea de entradas quedan registrados). Detalle y reglas en la entrada EXP-013.
- *Lección sobre horizontes largos:* en un activo con tendencia, el retorno bruto o neto absoluto de LONG crece con el horizonte aun sin ninguna señal (la línea base sin condición lo reproduce); sólo el lift contra la línea base de la misma ventana y geometría es interpretable. Y: el mínimo efectivo de operaciones es `max(30, 1 % de las barras del TRAIN)`; al cambiar la longitud del TRAIN hay que decidirlo explícitamente (EXP-012/012b).
- *Decisiones tomadas por Claude que conviene que conozcas y puedas revertir:* (a) se enmendó el criterio de candidato a "t entre folds ≥ 3" (EXP-003); (b) se fijó en 1 % el ATR supuesto en las primeras velas del modelo de slippage (EXP-006); (c) se agregó la regla 7 (Bonferroni con la cuenta K).

### 0.4 Mini-glosario sin jerga (el glosario técnico está en la sección 1)
- **Fuera de muestra (OOS):** datos que la regla no usó para elegirse. Es lo único que cuenta.
- **Walk-forward:** probar el procedimiento repetidas veces: elegir con un tramo del pasado y medir en el tramo siguiente, avanzando en el tiempo.
- **Look-ahead:** que una regla use, sin querer, información del futuro. Hace que todo parezca mejor de lo real.
- **Purga / embargo:** descartar datos cuya información se solapa con el tramo que se evalúa, para que no se contaminen.
- **t entre folds:** número que dice cuántos errores estándar está el resultado lejos de cero, calculado entre períodos disjuntos (honesto); el t entre operaciones está inflado porque las operaciones se solapan.
- **Reality Check / PBO:** herramientas contra la "suerte del mejor entre muchos": la primera da una probabilidad de que el mejor sea azar; la segunda mide cuánto se degrada lo que se eligió como mejor.
- **Holdout:** último tramo de datos guardado bajo llave; se abre una sola vez, para un solo candidato.
- **K:** cantidad de variantes del procedimiento probadas contra los mismos datos; cuantas más, más exigente hay que ser.

### 0.5 Dónde está cada cosa
- Bitácora detallada: sección 3 de este archivo. Resultados en `results/` (no se versiona).
- Código: `trading_research/` (núcleo), `run_research.py` (búsqueda y walk-forward), `run_reality_check.py`, `run_pbo.py`, `run_lookahead.py`, `run_overlap_study.py`. Tests: `pixi run pytest -q`.
- Datos: `D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv` (fuera del repo).

### 0.6 Base metodológica vigente (fijada tras EXP-007, 2026-10-04)
Todo experimento nuevo se evalúa con estas reglas; cambiarlas requiere registrar el motivo.
- **Cooldown estándar: `until_exit`.** Con `fixed` y cooldown menor que el horizonte, las operaciones de una condición se solapan: eso es un problema de **dependencia estadística** (el t sale inflado), **no de filtración de información (leakage)**.
- **`n_dropped_horizon` es el mecanismo de purga entre segmentos**: descarta toda señal cuyo horizonte se sale del segmento, de modo que ningún resultado de TRAIN usa precios de VALIDATION. Los tests verifican esa propiedad (`test_trade_label_window_stays_inside_segment`, `test_train_results_do_not_depend_on_future_prices`).
- **El t entre operaciones es sólo descriptivo; nunca decide.** Decide el **t entre folds** junto con el **t HAC con 3H rezagos (`oos_hac_t_3H`)** (regla 4).
- Corrección por varias variantes: **regla 7 y definición de K** (sección 2, "Aclaración de la regla 7 y definición de K"). Una sola corrección por familia (Reality Check *o* Bonferroni, no ambas).
- **El holdout sigue cerrado.** Contador acumulado de hipótesis (condiciones evaluadas): 13.831.500 al cierre de EXP-012b. K (variantes en el Reality Check) = 30.
- Si se cambia la longitud de TRAIN, recordar que el mínimo efectivo de operaciones es `max(30, 1 % de las barras del TRAIN)` (lección de EXP-012). Toda feature nueva: test de causalidad por truncación/perturbación del futuro y `run_lookahead.py` (EXP-006).

---

## 1. Glosario

Notación: `P` = precio de entrada (Open de la vela siguiente a la señal),
`X` = precio de salida, `N` = cantidad de entradas, `R_i` = retorno de la
operación i. Todo se expresa como fracción (0.01 = 1 %).

### Cómo se genera cada operación

| Término | Significado |
|---|---|
| Vela de confirmación `t` | La condición es verdadera al cierre de la vela t. Sólo usa información hasta t. |
| Entrada | En `Open[t+1]`. |
| TP / SL | Take profit / stop loss, en % sobre `P`. LONG: TP = P(1+tp), SL = P(1−sl). SHORT al revés. |
| Horizonte | Cantidad máxima de velas que se mantiene la operación. |
| `TP_FIRST` | Se tocó el TP antes que el SL. |
| `SL_FIRST` | Se tocó el SL antes que el TP. |
| `NONE` | No se tocó ninguno en el horizonte: se cierra al Close de la última vela. |
| `AMBIGUOUS` | TP y SL tocados en la misma vela. Con datos OHLC no se sabe cuál fue primero; para el retorno se asume SL (conservador). |
| Cooldown `fixed` | Dos entradas de la misma condición deben estar separadas por al menos N velas. Las operaciones pueden superponerse. |
| Cooldown `until_exit` | No se vuelve a entrar con la misma condición hasta que la operación anterior cerró. Nunca hay superposición. |

### Retornos

| Columna | Cálculo |
|---|---|
| `gross_return` (bruto) | LONG: `X/P − 1`. SHORT: `1 − X/P`. |
| `net_return` (neto) | El bruto descontando costos según el escenario principal (`COST_SCENARIO`, por defecto `typical`). Entrada de mercado: comisión taker + medio spread + slippage. Salida por TP con orden límite: comisión maker, sin spread ni slippage. Salida por SL o por tiempo: taker + medio spread + slippage. En `typical` son unos 0,22–0,26 % por operación completa (casi todo es la comisión de Binance, 0,10 % por lado). |
| `mean_net_return_optimistic / _typical / _conservative` | El mismo retorno neto medio bajo cada escenario de costos. Si algo sólo es positivo en `optimistic`, no es robusto. Spread y slippage de los escenarios son **estimaciones**, no datos observados. |
| `mean_gross_return`, `mean_net_return` | `(1/N) Σ R_i`. Es el **retorno esperado** por operación (`expected_return` y `net_expected_return` son el mismo valor con otro nombre). |
| `median_*_return` | Retorno de la operación del medio al ordenarlas. Si es muy distinto de la media, unas pocas operaciones extremas mueven el promedio. |
| `std_net_return` | Desvío estándar de los `R_i` netos. |
| `se_mean_net_return` | Error estándar de la media: `std / √N`. Cuánto podría variar la media sólo por azar. |
| `t_mean_net_return` | `media / se`. Cuántos "errores estándar" está la media lejos de 0. Regla práctica: \|t\| < 2 → no se distingue de 0. **Advertencia:** si las operaciones se superponen (cooldown `fixed` < horizonte) el t está inflado. Y con miles de condiciones probadas, un t de 2–3 aparece por azar varias veces. |
| `mean_net_return_excl_ambiguous` | Igual que la media neta pero sin los AMBIGUOUS, para ver cuánto pesa la suposición conservadora. |
| `win_rate_net` | Fracción de operaciones con retorno neto > 0. |
| `net_return_q0.1 … q0.9` | Cuantiles del retorno neto: q0.1 = el 10 % de las operaciones dio menos que esto. |
| `mean_holding_bars` | Velas que duró en promedio cada operación. |

### Probabilidades

| Columna | Cálculo |
|---|---|
| `TP_FIRST_count`, … | Cantidad de operaciones con cada resultado. |
| `P_TP_FIRST`, `P_SL_FIRST`, `P_NONE`, `P_AMBIGUOUS` | `count / N`. Suman 1. |
| `P_TP_FIRST_ci95_low / high` | Intervalo de confianza de Wilson al 95 % para P(TP): el rango donde razonablemente está la probabilidad real. Con pocos casos es ancho. Fórmula: centro `(p + z²/2N)/(1 + z²/N)`, semiancho `z·√(p(1−p)/N + z²/4N²)/(1 + z²/N)`, con z = 1,96. |
| `n_entries` | N, entradas que quedaron después del cooldown. |
| `fraction_of_dataset` | `N / velas del segmento`. |
| `n_raw_signals` | Velas en que la condición fue verdadera, antes del cooldown. |
| `n_dropped_cooldown` | Señales descartadas por el cooldown. |
| `n_dropped_horizon` | Señales descartadas porque su horizonte se salía del segmento (para no usar precios del segmento siguiente). |

### Excursiones (camino del precio después de entrar)

| Columna | Cálculo |
|---|---|
| `MFE` (máxima excursión favorable) | LONG: `max(High)/P − 1` en todo el horizonte. Lo máximo que llegó a ir a favor. |
| `MAE` (máxima excursión adversa) | LONG: `min(Low)/P − 1`. Lo máximo que llegó a ir en contra (es negativo). |
| `mean_MFE`, `median_MFE`, `MFE_q…` | Media, mediana y cuantiles del MFE entre las operaciones. Ídem MAE. |
| `P_MFE_ge_0.02` | Fracción de operaciones cuyo MFE fue ≥ 2 %. |
| `P_MAE_le_-0.02` | Fracción de operaciones que en algún momento fueron −2 % o peor. |
| `P_reach_0.02_in_10` | Fracción que llegó a +2 % a favor dentro de 10 velas. |
| `P_ret_ge_0_at_10` | Fracción con retorno ≥ 0 al cierre de la vela 10. |
| `P_down_0.01_then_up_0.03` | Fracción que primero fue −1 % y después +3 % (desde el punto de vista de la posición). |

### Comparación con la línea base

| Columna | Cálculo |
|---|---|
| Línea base | Entrar en **todas** las velas del mismo segmento. Representa "no saber nada". |
| `lift_P_TP_FIRST` | `P_TP` de la condición − `P_TP` de la línea base. |
| `lift_mean_net_return` | Retorno neto medio de la condición − el de la línea base. |
| Interpretación | Lift > 0 = la condición agrega información. Pero si la línea base es muy negativa, puede tener lift > 0 y seguir perdiendo plata. |

### Filtros

| Columna | Significado |
|---|---|
| `passed` | La condición pasó los filtros en ese segmento. |
| `reject_reasons` | Por qué no pasó, p. ej. `n<145`, `P_TP<0.15`, `lift_mean_net_return<=0`. |
| Mínimo de casos | `max(MIN_CASES_ABSOLUTE, MIN_CASES_FRACTION × velas del segmento)`. Es un filtro de frecuencia, no de significancia. |
| `depth` | Profundidad del árbol de la condición (1 = simple). |
| `kind` | `STATE` (puede ser verdadera muchas velas seguidas) o `EVENT` (puntual, como un cruce). |

### Walk-forward (`wf_summary.csv`)

| Columna | Cálculo |
|---|---|
| `fold` | Número de ventana. Cada fold busca en su TRAIN y mide en su VALIDATION (el período siguiente, fuera de muestra = OOS). |
| `val_price_change` | Cuánto subió o bajó el precio en ese VALIDATION (para saber el régimen del mercado). |
| `selected_in_train` | Condiciones que pasaron los filtros en el TRAIN del fold. |
| `passed_val` | De ésas, cuántas pasan también en VALIDATION. |
| `oos_entries` | Total de operaciones de las seleccionadas en VALIDATION. |
| `base_val_mean_net` | Línea base del VALIDATION. |
| `oos_pooled_mean_net` | Retorno neto medio de **todas** las operaciones OOS de las seleccionadas juntas: `Σ(N_c × media_c) / Σ N_c`. Es lo que habría ganado alguien que operara todo lo que el TRAIN eligió. |
| `oos_pooled_lift_net` | `oos_pooled_mean_net − base_val_mean_net`. |
| `oos_pooled_mean_net_<escenario>` | El mismo retorno OOS agrupado bajo cada escenario de costos. |
| `oos_frac_cond_net_gt0` | Fracción de condiciones seleccionadas con media neta > 0 en OOS. |
| `oos_frac_cond_beat_base` | Fracción que supera a la línea base en OOS. |
| `folds_oos_net_gt0` | En cuántos folds `oos_pooled_mean_net` > 0. |
| `folds_oos_beat_base` | En cuántos folds `oos_pooled_lift_net` > 0. |
| Holdout | Último tramo de los datos, que ningún fold usa. Se evalúa una sola vez por candidato. |

---

## 2. Reglas de decisión (fijadas antes de ver resultados)

1. **Las decisiones se toman sólo con métricas walk-forward fuera de muestra.**
   No se mira el gráfico del precio ni los datos crudos para elegir qué probar.
2. **El holdout final queda cerrado.** Sólo se abre para un candidato que
   cumpla los criterios del punto 4, una vez por candidato, y se registra
   aunque dé mal.
3. **Se lleva la cuenta de todas las hipótesis probadas** (condiciones ×
   combinaciones × experimentos). Cuantas más se prueben, más exigente hay
   que ser con lo que aparece.
4. **Criterio para llamar "candidato" a algo** (a nivel procedimiento, en walk-forward con ≥ 5 folds):
   - retorno neto OOS agrupado > 0 en al menos 4 de 5 folds;
   - supera a la línea base en al menos 4 de 5 folds;
   - retorno neto OOS agrupado de todos los folds > 0 con **t entre folds ≥ 3** (enmendado en EXP-003; antes era t entre entradas, inflado por el solapamiento), usando cooldown `until_exit`;
   - lo anterior con costos `typical`, y retorno OOS agrupado > 0 también con `conservative`;
   - al menos 100 operaciones OOS en total.
   - (agregado en EXP-007) el t HAC con 3H rezagos sobre la serie OOS por vela (`oos_hac_t_3H`) se informa siempre; si es < 2 mientras el t entre folds es ≥ 3, el candidato se considera no confirmado. El t entre entradas es sólo descriptivo.
5. **Una sola variable por experimento** cuando sea posible, para saber qué causó el cambio.
6. **Un resultado negativo también se registra.** Descartar ideas es parte del avance.
7. **Cuenta K de variantes** (agregada en EXP-004): toda variante de procedimiento (lado, TP/SL/H, ventana, filtro) evaluada contra la misma historia OOS suma a K. Mientras no exista el Reality Check sobre series OOS, el umbral de t entre folds se ajusta por Bonferroni (p ajustado = K × p ≤ 0,05). K actual = 4 (EXP-001 y EXP-002, LONG y SHORT).


### Aclaración de la regla 7 y definición de K (agregada antes de EXP-008, 2026-10-04)

**Qué corrige la regla 7.** Un problema concreto: el investigador (yo) prueba varias *variantes completas* del procedimiento contra la misma historia fuera de muestra y termina reportando la que mejor se ve. Aunque cada variante, por sí sola, esté medida sin filtración, la probabilidad de que *alguna* de K variantes parezca buena por azar crece con K (hasta ≈ K × p). La regla controla esa probabilidad ("al menos un falso descubrimiento" entre las K). H0 de cada variante: su retorno esperado neto fuera de muestra es ≤ 0 (o ≤ el de la línea base, en la versión "lift").

**Unidad de múltiples testing que se cuenta: la variante de procedimiento.** Una variante es una configuración completa y fija de la búsqueda — conjunto de features del generador, lado (LONG y SHORT cuentan por separado), TP/SL/horizonte, filtros, diseño de folds/ventanas, escenario de costos de decisión — cuyo resultado OOS se calculó sobre la historia OOS compartida y se miró. No son variantes: cambiar de escenario de costos para reportar sensibilidad (`conservative`, `optimistic`: la decisión es con `typical`); repetir la misma variante con otra semilla de condiciones *si se reporta el agregado* (elegir la mejor semilla sí contaría).

**Por qué K es la cuenta correcta (y no otra).** El sesgo de selección depende del número de resultados OOS entre los que se puede elegir. Por eso:
| Concepto | Valor actual | ¿Entra en K? | Motivo |
|---|---|---|---|
| Condiciones individuales generadas | 7.500 por fold y lado | **No** | Se eligen con TRAIN y se miden en VALIDATION sin seleccionar por VALIDATION: la selección ya quedó dentro del procedimiento (EXP-003/004). |
| Variantes / configuraciones (procedimientos completos) | 30 al cierre de EXP-012b (EXP-001, EXP-002, EXP-008-régimen, EXP-009-estructurada, las cuatro variantes ATR de EXP-010, EXP-011-4h, las tres variantes escaladas de EXP-012 y las tres de EXP-012b, cada una LONG/SHORT; eran 4 antes de EXP-008, 6 antes de EXP-009, 8 antes de EXP-010, 16 antes de EXP-011, 18 antes de EXP-012 y 24 antes de EXP-012b) | **Sí: K** | Son las que se comparan contra el mismo OOS y entre las que se podría reportar "la mejor". |
| Experimentos | 14 (EXP-000 a EXP-012b) | **No** | Unidad de organización: un experimento puede tener 0, 1 o varias variantes, y variantes de experimentos distintos sobre los mismos datos compiten igual. |
| Hipótesis acumuladas | 13.831.500 (al cierre de EXP-012b) | **No** | Contador de transparencia sobre cuánto se exploró; no entra en ningún test porque esa exploración está absorbida en TRAIN. Usarlo en Bonferroni sobreestimaría la corrección en unos seis órdenes de magnitud. |
| Universo conjunto del Reality Check | las K variantes con series OOS alineables | **Define K** | K = tamaño de ese universo. |
Pertenece al universo de una variante si: (i) mismo activo, datos y timeframe; (ii) su serie OOS puede alinearse con las demás en la historia común (se usa la intersección); (iii) el investigador podría haber reportado esa variante como "el resultado". Si alguna de las tres no está clara, **no se decide arbitrariamente**: se documenta la duda en la entrada del experimento y se informa el Reality Check con y sin esa variante. Cada variante de una ablación (quitar una feature) cuenta si se mira su resultado OOS.

**Relación con White Reality Check y PBO.** El Reality Check contrasta exactamente la misma familia de K variantes teniendo en cuenta que están correlacionadas, por lo que su p-valor es menor o igual que el de Bonferroni: Bonferroni es una cota superior conservadora. La PBO responde otra pregunta (cuánto se degrada lo que se elige como mejor entre condiciones) y no entra en la cuenta de K.

**Riesgo de corregir dos veces.** Existe si se aplica Bonferroni *y* el Reality Check sobre el mismo K. Regla: **una sola corrección por familia**. Cuando se puede calcular el Reality Check sobre las K variantes (series OOS alineables), se usa éste; Bonferroni sirve sólo para variantes sin serie común o como cota rápida. Además, el umbral fijo t entre folds ≥ 3 ya incluye margen: P(t > 3) vale 0,0100 con 7 g.l., 0,0075 con 9, 0,0048 con 14, 0,0018 con 89 y 0,0013 con infinitos; Bonferroni (K × p ≤ 0,05) sólo supera al umbral de 3 si K ≥ 7 con 10 folds, K ≥ 11 con 15 folds y K ≥ 29 con 90 folds. *(Corrección de EXP-004: allí se escribió "t ≥ 3 cubre hasta K ≈ 18", cifra aproximada que sólo vale para ~30 g.l.; los valores correctos dependen de los folds, como arriba.)*

**Qué cambiaría si se quitara la regla.** Hoy, nada: ninguna variante se acerca al umbral (los t entre folds de EXP-001/002 están entre −2,2 y +0,1 para el retorno neto y hasta +1,3 para el lift) y para K = 4–6 el umbral Bonferroni queda por debajo de 3 en todos los diseños de folds usados (2,3–2,9). La regla es una salvaguarda para que el rigor no se erosione a medida que K crezca; no está condicionando ningún resultado actual. Se mantiene, con la forma: **umbral de decisión = máx(3, t Bonferroni(K, g.l.))**, usando `bonferroni_t_threshold` (en `multiple_testing.py`) cuando no se use el Reality Check.

**K antes y después de EXP-008:** ver la entrada EXP-008.

---

## 3. Bitácora

Las entradas nuevas se agregan al final de esta sección (antes de "## 4. Plan"), y se actualiza el plan si cambia.

Formato de cada entrada:

```
### EXP-NNN — título corto (fecha)
Hipótesis: qué se espera y por qué.
Cambio: qué se modificó respecto del experimento anterior.
Comando: el comando exacto.
Hipótesis probadas en este experimento: N (acumulado: M).
Resultado: números clave del walk-forward.
Lectura: qué significa.
Decisión: qué se descarta / qué se mantiene.
Próximo paso: qué se prueba después y por qué.
```

### EXP-000 — Estado de partida (2026-10-04)
Hipótesis: con indicadores técnicos simples sobre BTC 1h existe alguna condición rentable después de costos.
Datos: Yahoo, BTC-USD 1h, 2024-01 → 2026-10 (24.138 velas).
Costos: modelo anterior (hoy escenario `custom`: 0,1 % por lado + slippage 0,05 % + spread 0,02 %, ≈ 0,32 % por operación).
Resultado:
- Split único TRAIN/VAL/TEST: miles de condiciones probadas en varias grillas; ninguna sobrevive de forma creíble. La única que pasó un TEST tuvo t ≈ 0,19 (indistinguible de 0) y fue 1 de 288 evaluadas.
- Walk-forward 4 folds (TP 5 %, SL 3 %, 100 velas, `until_exit`, filtro `both`): LONG con OOS > 0 en 1/4 folds; SHORT en 0/4.
- Con una serie aleatoria de 80.000 velas, el procedimiento no "encuentra" nada (control correcto).
Lectura: dos años de datos alcanzan para un solo régimen por segmento; no se puede distinguir una señal de un efecto del régimen del mercado.
Decisión: pasar a historia larga de Binance (desde 2017) y evaluar todo en walk-forward.
Próximo paso: EXP-001 (ver "Plan").

Nota (2026-10-04): se reemplazó el modelo de costos por `costs.py` con escenarios. Con los mismos datos y walk-forward de 4 folds (LONG, TP 5 %/SL 3 %/100 velas), el retorno OOS agrupado fue −0,37 % (`typical`), −0,29 % (`optimistic`) y −0,48 % (`conservative`), con 2/4 folds positivos en `typical`. Los resultados de EXP-000 con el modelo viejo no son directamente comparables con los nuevos.

### EXP-001 — Línea base en BTCUSDT 1h de Binance (2026-10-04)
Hipótesis: con 9 años de historia (varios regímenes), el procedimiento "buscar en TRAIN, medir en VALIDATION" sobre condiciones técnicas simples NO produce retorno neto OOS > 0 consistente con costos `typical`. Se espera que sea negativo (cercano a −costos) y que LONG/SHORT cumplan menos de 4 de 10 folds. Es la referencia para los experimentos siguientes.
Datos: Binance spot BTCUSDT 1h, 2017-08-17 → 2026-10-03 (79.909 velas), en `D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv` (fuera del repo; caché de zips en la misma carpeta).
Cambio: datos nuevos (Binance en vez de Yahoo) y costos `typical`; resto = config por defecto (depth 1, 10 folds, ratio 3, ventana móvil, holdout 15 % sin abrir).
Comando: `pixi run python run_research.py --csv "D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv" --walk-forward --side LONG SHORT --tp 0.05 --sl 0.03 --horizon 100 --cooldown-mode until_exit --filter-mode both --cost-scenario typical --no-events --output results/exp001`
Hipótesis probadas en este experimento: 150.000 (7.500 condiciones × 10 folds × 2 lados) (acumulado: 150.000, sin contar las grillas de EXP-000, que no se cuantificaron).
Resultado (costos `typical`, TP 5 %/SL 3 %/100 velas, `until_exit`, filtro `both`, 10 folds):
- LONG: retorno neto OOS agrupado −0,14 % (línea base promedio −0,16 %); folds con OOS > 0: 5/10; folds que superan la línea base: 8/10. Por escenario: optimistic −0,06 % (5/10), typical −0,14 % (5/10), conservative −0,29 % (4/10).
- SHORT: −0,61 % (línea base −0,30 %); 2/10 folds con OOS > 0; 3/10 superan la línea base. Folds 9 y 10 sin condiciones seleccionadas.
- Pocos folds aportan casi todo el volumen OOS (p. ej. LONG folds 9 y 10: 185 k y 247 k entradas, sin independencia: se superponen en el mismo precio). Folds 7 y 8 tienen 15 y 114 entradas: ruido.
- Ningún lado cumple el criterio de candidato (LONG: neto OOS < 0, 5/10 en vez de ≥ 80 %).
Lectura: LONG "le gana" a la línea base en 8/10 folds, pero por márgenes de ±0,1–0,3 % y el neto sigue ≈ 0 o negativo; la línea base ya es negativa en muchos folds (el costo por operación es del mismo orden que el efecto). El signo del retorno OOS acompaña al régimen del mercado más que a la condición (folds alcistas positivos, bajistas negativos). SHORT es peor que la línea base. Con 7.500 condiciones sorteadas al azar y un filtro por TRAIN, el procedimiento no extrae señal reproducible.
Decisión: se mantiene esto como referencia. Holdout cerrado. No hay candidato.
Próximo paso: EXP-002 (ventanas cortas, idea A) según el Plan: re-buscar seguido para adaptarse al régimen, y evaluarlo como procedimiento. Pendiente de implementar y testear.

### EXP-002 — Walk-forward de ventanas cortas (2026-10-04)
Hipótesis: re-buscar condiciones seguido (TRAIN ~3,5 meses) y operarlas sólo el mes siguiente permite adaptarse al régimen, así que el procedimiento tendría retorno OOS agrupado mejor que en EXP-001 (LONG −0,14 %). Expectativa honesta: sigue ≤ 0 en `typical`; con TRAIN de ~2.500 velas, las seleccionadas son más ruido que señal.
Cambio: nuevo modo de folds por largo en velas (`--wf-train-bars 2500 --wf-val-bars 720`, ≈ 3,5 meses y 1 mes; la VALIDATION es la "situación real", sin TEST intermedio ni extensión de ventana). Agregado además el t del retorno OOS agrupado y el total de entradas OOS al resumen (criterio 4). Tests nuevos: `test_walk_forward_short_windows`, `test_pooled_t_matches_direct`. Las features no cambiaron (test de causalidad intacto).
Comando: `pixi run python run_research.py --csv "D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv" --walk-forward --wf-train-bars 2500 --wf-val-bars 720 --side LONG SHORT --tp 0.05 --sl 0.03 --horizon 100 --cooldown-mode until_exit --filter-mode both --cost-scenario typical --no-events --output results/exp002`
Hipótesis probadas en este experimento: 1.350.000 (7.500 × 90 folds × 2 lados) (acumulado: 1.500.000, sin contar EXP-000).
Resultado (`typical`, 90 folds de VAL = 1 mes cada uno, contiguos):
- LONG: neto OOS agrupado −0,19 % (línea base −0,19 %, o sea lift ≈ 0); folds OOS > 0: 39/90; superan la base: 52/90; 895.090 entradas OOS; t agrupado −49 (inflado, pero negativo). Por escenario: optimistic −0,11 %, conservative −0,34 % (32/90).
- SHORT: −0,15 % (línea base −0,29 %); 37/90 con OOS > 0; superan la base 31/90; 492.594 entradas; t −28. Optimistic −0,06 %, conservative −0,30 %.
- Sin lado que cumpla el criterio de candidato (neto OOS < 0 en los tres escenarios y t muy negativo).
Lectura: re-buscar mensualmente no mejoró nada respecto de EXP-001 (LONG −0,14 % → −0,19 %): el lift de LONG es ≈ 0 en el agregado. En SHORT el agregado supera a la base en +0,14 pp, pero sólo en 31/90 folds, es decir, el efecto lo da una minoría de folds (probablemente con muchas entradas) y no es consistente. Lo que se selecciona en 3,5 meses de TRAIN no se mantiene el mes siguiente: el efecto del costo (~0,25 %) domina y las selecciones son ruido. La idea A, tal como está implementada (misma búsqueda aleatoria de condiciones, sólo ventanas más cortas), no aporta.
Decisión: se descarta la idea A como mejora por sí sola; se deja el modo de ventanas cortas disponible (`--wf-train-bars/--wf-val-bars`) para evaluar experimentos posteriores. Holdout cerrado. No hay candidato. Cuenta de experimentos seguidos sin avance: 2.
Próximo paso: EXP-003 (features de régimen: tendencia en 4h/diario y volatilidad relativa), requisito de la idea B. Se evaluará con el walk-forward de EXP-001 (10 folds, más rápido: ~10 min por lado) como referencia.

### EXP-003 — Purged / Embargoed Walk-Forward: ¿es válido nuestro WFO? (2026-10-04)
Orden cambiado a pedido del usuario: antes de agregar features/temporalidades se revisa la validez estadística del proceso (EXP-003 y EXP-004). No se corrió ninguna búsqueda nueva (0 hipótesis nuevas, acumulado 1.500.000); sólo análisis de código, tests, una simulación de nulidad y un re-análisis de los `wf_summary.csv` de EXP-001/002.

**1. Conceptos (qué problema es cuál).**
- *Leakage*: el resultado de una observación de TRAIN usa información (precios) de VAL. Se evita con **purga**: eliminar del TRAIN las observaciones cuyo intervalo de información se solapa con el período evaluado.
- *Embargo*: además se descarta un margen de TRAIN **posterior** a un bloque de test porque la correlación serial de features/labels lo contamina. Sólo tiene sentido cuando hay entrenamiento DESPUÉS del test (K-fold, CPCV). En un walk-forward estrictamente hacia adelante (TRAIN → VAL) no hay TRAIN posterior: el embargo no aporta.
- *Dependencia temporal / overlap entre labels*: operaciones cuyos intervalos [entrada, salida] se solapan no son independientes, y el t por entradas sobreestima la evidencia. No es leakage: ocurre aun sin ningún cruce de segmentos.
- *Data snooping, múltiples hipótesis, selection bias, overfitting del backtest*: ver EXP-004. Son problemas del PROCESO de selección, no de cómo se cortan los segmentos.
Referencias consultadas: López de Prado (AFML, caps. 7 y 12: purged K-fold, embargo, CPCV) y la documentación de `eslazarev/purged-cross-validation` y `landtml/purgedcv`: ambos definen para cada observación un intervalo [momento en que está disponible la feature, momento en que se resuelve el label] y purgan del TRAIN lo que se solapa con el test; el embargo es un margen (en observaciones, tiempo o fracción) después del bloque de test. No se instalaron (sin dependencias nuevas): la lógica necesaria es de pocas líneas.

**2. Qué hace hoy el código (`entry_detector.detect_entries`).** Para cada segmento sólo acepta señales con `t ≤ end−1−H`, o sea `e+H−1 ≤ end−1` (e = t+1). La ventana de evaluación [e, e+H−1] siempre cae entera en el segmento. Además: el generador de condiciones y los umbrales usan sólo el slice TRAIN; la selección sólo usa TRAIN; el `oos_pooled` se calcula sobre TODAS las seleccionadas en TRAIN (no sólo las que pasan el filtro en VAL).

**3. Respuestas.**
1. `n_dropped_horizon` NO es sólo "operaciones incompletas": es exactamente la purga. Descartar toda señal cuyo horizonte sale del segmento deja a cada observación con intervalo de información dentro de su segmento. Es la purga de López de Prado con ancho H (+1 por la vela de entrada), aplicada de forma conservadora.
2. No. Una operación de TRAIN cerca del final usa precios ≤ `train.end−1` por construcción (test `test_train_results_do_not_depend_on_future_prices`: reemplazar todos los precios posteriores al TRAIN no altera ni una sola métrica de TRAIN; con control negativo que muestra que sin purga sí cambiarían).
3. No. El label de una operación de comienzo de VAL sólo usa precios de VAL (`test_validation_labels_use_only_validation_prices`). Lo único que mira a TRAIN es el indicador que genera la señal (ventana hacia atrás: una SMA200 al inicio de VAL usa precios de TRAIN). Eso es causal y legítimo: en vivo también se conoce el pasado; purga y embargo no se aplican a las ventanas de features.
4. Sí distorsionan, pero por dependencia, no por leakage. Simulación de nulidad (señales aleatorias sin ventaja, 60 series, H=50, TP=SL=5 %): con cooldown `fixed`=1 el desvío del t es 1,7 (debería ser 1) y rechaza H0 (|t|>2) el 27 % de las veces (debería ser 5 %); con `until_exit` 0 % (algo conservador, desvío 0,8); con `fixed`=15 ≈ correcto. Y el t agrupado entre condiciones es peor: las seleccionadas comparten las mismas velas.
5. **Purga: sí, ya aplicada. Embargo: no hace falta** en walk-forward hacia adelante. Serían obligatorios ambos si se usara K-fold o CPCV, donde hay TRAIN posterior al test.
6. Intervalos por operación (función `trade_intervals`): `signal_idx` t; `entry_idx` e=t+1; `exit_idx` = e+exit_offset (TP/SL/tiempo); `info_end_idx` = e+H−1. Para purgar se usa `info_end_idx` y no `exit_idx`, porque MFE/MAE y las métricas `favorable` miran todo el horizonte aunque TP/SL cierren antes. Con `until_exit` el estado de re-entrada sí depende de `exit_idx`, que siempre es ≤ `info_end_idx`.
7. Del TRAIN hay que eliminar toda observación con `info_end_idx ≥ inicio de VAL`, o sea las señales de las últimas H velas. Eso ya ocurre (misma regla). Costo: se pierden H velas por segmento (≈14 % de cada VAL de 720 velas con H=100 en EXP-002), igual para la línea base, así que la comparación es consistente; el descarte depende sólo de la posición temporal, no del resultado, por lo que no introduce sesgo.
8. Cooldown/horizonte/TP-SL: la regla de purga es la misma en todos (depende sólo de H). `until_exit` evita el solapamiento dentro de cada condición y es el único modo con t por entradas aproximadamente válido; `fixed` con cooldown < H solapa operaciones. TP/SL sólo acortan `exit_idx`; no cambian la purga.
9. **El criterio de candidato, tal como estaba, no es válido.** "t ≥ 3 sobre las entradas OOS agrupadas" usa un t entre entradas: ignora el solapamiento entre condiciones (EXP-002: t = −49 LONG y −28 SHORT, con 895 k y 493 k entradas: números sin sentido estadístico) y pondera casi todo por los pocos folds con más entradas. Hay que usar un estadístico a nivel de fold: el **t entre folds** (media de los `oos_pooled_mean_net` por fold, error estándar entre folds, K−1 grados de libertad). Las VALIDATION son períodos disjuntos, así que es mucho más cercano a independencia. Re-análisis de lo ya corrido (sin experimentos nuevos), t entre folds del retorno neto OOS / del lift sobre la línea base: EXP-001 LONG 0,08 / 1,28 (K=10); EXP-001 SHORT −2,15 / −0,62 (K=8); EXP-002 LONG −1,56 / 1,13 (K=89); EXP-002 SHORT −1,89 / −0,43 (K=74). Ninguno distingue de 0 a favor de la estrategia; las conclusiones de EXP-001/002 (sin candidato) no cambian, pero ahora con un número interpretable en lugar de t = −49.

**4. Veredicto.** El WFO actual es válido respecto de leakage: purga correcta por construcción, embargo innecesario. Lo que fallaba era la **inferencia** (t por entradas), no la separación temporal.

**5. Cambios (mínimos).**
- `entry_detector.py`: `trade_intervals` y `fits_in_segment` (hacen explícita la regla de purga; `detect_entries` no cambió).
- `walk_forward.py`: `fold_level_t` y `oos_fold_level_t` en el agregado (`oos_pooled_t_all_folds` se conserva, documentado como inflado). `run_research.py` imprime ambos.
- Regla de candidato (sección 2, punto 4), **enmendada a partir de EXP-003**: se reemplaza "t ≥ 3 sobre las entradas OOS agrupadas" por "**t entre folds ≥ 3** del retorno neto OOS (y también del lift sobre la línea base, para no confundir régimen con señal)", con costos `typical` y neto OOS > 0 también en `conservative`. Se mantiene "≥ 80 % de folds con neto > 0 y con lift > 0" como filtro descriptivo, no como prueba. Sigue pendiente la corrección por múltiples hipótesis (EXP-004): cumplir esto es **necesario, no suficiente**. Es una modificación más exigente, no menos; se avisa al usuario.

**6. Tests que lo protegen** (28 pasan; los de no-lookahead siguen intactos): `test_trade_label_window_stays_inside_segment` (3 modos de cooldown × 3 segmentos; verificado que falla si se debilita la purga), `test_train_results_do_not_depend_on_future_prices` (invariancia de TRAIN ante cambios futuros + control negativo), `test_validation_labels_use_only_validation_prices`, `test_overlap_inflates_t_but_until_exit_does_not` (simulación de nulidad), `test_fold_level_t`.
Nota de robustez: si el filtro de horizonte se rompiera, `apply_until_exit` entraría en un bucle infinito (exit_offset = −1 fuera de la tabla); no se cambió porque es inalcanzable con la purga vigente y el test de purga lo detectaría.

**7. Efecto en experimentos futuros.** Todos se evalúan con el t entre folds; el t por entradas queda sólo como descriptivo. Preferir `until_exit`. Con pocos folds el t entre folds tiene pocos grados de libertad: más folds cortos (como EXP-002) es más informativo que pocos folds largos. Si se implementa CPCV hará falta purga + embargo con `trade_intervals`.
Decisión: sin cambios en búsqueda ni costos. Holdout cerrado. Próximo paso: EXP-004. El contador de "experimentos sin avance" no se incrementa (no fue un experimento de búsqueda).

### EXP-004 — White Reality Check + PBO (2026-10-04)
Hipótesis (escrita antes de la corrida definitiva de `run_pbo.py`): en el espacio de búsqueda actual (7.500 condiciones simples, TP 5 %/SL 3 %/100 velas, `until_exit`, costos `typical`, 16 bloques del período de desarrollo, holdout fuera) la PBO es ≥ 0,5 y el retorno neto medio de la mejor condición IN-sample es negativo o ~0 OUT-of-sample, porque no hay información en las condiciones y el costo (~0,25 %) empuja todo hacia abajo. Un piloto con 1.500 condiciones LONG (ya corrido, cuenta como 1.500 hipótesis) dio PBO 0,62, mejor IN +0,68 % → OUT −0,27 %. Corrida definitiva: LONG y SHORT × 7.500 = 15.000 hipótesis (acumulado: 1.516.500).
Resultado de la corrida definitiva (seed 42) y de una repetición con otra semilla del generador (seed 7, +15.000 hipótesis; acumulado total: 1.531.500). PBO por CSCV, S = 16 bloques de ~4.300 velas, 11.000–12.000 particiones IN/OUT, métrica = retorno neto medio por operación (`typical`), mínimo 30 operaciones, cada bloque purgado como un segmento:

| Lado / seed | PBO | Mejor IN (media) | Esa misma OUT | P(pérdida OUT) | % condiciones con media > 0 en todo el desarrollo |
|---|---|---|---|---|---|
| LONG / 42 | 0,72 | +0,87 % | −0,30 % | 84 % | 13 % |
| LONG / 7 | 0,49 | +0,97 % | −0,09 % | 62 % | 13 % |
| SHORT / 42 | 0,24 | +0,94 % | +0,10 % | 44 % | 0,5 % |
| SHORT / 7 | 0,28 | +0,94 % | −0,05 % | 52 % | 0,6 % |

Lectura: la mejor condición IN-sample entre 7.500 sorteadas ("+0,9 % por operación") se degrada a ≈ 0 o negativo OUT en los cuatro casos, que es exactamente el sesgo de selección. La PBO por sí sola es inestable entre sorteos del generador (LONG 0,72 vs 0,49): leer el nivel de degradación y P(pérdida), no la PBO sola. El 0,24–0,28 de SHORT **no** significa que haya señal: la PBO mide persistencia del ranking, y el ranking puede persistir por estructura (qué condiciones operan poco o en qué régimen, bajo un costo común que arrastra todo a negativo); el retorno OUT de la mejor cambia de +0,10 % a −0,05 % con otra semilla. Coherente con EXP-001/002.

#### Análisis conceptual (qué problema es cuál)
| Problema | Qué es | Dónde aparece en este proyecto | Cobertura |
|---|---|---|---|
| Leakage | El resultado de una observación usa información de otro segmento | TRAIN→VAL | Resuelto y testeado (EXP-003) |
| Dependencia temporal / overlap de labels | Observaciones no independientes → errores estándar subestimados | t entre entradas; condiciones que comparten velas | t entre folds (EXP-003); bloques ≥ H en el bootstrap (EXP-004) |
| Data snooping | Usar los mismos datos para elegir y para evaluar | Elegir TP/SL/lado/H/experimento mirando el OOS; reusar siempre los mismos VAL | Parcial: contador de hipótesis y K de procedimientos; RC cuando haya series |
| Múltiples hipótesis | Con K pruebas, el máximo de K estadísticos crece aunque no haya nada | 7.500 condiciones por fold; K variantes de procedimiento | RC (implementado, no aplicado a datos reales todavía); Bonferroni de K como regla provisoria |
| Selection bias | Lo que se elige por ser el mejor está inflado | "La mejor IN-sample" | Dentro de un fold se evita (se mide en VAL lo elegido en TRAIN); PBO lo mide |
| Backtest overfitting | Elegir un proceso que se ajusta al pasado y se degrada fuera | Cualquier selección sobre la historia | PBO/CSCV (implementado) |
| Robustez OOS | Que el desempeño persista en datos no vistos | Folds, holdout, escenarios de costos | Walk-forward + holdout (reglas vigentes) |
Evitar look-ahead ≠ evitar overfitting ≠ corregir múltiples hipótesis ≠ demostrar robustez: se puede tener cero leakage y aun así reportar el máximo de miles de pruebas.

**Qué es una "hipótesis".** Tres niveles: (a) *condición*: (condición, lado, TP, SL, H, costos) en un período con H0: E[retorno neto por operación] ≤ 0; (b) *procedimiento*: una búsqueda totalmente especificada (generador, filtros, lado, TP/SL/H, ventana de re-búsqueda), cuyo OOS walk-forward es UNA trayectoria, con H0: E[retorno neto OOS] ≤ 0; (c) *programa de investigación*: todos los procedimientos probados contra la misma historia OOS. **Dónde hace falta corregir:** dentro de un fold, el OOS de "todo lo que TRAIN seleccionó" es insesgado respecto de la selección de condiciones (la búsqueda entera quedó absorbida en TRAIN), así que no se corrige por las 7.500 condiciones sino por lo que el investigador elige mirando el OOS: variantes de procedimiento, parámetros (grillas), qué candidato abrir en el holdout, y el reuso de las mismas VALIDATION en todos los experimentos (el OOS se "gasta"; sólo el holdout es virgen).

**White Reality Check aplicado a este sistema.**
- *Universo*: todas las variantes de procedimiento evaluadas contra la misma historia OOS (hoy K = 4: EXP-001/002 × LONG/SHORT; hay que sumar cada grilla de TP/SL/H/lado). Si se elige entre condiciones mirando un período concreto, el universo es toda condición que pudo ser elegida ahí, no sólo las que pasaron el filtro.
- *Benchmark*: cero (efectivo) después de costos, que es el objetivo del proyecto; como benchmark secundario, la media de la línea base del segmento (exceso sobre entrar en cualquier vela, para separar señal de régimen).
- *Estadístico*: máximo, entre las K reglas, de la media neta por vela estudentizada (la serie vale el retorno neto en la vela de entrada y 0 si no hay operación; `entry_series`). Estudentizar evita que ganen sólo las reglas más volátiles.
- *Bootstrap*: estacionario (bloques geométricos). Simulación: si la serie es dependiente (operaciones de hasta H velas) el bootstrap iid rechaza H0 bajo nulidad más del 50 % de las veces; con bloques ≥ 4× la dependencia y T ≫ bloque queda en ~5 %. **Requisito práctico: T ≳ 200·H** (para H = 100, ≳ 20.000 velas). Por lo tanto el RC no sirve por fold (720 velas) ni sobre el holdout de 15 % con H = 100 sin cuidado (~12.000 velas): hay que aplicarlo a la serie OOS completa del walk-forward (~70.000 velas).
- *Costos*: las series ya son netas (`typical`; `conservative` como sensibilidad; nunca `optimistic`).
- *Walk-forward*: cada vela cae en una sola VALIDATION, así que la serie OOS de un procedimiento se arma concatenando los tramos VAL (una serie por procedimiento). Pendiente: persistir las operaciones OOS por fold (`events.csv.gz` ya las tiene) y definir la ponderación entre condiciones (propuesta: promedio simple de las operaciones abiertas en cada vela).
- *Nivel*: al programa de investigación completo (todas las variantes probadas contra la misma historia), no a cada experimento por separado ni a cada fold.
- *Límites*: sólo cubre un universo enumerado (la búsqueda aleatoria no enumera 1,5 M de condiciones: se aplica a las variantes de procedimiento y a los candidatos a abrir); es conservador si hay muchas reglas malas en el universo (SPA de Hansen lo corrige, no implementado); poca potencia; sensible al largo de bloque; no resuelve no estacionariedad; el máximo no dice cuántas reglas son reales.

**PBO/CSCV aplicado a este sistema.** "Proceso de selección" = "de N condiciones sorteadas, quedarse con la mejor IN-sample por retorno neto medio por operación". CSCV: S = 16 bloques temporales contiguos del período de desarrollo; para cada una de las C(16,8) particiones, mejor IN → su rango OUT entre las N; PBO = fracción con rango ≤ mediana. Como CSCV mezcla bloques de cualquier época, **cada bloque se purga como un segmento** (`detect_entries`: ninguna operación cruza su borde). No se aplicó embargo (el bloque ≈ 40 H; el efecto del borde es pequeño: documentado). Qué agrega frente al walk-forward: (1) no depende de un único corte cronológico; (2) mide la degradación de *lo que se elegiría*, no de un promedio de un conjunto; (3) cuantifica el sesgo de selección (+0,9 % IN → ≈ 0 OUT). Qué NO da: causalidad temporal (usa el futuro para elegir: no detecta cambio de régimen), p-valor, ni magnitud; el nivel de PBO varía mucho con el sorteo. Es directamente aplicable sobre sumas por bloque; no hizo falta adaptar la metodología salvo usar retorno medio por operación (no Sharpe: pocas operaciones por bloque) y exigir un mínimo de operaciones.
**DSR** (Bailey y López de Prado, 2014): corrige el Sharpe del mejor por el número de pruebas independientes N_eff y por asimetría/curtosis. Con ~1,5 M condiciones sorteadas y altamente correlacionadas N_eff no está definido; el bootstrap del RC usa la dependencia real sin necesitar N_eff. DSR queda como herramienta futura para reportar un candidato final; no implementado.

#### Implementado, no implementado
- Implementado (`trading_research/multiple_testing.py`, `run_pbo.py`): `reality_check` (White con bootstrap estacionario y estadístico estudentizado), `cscv_pbo`, `entry_series`, `condition_block_stats`, `stationary_bootstrap_weights`. 7 tests/simulaciones nuevos (35 en total): calibración del RC bajo nulidad (el mejor de 200 reglas de ruido tiene t > 2 el 100 % de las veces; RC rechaza ≈ 5 %), potencia ante una ventaja real, necesidad de bloques con series dependientes, PBO ≈ 0,5 con ruido y ≈ 0 con ventaja estable, degradación del mejor IN-sample, y purga de bordes de bloque.
- No implementado (trabajo futuro): construir la serie OOS del walk-forward (`procedure_oos_series`) y correr el RC sobre las variantes de procedimiento; SPA (recentrado consistente); PBO sobre el lift respecto de la línea base y con una métrica tipo t; embargo en CSCV; DSR; CPCV (necesita purga + embargo con `trade_intervals`). No se simplificó nada para "aparentar" un RC real: no hay todavía series OOS por procedimiento, así que NO se aplicó el RC a los datos reales.

#### Respuesta a la pregunta: ¿qué evidencia hace falta para decir que probablemente no es un ganador por azar?
Todas estas condiciones juntas, y sigue siendo "improbable que sea azar", no una demostración:
1. Sin leakage y con la señal causal (tests de EXP-003 y de no-lookahead).
2. Procedimiento fijado antes de mirar el OOS; toda variante (lado, TP/SL/H, ventana, filtro) probada contra el mismo OOS suma al contador K.
3. t entre folds ≥ 3 del retorno neto OOS y también del lift sobre la línea base, con costos `typical`, y neto > 0 en `conservative` (regla vigente desde EXP-003).
4. Corrección por K: hasta tener RC, Bonferroni (p_ajustado = K × p ≤ 0,05; con K = 4, |t| ≳ 2,6; t ≥ 3 cubre hasta K ≈ 18). Con la serie OOS completa, RC con p < 0,05 sobre el programa de variantes.
5. La degradación de la selección debe ser pequeña: PBO bien por debajo de 0,5 de forma repetida (≥ 3 sorteos) y el retorno OUT del mejor IN positivo; con 0,49–0,72 y OUT ≤ 0 (resultado actual) no hay evidencia.
6. Consistencia entre sub-períodos y regímenes (no sólo en el agregado).
7. Holdout abierto una sola vez, para un candidato fijado de antemano (K del holdout = 1).
8. Plausibilidad económica (por qué existiría el efecto) y margen sobre costos `conservative`.
Estado actual: ningún procedimiento supera el paso 3; las pruebas de PBO muestran el sesgo de selección en acción (+0,9 % IN → ≈ 0 OUT).

Decisión: sin candidato; holdout cerrado. Se mantiene el contador de hipótesis (1.531.500) y se agrega la regla K a la sección 2. Experimentos seguidos sin avance: 2 (EXP-003/004 fueron metodológicos, no cuentan).
Próximo paso: volver a la hoja de ruta (sección 4). Lo siguiente con más valor para esta línea es `procedure_oos_series` + RC sobre las 4 variantes ya corridas, antes de agregar capacidad de búsqueda.

### EXP-005 — Serie OOS del walk-forward y Reality Check sobre las 4 variantes (2026-10-04)
Hipótesis (escrita antes de correr): sobre la historia OOS común de las K = 4 variantes (EXP-001 y EXP-002, LONG y SHORT), el Reality Check NO rechaza H0 "ninguna variante rinde > 0 neto" (p > 0,05) con el benchmark cero, y tampoco con el benchmark "exceso sobre la línea base". Esperado: la mejor variante es EXP-001 LONG o EXP-002 SHORT, con p ajustado claramente > 0,05.
Especificación fijada antes de ver resultados (no se cambia después de mirar): universo = las 4 variantes; serie por vela = promedio simple de los retornos netos de las operaciones abiertas en esa vela por TODAS las condiciones seleccionadas en TRAIN (0 si ninguna; efectivo); período = intersección de las velas de VALIDATION de las 4 variantes; costos `typical` (primario) y `conservative` (sensibilidad); benchmarks: (a) cero, (b) media de la línea base del fold restada en las velas con operación; estadístico = máximo del t estudentizado; bootstrap estacionario, bloque medio 300 (= 3H) primario, 100 y 600 como sensibilidad; 1.000 remuestreos (semilla 0). Se reportan también los p-valores individuales (K = 1) y el ajuste de Bonferroni para compararlos.
Cambio de código: el walk-forward guarda `oos_series.npz` (cnt, sum por escenario, línea base por vela, velas cubiertas) y la corrida repite EXP-001 y EXP-002 con la misma configuración y semilla (determinista: no son hipótesis nuevas; acumulado sin cambio: 1.531.500; K = 4). Test nuevo `test_walk_forward_oos_series_matches_fold_results`.
Comandos: los de EXP-001 y EXP-002 (arriba) con `--output results/exp005/exp001` y `results/exp005/exp002`; luego `run_reality_check.py`.
Resultado. Las repeticiones reprodujeron EXP-001/002 al dígito (retornos OOS agrupados y folds idénticos). Historia común: T = 52.240 velas contiguas de VALIDATION (≈ 5 años; T ≈ 520·H, por encima del mínimo T ≳ 200·H de EXP-004). Retorno neto medio por vela (efectivo cuando no hay operación; costos `typical`):

| Variante | Operaciones OOS | Media por vela, benchmark 0 | Media por vela, exceso sobre línea base |
|---|---|---|---|
| EXP-001 LONG | 873.879 | −0,145 % | +0,0067 % |
| EXP-001 SHORT | 247.116 | −0,161 % | −0,0084 % |
| EXP-002 LONG | 765.328 | −0,109 % | +0,0094 % |
| EXP-002 SHORT | 291.436 | −0,039 % | −0,0094 % |

Reality Check (1.000 remuestreos, bootstrap estacionario, estadístico = máximo t estudentizado):
- Benchmark 0, `typical`: p = 1,000 (bloque 300; mejor = EXP-002 SHORT); 1,000 (bloque 100); 0,999 (bloque 600). Individuales: 0,81–0,997. Con `conservative`: p = 1,000 en los tres bloques.
- Benchmark exceso sobre la línea base, `typical`: p = 0,924 (bloque 300; mejor = EXP-002 LONG); 0,923 (100); 0,916 (600). Individuales 0,41–0,63. Con `conservative`: 0,931 / 0,932 / 0,925.
- Bonferroni sobre el mínimo individual: 1,000 en todos los casos. Los p son insensibles al largo de bloque (100–600).

Lectura: ninguna de las 4 variantes rinde > 0 neto OOS (las medias por vela son todas negativas: en el período común el procedimiento pierde costos, hasta la "mejor", EXP-002 SHORT, a −0,04 % por vela). Respecto de la línea base, los exceso de LONG son positivos pero ínfimos (< 0,01 % por vela) y con p individual ≈ 0,4: no se distinguen de 0, y SHORT queda por debajo. El RC con K = 4 no cambia la conclusión porque ni siquiera el mejor p individual está cerca de 0,05; la corrección por múltiples variantes no es lo que decide acá, lo decide la ausencia de efecto. Esto es consistente con el t entre folds de EXP-003 (|t| ≤ 2,2, ninguno a favor) y con la PBO de EXP-004. Con costos `typical`, el exceso LONG sobre la base (≈ +0,007–0,009 % por vela) es ~100 veces menor que el costo por operación: aunque fuera real no sería operable.
Notas de validez: (1) la media "por operación" y las medias por vela dependen de la definición de serie (promedio simple entre condiciones, 0 si no hay operación); otras ponderaciones cambian el nivel, no el signo; no se exploraron (especificación fijada antes). (2) El RC aquí tiene K = 4 porque el universo son procedimientos, no condiciones: no sustituye una corrección sobre las 7.500 condiciones por fold, que no hace falta mientras el OOS no se use para elegir. (3) Límite conocido: RC estudentizado sin recentrado SPA es algo conservador; no cambia nada con p ≥ 0,4.
Decisión: sin candidato; K sigue en 4 (no se agregaron variantes); acumulado de hipótesis 1.531.500 (las repeticiones son deterministas). Infraestructura lista y probada: `oos_series.npz` por walk-forward, `run_reality_check.py` y la serie. Holdout cerrado. Experimentos seguidos sin avance de búsqueda: 2 (EXP-001/002; los metodológicos 003–005 no cuentan).
Próximo paso: segunda prueba de look-ahead a nivel de señales (ítem 2 del plan), antes de agregar capacidad de búsqueda. De ahora en adelante cada variante nueva se compara contra estas cuatro con el mismo RC (K crece) y debería guardar `oos_series.npz` (ya lo hace por defecto).

### EXP-006 — Segunda prueba de look-ahead a nivel de señales (inspirada en Freqtrade) (2026-10-04)
Hipótesis (escrita al lanzar la corrida sobre datos reales, antes de ver su salida; el desarrollo de los tests sí ocurrió antes y ya dio un hallazgo, ver abajo): sobre BTCUSDT 1h real, con el espacio completo de operandos del generador, no hay look-ahead en operandos, señales ni entradas; el único efecto dependiente del arranque de la historia son los indicadores recursivos (EMA/RSI/ATR/MACD…), que no son look-ahead.
Método (`trading_research/lookahead.py`, `run_lookahead.py`): como `lookahead-analysis` y `recursive-analysis` de Freqtrade, se calcula con la historia completa y de nuevo con el futuro (velas > k) borrado (`truncate`) o reemplazado por otro camino de precios y volumen (`perturb`); hasta la vela k todo debe ser idéntico. Tres niveles: (1) operandos, (2) señales de condiciones (profundidad 3: And/Or/Not/Then/OccurredWithin/Cross), (3) entradas y retornos netos de punta a punta (señal recalculada sobre datos truncados + cooldown `fixed`/`until_exit` + tabla de resultados + costos); más (4) informativo: sensibilidad al punto de partida de los datos. 3.000 simples + 2.000 complejas (semilla 11), 15 cortes k (12 aleatorios + 60, 300, 700 para el calentamiento), 300 condiciones en el nivel (3). Costos `typical`/`conservative`/`optimistic`. No son hipótesis de rentabilidad: no suman al contador (acumulado 1.531.500).
Hallazgo durante el desarrollo (test de entradas con señales reales sobre una serie aleatoria, cortes tempranos): `VolatilitySlippage` rellenaba el ATR no definido de las primeras ~15 velas con la MEDIANA del ATR% de TODA la muestra: look-ahead leve (el retorno neto de una operación en las primeras velas cambiaba con el largo de los datos). Sólo afecta al escenario `conservative` (y a cualquier modelo de slippage por volatilidad); el escenario `typical`, que decide, usa slippage fijo y no se ve afectado. Corregido: constante fija `warmup_atr_pct = 0,01` (1 %, conservador para BTC 1h; mediana real ≈ 0,4 %). Ninguna de las operaciones afectadas cae en una VALIDATION de EXP-001/002/005 (sólo las primeras ~15 velas de 2017 del primer TRAIN), de modo que sus resultados OOS no cambian.
Resultado (BTCUSDT 1h, 79.909 velas; 5.000 condiciones, 2.153 operandos distintos, 15 cortes k = 60, 300, 700 y 12 aleatorios entre 3.692 y 72.423; modos `truncate` y `perturb`):
- (1) Operandos con cambios hasta k: **0/2.153** (ATR%, velas, constantes, EMA, MACD, RSI, SMA, precios, retornos).
- (2) Condiciones con señal distinta hasta k: **0/5.000**.
- (3) Entradas y retornos netos de punta a punta: **0/300** con `until_exit` y **0/300** con `fixed` (cooldown 15), H = 100, los tres escenarios de costos (la corrección del ATR de calentamiento ya estaba aplicada).
- (4) Sensibilidad al arranque de la historia (informativo; arranques en las velas 1.000, 5.000 y 20.000, comparando desde 2.000 velas después): **0/2.153**. Los indicadores recursivos (EMA, RSI, ATR) convergen dentro de 2.000 velas con tolerancia relativa 1e-6; sí dependen del arranque en los primeros cientos de velas (test unitario con `after=300`). No hay efecto práctico en el walk-forward (los TRAIN arrancan con miles de velas de calentamiento), pero un backtest que empiece con menos de ~2.000 velas de historia vería señales algo distintas en EMA lentas.
Validez de la prueba (tests): `tests/test_lookahead.py` incluye "canarios" con fuga deliberada (cierre de la vela siguiente, media centrada, normalización con media de toda la muestra, máximo de las próximas 5 velas, y una señal "sube la vela siguiente" a nivel de entradas): la prueba los detecta en los niveles correspondientes (el de normalización global también con sólo `perturb`), y no marca falsos positivos en una señal causal ni en los operandos/condiciones reales. Un hallazgo sobre el diseño: el nivel (3) por sí solo es ciego a fugas más cortas que H (la purga descarta las últimas H confirmaciones del tramo truncado), por eso también compara la señal misma hasta k; y el nivel (3) con señales precalculadas sólo prueba cooldown/tabla/costos, no la generación de la señal.
Lectura: la hipótesis se cumple, con una excepción encontrada antes de la corrida y ya corregida (relleno de ATR con la mediana de la muestra en `VolatilitySlippage`; sólo `conservative`, sólo las primeras ~15 velas de los datos, sin efecto en ningún OOS ya registrado). Con esto hay dos pruebas independientes de causalidad (las de EXP-000/003 y ésta, con datos reales, perturbación del futuro y entradas de punta a punta).
Decisión: se mantiene todo; `run_lookahead.py` se vuelve parte del protocolo: **correrlo después de agregar cualquier feature, indicador o modelo de costos nuevo** (cada feature nueva ya requería un test de causalidad; este chequeo lo cubre en bloque). Holdout cerrado; sin cambios en K ni en el contador (1.531.500).
Próximo paso: ítem 3 del plan, revisión del tratamiento estadístico de operaciones superpuestas (cooldown `fixed` vs `until_exit`; t por entradas vs por folds vs HAC), o directamente volver a la búsqueda con las features de régimen si preferís priorizar capacidad; sugiero el ítem 3 porque define cómo se evaluará todo lo siguiente.

### EXP-007 — Operaciones superpuestas: qué estadístico es válido y qué cooldown conviene (2026-10-04)
Pregunta: cooldown `fixed` vs `until_exit`, y t entre entradas vs t entre folds vs HAC vs bootstrap, ¿cuál se calibra bien (no rechaza de más cuando no hay nada) y cuál tiene potencia cuando hay algo? No es un experimento de rentabilidad: usa series sintéticas, no suma al contador de hipótesis (1.531.500) ni a K.
Hipótesis (escritas antes de correr el estudio completo):
- H1 (por condición, nula): con `fixed` y cooldown < H el t entre entradas está inflado (desvío > 1, P(|t|>2) ≫ 5 %); se normaliza cuando cooldown ≳ H; `until_exit` es válido o algo conservador.
- H2 (por procedimiento, nula): el t entre todas las entradas OOS agrupadas (el de antes de EXP-003) está muy inflado en cualquier cooldown (P(t>3) ≫ 0,13 %); el t entre folds y el HAC sobre la serie por vela (rezagos ≥ H) quedan cerca de lo nominal (P(t>3) ≲ 1 %); el HAC puede ser algo liberal con T chico.
- H3: el cooldown no cambia la calibración del t entre folds/HAC; `until_exit` tiene más potencia que `fixed` con cooldown = H (más operaciones).
Diseño (`run_overlap_study.py`): Parte A: 150 caminos aleatorios, UNA condición con señales aleatorias (10 % de las velas), H = 50, cooldown ∈ {fixed 1, 5, 15, H, 2H, until_exit}. Parte B: 60 repeticiones del walk-forward COMPLETO (7.500→300 condiciones simples sorteadas, TRAIN 1.500 / VAL 500, 15 folds, TP = SL = 3 %, H = 50, sin costos, ambigüedad `midpoint`, filtro `both`) sobre 9.000 velas sintéticas, en (i) camino aleatorio sin ventaja con precio martingala (nula) y (ii) autocorrelación AR(1) φ = 0,2 en los retornos (ventaja exagerada, sólo para comparar potencia), para cooldown ∈ {until_exit, fixed 15, fixed H}. Estadísticos: t entre entradas, t entre folds, HAC con H y 3H rezagos, p del bootstrap estacionario (bloque 3H). Se reporta P(t>2), P(t>3) y P(p<0,05).
Nota de diseño: con log-retornos de media 0 el precio tiene deriva +σ²/2 y las operaciones LONG ganan en promedio aun sin ventaja; el generador usa media −σ²/2 para que la nula tenga retorno esperado 0.
Resultados.
**Parte A (una condición aleatoria sin ventaja, H = 50, 150 caminos):**

| Cooldown | Entradas (media) | Desvío del t (ideal 1) | P(\|t\|>2) (ideal 4,6 %) |
|---|---|---|---|
| fixed 1 | 492 | 1,89 | 30,7 % |
| fixed 5 | 352 | 1,56 | 19,3 % |
| fixed 15 (valor por defecto de `MIN_BARS_BETWEEN…`) | 205 | 1,21 | 10,7 % |
| fixed H (50) | 84 | 1,01 | 4,7 % |
| fixed 2H (100) | 46 | 0,99 | 4,0 % |
| until_exit | 148 | 0,96 | 4,0 % |

**Parte B (procedimiento completo, 60 repeticiones por celda, 15 folds, sin costos, escenario nulo con precio martingala; ideal con t normal: P(t>2) = 2,3 %, P(t>3) = 0,13 %, p-bootstrap < 0,05 el 5 %):**

| Estadístico (cooldown until_exit) | Desvío | P(t>2) | P(t>3) |
|---|---|---|---|
| t entre entradas OOS agrupadas | 6,0 | 26,7 % | **23,3 %** |
| t entre folds | 0,93 | 1,7 % | 0 % |
| t HAC (H rezagos) | 1,07 | 3,3 % | 0 % |
| t HAC (3H rezagos) | 1,03 | 1,7 % | 0 % |
| p bootstrap estacionario (bloque 3H) | — | — | P(p<0,05) = 5 % |
Con `fixed` 15 los números son prácticamente idénticos (t entre entradas: P(t>3) = 25 %; t entre folds 0 %; HAC 3,3 %; bootstrap 5 %). Con `fixed` H el procedimiento no seleccionó ninguna condición (TRAIN de 1.500 velas / cooldown 50 deja ≤ 30 entradas posibles y el mínimo exigido es 30): esa celda no se pudo medir en el procedimiento; sólo vale la Parte A.
Escenario con "ventaja" (AR(1) φ = 0,2, exagerada a propósito): el procedimiento casi no la aprovecha. `until_exit`: retorno medio por vela +0,012 % (nula: −0,008 %), P(t entre folds > 2) = 11,7 %, HAC 3,3 %, bootstrap 6,7 %. `fixed` 15: +0,003 %, t entre folds 6,7 %, HAC 3,3 %, bootstrap 8,3 %. Potencia baja para todos los estadísticos en este escenario; no permite ordenarlos por potencia, sólo muestra que `until_exit` captura más de la ventaja que `fixed` 15 (+0,012 % vs +0,003 %) y que ningún estadístico "se inventa" una ventaja que el procedimiento no encontró.

Lectura:
- H1 se cumple: con cooldown fijo menor que el horizonte, el t de UNA condición está inflado; con `fixed` ≥ H o `until_exit` es correcto. `until_exit` tiene el mismo tamaño de error que `fixed` H pero conserva 76 % más entradas (148 vs 84): es el único modo que evita solapamiento sin tirar muestra.
- H2 se cumple y es contundente: el t entre todas las entradas OOS agrupadas rechaza la nula con t > 3 el ~24 % de las veces (debería ser 0,13 %). Es decir, bajo ruido puro un procedimiento "pasaba" el criterio viejo de t ≥ 3 una de cada cuatro veces. EXP-003 ya lo había corregido; esto lo mide. El t entre folds y el HAC están bien calibrados (algo conservadores); el bootstrap acierta el 5 % nominal.
- H3 sólo se confirma en la parte de que el cooldown no cambia la calibración de los estadísticos válidos; la comparación de potencia entre estadísticos quedó sin resolver (el escenario de ventaja es demasiado débil).
Decisión (estándar de medición desde acá):
1. **Cooldown:** `until_exit` es el estándar. Se agregó una advertencia en `ResearchConfig.validate` si se usa `fixed` con cooldown < horizonte.
2. **Estadísticos:** el t entre entradas queda **sólo descriptivo; nunca decide**. Decide el t entre folds (regla 4). Se agrega el t HAC con 3H rezagos sobre la serie OOS por vela (`oos_hac_t_3H` en el resumen y en la salida de `run_research.py`), que se informa siempre; si discrepa mucho del t entre folds (HAC < 2 con t entre folds ≥ 3) el candidato se considera **no confirmado**. Para comparar varias variantes: Reality Check (EXP-005).
3. Con pocos folds el t entre folds tiene pocos grados de libertad (K = 15 aquí fue conservador); preferir ≥ 10 folds.
Cambios de código: `newey_west_t` y `procedure_series` en `multiple_testing.py`, `oos_hac_t_3H` en `walk_forward.py`, advertencia en `config.py`, `run_overlap_study.py`; tests `test_newey_west_t_matches_iid_t_without_lags_and_corrects_dependent_series`, `test_procedure_series_zero_when_no_trades_and_lift_subtracts_baseline`, `test_fixed_cooldown_shorter_than_horizon_warns` (47 pasan). No suma al contador de hipótesis (1.531.500) ni a K (4).
Próximo paso: con la medición estandarizada, volver a la parte experimental. Propuesta: features de régimen (tendencia en 4h/diario y volatilidad relativa), seguidas de `run_lookahead.py` y comparación con las 4 variantes por Reality Check.

### EXP-008 — Features de régimen: ¿mejoran la generalización OOS o sólo suman ganadores aparentes? (2026-10-04/05)
**Pregunta.** ¿Agregar información de régimen/contexto mejora la capacidad del procedimiento de encontrar condiciones que generalicen fuera de muestra, sin que la mejora se explique por haber probado más hipótesis? Si la respuesta es negativa, es un resultado válido.
**Variable experimental (una sola, aislada).** Tres familias de operandos nuevas, todas juntas como UNA variante (sin ablación hasta cerrar el experimento): tendencia 4h (`HTFTrend("4h", n)`, n ∈ [6, 60]), tendencia diaria (`HTFTrend("1D", n)`, n ∈ [5, 100]) y volatilidad relativa (`RelativeVolatility(corto, largo)` = ATR(corto)/ATR(largo), corto ∈ [5, 30], largo ∈ [60, 300]). No se agrega volumen, hora del día, día de la semana, TP/SL por ATR ni patrones de velas nuevos.
**Causalidad.** `HTFTrend` = cierre de la última vela superior COMPLETA / media de sus últimos n cierres − 1. La vela superior que contiene a la vela i sólo se considera completa al cierre de i si ts_i + base cae exactamente en el borde de la vela superior (4h: 00, 04, 08…; 1D: 00:00 UTC); si no, se usa la anterior. Nunca se usa una vela superior abierta ni posteriores a i. La alineación usa la época UTC (la zona horaria del índice no influye; sin zona = UTC). Tests (`tests/test_regime.py`): invariancia por truncación y por perturbación del futuro (cortes a cualquier hora del día), inicio no alineado, huecos de datos, zonas horarias, valores conocidos hora por hora, un "canario" que mira la vela abierta (se detecta) y que con el flag apagado el generador produce exactamente las mismas condiciones que antes (misma semilla). Además: `run_lookahead.py --regime-features`.
Hallazgo durante los tests: con pandas 3 el índice de fechas puede venir en microsegundos (`datetime64[us]`) y `asi8` no está en nanosegundos; la alineación salía mal (los tests de causalidad pasaban igual porque eran coherentes consigo mismos y lo detectó el test de valores conocidos). Corregido con `as_unit("ns")`; las demás partes del código no usan `asi8`.
**Diseño.** Referencia A (baseline) = EXP-002 (TRAIN 2.500 / VAL 720 velas, 90 folds, rolling), LONG y SHORT, ya corrida y reproducida al dígito en EXP-005 (`results/exp005/exp002`); con el flag apagado el generador es idéntico (test). Regime-aware B = el mismo comando con `--regime-features`. Constantes: datos (BTCUSDT 1h Binance), TP 5 % / SL 3 % / H 100, costos (`typical` decide; `conservative` robustez), `until_exit`, filtro `both`, mismo número de condiciones por fold (7.500, así B no prueba más hipótesis que A), semilla 42, mismos folds, holdout cerrado. Se comparan folds idénticos, de a pares.
**K (Reality Check) — definición antes y después** (ver "Aclaración de la regla 7 y definición de K", sección 2):
- *Antes de este experimento, K = 4*, porque representa las cuatro variantes de procedimiento completo (EXP-001 y EXP-002, cada una LONG y SHORT) evaluadas sobre la misma historia OOS (intersección de 52.240 velas), con el mismo activo, costos, horizonte, TP/SL y filtros.
- *Después de incorporar estas variantes, K = 6*, porque B-LONG y B-SHORT cumplen las tres condiciones de pertenencia: (i) mismo activo, datos, timeframe, costos, filtros, H y TP/SL; (ii) su serie OOS se alinea con las demás (usan los folds de EXP-002, que contienen la intersección); (iii) podría reportarse cualquiera como "el resultado". Duda registrada, no resuelta arbitrariamente: las variantes de EXP-001 tienen otro diseño de folds, pero ya estaban en el universo desde EXP-005 y la historia común es la misma; por eso se informa también el Reality Check con K = 4 (sólo A y B de EXP-002) como sensibilidad. No se cuentan: las 7.500 condiciones por fold, los experimentos, el contador de hipótesis, ni los escenarios de costos.
**Reglas de decisión, fijadas antes de ver los resultados de B:**
- R1 *(mejora relativa, por lado, 2 comparaciones)*: t pareado entre folds de (B − A) sobre `oos_pooled_mean_net` ≥ 2,5 **y** t HAC (3H rezagos) de la serie diferencia B − A ≥ 2 (Bonferroni para 2 comparaciones con 89 g.l. exige 1,99).
- R2 *(candidato absoluto, por lado)*: criterio de la regla 4 para B: t entre folds ≥ máx(3, Bonferroni(K = 6, 89 g.l.) = 2,44) = 3 tanto en retorno neto como en lift, neto OOS > 0 también en `conservative`, `oos_hac_t_3H` ≥ 2, ≥ 100 operaciones OOS; y Reality Check (K = 6) con p < 0,05.
- Lectura: ni R1 ni R2 → el contexto de régimen no mejora la generalización (resultado negativo válido). R1 sin R2 → reduce pérdidas relativas pero no es rentable; antes de aceptarlo hay que correr un control (features de régimen sin información, p. ej. barajadas por bloques, y A con el doble de condiciones). R2 → frenar y mostrar al usuario antes de cualquier otra cosa; el holdout no se abre sin su autorización.
- "Ganadores aparentes": además se comparan, A vs B, las condiciones que pasan el filtro en TRAIN y en VALIDATION, la fracción con neto OOS > 0 y que superan a la línea base, y la PBO del proceso de selección (`run_pbo.py` con y sin `--regime-features`, semillas 42 y 7). Si B tiene más "ganadores" pero no mejor retorno OOS, es el síntoma de ganadores aparentes.
Hipótesis (antes de correr B): R1 y R2 no se cumplen; el t pareado queda dentro de ±2; B no tiene más retorno OOS que A. Hipótesis probadas: B = 7.500 × 90 folds × 2 lados = 1.350.000, más la PBO de B (7.500 × 2 lados × 2 semillas = 30.000): acumulado 1.531.500 → 2.911.500.
Comandos: `pixi run python run_research.py --csv "D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv" --walk-forward --wf-train-bars 2500 --wf-val-bars 720 --side LONG SHORT --tp 0.05 --sl 0.03 --horizon 100 --cooldown-mode until_exit --filter-mode both --cost-scenario typical --no-events --regime-features --output results/exp008/regime`; `run_lookahead.py --regime-features`; `run_pbo.py --regime-features --seed {42,7}`; análisis pareado `run_regime_comparison.py`.

**Resultados (2026-10-05).** Look-ahead con las features nuevas (`run_lookahead.py --regime-features`, 5.000 condiciones, 2.631 operandos, 15 cortes): **0/2.631** operandos, **0/5.000** señales y **0/600** chequeos de entradas con diferencias. (Informativo: 326/2.631 operandos dependen del punto de arranque de la historia; son los de ventana larga —ATR largo hasta 300 velas, medias de hasta 100 velas diarias— que necesitan más de 2.000 horas para converger. En el walk-forward los TRAIN arrancan con años de calentamiento; un uso en vivo debe arrancar con ≥ 100 días de historia.)

Walk-forward, 90 folds, costos `typical` salvo donde se indica. A = baseline (EXP-002, reproducido en EXP-005), B = regime-aware (mismo comando con `--regime-features`):

| | A LONG | B LONG | A SHORT | B SHORT |
|---|---|---|---|---|
| Retorno neto OOS agrupado (todas las entradas) | −0,191 % | −0,219 % | −0,146 % | −0,136 % |
| Ídem `conservative` | −0,344 % | −0,376 % | −0,296 % | −0,287 % |
| Media por fold del neto OOS | −0,154 % | −0,060 % | −0,184 % | −0,255 % |
| Media por fold del lift sobre la línea base | +0,053 % | +0,107 % | −0,020 % | −0,029 % |
| t entre folds, neto | −1,56 | −0,55 | −1,89 | **−2,59** |
| t entre folds, lift | +1,13 | +1,84 | −0,43 | −0,64 |
| `oos_hac_t_3H`, neto (lift) | −1,99 (+0,04) | −1,96 (+0,13) | −0,89 (−0,12) | −1,03 (−0,14) |
| Folds con neto > 0 (de los que operaron) | 39/89 | 37/89 | 37/74 | 33/78 |
| Folds que superan la línea base | 52 | 55 | 31 | 34 |
| Folds con neto > 0 en `conservative` | 32 | 32 | 31 | 32 |
| Operaciones OOS | 895.090 | 722.946 | 492.594 | 394.254 |
| Condiciones seleccionadas en TRAIN (suma de folds) | 70.595 | 56.795 | 44.549 | 35.992 |
| Pasan también el filtro en VALIDATION | 83 | 82 | 58 | 47 |
| Fracción media de seleccionadas con neto OOS > 0 | 42,2 % | 42,0 % | 46,1 % | 42,4 % |

**R1 (mejora relativa B − A, mismos folds):** LONG: diferencia media por fold +0,020 %, t pareado **1,29** (n = 88), HAC de la diferencia 0,30, bootstrap p(B > A) = 0,36 → **NO**. SHORT: −0,017 %, t pareado **−1,14** (n = 74), HAC −1,34, p = 0,92 → **NO**.
**R2 (candidato absoluto):** ningún lado: t entre folds de neto −0,55 (LONG) y −2,59 (SHORT); neto OOS negativo también en `conservative`; HAC < 2 → **NO**.
**Reality Check** (bloque 300, 1.000 remuestreos), universo K = 6 (EXP-001 L/S + A L/S + B L/S), T = 52.240 velas: benchmark cero, `typical`: p = 1,000 (mejor A SHORT; B LONG individual 0,97, B SHORT 0,83); exceso sobre la línea base, `typical`: p = 0,914 (mejor B LONG, p individual 0,38); `conservative`: 1,000 / 0,925. Sensibilidad K = 4 (sólo EXP-002 A y B, T = 64.800): 0,995 / 0,793 / 1,000 / 0,811. Sin diferencias de conclusión entre K = 4 y K = 6.
**PBO del proceso de selección** (`run_pbo.py`, 7.500 condiciones, 16 bloques; semillas 42 / 7):

| | PBO | Mejor IN | Esa misma OUT | % condiciones con media > 0 en todo el desarrollo |
|---|---|---|---|---|
| A LONG | 0,72 / 0,49 | +0,87 % / +0,97 % | −0,30 % / −0,09 % | 13 % / 13 % |
| B LONG | 0,60 / 0,24 | +1,45 % / +1,46 % | −0,24 % / +0,13 % | 15 % / 15 % |
| A SHORT | 0,24 / 0,28 | +0,94 % / +0,94 % | +0,10 % / −0,05 % | 0,5 % / 0,6 % |
| B SHORT | 0,34 / 0,23 | +1,21 % / +1,22 % | −0,11 % / −0,07 % | 2,8 % / 3,1 % |

**Lectura.**
- *¿Mejora la generalización OOS?* **No.** Ninguna regla de decisión se cumple. LONG tiene un lift de fold algo mayor (+0,107 % vs +0,053 %), pero el t pareado (1,29) y el HAC de la diferencia (0,30) no lo distinguen de cero, y el retorno agrupado es un poco peor (−0,219 % vs −0,191 %). En SHORT, B es peor en la media por fold (t entre folds de −2,59: pierde de forma significativa; es el t más negativo de la serie, EXP-001 SHORT había dado −2,15). El Reality Check no encuentra nada (p ≥ 0,79).
- *¿Más "ganadores aparentes"?* **En la selección in-sample sí; en la selección que realmente se mide fuera de muestra, no.** La PBO muestra que la mejor condición IN-sample es sistemáticamente más alta con régimen (≈ +1,2 a +1,5 % por operación vs +0,9 a +1,0 %) y que la fracción de condiciones "positivas" en todo el desarrollo sube (SHORT: de 0,5 % a ~3 %), pero la misma condición vuelve a ≈ 0 o negativo OUT: el hueco IN − OUT crece (promedio de las 4 combinaciones ≈ 1,0 pp en A → 1,4 pp en B), señal clásica de que el espacio más grande produce mejores aparentes y no mejores reales. En el walk-forward, en cambio, B no tiene más sobrevivientes (82 vs 83 y 47 vs 58 pasan VALIDATION; 20 % menos condiciones seleccionadas y 20 % menos operaciones OOS), de modo que el filtro de TRAIN no se infla. La PBO es muy variable con la semilla (B LONG 0,60 vs 0,24; el OUT del mejor, −0,24 % vs +0,13 %): no se saca ninguna conclusión de una sola semilla.
- Respuesta a la pregunta del experimento: **agregar tendencia 4h, tendencia diaria y volatilidad relativa no mejora la generalización OOS** del procedimiento actual; lo único que aumenta es el sesgo de selección in-sample. Resultado negativo, válido y registrado.
- Predicción previa (R1 y R2 no se cumplen, |t pareado| < 2, B no mejor): se cumplió.

**Cuentas.** Hipótesis de este experimento: 1.350.000 (walk-forward B: 7.500 × 90 folds × 2 lados) + 30.000 (PBO B: 7.500 × 2 lados × 2 semillas) = 1.380.000; **acumulado 2.911.500**. **K = 6** desde este experimento (B LONG y B SHORT se suman al universo por las tres condiciones de pertenencia declaradas arriba; no hubo ablaciones: las tres familias de features se probaron juntas, como una sola variante por lado).
**Decisión.** (1) Las features de régimen quedan implementadas y probadas pero **apagadas por defecto** (`REGIME_FEATURES=False`); no se usan en los experimentos siguientes salvo como componente de una estructura distinta. (2) No se hace control de placebo ni ablación: R1 no se cumplió, así que no hay mejora que explicar. (3) Holdout cerrado; sin candidato. Experimentos de búsqueda seguidos sin avance: 3 (EXP-001, 002, 008; los metodológicos no cuentan); el umbral para revisar el rumbo es 10, pero la señal es consistente: **el costo (≈ 0,25 % por operación) y la falta de información en condiciones simples sorteadas aleatoriamente** dominan, no la falta de features.
**Próximo paso (a decidir con el usuario).** Opciones: (a) condiciones estructuradas "contexto + disparador" (idea B): los tres operandos de régimen como contexto y un disparador rápido, con muchas menos combinaciones que la búsqueda aleatoria; (b) cambiar la relación costo/ganancia (TP/SL más grandes o proporcionales al ATR, horizontes más largos: menos operaciones y más recorrido por operación frente a un costo fijo); (c) validez adicional (CPCV, PBO sobre el lift). No se avanza con ATR, volumen ni otras features hasta que se decida.

### EXP-009 — Búsqueda estructurada "contexto + disparador" vs búsqueda aleatoria (2026-10-05)
**Pregunta.** ¿Es mejor buscar condiciones como combinaciones aleatorias de features, o como una estructura explícita de contexto de mercado + evento disparador, con un presupuesto de candidatos comparable? Se evalúa el *procedimiento de búsqueda*, no una condición particular.
**Hipótesis (del usuario, registrada antes de correr):** el problema puede estar parcialmente en cómo se buscan las condiciones; una búsqueda que separe un contexto lento de un disparador rápido puede producir menos hipótesis efectivas, menos selección por azar y mejor generalización OOS. **Predicción de Claude (escrita antes de correr):** no pasa R1 ni R2; selecciona *menos* condiciones en TRAIN que la búsqueda aleatoria (estructuras más raras → muchas con < 30 operaciones) y un mejor-IN algo menor; PBO no mejor de forma consistente; la rentabilidad sigue limitada por el costo (≈ 0,25 % por operación).
**Representación (explícita, no etiquetada a posteriori).** Nuevo tipo `ContextTrigger(context, trigger)` en `conditions.py`: el constructor *exige* que el contexto sea un ESTADO y el disparador un EVENTO (si no, `ValueError`). Se confirma en la vela t sólo si al cierre de t el contexto es verdadero Y el disparador ocurre en esa misma vela; entrada en `Open[t+1]` (sin cambios). Como el disparador es un evento, un contexto verdadero durante 50 velas no genera 50 entradas (test). Profundidad: contexto ≤ 2, disparador ≤ 2, total = 1 + máx(contexto, disparador) ≤ `MAX_CONDITION_DEPTH` (= 3 para esta búsqueda); la etapa 2 (combinaciones) se omite en este modo.
**Contexto (definido antes de correr).** Hojas `Compare(operando de régimen, op, umbral)` con los operandos de EXP-008, sin features nuevas: `HTFTrend("4h", n ∈ [6, 60])`, `HTFTrend("1D", n ∈ [5, 100])`, `RelativeVolatility(corto ∈ [5, 30], largo ∈ [60, 300])`, con pesos iguales. Un contexto tiene 1 o 2 hojas distintas unidas por AND (profundidad 1 o 2). Umbrales: cuantiles de la distribución del operando en TRAIN. Coherencia con la dirección: LONG = tendencia **>** umbral con cuantil en [0,50, 0,95] (tendencia por encima de su mediana); SHORT = tendencia **<** umbral con cuantil en [0,05, 0,50]; la volatilidad relativa no tiene dirección (el operador `<`/`>` se sortea; cuantil en [0,05, 0,95]). No se prueba contexto contrario a la dirección (sería una variante aparte y se contaría como hipótesis nueva).
**Disparadores (4 familias, pesos iguales, todas expresables con el árbol existente; sin features nuevas).** LONG usa cruces "above" y SHORT "below":
1. `rsi_cross`: RSI(p) cruza un umbral X (cuantil de TRAIN, [0,05, 0,95]).
2. `macd_cross`: la línea MACD cruza su señal.
3. `ret_cross`: return(N) cruza un umbral X (movimiento).
4. `rsi_recovery` (pullback/recuperación): "RSI estuvo en zona extrema en alguna de las N velas previas (N ∈ [2, 25]) Y cruza un nivel de recuperación": LONG = RSI < X_bajo en las N velas previas y cruza X_alto hacia arriba; SHORT = el espejo (RSI > X_alto previo y cruza X_bajo hacia abajo), con X_bajo < X_alto cuantiles de TRAIN. Es "alguna vela" (OccurredWithin) y no "todas las N": "todas" exigiría profundidad 3 y el cruce simple ya implica que la vela anterior estaba del otro lado.
*No incluido:* **breakout** (Close > máximo de las últimas N velas): no se puede expresar con el árbol y los operandos actuales (falta un operando de máximo/mínimo móvil); agregarlo sería una feature nueva, que se pidió no hacer en este experimento. Queda como variante futura (contaría como variante nueva).
**Presupuesto de hipótesis (idéntico en los tres procedimientos).** 7.500 condiciones evaluadas por fold y por lado. Procedimientos: **S** = estructurada (nuevo); **A1** = aleatoria con las features de régimen disponibles (EXP-008 B): *misma información* que S, sólo cambia la forma de buscar → es la comparación **primaria**; **A0** = aleatoria sin features de régimen (EXP-002): comparación secundaria. A0 y A1 ya se corrieron con exactamente la misma configuración (no se repiten; reproducibilidad verificada en EXP-005). Se registran por fold: candidatos generados (distintos), intentos de sorteo, descartados por repetidos, evaluados, seleccionados en TRAIN y que sobreviven VALIDATION (`n_attempts`, `n_discarded_duplicate` en `wf_summary.csv`).
**Constantes.** BTCUSDT 1h Binance, mismo dataset y folds que EXP-002/008 (TRAIN 2.500 / VAL 720 velas, 90 folds, rolling), TP 5 % / SL 3 % / H 100, `until_exit`, `filter_mode=both`, costos `typical` decide y `conservative` robustez, semilla 42, holdout cerrado. No se agrega ATR, volumen ni otras features/temporalidades (contexto 4h/1D, disparador 1h).
**Causalidad.** Operandos de régimen sin cambios (tests de EXP-008). Nuevos tests (`tests/test_structured.py`, 8): validación estado/evento, contexto activo ≠ entradas repetidas, coherencia de dirección y profundidad de lo generado, toda señal estructurada ⊆ evento disparador, truncación/perturbación del futuro sobre operandos y señales estructuradas, contabilidad del presupuesto, etapa 2 omitida, y que el modo aleatorio no cambió (test dorado de EXP-008). Además `run_lookahead.py --search-mode structured` sobre 5.000 estructuras (la mitad LONG, la mitad SHORT).
**Hipótesis probadas.** S: 7.500 × 90 folds × 2 lados = 1.350.000, más PBO de S (7.500 × 2 lados × 2 semillas = 30.000): +1.380.000; **acumulado 2.911.500 → 4.291.500**.
**K (Reality Check) — antes y después** (definición en "Aclaración de la regla 7 y definición de K"):
- *Antes de EXP-009, K = 6*: EXP-001, EXP-002 y EXP-008-régimen (A0, A1), cada uno LONG y SHORT, procedimientos completos evaluados sobre la misma historia OOS (intersección de 52.240 velas), mismo activo, costos, H, TP/SL y filtros.
- *Después, K = 8*: S-LONG y S-SHORT cumplen las tres condiciones de pertenencia (mismo activo/datos/costos/filtros/H/TP-SL; serie OOS alineable con los folds de EXP-002; podría reportarse como "el resultado"). Se trata como **una** variante por lado (las cuatro familias de disparador y tres de contexto juntas; sin ablaciones). Si luego se prueba otro conjunto de disparadores, cada conjunto será otra variante y K crecerá en consecuencia. Sensibilidad: Reality Check con K = 6 sin las variantes de EXP-001.
**Reglas de decisión (fijadas antes de ver los resultados de S; no modifican las reglas existentes).**
- R1 *(mejora relativa; 4 comparaciones: {LONG, SHORT} × {A1 primaria, A0 secundaria})*: t pareado entre folds de (S − baseline) sobre `oos_pooled_mean_net` ≥ 2,5 **y** t HAC (3H) de la serie diferencia ≥ 2 (Bonferroni para 4 comparaciones, 89 g.l., exige 2,28). También se informa el t pareado del lift y de `conservative`.
- R2 *(candidato absoluto, por lado)*: regla 4 con K = 8: t entre folds ≥ máx(3, Bonferroni(8; 89 g.l.) = 2,55) = 3 en neto y en lift, neto OOS > 0 en `conservative`, `oos_hac_t_3H` ≥ 2, ≥ 100 operaciones OOS, y Reality Check (K = 8) con p < 0,05.
- Una mejora de S se considera **evidencia a favor** sólo si se cumplen TODOS: (1) R1 contra A1; (2) la mejora también aparece en `conservative` (no sólo en `typical`/`optimistic`); (3) no se explica por más hipótesis: el presupuesto es igual por diseño y además S no selecciona más condiciones en TRAIN ni sobrevive más en VALIDATION que A1; (4) el otro lado no empeora fuerte (t pareado ≥ −2 en el lado que no mejora); (5) Reality Check y PBO no la contradicen (PBO promedio de S ≤ PBO de A1 y mejor-OUT de S ≥ mejor-OUT de A1); (6) cumple R2 para poder llamarse candidato.
- Escenarios que se registran explícitamente al cerrar (se marca cuál ocurrió): (a) S no mejora; (b) S mejora el lift pero sigue perdiendo; (c) S reduce la PBO / la brecha IN − OUT pero no consigue rentabilidad; (d) S mejora un lado y empeora el otro; (e) S cumple R1 y R2 → **detenerse y mostrar al usuario** (candidato, folds, métricas OOS, HAC, Reality Check, PBO, hipótesis, K, comparación S vs A1 vs A0); (f) otro, descrito.
- **El holdout no se abre** aunque aparezca un candidato; sólo con autorización explícita.
**Comparación de PBO.** `run_pbo.py --search-mode structured` (semillas 42 y 7) vs A0 (EXP-004) y A1 (EXP-008): PBO, mejor IN, mejor OUT, brecha IN − OUT (¿S la reduce?; "peor IN pero mejor OUT" sería lo más interesante, pero debe pasar los criterios OOS para valer).
**Comandos.** `pixi run python run_research.py --csv "D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv" --walk-forward --wf-train-bars 2500 --wf-val-bars 720 --side LONG SHORT --tp 0.05 --sl 0.03 --horizon 100 --cooldown-mode until_exit --filter-mode both --cost-scenario typical --no-events --search-mode structured --depth 3 --output results/exp009/structured`; `run_lookahead.py --search-mode structured`; `run_pbo.py --search-mode structured --seed {42,7}`; comparación `run_structure_comparison.py`.

**Resultados (2026-10-05).** Look-ahead de las estructuras (`run_lookahead.py --search-mode structured`, 5.000 estructuras LONG/SHORT, 6.054 operandos, 15 cortes): **0/6.054** operandos, **0/5.000** señales y **0/600** chequeos de entradas con diferencias (informativo: 687/6.054 operandos dependen del arranque de la historia: los de ventana larga). Presupuesto cumplido: **7.500 condiciones evaluadas por fold y lado** en S (675.000 por lado; 0 descartadas por repetidas; 675.000 intentos = 675.000 evaluadas), igual que A0 y A1.

Walk-forward de 90 folds, costos `typical` salvo donde se indica. A0 = aleatoria sin features de régimen (EXP-002), A1 = aleatoria con las features de régimen (EXP-008), S = estructurada:

| | A0 LONG | A1 LONG | **S LONG** | A0 SHORT | A1 SHORT | **S SHORT** |
|---|---|---|---|---|---|---|
| Neto OOS agrupado (todas las entradas) | −0,191 % | −0,219 % | **−0,351 %** | −0,146 % | −0,136 % | **−0,085 %** |
| Ídem `conservative` | −0,344 % | −0,376 % | −0,515 % | −0,296 % | −0,287 % | −0,258 % |
| Media por fold del neto | −0,154 % | −0,060 % | −0,110 % | −0,184 % | −0,255 % | −0,191 % |
| Media por fold del lift | +0,053 % | +0,107 % | +0,110 % | −0,020 % | −0,029 % | −0,003 % |
| t entre folds, neto | −1,56 | −0,55 | −1,00 | −1,89 | −2,59 | −1,68 |
| t entre folds, lift | +1,13 | +1,84 | +1,76 | −0,43 | −0,64 | −0,05 |
| `oos_hac_t_3H` neto (lift) | −1,99 (+0,04) | −1,96 (+0,13) | −2,42 (−0,17) | −0,89 (−0,12) | −1,03 (−0,14) | −1,22 (−1,05) |
| Folds con neto > 0 (de los que operaron) | 39/89 | 37/89 | 34/82 | 37/74 | 33/78 | 32/68 |
| Folds que superan la línea base | 52 | 55 | 50 | 31 | 34 | 34 |
| Folds con neto > 0 en `conservative` | 32 | 32 | 29 | 31 | 32 | 27 |
| Operaciones OOS | 895.090 | 722.946 | **44.935** | 492.594 | 394.254 | **43.501** |
| Condiciones seleccionadas en TRAIN (suma de folds) | 70.595 | 56.795 | **4.870** | 44.549 | 35.992 | **5.187** |
| Sobreviven también el filtro de VALIDATION | 83 | 82 | 0 | 58 | 47 | 5 |
| Fracción media de seleccionadas con neto OOS > 0 | 42,2 % | 42,0 % | 43,3 % | 46,1 % | 42,4 % | 43,9 % |
| Fracción media que supera la línea base OOS | 52,3 % | 51,8 % | 54,2 % | 49,4 % | 48,3 % | 50,0 % |

**R1 (S − baseline, mismos folds; 4 comparaciones):**
| | dif. media por fold (neto) | t pareado | t pareado `conservative` | HAC (3H) de la diferencia | bootstrap p(S > base) | R1 |
|---|---|---|---|---|---|---|
| S vs A1 LONG (primaria) | +0,044 % | 0,93 (n = 82) | 1,03 | 1,53 | 0,077 | NO |
| S vs A1 SHORT (primaria) | +0,015 % | 0,30 (n = 68) | 0,38 | 0,80 | 0,195 | NO |
| S vs A0 LONG | +0,069 % | 1,26 | 1,34 | 1,57 | 0,064 | NO |
| S vs A0 SHORT | +0,013 % | 0,25 | 0,31 | 0,60 | 0,253 | NO |
**R2 (candidato, K = 8):** ningún lado: t entre folds de neto −1,00 (LONG) y −1,68 (SHORT), `conservative` negativo (−0,52 % y −0,26 %), HAC −2,42 y −1,22 → NO.
**Reality Check** (bloque 300, 1.000 remuestreos), K = 8 (EXP-001, A0, A1, S; cada uno LONG/SHORT; T = 52.240): benchmark cero, `typical`: p = 1,000 (S LONG individual 0,97; S SHORT 0,80); exceso sobre la línea base, `typical`: p = 0,937 (mejor A1 LONG, individual 0,38; S LONG 0,54, S SHORT 0,89); `conservative`: 1,000 / 0,946. Sensibilidad K = 6 sin EXP-001 (T = 64.800): 0,999 / 0,870 / 1,000 / 0,879.
**PBO del proceso de selección** (7.500 condiciones, 16 bloques; semillas 42 / 7):

| | PBO | Mejor IN | Esa misma OUT | IN − OUT | P(pérdida OUT) | % condiciones con media > 0 en todo el desarrollo |
|---|---|---|---|---|---|---|
| A0 LONG | 0,72 / 0,49 | +0,87 / +0,97 % | −0,30 / −0,09 % | 1,16 / 1,05 pp | 0,84 / 0,62 | 13 / 13 |
| A1 LONG | 0,60 / 0,24 | +1,45 / +1,46 % | −0,24 / +0,13 % | 1,69 / 1,33 pp | 0,70 / 0,33 | 15 / 15 |
| **S LONG** | 0,43 / 0,38 | +1,88 / +1,84 % | +0,06 / +0,12 % | 1,82 / 1,72 pp | 0,47 / 0,41 | 39 / 39 |
| A0 SHORT | 0,24 / 0,28 | +0,94 / +0,94 % | +0,10 / −0,05 % | 0,84 / 0,99 pp | 0,44 / 0,51 | 0,5 / 0,6 |
| A1 SHORT | 0,34 / 0,23 | +1,21 / +1,22 % | −0,11 / −0,07 % | 1,32 / 1,29 pp | 0,57 / 0,49 | 2,8 / 3,1 |
| **S SHORT** | 0,44 / 0,42 | +1,75 / +1,75 % | −0,13 / +0,10 % | 1,88 / 1,65 pp | 0,62 / 0,56 | 14 / 14 |

**Lectura.**
- *Escenario ocurrido:* **(a) S no mejora** (R1 = NO en las 4 comparaciones, R2 = NO). No se cumple el criterio 1 de "evidencia a favor" (mejora OOS estadísticamente defendible), de modo que no hace falta evaluar el resto. Es además un caso parcial de **(d)**: el lado LONG muestra una tendencia a favor (t pareado 0,93–1,26, HAC 1,5–1,6, bootstrap p ≈ 0,06–0,08), pero no alcanza los umbrales fijados de antemano (2,5 y 2) y el SHORT casi no se mueve; con 4 comparaciones corregidas no es defendible. El retorno agrupado de S LONG es *peor* (−0,35 % vs −0,22 %); el de S SHORT algo mejor (−0,09 % vs −0,14 %): no es una mejora consistente.
- *Qué sí cambia con la estructura:* (i) **entre 9 y 16 veces menos operaciones OOS y entre 7 y 12 veces menos condiciones seleccionadas** en TRAIN (los disparadores son eventos raros y muchas estructuras no llegan al mínimo de casos): menos exposición al costo, pero el lift por fold queda igual que en A1 (LONG +0,110 % vs +0,107 %; SHORT −0,003 % vs −0,029 %). (ii) La fracción de seleccionadas con neto OOS > 0 (43 %) y de las que superan la base (54 % / 50 %) es la de siempre. (iii) La filtración de VALIDATION casi vacía (0 y 5 sobrevivientes) es mecánica: con un mes de VALIDATION casi ninguna estructura reúne 30 operaciones; no afecta al retorno OOS agrupado, que no depende de ese filtro.
- *PBO / ganadores aparentes:* S tiene un mejor IN mucho más alto (+1,75 a +1,88 % vs +0,9 a +1,5 %), una fracción de condiciones "positivas" en todo el desarrollo de 39 % (LONG) y 14 % (SHORT) —contra 15 % y 3 % en A1—, y una brecha IN − OUT *mayor* (1,65–1,88 pp vs 1,3–1,7 pp en A1). El mejor OUT es algo más alto (LONG +0,06/+0,12 %; SHORT −0,13/+0,10 %), pero la PBO sola no cambia claramente (promedio LONG 0,41 vs 0,42 en A1; SHORT 0,43 vs 0,29) y la variación entre semillas (±0,2) es mayor que las diferencias. **No ocurrió "peor IN pero mejor OUT"**: S tiene mejor IN y un OUT apenas mayor. Los "positivos" en todo el desarrollo (39 %) reflejan sobre todo que las estructuras coherentes con la dirección heredan el sesgo direccional del período de desarrollo, no información: fuera de muestra se desvanecen (R1/R2).
- *Reality Check:* no contradice ni respalda (p ≥ 0,87 en todas las variantes).
- *Predicción previa:* acertada en que S no pasa R1 ni R2 y en que selecciona menos condiciones en TRAIN (7–12×); **errada** en que S tendría un mejor-IN algo menor (resultó mayor).
- **Respuesta a la pregunta de EXP-009:** con este diseño (4 familias de disparador, 3 de contexto, 7.500 candidatos por fold, TP 5 %/SL 3 %/H 100 y costos `typical`), buscar con una estructura explícita contexto + disparador **no es mejor** que buscar combinaciones aleatorias: no mejora la generalización OOS de forma defendible, aunque reduce entre 9 y 16 veces el número de operaciones. Ningún procedimiento probado (A0, A1, S) es rentable fuera de muestra.

**Cuentas.** Hipótesis de este experimento: 1.350.000 (S, walk-forward: 7.500 × 90 folds × 2 lados) + 30.000 (PBO de S) = 1.380.000; **acumulado 4.291.500**. (Una primera corrida del walk-forward se interrumpió en el fold 34 por lentitud —competía por CPU con otras corridas— y se relanzó con la misma configuración y semilla tras acelerar el cálculo de features con memoria por DataFrame, que da exactamente los mismos valores; no se miraron sus resultados parciales y las condiciones regeneradas son las mismas, así que no suman hipótesis.) **K = 8** desde este experimento (S LONG y S SHORT se agregan al universo; una variante por lado, sin ablaciones; ver su definición arriba).
**Decisión.** (1) El generador estructurado queda implementado y probado (`SEARCH_MODE="structured"`, apagado por defecto); no se sigue refinando triggers para "hacerlo funcionar" (cada cambio sería una variante nueva que sube K y las hipótesis). (2) Holdout cerrado; sin candidato. (3) Experimentos de búsqueda seguidos sin avance: **4** (EXP-001, 002, 008, 009); el umbral de CLAUDE.md para revisar el rumbo es 10, pero el patrón es consistente en los cuatro: ningún procedimiento supera el costo, y ni más features ni más estructura cambian eso. La explicación más simple, compatible con todos los resultados, es que **el costo (≈ 0,25 % por operación) es del mismo orden que cualquier efecto detectable con TP 5 % / SL 3 % y condiciones sobre BTC 1h**.
**Próximo paso (a decidir con el usuario).** Con la variable "forma de buscar" y la variable "información de contexto" ya exploradas sin resultado, la palanca que queda es la **relación costo/ganancia**: TP/SL mayores o proporcionales al ATR, horizontes más largos y/o temporalidades más lentas (menos operaciones y más recorrido por operación frente a un costo casi fijo). También: abrir la discusión sobre si la búsqueda de reglas de entrada sobre una sola serie (BTC 1h) tiene salida, o si conviene ampliar a otros activos. No se avanza con ATR, volumen ni otras features hasta que se decida.

### EXP-010 — Salidas TP/SL proporcionales al ATR vs TP/SL fijos (2026-10-06)
**Contexto.** Cuatro experimentos de búsqueda (EXP-001, 002, 008, 009) no dieron rentabilidad OOS defendible con la geometría de salida fija TP 5 % / SL 3 % / H 100 sobre BTCUSDT 1h con costos `typical`. Esos experimentos cambiaron el espacio de entradas y la forma de buscar; nunca la geometría de salida.
**Hipótesis H1 (del usuario).** Adaptar TP y SL a la volatilidad contemporánea mediante ATR puede mejorar el retorno OOS y/o la estabilidad entre folds respecto de los exits fijos actuales. H1 no afirma que ATR produzca una estrategia rentable: pregunta si cambiar la escala de las operaciones elimina parte del problema observado.
**Restricción metodológica.** Sólo cambia la geometría de la salida. Mismo generador de entradas, presupuesto, features, profundidad, semilla, folds, filtros, `until_exit`, costos, ambigüedad, horizonte y datos que el baseline; sin features, operadores, activos ni temporalidades nuevas; holdout cerrado.
**Fórmula (implementada en `outcome_evaluator.atr_exit_levels`).** Señal confirmada al cierre de t; entrada = Open[t+1] (e = t+1); ATR = ATR de Wilder de 14 períodos (el indicador causal que ya existe, `indicators.atr`; se reutiliza, no se creó otro) medido al cierre de t, o sea ATR[t] = ATR[e−1]; los niveles quedan fijos durante toda la operación:
- LONG: TP = Open[e] + k_tp · ATR[t] ; SL = Open[e] − k_sl · ATR[t].
- SHORT: TP = Open[e] − k_tp · ATR[t] ; SL = Open[e] + k_sl · ATR[t].
Sólo dependen de Open[e] y de datos hasta t. La resolución de la operación (qué se toca primero, relleno del SL con gap en la apertura, TP con orden límite, salida por tiempo al cierre de la vela H) es exactamente la existente. **Calentamiento:** mientras el ATR no está definido (primeras 13 velas de los datos, que sólo caen en el primer TRAIN) la entrada es inválida: la señal no cuenta como operación, su resultado es NaN y la línea base del segmento también la excluye; se invalida además cualquier nivel ≤ 0.
**Variantes pre-especificadas (únicas; sin barrido de múltiplos):** V1: TP = 2 ATR, SL = 1 ATR; V2: TP = 3 ATR, SL = 1 ATR; V3: TP = 3 ATR, SL = 2 ATR; V4: TP = 4 ATR, SL = 2 ATR. Cada una en LONG y SHORT. Horizonte **H = 100 fijo** en todas (no se varía a la vez); relaciones TP:SL teóricas: V1 2:1, V2 3:1, V3 1,5:1, V4 2:1 (baseline fijo 5:3 = 1,67:1).
**Baseline y comparación primaria.** B0 = TP 5 % / SL 3 % / H 100 con el mismo procedimiento que EXP-002: aleatoria sin features de régimen (profundidad 1), 7.500 condiciones por fold y lado, semilla 42, 90 folds (TRAIN 2.500 / VAL 720 velas, rolling), `until_exit`, `filter_mode=both`, costos `typical` (decide) y `conservative` (robustez). B0 se **vuelve a correr con el código nuevo** (necesario para tener el desglose por motivo de salida) y debe reproducir al dígito los resultados de EXP-002/005; si no coincide, se detiene todo y se investiga (el modo fijo ya se verificó: los 34 arrays de la tabla de resultados sobre BTC real son idénticos antes y después del cambio, y hay un test con números dorados). Todas las variantes usan *exactamente* el mismo procedimiento de búsqueda; las condiciones candidatas son las mismas (la generación no depende de TP/SL), cambia cuáles se seleccionan en TRAIN porque el filtro usa los resultados de la operación. Los umbrales de los filtros se dejan idénticos (`MIN_P_TP_FIRST = 0,15`, lift de P(TP) ≥ 0,03, retorno neto > 0): su significado en P(TP) cambia con la geometría; no se retocan (sería una regla de selección nueva).
**Presupuesto y contabilidad (registrado antes de correr).**
- Hipótesis (unidad del proyecto: condición evaluada; una hipótesis = condición × lado × TP × SL × H × período): cada variante evalúa 7.500 × 90 folds × 2 lados = 1.350.000. Las condiciones son las mismas que en B0, pero con otra salida son hipótesis distintas. V1–V4: 4 × 1.350.000 = **5.400.000**. La repetición de B0 es determinista e idéntica a EXP-002: **0 nuevas**. **Acumulado: 4.291.500 → 9.691.500.** No se cuenta cada fold como hipótesis independiente aparte de lo ya contado (la unidad sigue siendo condición × fold × lado, como en EXP-002/008/009); la selección interna del walk-forward (TRAIN) queda absorbida en el procedimiento y no suma.
- **K del Reality Check:** *antes de EXP-010, K = 8* (EXP-001, EXP-002, EXP-008-régimen y EXP-009-estructurada, cada uno LONG/SHORT). *Después, K = 16*: V1–V4 × LONG/SHORT = 8 variantes nuevas, cada una un procedimiento completo evaluado sobre la misma historia OOS (los folds de EXP-002, con intersección de 52.240 velas), mismo activo/datos/costos/filtros/H, que podría reportarse como "el resultado"; TP/SL distintos hacen variantes distintas por la definición de la regla 7. B0 re-corrida no es una variante nueva (es EXP-002).
- **Comparaciones contra el baseline** (4 variantes × 2 lados = 8 comparaciones pareadas): no son variantes ni suman a K; son pruebas múltiples sobre la *mejora relativa*, que se corrigen con Bonferroni por 8 comparaciones (89 g.l.: t ≥ 2,55). El Reality Check con K = 16 responde otra pregunta (¿alguna variante rinde > 0 en términos absolutos?). No se corrige dos veces el mismo problema.
- **Umbrales calculados antes de mirar resultados:** Bonferroni(8 comparaciones; 89 g.l.) = 2,55; Bonferroni(K = 16; 89 g.l.) = 2,80 < 3, de modo que el umbral absoluto sigue siendo t ≥ 3.
**Reglas de decisión (fijadas ahora; no se modifican después).**
- *R1 (mejora relativa, por variante y lado):* t pareado entre folds de (variante − B0) sobre `oos_pooled_mean_net` ≥ 2,55 **y** t HAC (3H) de la serie diferencia ≥ 2 **y** el t pareado en `conservative` ≥ 2. Se informan además el bootstrap de P(variante > B0), los folds con neto > 0, los folds que superan la línea base y el lift por fold.
- *R2 (aceptación absoluta, regla 4 con K = 16):* t entre folds ≥ 3 en retorno neto y en lift; neto OOS agrupado > 0 con `typical` y con `conservative`; `oos_hac_t_3H` ≥ 2; ≥ 100 operaciones OOS; Reality Check (K = 16) con p < 0,05; y R1 cumplido.
- *Casos (precedencia D > C > B > A):* **A negativo** = ninguna (variante, lado) cumple R1. **B mejora relativa** = alguna cumple R1 pero el retorno neto OOS agrupado (`typical`) sigue ≤ 0 en todas las que la cumplen. **C mejora fuerte no robusta** = alguna tiene retorno neto OOS agrupado > 0 y t entre folds ≥ 2 pero no cumple todo R2 (estabilidad, HAC, `conservative`, o corrección por múltiples hipótesis). **D evidencia fuerte** = alguna cumple R2 completa → **detenerse y mostrar al usuario**; el holdout no se abre ni en ese caso sin autorización explícita.
- Qué implicaría cada caso: A → adaptar TP/SL por ATR no resuelve el problema observado; la geometría de salida con esos múltiplos no explica el fracaso. B → ATR mejora la geometría pero todavía no hay evidencia de estrategia rentable; no justifica el holdout; el siguiente experimento (decisión posterior) podría estudiar horizonte/escala temporal. C → resultado de interés para investigación, insuficiente como evidencia. D → mostrar candidato, folds, métricas OOS, HAC, Reality Check, PBO, hipótesis, K y comparación con B0.
**Métricas (por variante y lado, `typical` y `conservative`).** Neto OOS por fold; lift contra la línea base por fold; t de la diferencia pareada con B0; HAC de la diferencia; bootstrap de P(variante > B0); folds con trades; folds con neto > 0; folds que superan la línea base; operaciones OOS; retorno agrupado; t entre folds; `oos_hac_t_3H`. **Motivo de salida** de las operaciones OOS: cantidad, porcentaje, retorno medio y contribución al retorno total para TP_FIRST, SL_FIRST, NONE y AMBIGUOUS (la serie OOS guarda ahora esas sumas), más distancia media de TP/SL (% del precio) y duración media. Regla de lectura fijada de antemano para el horizonte: si NONE ≥ 20 % de las operaciones OOS en alguna variante, H = 100 se considera candidato a revisión en un experimento posterior (no se cambia en éste). Reality Check (K = 16) con bloque 300 y 1.000 remuestreos; PBO sólo si corresponde (ver más abajo).
**PBO.** `run_pbo.py` mide la degradación de elegir "la mejor condición" entre 7.500 sorteadas en una geometría de salida dada; no se corre aquí (la comparación pareada por fold y el Reality Check responden la pregunta del experimento sin sumar 120.000 hipótesis de PBO). Se deja para el caso D o C si hace falta.
**Orden de ejecución (fijado).** (1) Tests: 75 pasan (13 nuevos en `tests/test_atr_exits.py`: causalidad del ATR por truncación y por recálculo sin datos posteriores a t; truncación y perturbación del futuro sobre los niveles (LONG y SHORT) con un canario que mira t+1 y se detecta; fórmula de niveles LONG/SHORT; niveles fijados al entrar y salidas exactamente en ellos; calentamiento (sin ATR → entrada inválida, NaN, excluida de señales y línea base); ambigüedad TP/SL en la misma vela con política conservadora; invariancia ante datos posteriores a la operación; baseline fijo con números dorados; consistencia del desglose por motivo de salida). (2) `run_lookahead.py --exit-mode atr` para los cuatro pares de múltiplos. (3) Recién después el walk-forward (B0 + V1–V4). No se miran resultados parciales para cambiar la metodología.
**Comandos.** Base: `pixi run python run_research.py --csv "D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv" --walk-forward --wf-train-bars 2500 --wf-val-bars 720 --side LONG SHORT --horizon 100 --cooldown-mode until_exit --filter-mode both --cost-scenario typical --no-events`; B0: `--tp 0.05 --sl 0.03 --output results/exp010/b0`; variantes: `--exit-mode atr --tp-atr K --sl-atr K --output results/exp010/vN`. Comparación: `run_atr_comparison.py`.

**Resultados (2026-10-06).** *Regresión:* B0 re-corrida con el código nuevo reproduce **idénticas** (20 columnas numéricas de `wf_summary.csv`, diferencia máxima 0) las corridas de EXP-002 para LONG y SHORT: el cambio de código no alteró el baseline. *Look-ahead* (antes del WFO): 0 cambios en 588 operandos, 1.000 señales, 100 + 100 chequeos de entradas y en los niveles de TP/SL, para cada uno de los 4 pares de múltiplos y para LONG y SHORT.

90 folds, costos `typical` salvo donde se indica (B0 = TP 5 % / SL 3 %; V1–V4 con salidas por ATR; H = 100 en todas):

| | Neto OOS agrupado | Ídem `conservative` | Media por fold del neto | Media por fold del lift | t folds neto | t folds lift | `oos_hac_t_3H` neto | Folds neto > 0 | Folds > base | Operaciones OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| B0 LONG | −0,191 % | −0,344 % | −0,154 % | +0,053 % | −1,56 | +1,13 | −1,99 | 39/89 | 52 | 895.090 |
| V1 2/1 LONG | −0,250 % | −0,408 % | −0,222 % | +0,057 % | **−10,40** | **+3,69** | −9,28 | 15/89 | 56 | 463.501 |
| V2 3/1 LONG | −0,261 % | −0,412 % | −0,217 % | +0,065 % | −7,80 | +3,99 | −7,48 | 18/89 | 61 | 711.920 |
| V3 3/2 LONG | −0,273 % | −0,408 % | −0,192 % | +0,075 % | −3,50 | +2,81 | −3,91 | 30/90 | 56 | 1.049.487 |
| V4 4/2 LONG | −0,241 % | −0,381 % | −0,218 % | +0,069 % | −2,86 | +1,87 | −3,36 | 33/89 | 55 | 1.015.441 |
| B0 SHORT | −0,146 % | −0,296 % | −0,184 % | −0,020 % | −1,89 | −0,43 | −0,89 | 37/74 | 31 | 492.594 |
| V1 2/1 SHORT | −0,255 % | −0,396 % | −0,255 % | +0,008 % | **−11,90** | +0,45 | −9,25 | 3/89 | 50 | 504.128 |
| V2 3/1 SHORT | −0,277 % | −0,423 % | −0,308 % | −0,018 % | −10,65 | −0,81 | −7,26 | 13/89 | 44 | 611.678 |
| V3 3/2 SHORT | −0,259 % | −0,387 % | −0,254 % | +0,022 % | −4,07 | +0,64 | −3,60 | 28/87 | 50 | 660.769 |
| V4 4/2 SHORT | −0,287 % | −0,417 % | −0,238 % | +0,042 % | −3,29 | +1,28 | −3,27 | 30/87 | 52 | 632.026 |

**Comparación pareada (variante − B0, mismos folds; R1 exige t ≥ 2,55, HAC ≥ 2 y t pareado en `conservative` ≥ 2):** todas las diferencias medias por fold son ≤ 0 salvo V3 SHORT (+0,002 %) y V4 SHORT (+0,023 %); t pareados entre −0,97 y +0,32; t HAC de la diferencia entre −2,31 y −0,41; bootstrap P(variante > B0) entre 0,67 y 0,99. **R1 = NO en las 8 (variante, lado).** Detalle: V1 L −0,068 % (t −0,76), V1 S −0,051 % (−0,58), V2 L −0,063 % (−0,76), V2 S −0,071 % (−0,89), V3 L −0,037 % (−0,53), V3 S +0,002 % (+0,03), V4 L −0,061 % (−0,97), V4 S +0,023 % (+0,32).
**R2:** ninguna variante tiene retorno neto OOS agrupado > 0 (ni en `typical` ni en `conservative`); t entre folds de neto entre −2,86 y −11,90.
**Reality Check, K = 16 (T = 52.240):** benchmark cero, `typical`: p = 1,000 (mejor B0 SHORT); `conservative`: 1,000; exceso sobre la línea base, `typical`: p = 0,812 (mejor V1 LONG, p individual 0,21); `conservative`: 0,849. Ninguna variante V tiene p individual < 0,2.

**Motivo de salida de las operaciones OOS** (todas las condiciones seleccionadas; porcentaje de las operaciones; retorno neto medio por operación; entre paréntesis la contribución al retorno medio por operación, que suma el neto agrupado):

| | TP_FIRST | SL_FIRST | NONE | AMBIGUOUS | TP / SL medios (% del precio) | Duración media (velas) |
|---|---|---|---|---|---|---|
| B0 LONG | 32,4 % · +4,76 % (+1,55) | 55,6 % · −3,24 % (−1,80) | 11,8 % · +0,60 % (+0,07) | 0,1 % | 5,00 / 3,00 | 37,6 |
| B0 SHORT | 31,9 % · +4,78 % (+1,52) | 52,7 % · −3,26 % (−1,71) | 15,4 % · +0,31 % (+0,05) | 0,1 % | 5,00 / 3,00 | 41,4 |
| V1 LONG | 32,8 % · +2,47 % (+0,81) | 66,7 % · −1,58 % (−1,06) | 0,0 % | 0,4 % | 2,68 / 1,34 | 7,2 |
| V1 SHORT | 33,5 % · +1,96 % (+0,66) | 65,8 % · −1,37 % (−0,90) | 0,0 % | 0,7 % | 2,22 / 1,11 | 7,4 |
| V2 LONG | 24,9 % · +3,25 % (+0,81) | 74,7 % · −1,44 % (−1,07) | 0,2 % | 0,2 % | 3,55 / 1,18 | 10,4 |
| V2 SHORT | 24,9 % · +2,96 % (+0,74) | 74,7 % · −1,35 % (−1,01) | 0,1 % | 0,3 % | 3,27 / 1,09 | 10,4 |
| V3 LONG | 39,3 % · +3,05 % (+1,20) | 58,9 % · −2,53 % (−1,49) | 1,5 % · +1,46 % | 0,2 % | 3,40 / 2,27 | 20,0 |
| V3 SHORT | 39,9 % · +2,77 % (+1,10) | 58,8 % · −2,31 % (−1,36) | 1,2 % | 0,1 % | 3,07 / 2,04 | 20,0 |
| V4 LONG | 32,2 % · +4,07 % (+1,31) | 64,1 % · −2,51 % (−1,61) | 3,7 % · +1,65 % (+0,06) | 0,1 % | 4,53 / 2,26 | 25,1 |
| V4 SHORT | 31,8 % · +3,57 % (+1,14) | 64,6 % · −2,22 % (−1,43) | 3,4 % · +0,37 % (+0,01) | 0,1 % | 3,92 / 1,96 | 25,1 |

**Lectura (las 9 preguntas del usuario).**
1. *¿ATR mejora respecto de TP 5 % / SL 3 %?* **No.** En el retorno neto OOS ninguna variante mejora de forma defendible (R1 = NO en las 8); en el agregado las 8 son *peores* que B0 salvo, apenas, V3 SHORT y V4 SHORT por fold (+0,002 % y +0,023 %, t 0,03 y 0,32), y en el retorno agrupado todas lo son (−0,24 a −0,29 % vs −0,19 y −0,15 %).
2. *¿Consistente entre folds?* No hay mejora; lo consistente es la pérdida: V1 y V2 pierden en 71–86 de 89 folds (V1 SHORT gana en 3/89), con t entre folds de −7,8 a −11,9 (pérdidas "significativas"); V3 y V4, de −2,9 a −4,1.
3. *¿Sobrevive HAC/bootstrap?* No hay mejora que verificar: el HAC de la diferencia es ≤ 0 en las 8 y el bootstrap da P(variante > B0) entre 0,67 y 0,99 (a favor de B0).
4. *¿Sobrevive costos conservadores?* Tampoco: con `conservative` ninguna diferencia es significativa (t pareado −0,82 a +0,49) y los retornos agrupados son −0,38 a −0,42 %.
5. *Motivo de salida:* ver tabla. AMBIGUOUS es ≤ 0,7 % en todo; TP_FIRST 25–40 %; SL_FIRST 53–75 %; **NONE** 11,8 % / 15,4 % en B0 y 0,0–3,7 % en las variantes ATR.
6. *¿H = 100 es demasiado corto?* **No hay evidencia de eso.** NONE no llega al umbral fijado (20 %) en ninguna variante; la duración media es de 38–41 velas en B0 y de 7–25 en las ATR; H = 100 casi nunca es el factor que cierra la operación. Si algo, es largo para las geometrías ATR de 1–2 ATR. No se justifica un experimento de horizonte por este motivo.
7. *¿Cambia materialmente la relación riesgo/beneficio?* En lo realizado, sí, pero sin efecto en el resultado: cociente entre ganancia media en TP y pérdida media en SL: B0 1,47; V1 1,56 (LONG) y 1,42 (SHORT); V2 2,26 y 2,19; V3 1,21 y 1,20; V4 1,62 y 1,61; y las distancias medias de TP/SL pasan de 5,0 / 3,0 % a 2,2–4,5 / 1,1–2,3 %. Pero la frecuencia de TP entre las operaciones resueltas (TP ÷ (TP + SL)) coincide casi exactamente con la de una caminata sin ventaja, SL ÷ (TP + SL) en términos de distancias: B0 36,8 % LONG y 37,7 % SHORT frente a 37,5 % teórico; V1 33,0 % y 33,8 % (33,3 %); V2 25,0 % y 25,0 % (25,0 %); V3 40,0 % y 40,4 % (40,0 %); V4 33,4 % y 33,0 % (33,3 %). Es decir: con cualquier geometría, las condiciones seleccionadas en TRAIN aciertan el TP con la frecuencia que daría una caminata sin ventaja; y el retorno neto agrupado de las variantes ATR (−0,24 a −0,29 %) es prácticamente igual al costo de ida y vuelta (≈ 0,22–0,26 %): retorno bruto ≈ 0 menos costo.
8. *¿El problema es la geometría de salida y no la búsqueda de entradas?* **La evidencia apunta a lo contrario.** Cambiar la escala de la salida cinco veces (B0, V1–V4) no mueve el retorno bruto de cero. Con las entradas seleccionadas, el TP se alcanza con la frecuencia de una caminata sin ventaja, de modo que lo que falta no es una mejor salida sino información en la entrada capaz de superar el costo. Una observación honesta que no cambia la conclusión: en LONG, V1–V3 tienen un t entre folds del lift sobre *su propia* línea base de +3,7, +4,0 y +2,8 (B0: +1,1), con el mismo lift medio (+0,06 a +0,08 % por fold vs +0,05 %) pero menos dispersión entre folds; es decir, la normalización por ATR hace *más estable* la medición del pequeño lift que ya existía (lo que H1 anticipaba como "estabilidad"), pero ese lift es unas cuatro veces menor que el costo por operación, el HAC del lift no lo confirma (0,2 a 0,7: según la regla de EXP-007 queda "no confirmado") y las diferencias pareadas contra B0 no son significativas.
9. *¿Alguna variante justifica detenerse y reconsiderar el holdout?* **No.** Caso **A (negativo)**: ninguna variante mejora de manera estadísticamente defendible al baseline; ninguna tiene retorno neto OOS > 0.

**Conclusión.** Adaptar TP/SL a la volatilidad mediante ATR (con estos cuatro pares de múltiplos y H = 100) no resuelve el problema observado. Hipótesis H1 no se sostiene en su parte de retorno; en su parte de estabilidad hay un efecto marginal sobre la dispersión del lift entre folds, sin consecuencia sobre la rentabilidad.
**Cuentas.** Hipótesis de este experimento: **5.400.000** (V1–V4: 7.500 × 90 folds × 2 lados × 4); B0 repetida: 0 nuevas; **acumulado 9.691.500**. **K = 16** desde este experimento (V1–V4 × LONG/SHORT). Las 8 comparaciones pareadas contra B0 se corrigieron por Bonferroni (t ≥ 2,55) y no suman a K. PBO no se corrió (como se pre-especificó). Holdout cerrado.
**Decisión.** (1) Las salidas por ATR quedan implementadas y probadas (`EXIT_MODE="atr"`, apagadas por defecto; el modo fijo es numéricamente idéntico a antes). (2) No se encadena ningún experimento (ni ATR + indicador, ni nuevo horizonte, ni nuevo activo). (3) Experimentos de búsqueda seguidos sin avance: **5** (EXP-001, 002, 008, 009, 010; CLAUDE.md pide revisar el rumbo a los 10).
**Próximo paso (a decidir con el usuario, después de leer esta conclusión).** Con entradas simples sobre BTC 1h, ni más información (EXP-008), ni más estructura (EXP-009), ni otra geometría de salida (EXP-010) superan un costo de ≈ 0,25 % por operación: en todas las geometrías la tasa de acierto es la de una caminata sin ventaja. Lo que queda por probar cambia el *problema* y no la búsqueda: (a) temporalidades más lentas (4h/1D como temporalidad de operación), donde el movimiento por operación es mucho mayor que el costo; (b) otros activos u otros mercados (más historia independiente, otra estructura de costos); (c) revisar el objetivo (por ejemplo, reglas que no sean sólo de entrada: tamaño/gestión, o estrategias de menor frecuencia); (d) más validez (CPCV, PBO sobre el lift). Cada una es un experimento separado y suma variantes a K.

### EXP-011 — Escala temporal: BTCUSDT 1h vs 4h con la misma duración de operación (2026-10-06)
**Pregunta.** Tras EXP-001, 002, 008, 009 y 010 no hay señal de entrada que supere de forma defendible el costo de operar BTCUSDT 1h. ¿La falta de rentabilidad se debe, al menos en parte, a operar a una escala temporal demasiado rápida para que una ventaja pequeña supere los costos? Se compara 1h contra 4h cambiando **sólo** la temporalidad: sin features, salidas, activos ni métodos de búsqueda nuevos.
**Por qué 4h.** Con costos de ≈ 0,25 % por operación y movimientos típicos por barra de ≈ 0,25–0,5 % (1h), el costo es del mismo orden que el recorrido; en 4h el movimiento por barra se duplica (≈ 0,5–1,1 %) y, a igual duración máxima de la operación, la fricción porcentual por operación es la misma pero cada operación captura un movimiento mayor por barra. Es la hipótesis económica a contrastar; no se asume que sea cierta.
**Diseño económico.** Misma duración máxima: 1h: H = 100 barras = 100 h; 4h: **H = 25 barras = 100 h** (no 100 barras de 4h = 400 h). TP = 5 %, SL = 3 % (fijos, como EXP-002/010; sin ATR ni otros pares). Entrada: condición confirmada al cierre de t, entrada en Open[t+1]; en 4h, t es una vela 4h completamente cerrada y t+1 la siguiente vela 4h completa.
**Construcción de las velas 4h** (`trading_research/resample.py`, `aggregate_ohlc_strict`): a partir del CSV de 1h, alineadas a UTC (época Unix): bloques 00:00–03:59, 04:00–07:59, 08:00–11:59, 12:00–15:59, 16:00–19:59, 20:00–23:59. Open = Open de la primera vela 1h; High = máx de los High; Low = mín de los Low; Close = Close de la cuarta. Volume no se carga ni se usa (el cargador sólo toma OHLC; ninguna condición lo usa).
**Huecos.** Una vela 4h se crea sólo si el bloque tiene sus cuatro velas 1h, cada una en su instante exacto. No hay forward-fill ni OHLC inventado: los bloques incompletos se descartan y quedan como huecos de tiempo. Las velas 1h cuyo timestamp no cae en la grilla horaria (43, en febrero de 2018, con minutos y segundos corridos) no pueden asignarse a un bloque UTC sin deformarlo: se descartan y su bloque queda incompleto. Una vez descartado un bloque, la "fila siguiente" es la siguiente vela 4h completa aunque haya un hueco de tiempo entre ambas (literal a "entrada = Open de la siguiente vela 4h completa"); es el mismo tratamiento que reciben los 29 huecos de la serie de 1h (que no se corrigen: el baseline 1h no se toca). No se aplica ninguna regla nueva de "salto de hueco".
**Timestamp y disponibilidad.** El timestamp de la vela es el INICIO del intervalo (igual que en 1h/Binance). Una vela con timestamp T está disponible en T + 4h, cuando existe su cuarta vela 1h; una condición evaluada en t usa sólo datos hasta ese cierre; una vela 4h en formación nunca aparece en la serie.
**Features y parámetros.** Exactamente las mismas familias y rangos que el baseline (generador aleatorio de EXP-002: RSI, MACD, SMA, EMA, ATR%, retornos de N barras, ratios de vela; profundidad 1). **Decisión explícita:** los períodos se expresan en *barras del timeframe actual*; no se convierten horas (RSI(14) en 4h es RSI de 14 velas de 4h = 56 h, no ≈ 3,5 velas); lo mismo vale para SMA/EMA/MACD/ATR, `return(N)`, rangos de umbral y ventanas temporales. La pregunta del experimento es qué ocurre cuando el mismo espacio de representación se usa sobre otra resolución. Sin Volume, breakout, máximos/mínimos móviles, patrones, calendario, régimen, ContextTrigger, features de EXP-008 ni ATR exits.
**Búsqueda y selección.** La de EXP-002: 7.500 condiciones simples por fold y lado, semilla 42, LONG y SHORT, `filter_mode = both`, `cooldown_mode = until_exit`, mismos filtros de TRAIN (incluido el mínimo de 30 operaciones y `MIN_P_TP_FIRST = 0,15`).
**Walk-forward.** TRAIN = 625 barras (2.500 h) y VALIDATION = 180 barras (720 h), rolling, holdout 15 % cerrado. Con 19.945 velas 4h el número de folds posibles es **90** (el mismo que en 1h; comprobado con `make_folds` antes de correr); el desfase calendario entre las VALIDATION de 4h y de 1h por fold va de −110 a +18 horas (las dos series pierden barras por huecos en puntos distintos; el emparejamiento de la comparación se hace por calendario, ver abajo). 1h baseline: 90 folds de 2.500/720 barras, H = 100 (EXP-002), **re-corrido con el código nuevo** (necesario para tener el retorno bruto por operación; debe reproducir al dígito EXP-002: si no, se detiene todo).
**Costos.** Modelo y escenarios idénticos (`typical` decide, `conservative` robustez), sin reducciones. Nota: `conservative` incluye un slippage proporcional al ATR(14)/Close de las barras del timeframe actual; con barras de 4h ese ATR es ≈ 2× el de 1h, de modo que el costo `conservative` por operación es mecánicamente mayor en 4h. Es el modelo existente aplicado tal cual; se informa el costo realizado por escenario.
**Ambigüedad.** Política conservadora existente, sin cambios; se reporta la proporción AMBIGUOUS por timeframe (en la línea base sin condición: 0,03–0,05 % en 1h y 0,24–0,26 % en 4h).
**Sanity checks descriptivos (antes del WFO; no modifican el protocolo; `results/exp011/sanity.json`).** 79.909 velas 1h (2017-08-17 04:00 → 2026-10-03 23:00 UTC); 19.945 velas 4h válidas (2017-08-17 04:00 → 2026-10-03 20:00) de 20.009 bloques esperados: **0,32 % descartado** (36 incompletos con datos + 28 sin datos), 43 velas 1h fuera de la grilla horaria, 28 huecos de tiempo en 4h (29 discontinuidades en 1h). |retorno cierre-cierre|: mediana 0,251 % (1h) vs 0,500 % (4h), cuantil 0,9 1,00 % vs 2,09 %, cuantil 0,99 2,96 % vs 5,42 %; mediana de (High−Low)/Low 0,69 % vs 1,46 %. Línea base sin condición (entrar en todas las barras) con TP 5 %/SL 3 %: TP 29,2 % / 29,0 %, SL 50,2 % / 50,2 %, NONE 20,6 % / 20,5 %, duración ≈ 48 h / 49 h (LONG; 1h/4h): la geometría en horas es equivalente. Operaciones esperadas de una condición aleatoria con señales del 5 % de las barras: 9,7 (1h) y 6,1 (4h) por ventana de 720 h; costo típico ≈ 0,243 % por operación en ambas (los retornos brutos de esa referencia son ruido muestral: ≈ 200–300 operaciones). No hay anomalías graves.
**Causalidad (tests y look-ahead, antes del WFO).** 85 tests pasan (10 nuevos en `tests/test_resample.py`: vela conocida (OHLC), alineación UTC y zonas horarias, inicio a mitad de bloque, bloques incompletos descartados sin forward-fill ni relleno, ausencia de una quinta vela 1h, truncación y perturbación del futuro, canario de vela 4h abierta que se detecta, entrada = Open de la siguiente vela completa también tras un hueco, TP/SL/H/TRAIN/VAL de la especificación y H = 25 ≙ 100 h, y 1h sin cambios; los 34 arrays de la tabla de resultados de 1h siguen idénticos a los de antes de EXP-010). `run_lookahead.py --timeframe 4h --csv-timeframe 1h` sobre datos reales: **0/582 operandos, 0/1.000 señales, 0/200 chequeos de entradas** con cambios, y causalidad de la construcción 1h→4h con 14 posiciones × 5 variantes (se altera una vela 1h del mismo bloque 4h que genera la señal, del bloque siguiente, de un bloque posterior; se reemplaza el futuro; se trunca a mitad de bloque): **0 diferencias** en OHLC, señales ni entradas anteriores a la disponibilidad de esos datos.
**Contabilidad (registrada antes de correr).** Unidad del proyecto: hipótesis = condición × lado × TP × SL × H × período; una condición evaluada sobre otra serie de barras (4h) con otro H es otra hipótesis, y un procedimiento con otro timeframe/H/ventanas es otra variante (regla 7 enumera lado, TP/SL, H, ventana, filtro). Entonces: **4h = 7.500 × 90 folds × 2 lados = 1.350.000 hipótesis nuevas**; el 1h re-corrido no suma (idéntico a EXP-002). **Acumulado: 9.691.500 → 11.041.500.** **K: antes de EXP-011, K = 16; después, K = 18** (4h LONG y SHORT: procedimientos completos, mismo activo/datos de origen/costos/búsqueda/filtros, serie OOS alineable sobre una grilla horaria común —el valor de cada operación de 4h se asigna a la hora de apertura de su vela y 0 en las otras horas; las horas de cada vela 4h de VALIDATION quedan cubiertas— y podrían reportarse como "el resultado"). Duda registrada, no decidida arbitrariamente: la serie de 4h tiene otra resolución; se informa también el Reality Check con K = 16 (sin 4h), ya calculado en EXP-010. Las comparaciones 4h − 1h (2 lados × 2 vistas = 4) se corrigen por Bonferroni y no suman a K.
**Métricas.** Por timeframe y lado (typical y conservative): retorno neto OOS agrupado, media por fold, t entre folds (neto y lift), `oos_hac_t_3H` (3H = 300 h en ambos), folds con neto > 0, folds que superan la línea base interna, operaciones OOS, duración media, TP_FIRST/SL_FIRST/NONE/AMBIGUOUS (cantidad, %, neto medio, contribución). **Economía por operación y por condición:** retorno bruto, costo total (bruto − neto) y neto por operación, y por condición seleccionada y ventana de 30 días (neto = operaciones × neto por operación); costo por unidad de tiempo; diferencia 4h − 1h de cada una. **Turnover:** operaciones por año (agregado de todas las condiciones seleccionadas, sobre las horas OOS), por 1.000 barras, por condición y ventana, horas medias entre entradas (por condición) y duración media. **Descomposición** del cambio en neto por condición y ventana entre (1) menor turnover (cambio en la cantidad de operaciones por condición × neto por operación de 1h), (2) cambio en el neto por operación (cantidad de 4h × diferencia del neto por operación), y éste a su vez en retorno bruto vs costo. **Predictibilidad:** t entre folds y HAC del *lift* sobre la línea base interna, y la frecuencia de TP entre las operaciones resueltas frente a la de una caminata sin ventaja (SL ÷ (TP + SL) en distancias, 37,5 % para 5 %/3 %).
**Comparación 4h − 1h (emparejada por calendario).** Sobre una grilla horaria común y las horas cubiertas por ambas OOS: serie por hora de "neto por condición seleccionada" (suma de los netos de las operaciones abiertas esa hora ÷ condiciones seleccionadas del fold); ventanas = las 90 VALIDATION de 1h; diferencia por ventana y t pareado, t HAC (300 rezagos) de la serie horaria diferencia y bootstrap estacionario (bloque 300) de P(4h > 1h). Vista secundaria: neto *por operación* por ventana.
**Reglas de decisión (fijadas ahora; no se modifican después).**
- *R1h (mejora económica por unidad de tiempo, por lado):* t pareado de la diferencia de neto por condición y ventana ≥ 2,5, **y** t HAC de la diferencia ≥ 2, **y** t pareado en `conservative` ≥ 2. *R1t (mejora por operación):* t pareado del neto por operación por ventana ≥ 2,5 y en `conservative` ≥ 2. (4 comparaciones; Bonferroni exige 2,28.)
- *R2 (aceptación absoluta de 4h, por lado; regla 4 con K = 18):* t entre folds ≥ 3 en neto y en lift; neto OOS agrupado > 0 con `typical` y con `conservative`; `oos_hac_t_3H` ≥ 2; ≥ 100 operaciones OOS; Reality Check (K = 18) con p < 0,05; y R1h cumplido. (Bonferroni(18; 89 g.l.) = 2,84 < 3: el umbral sigue siendo 3.)
- *Escenarios:* **A** = 4h no mejora (ni R1h ni R1t) y sigue negativo → la mayor escala temporal no elimina el problema; la hipótesis del costo relativo a 1h como cuello de botella principal pierde apoyo. **B** = 4h mejora (R1h o R1t) pero el neto agrupado sigue ≤ 0 → reducir turnover y aumentar el recorrido por operación mejora la economía sin evidencia de una señal suficientemente fuerte (útil para decidir otra escala o cambiar el objetivo; no abre el holdout). **C** = 4h con neto agrupado > 0 y t entre folds ≥ 2 pero sin cumplir todo R2 → señal de investigación, no evidencia suficiente; se registra exactamente qué criterio falla. **D** = cumple R2 completa → detenerse y mostrar al usuario (procedimiento, folds, operaciones, neto, bruto, costos, HAC, Reality Check, comparación 1h/4h, hipótesis, K); no se abre el holdout sin autorización. Precedencia D > C > B > A. Una reducción de operaciones por sí sola no se interpreta como evidencia de una señal mejor: eso lo mide el neto/bruto por operación y el lift.
**Pregunta final del informe.** ¿Hay evidencia de que 1h fracasa porque ≈ 0,25 % por operación es demasiado grande frente al movimiento capturado y que 4h ofrece una relación económica más favorable? Se responderá separando: menor turnover; mayor movimiento por operación; cambio en la frecuencia de señales; cambio en el retorno bruto; en los costos; en el neto; evidencia de predictibilidad; robustez estadística.
**Comandos.** 4h: `pixi run python run_research.py --csv "D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv" --timeframe 4h --csv-timeframe 1h --walk-forward --wf-train-bars 625 --wf-val-bars 180 --side LONG SHORT --tp 0.05 --sl 0.03 --horizon 25 --cooldown-mode until_exit --filter-mode both --cost-scenario typical --no-events --output results/exp011/h4`; 1h: igual con `--timeframe 1h --wf-train-bars 2500 --wf-val-bars 720 --horizon 100 --output results/exp011/h1`. Comparación: `run_timeframe_comparison.py`.

**Resultados (2026-10-06).** *Regresión:* el 1h re-corrido con el código nuevo reproduce **idénticas** las 20 columnas numéricas de `wf_summary.csv` de EXP-002 (LONG y SHORT): el baseline 1h no cambió. 90 folds en ambos timeframes; costos `typical` salvo donde se indica.

| | 1h LONG | **4h LONG** | 1h SHORT | **4h SHORT** |
|---|---|---|---|---|
| Neto OOS agrupado | −0,191 % | −0,231 % | −0,146 % | −0,082 % |
| Ídem `conservative` | −0,344 % | −0,499 % | −0,296 % | −0,332 % |
| Media por fold del neto | −0,154 % | −0,160 % | −0,184 % | −0,185 % |
| Media por fold del lift | +0,053 % | +0,060 % | −0,020 % | +0,006 % |
| t entre folds, neto (lift) | −1,56 (+1,13) | −1,60 (+1,14) | −1,89 (−0,43) | −1,80 (+0,12) |
| `oos_hac_t_3H` neto (lift) | −1,99 (+0,04) | −2,15 (+0,29) | −0,89 (−0,12) | −1,12 (+0,03) |
| Folds con neto > 0 (de los que operaron) | 39/89 | 36/87 | 37/74 | 34/73 |
| Folds que superan la línea base interna | 52 | 48 | 31 | 35 |
| Folds con neto > 0 en `conservative` | 32 | 27 | 31 | 26 |
| Operaciones OOS (todas las condiciones seleccionadas) | 895.090 | 449.573 | 492.594 | 266.439 |
| Condiciones seleccionadas en TRAIN (suma de folds) | 70.595 | 35.745 | 44.549 | 24.267 |
| Sobreviven el filtro de VALIDATION | 83 | 34 | 58 | 18 |

**Economía por operación y por condición** (1h → 4h; "por condición y ventana" = retorno por condición seleccionada y por ventana de 30 días, promedio de los folds):

| | LONG 1h | LONG 4h | Dif. | SHORT 1h | SHORT 4h | Dif. |
|---|---|---|---|---|---|---|
| Retorno bruto por operación | +0,050 % | +0,010 % | −0,040 pp | +0,096 % | +0,160 % | +0,064 pp |
| Costo por operación (`typical`) | 0,241 % | 0,241 % | 0,000 | 0,242 % | 0,242 % | 0,000 |
| Neto por operación (`typical`) | −0,191 % | −0,231 % | −0,040 | −0,146 % | −0,082 % | +0,064 |
| Costo por operación (`conservative`) | 0,395 % | 0,509 % | +0,114 | 0,392 % | 0,492 % | +0,100 |
| **Operaciones por condición y ventana de 30 días** | **11,43** | **11,25** | −0,18 | **11,34** | **10,55** | −0,79 |
| Horas medias entre entradas (por condición) | 63,0 | 64,0 | +1,0 | 63,5 | 68,3 | +4,8 |
| Duración media de la operación | 37,6 h | 35,8 h | −1,8 h | 41,4 h | 39,4 h | −1,9 h |
| Bruto por condición y ventana | +0,63 % | +0,19 % | −0,44 pp | +1,21 % | +0,83 % | −0,38 pp |
| **Costo `typical` por condición y ventana** | **2,76 %** | **2,72 %** | −0,05 pp | **2,75 %** | **2,56 %** | −0,19 pp |
| **Neto por condición y ventana (`typical`)** | −2,13 % | −2,53 % | −0,39 pp | −1,54 % | −1,73 % | −0,19 pp |
| Neto por condición y ventana (`conservative`) | −3,89 % | −5,38 % | −1,50 pp | −3,39 % | −4,57 % | −1,18 pp |
| Operaciones por año, agregadas (todas las condiciones seleccionadas) | 121.086 | 60.817 | −50 % | 66.637 | 36.043 | −46 % |
| TP ÷ (TP + SL) resueltas (caminata sin ventaja: 37,5 %) | 36,8 % | 36,6 % | | 37,7 % | 38,8 % | |

**Motivo de salida (`typical`; % de operaciones · neto medio):** 1h LONG TP 32,4 % (+4,76 %), SL 55,6 % (−3,24 %), NONE 11,8 % (+0,59 %), AMBIGUOUS 0,1 %; 4h LONG TP 32,4 %, SL 56,1 %, NONE 10,8 %, AMBIGUOUS **0,6 %**; 1h SHORT TP 31,9 %, SL 52,7 %, NONE 15,4 %, AMBIGUOUS 0,1 %; 4h SHORT TP 33,5 %, SL 52,9 %, NONE 13,1 %, AMBIGUOUS **0,5 %**. La proporción de AMBIGUOUS se multiplica por ~5–6 al pasar a 4h (barras más grandes tocan TP y SL a la vez), todavía menor al 1 %.

**Descomposición del cambio 4h − 1h en el neto por condición y ventana** (cada condición-ventana con el mismo peso; neto por operación = neto por condición·ventana ÷ operaciones por condición·ventana, de modo que la identidad es exacta): LONG: menor turnover **+0,034 pp**; cambio por operación **−0,427 pp** (bruto −0,428, costo +0,002) → total −0,393 pp, que es la diferencia de neto por condición y ventana de la tabla. SHORT: turnover **+0,108 pp**; por operación **−0,297 pp** (bruto −0,293, costo −0,004) → total −0,190 pp. (El neto por operación agregado de las tablas anteriores pondera por cantidad de operaciones, de ahí que difiera de este neto por operación.)
**Comparación emparejada por calendario** (ventanas = las 90 VALIDATION de 1h; grilla horaria común; 4h − 1h):
- LONG: neto por condición y ventana −0,307 pp, t pareado **−0,61** (n = 90), HAC (300 rezagos) −0,56, bootstrap P(4h > 1h) = 0,68, t en `conservative` **−2,15** → R1h = NO. Neto por operación −0,058 pp, t −1,02; `conservative` −2,49 → R1t = NO.
- SHORT: −0,130 pp, t **−0,28**, HAC −0,26, bootstrap 0,58, `conservative` −1,70 → R1h = NO. Por operación +0,006 pp, t +0,08; `conservative` −1,16 → R1t = NO.
**R2:** ningún lado (neto agrupado < 0 en `typical` y `conservative`; t entre folds de neto −1,60 y −1,80; HAC −2,15 y −1,12). **Reality Check** (K = 18, bloque 300 h, T = 52.183 h): benchmark cero `typical` p = 1,000 (mejor EXP-009 SHORT; 4h LONG 0,97, 4h SHORT 0,90); exceso sobre la línea base `typical` p = 0,861 (mejor EXP-010 V1 LONG; 4h LONG 0,39, 4h SHORT 0,43); `conservative`: 1,000 / 0,897.
**Escenario: A — 4h no mejora y sigue negativo.**

**Lectura.** La pregunta final: *¿hay evidencia de que 1h fracasa porque ≈ 0,25 % por operación es demasiado grande frente al movimiento capturado, y de que 4h ofrece una relación más favorable?* **No.** Y el experimento muestra por qué esa premisa no se cumplió en este diseño:
1. *Efecto de menor turnover — ausente.* A igual TP/SL (5 %/3 %) y a igual duración máxima en horas, la duración media de la operación es la misma (36–41 h en ambos) y también la cantidad de operaciones por condición y ventana de 30 días (11,4 vs 11,2 en LONG; 11,3 vs 10,5 en SHORT). La mitad de operaciones agregadas de 4h (−50 % LONG, −46 % SHORT) se debe a que se seleccionan la mitad de condiciones en TRAIN (35.745 vs 70.595; 24.267 vs 44.549), no a que cada condición opere menos. El efecto de turnover sobre el neto es +0,034 pp (LONG) y +0,108 pp (SHORT): despreciable frente a la caída por operación de −0,427 y −0,297 pp (sin significancia, ver comparación emparejada). El costo por condición y ventana prácticamente no cambia (2,76 → 2,72 % LONG; 2,75 → 2,56 % SHORT). *Con exits en % y horizonte en horas, la temporalidad de las barras no determina el turnover: lo determina el tiempo que tarda el precio en recorrer ±3–5 %.*
2. *Mayor movimiento por operación — ausente.* El recorrido por operación lo fija el TP/SL en % (TP medio realizado 5,0 %, SL 3,0 % en ambos); el movimiento por *barra* se duplica en 4h (mediana de |retorno| de 0,25 % a 0,50 %), pero eso sólo cambia en cuántas barras se resuelve una operación (≈ 38 barras de 1h vs ≈ 9 barras de 4h), no lo que se captura.
3. *Frecuencia de señales.* Por condición, sin cambios; menos condiciones superan los filtros de TRAIN en 4h (49–54 % de las de 1h) y menos sobreviven el filtro de VALIDATION (34 y 18 vs 83 y 58).
4. *Retorno bruto.* ≈ 0 en ambos (+0,05 % y +0,01 % por operación en LONG; +0,10 % y +0,16 % en SHORT); las diferencias (−0,040 pp y +0,064 pp) no son significativas (t por ventana −1,02 y +0,08).
5. *Costos.* Idénticos por operación con `typical` (0,241–0,242 %); con `conservative` el costo por operación sube de 0,39 % a 0,49–0,51 % en 4h, como se anticipó, porque ese escenario suma un slippage proporcional al ATR de las barras del timeframe (en 4h es ≈ 2× el de 1h): es una propiedad mecánica del modelo existente y explica que 4h luzca peor en `conservative` (t pareado −2,15 en LONG).
6. *Neto.* Sin mejora: LONG −0,191 % → −0,231 %, SHORT −0,146 % → −0,082 % por operación (agregado), pero por ventana y emparejado por calendario las diferencias son −0,31 pp (t −0,61) y −0,13 pp (t −0,28).
7. *Predictibilidad.* Sin evidencia: t entre folds del lift +1,13 / +1,14 (LONG) y −0,43 / +0,12 (SHORT) para 1h / 4h; HAC del lift 0,04 / 0,29 y −0,12 / 0,03; y la frecuencia de TP entre las operaciones resueltas (36,6–38,8 %) es la de una caminata sin ventaja (37,5 %) en ambos timeframes.
8. *Robustez estadística.* Ningún criterio de R1 ni de R2; Reality Check p ≥ 0,86 en las cuatro combinaciones.
**Conclusión.** Pasar de 1h a 4h con TP 5 %/SL 3 % y H equivalente a 100 h **no cambia la economía**: mismos costos por operación, misma cantidad de operaciones por condición, mismo retorno bruto ≈ 0 y mismo neto ≈ −costo. La hipótesis de que "el costo relativo a 1h sea el principal cuello de botella" **no recibe apoyo de este experimento**, pero tampoco queda refutada en general: lo que el experimento muestra es que **cambiar la escala de las barras sin cambiar la escala del objetivo (TP/SL/horizonte en % y horas) no cambia el cociente costo/movimiento capturado**; y que, además, con retorno bruto ≈ 0 en todos los diseños probados (EXP-009, 010 y 011), una fricción menor por unidad de tiempo reduciría las pérdidas pero no produciría ganancia. Consistente con EXP-010 (con cualquier geometría el TP se alcanza con la frecuencia de una caminata sin ventaja).
**Cuentas.** Hipótesis de este experimento: **1.350.000** (4h: 7.500 × 90 folds × 2 lados); 1h re-corrido: 0 nuevas; **acumulado 11.041.500**. **K = 18** (4h LONG y SHORT se agregan al universo). Las 4 comparaciones 4h − 1h (2 lados × 2 vistas) no suman a K. Holdout cerrado.
**Decisión.** (1) La agregación estricta 1h→4h queda implementada y probada (`resample.aggregate_ohlc_strict`, `CSV_TIMEFRAME`); el 1h no cambió. (2) No se encadena ningún experimento (ni 4h + ATR, ni 4h + features, ni 1D, ni otro activo). (3) Experimentos de búsqueda seguidos sin avance: **6** (EXP-001, 002, 008, 009, 010, 011; CLAUDE.md pide revisar el rumbo a los 10).
**Próximo paso (a decidir con el usuario, después de leer esta conclusión).** EXP-011 deja una pista concreta sobre qué cambia el cociente costo/movimiento: la escala del *objetivo* y no la de las barras. Opciones, cada una un experimento separado que suma variantes a K: (a) objetivos más grandes frente al costo (TP/SL y horizonte escalados en % y horas, p. ej. ×3, con o sin temporalidad más lenta), sabiendo de antemano que con bruto ≈ 0 el resultado esperado es "pierde menos", no "gana"; (b) otros activos o mercados con otra estructura de costos; (c) revisar el objetivo del proyecto, porque en seis experimentos las entradas seleccionadas no superan a una caminata sin ventaja; (d) más validez estadística (CPCV, PBO sobre el lift).

### EXP-012 — Escala del objetivo: TP/SL y horizonte mayores (2026-10-06)
**Contexto.** EXP-010 (salidas por ATR) y EXP-011 (4h con la misma duración de operación) no mejoraron nada; en ambos el retorno bruto por operación quedó ≈ 0 y la frecuencia de TP entre las operaciones resueltas, cerca de la de una caminata sin ventaja. Ya no se asume que el problema principal sea el costo de transacción.
**Pregunta.** ¿Las condiciones de entrada descubiertas contienen alguna predictibilidad que sólo se manifiesta en movimientos de mayor magnitud y horizontes proporcionalmente mayores? Debe distinguir: (1) una señal predictiva real que aparece a mayor escala; (2) una simple reducción de la importancia relativa de los costos; (3) ruido o múltiples hipótesis.
**H1.** Existe una escala característica de la señal invisible con TP 5 % / SL 3 % / H 100 h: al escalar conjuntamente (TP, SL, H) → (k·TP, k·SL, k·H) debería observarse una mejora sistemática del **retorno bruto y/o del lift sobre la línea base**, consistente entre folds. **H0.** Escalar no revela ventaja adicional: bruto y lift ≈ 0, y cualquier mejora del neto se explica por menor peso relativo de los costos, variación muestral o selección múltiple. **Un neto "menos negativo" no es evidencia de señal**; primero se determina si hay predictibilidad en bruto/lift y sólo después si alcanza para superar costos.
**Variantes (únicas; sin otras combinaciones; relación TP/SL = 5/3 en todas; timeframe 1h, H en barras = horas).** B0: TP 5 % / SL 3 % / H 100; V1 (k = 2): 10 % / 6 % / H 200; V2 (k = 3): 15 % / 9 % / H 300; V3 (k = 4): 20 % / 12 % / H 400. Entrada: condición confirmada al cierre de t, Open[t+1]. Sin ATR exits, 4h, features, indicadores, patrones, breakout, ContextTrigger, régimen, activos ni fuentes nuevas. Idéntico a EXP-002: BTCUSDT 1h Binance, generador aleatorio de profundidad 1 (sin features de régimen), semilla 42, 7.500 condiciones por fold y lado, LONG y SHORT, `filter_mode = both`, `until_exit`, mínimo de 30 operaciones, `MIN_P_TP_FIRST = 0,15`, costos (`typical` decide, `conservative` robustez), política AMBIGUOUS, purga por horizonte (`n_dropped_horizon`), holdout cerrado.
**Decisión de diseño tomada con el usuario antes de correr (conflicto no previsto en el enunciado).** Con TRAIN = 2.500 barras, `until_exit` y mínimo 30 operaciones, aun la condición más frecuente posible (reentra apenas sale) llega a ≥ 30 operaciones en sólo ~20–23 % de los TRAIN en V1, ~10 % en V2 y ~5 % en V3 (100 % en B0), porque la duración media por operación crece de 33 barras a 100, 182 y 273: V2/V3 seleccionarían ≈ 0 condiciones por construcción y el experimento no respondería la pregunta; además con VAL = 720 y H = 400 el guard de `make_folds` (VAL ≥ 2H) falla. **Se escalan TRAIN y VALIDATION por k, se mantiene el mínimo de 30 operaciones** (no se baja a 30/k, que cambiaría la evidencia exigida a una condición). Hipótesis reinterpretada: *¿hay predictibilidad a una escala de movimiento mayor cuando TRAIN, VALIDATION y horizonte se escalan proporcionalmente?*

| Variante | TP/SL | H | TRAIN | VALIDATION | Folds | VAL útil tras la purga (H) | g.l. | Umbral absoluto máx(3; Bonferroni K=24) | Umbral relativo máx(2,5; Bonferroni 6 comp.) |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 5/3 % | 100 h | 2.500 h | 720 h | **90** | 86,1 % | 89 | 3,00 (2,94) | 2,50 (2,44) |
| V1 | 10/6 % | 200 h | 5.000 h | 1.440 h | **43** | 86,1 % | 42 | **3,03** | 2,50 (2,49) |
| V2 | 15/9 % | 300 h | 7.500 h | 2.160 h | **27** | 86,1 % | 26 | **3,14** | 2,56 |
| V3 | 20/12 % | 400 h | 10.000 h | 2.880 h | **20** | 86,1 % | 19 | **3,25** | 2,63 |

Rolling, holdout 15 % (desde 2025-05-22 14:00 UTC): en las cuatro variantes la última VALIDATION termina exactamente donde empieza el holdout (ninguna ventana lo toca). Primeras VALIDATION: B0 2017-12-25 → 2018-01-24; V1 2018-04-25 → 2018-06-24; V2 2018-09-23 → 2018-12-23; V3 2018-10-23 → 2019-02-21; todas terminan en 2025-05-22. Cobertura calendario de VALIDATION: B0 64.800 h; V1 61.920 h; V2 58.320 h; V3 57.600 h; las cuatro en común: **57.600 h (80 ventanas de 30 días)**; B0∩V1 61.920 h, B0∩V2 58.320 h, B0∩V3 57.600 h. **Con 20 folds en V3** las reglas se pueden aplicar (la regla 4 pide ≥ 5 folds y se prefiere ≥ 10) pero con menos potencia y umbrales más altos (los umbrales **suben** por tener menos grados de libertad; no se bajan). No se tocarán TRAIN/VAL, mínimo, número de condiciones ni criterios después de ver resultados. Limitación honesta: escalar TRAIN por k no compensa del todo, porque el tiempo de resolución de una operación crece ≈ k² (difusión): operaciones máximas por TRAIN escalado (condición que reentra al salir): B0 110 (100 % de los TRAIN con ≥ 30), V1 55–60 (98–100 %), V2 40–47 (92–98 %), V3 38–39 (78–92 %); se espera seleccionar menos condiciones en las variantes grandes (se reporta).
**Comparación por calendario.** Los folds de cada variante son distintos; la comparación V_k − B0 se hace sobre las ventanas de VALIDATION de V_k (n = 43, 27, 20): para cada ventana se calcula la misma métrica con las operaciones de B0 abiertas en esas mismas horas (cubiertas por ambas) y se empareja. Para métricas por operación se usan sumas/cantidades por ventana (el lift usa la línea base por barra de cada corrida).
**Dato descriptivo clave antes de correr (`results/exp012/sanity.json`; no modifica el protocolo).** La línea base sin condición (entrar en todas las barras, mismo TP/SL/H, `typical`), sin ninguna señal, da: LONG bruto +0,13 % (B0), +0,56 % (V1), +1,20 % (V2), +1,65 % (V3) y neto +0,32 % (V1), +0,96 % (V2), +1,40 % (V3); SHORT bruto −0,08, −0,36, −0,70 y −1,05 %; la proporción de NONE (salida por tiempo) sube de 18 % a 50 % y la duración media de 44 h a 292 h. Es la deriva alcista de BTC acumulada durante la operación: **el retorno bruto y el neto "positivos" de LONG a escalas grandes aparecerán aunque no haya ninguna señal**. Por eso la medida de predictibilidad es el **lift** (condición menos línea base de la misma ventana y geometría), y el bruto/neto absolutos sólo se informan. (La referencia de 37,5 % para TP ÷ (TP + SL) se informa como pidió el usuario, pero la línea base sin condición da 37,5–39,4 % en LONG y 25–34 % en SHORT: la referencia que descuenta la deriva es la propia línea base; ver P5.)
**Métricas (por variante y lado).** Retorno bruto OOS agrupado; neto `typical` y `conservative`; media por fold de bruto, neto y lift (bruto y neto); t entre folds del bruto, del neto, del lift bruto y del lift neto; HAC (rezagos = 3·H de la variante) del bruto, del neto y del lift (series por barra); operaciones OOS, por fold, por condición seleccionada y por ventana de 30 días, turnover (por año y por 1.000 barras), horas entre entradas, duración media y mediana; salidas TP_FIRST/SL_FIRST/NONE/AMBIGUOUS (cantidad, %, retorno medio, contribución); economía por operación y por condición·ventana de 30 días (bruto, costo, neto) y su descomposición vs B0 en: cambio en bruto, cambio en costo y cambio en número de operaciones; P(TP | TP o SL) vs 37,5 % y vs la línea base; condiciones seleccionadas/que sobreviven; bootstrap estacionario y Reality Check; PBO.
**Contabilidad (registrada antes de correr).** Unidad del proyecto: hipótesis = condición × lado × TP × SL × H × período. V1: 7.500 × 43 folds × 2 lados = 645.000; V2: 7.500 × 27 × 2 = 405.000; V3: 7.500 × 20 × 2 = 300.000; **total 1.350.000 hipótesis nuevas** (los 90 folds de B0 equivalen a la misma cuenta); B0 re-corrido: 0 (debe reproducir EXP-002 al dígito, si no se detiene el experimento). PBO: 7.500 condiciones × 2 lados × 2 semillas × 3 variantes = 90.000 (B0 ya está en EXP-004). **Acumulado: 11.041.500 → 12.391.500 → 12.481.500 con la PBO.** **K: antes de EXP-012, K = 18; después, K = 24** (V1–V3 × LONG/SHORT son procedimientos completos con TP/SL/H/ventanas propios sobre la misma historia OOS; que sean conceptualmente similares no reduce K). Comparaciones V_k − B0: 6 (3 variantes × 2 lados) sobre la métrica primaria (lift bruto), corregidas por Bonferroni con los g.l. de cada variante; no suman a K.
**Reglas de decisión (fijadas ahora; no se modifican después).** Para cada (variante k, lado s), con sus propios folds:
- **P1** lift bruto medio por fold > 0 y t entre folds ≥ umbral absoluto de k (3,00 / 3,03 / 3,14 / 3,25). **P2** t HAC (3·H_k rezagos) de la serie por barra del lift bruto ≥ 2. **P3** mejora respecto de B0: t pareado por calendario de la diferencia de lift bruto (V_k − B0) ≥ umbral relativo de k y HAC de la diferencia ≥ 2. **P4** Reality Check sobre las series de lift bruto del universo de predictibilidad {B0, V1, V2, V3} × {LONG, SHORT} (K_pred = 8; bloque 1.200 h = 3·H_max como principal y 300 h como sensibilidad) con p < 0,05. **P5** la frecuencia de TP supera a la línea base: t entre folds de (P_TP agrupado de las condiciones seleccionadas − P_TP de la línea base de la misma ventana) ≥ umbral absoluto de k, con signo positivo. **P6** consistencia entre escalas: para el mismo lado, al menos dos variantes entre V1–V3 cumplen P1 y P2 (no depende de una única variante).
- **Escenario A** (sin evidencia): ninguna (k, s) con lift bruto con t entre folds ≥ 2 ni diferencia pareada con B0 con t ≥ 2. **Escenario B** (pista exploratoria sin robustez): alguna (k, s) con t del lift bruto ≥ 2 o diferencia pareada con B0 con t ≥ 2, pero sin cumplir C; se registra exactamente qué criterio falla. **Escenario C** (evidencia robusta de predictibilidad): alguna (k, s) cumple P1–P5 y su lado cumple P6. **Escenario D** (predictibilidad y rentabilidad): C y, además, para esa (k, s): neto agrupado > 0 con `typical` y con `conservative`, ≥ 100 operaciones OOS, t entre folds de neto y de lift neto ≥ umbral absoluto de k, `oos_hac_t_3H` del neto ≥ 2 y Reality Check (K = 24, neto, benchmark cero) con p < 0,05. Precedencia D > C > B > A. En C o D se detiene todo y se presenta al usuario; el holdout no se abre sin autorización explícita.
- Reality Check (protocolo existente) sobre el universo de K = 24 en grilla horaria (benchmark cero y benchmark línea base; `typical` y `conservative`; bloque 300 h como en todos los EXP anteriores y 1.200 h de sensibilidad, dado que T ≈ 52.000 h es corto para series con operaciones de hasta 400 h): se reporta K, p, mejor variante, mejor lado y comparación con EXP anteriores. PBO: `run_pbo.py` sin cambios por variante (semillas 42 y 7), comparado con B0 de EXP-004.
**Causalidad (antes del WFO).** 105 tests pasan (20 nuevos en `tests/test_scale_exits.py`: niveles y salidas de TP/SL escalados (LONG/SHORT), H en barras = horas, invarianza ante truncación y perturbación del futuro para H = 100/200/300/400, extender o recortar el dataset no cambia la historia, entrada = Open[t+1] y purga con el horizonte escalado, folds escalados (90/43/27/20, holdout intacto, 86,1 % útil), series OOS con alias bruto, línea base bruta e histograma de duraciones; los números dorados del baseline fijo siguen idénticos). `run_lookahead.py` con cada geometría (H 100/200/300/400; TP/SL 5/3, 10/6, 15/9, 20/12 %): **0/588 operandos, 0/1.000 señales y 0/200 chequeos de entradas** con diferencias, en las cuatro. B0 se re-corre con el código final y se compara con EXP-002.
**Orden.** (1) tests ✓ (2) look-ahead ✓ (3) sanity ✓ (4) WFO B0, V1, V2, V3 + PBO (5) comparación (6) Reality Check (7) registro y commit. No se mira ningún resultado parcial; no se encadena EXP-013.
**Comandos.** `pixi run python run_research.py --csv "D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv" --walk-forward --wf-train-bars 2500·k --wf-val-bars 720·k --side LONG SHORT --tp TP --sl SL --horizon H --cooldown-mode until_exit --filter-mode both --cost-scenario typical --no-events --output results/exp012/{b0,v1,v2,v3}`; `run_pbo.py --tp --sl --horizon --seed {42,7}`; `run_scale_comparison.py`.

**Resultados (2026-10-06).** *Regresión:* B0 re-corrido con el código final reproduce **idéntica** EXP-002 (20 columnas numéricas de `wf_summary.csv`, LONG y SHORT). Look-ahead y tests previos: sin diferencias.

**⚠ Desviación respecto de la especificación, descubierta al diagnosticar los resultados (error mío).** El mínimo de operaciones en TRAIN que exige el framework no es sólo 30: es `max(MIN_CASES_ABSOLUTE = 30, ⌈MIN_CASES_FRACTION × barras del TRAIN⌉)` con `MIN_CASES_FRACTION = 0,01`. Al escalar TRAIN por k, el mínimo **efectivo** pasó a **30 (B0), 50 (V1), 75 (V2) y 100 (V3)**, en lugar de los 30 acordados con el usuario ("mantener el mínimo de 30 operaciones"); ni mi chequeo de factibilidad previo ni la pre-especificación consideraron el término fraccionario. Consecuencia: se seleccionaron muy pocas condiciones en las variantes escaladas (tabla). Diagnóstico sólo sobre TRAIN (no usa resultados OOS): con mínimo 30 y el resto de los filtros iguales habrían pasado en V1 LONG 14,8 % de las condiciones (41/43 folds con alguna), V1 SHORT 7,6 % (29/43), V2 LONG 14,3 % (25/27), V2 SHORT 3,7 % (17/27), V3 LONG 9,6 % (14/20), V3 SHORT 3,0 % (10/20); el 82–100 % de las condiciones de V1–V3 fue rechazado por el motivo `n` (mínimo de operaciones). **No se re-corrió ni se modificó nada**: el usuario prohibió cambiar el mínimo o los criterios después de ver resultados, y una re-corrida con el mínimo efectivo de 30 es otro procedimiento (otras hipótesis y K). Queda como decisión del usuario (ver "Próximo paso").

Con la regla tal como se ejecutó:

| | folds | folds con alguna condición seleccionada | condiciones seleccionadas (suma) | operaciones OOS |
|---|---|---|---|---|
| B0 LONG / SHORT | 90 | 89 / 74 | 70.595 / 44.549 | 895.090 / 492.594 |
| V1 LONG / SHORT | 43 | **17 / 12** | 4.765 / 4.173 | 51.326 / 37.352 |
| V2 LONG / SHORT | 27 | **1 / 1** | 559 / 21 | 6.891 / 232 |
| V3 LONG / SHORT | 20 | **0 / 0** | 0 / 0 | **0 / 0** |

V3 no tiene ninguna operación OOS en ningún fold ni lado; V2 sólo tiene datos en 1 fold por lado (t entre folds no definido); sólo V1 admite estadística entre folds, con 17 y 12 folds. **El experimento no puede responder la pregunta a las escalas V2 y V3 y sólo parcialmente a la de V1.**

Métricas (V1; costos `typical`; entre paréntesis B0): 
| | V1 LONG | B0 LONG | V1 SHORT | B0 SHORT |
|---|---|---|---|---|
| Bruto OOS agrupado por operación | +0,81 % | +0,05 % | +0,63 % | +0,10 % |
| Neto agrupado `typical` / `conservative` | +0,56 % / +0,41 % | −0,19 % / −0,34 % | +0,39 % / +0,24 % | −0,15 % / −0,30 % |
| Media por fold: bruto / neto | +0,28 % / +0,03 % | +0,09 % / −0,15 % | −0,17 % / −0,42 % | +0,06 % / −0,18 % |
| **Lift bruto medio por fold** | **+0,26 %** | +0,05 % | **−0,11 %** | −0,02 % |
| t entre folds: bruto / neto / **lift bruto** / lift neto | +0,57 / +0,07 / **+1,26** / +1,26 | +0,89 / −1,56 / +1,13 / +1,13 | −0,31 / −0,75 / **−0,63** / −0,63 | +0,61 / −1,89 / −0,44 / −0,43 |
| HAC (3·H): bruto / neto / **lift bruto** | +0,42 / +0,05 / **+0,46** | +0,19 / −1,99 / +0,04 | +0,80 / +0,49 / **+0,06** | +1,23 / −0,89 / −0,12 |
| Folds con neto > 0 / que superan la línea base | 9/17 / 11 | 39/89 / 52 | 7/12 / 2 | 37/74 / 31 |
| Frecuencia de TP entre resueltas | 40,5 % | 36,8 % | 39,2 % | 37,7 % |
| t entre folds del lift de P(TP) | +1,17 | +1,53 | −0,36 | +0,53 |
| Operaciones por condición y 30 días / horas entre entradas | 5,1 / 141 h | 11,4 / 63 h | 5,0 / 145 h | 11,3 / 63 h |
| Duración media / mediana | 106 h / 93 h | 38 h / 25 h | 128 h / 137 h | 41 h / 29 h |
| Costo por operación (`typical`) | 0,244 % | 0,241 % | 0,243 % | 0,242 % |
| Bruto / costo / neto por condición·30 días | +0,34 / 1,24 / −0,90 % | +0,63 / 2,76 / −2,13 % | −1,71 / 1,22 / −2,93 % | +1,21 / 2,75 / −1,54 % |
V2 (1 fold con datos por lado; no interpretable): LONG bruto −3,51 %, neto −3,75 % (6.891 operaciones); SHORT bruto +4,21 %, neto +3,98 % (232 operaciones).
Motivo de salida V1 (`typical`): LONG TP 29,7 % (+9,75 %), SL 43,6 % (−6,23 %), NONE 26,7 % (+1,46 %), AMBIGUOUS 0,0 %; SHORT TP 26,7 % (+9,79 %), SL 41,5 % (−6,26 %), NONE 31,7 % (+1,16 %). B0 (de EXP-002): NONE 11,8 % / 15,4 %.
**Comparación emparejada por calendario V1 − B0** (ventanas de V1 con operaciones: 17 LONG, 11 SHORT): LONG Δ lift bruto por operación +0,28 pp (t +1,04; HAC de la diferencia +0,34; bootstrap p(V1 > B0) = 0,34); SHORT −0,002 pp (t −0,01; HAC +0,18; p = 0,40). Umbral relativo 2,50: **no se cumple**. Descomposición del cambio en neto por condición·30 días en V1 LONG: +1,24 pp = **operaciones +1,18** + bruto +0,06 + costo −0,01 (es decir, "pierde menos" porque se opera la mitad, no porque el bruto mejore); V1 SHORT: −1,39 pp = operaciones +0,86 + bruto −2,24 + costo −0,02.
**Reality Check de predictibilidad** (series de lift bruto de {B0, V1, V2, V3} × {LONG, SHORT}, K_pred = 8, 57.600 h comunes): bloque 1.200 h (principal) p = **0,909** (mejor V1 LONG); bloque 300 h p = 0,963. **Reality Check del protocolo existente** (neto, K = 24, T = 52.183 h): benchmark cero `typical` p = 0,997 (bloque 300 h) y 0,999 (1.200 h); exceso sobre la línea base `typical` p = 0,927 y 0,707; `conservative` 1,000 / 0,954 y 1,000 / 0,792; ninguna variante de EXP-012 tiene p individual < 0,31.
**PBO** (7.500 condiciones, 16 bloques; semillas 42 / 7; mejor IN → esa misma OUT; métrica = neto por operación, **sin descontar la línea base**):

| | PBO | Mejor IN | Mejor OUT | Línea base sin condición (neto, EXP-012 sanity) |
|---|---|---|---|---|
| B0 LONG (EXP-004) | 0,72 / 0,49 | +0,87 / +0,97 % | −0,30 / −0,09 % | −0,12 % |
| V1 LONG | 0,30 / 0,50 | +2,28 / +2,29 % | +0,53 / +0,27 % | +0,32 % |
| V2 LONG | 0,39 / 0,43 | +3,75 / +3,89 % | +1,17 / +0,96 % | +0,96 % |
| V3 LONG | 0,42 / 0,38 | +4,77 / +5,09 % | +1,56 / +1,70 % | +1,40 % |
| V1 SHORT | 0,28 / 0,36 | +1,40 / +1,36 % | −0,06 / −0,43 % | −0,61 % |
| V2 SHORT | 0,31 / 0,56 | +1,78 / +1,37 % | −0,46 / −1,32 % | −0,95 % |
| V3 SHORT | 0,48 / 0,42 | +1,54 / +1,63 % | −1,91 / −1,72 % | −1,30 % |
Lectura de la PBO: el "mejor OUT" de LONG (+0,3 a +1,7 %) coincide con lo que gana la línea base sin condición por la deriva (+0,32, +0,96 y +1,40 %), y el de SHORT (−0,1 a −1,9 %) con lo que pierde; en V3 SHORT es peor que la línea base. La métrica de la PBO no descuenta la línea base, así que estos números muestran la **deriva de BTC y no predictibilidad**; lo único claro es que el mejor IN crece con la escala (+0,9 % → +2,3 % → +3,8 % → +4,8 %, LONG) sin que el OUT supere a la línea base.
**Reglas pre-registradas:** P1–P5 = NO en todas las (variante, lado) evaluables (V1: t del lift bruto +1,26 y −0,63 contra el umbral 3,03; HAC +0,46 y +0,06 < 2; Δ vs B0 t +1,04 y −0,01 < 2,50; Reality Check de predictibilidad p = 0,91; t del lift de P(TP) +1,17 y −0,36); P6 = NO. **Escenario formal: A (sin evidencia de predictibilidad)**, con la salvedad de que V2 y V3 no son evaluables y de la desviación descrita arriba: **el resultado A no debe leerse como "escalar el objetivo no revela una señal", sino como "este diseño, tal como se ejecutó, no tuvo potencia para detectarla"**.

**Informe (preguntas del usuario).**
- *¿Aparece evidencia de predictibilidad cuando TP, SL y H se escalan?* No en V1 (lift bruto no significativo: +0,26 % por fold LONG con t = 1,26, −0,11 % SHORT con t = −0,63; HAC < 0,5); **V2 y V3 no son evaluables** (1 fold y 0 folds con operaciones). *¿Es suficiente para superar los costos?* Pregunta sin objeto: no hay predictibilidad detectable.
- *Bruto:* el bruto de V1 LONG (+0,81 % por operación agrupado) es positivo, pero la línea base sin condición con la misma geometría ya da +0,56 %: es deriva; el lift es +0,26 pp/fold sin significancia. *Lift:* ver arriba. *Frecuencia de TP:* 40,5 % (LONG) y 39,2 % (SHORT) en V1 vs 37,5 % de referencia; el lift de P(TP) por fold no es significativo (t +1,17 y −0,36). *Duración:* 106–128 h (media) en V1 vs 38–41 h en B0; mediana 93–137 h vs 25–29 h. *Turnover:* por condición pasa de 11,4 a 5,1 operaciones por 30 días (horas entre entradas 63 → 141). *Costos:* por operación sin cambios (0,24 %); por condición·30 días caen de 2,76 % a 1,24 % (LONG), por la mitad de operaciones. *Neto:* V1 LONG +0,56 % agrupado, pero con media por fold de +0,03 % (t +0,07) y por debajo de/igual a la línea base de la misma geometría (+0,32 % neto); V1 SHORT +0,39 % agrupado y −0,42 % por fold (t −0,75): **"pierde menos" o ganancia por deriva, no señal** (la descomposición asigna +1,18 de los +1,24 pp de V1 LONG a operar menos). *Robustez:* nada supera ningún umbral (HAC, bootstrap, Reality Check: p individual ≥ 0,26 y global 0,71–1,00). *Selección múltiple:* los umbrales suben con menos folds (3,03 / 3,14 / 3,25 por Bonferroni con K = 24) y el Reality Check de K = 24 no encuentra nada; lo que sí hay son 17 y 12 folds en V1 y ninguna potencia en V2/V3.
**Cuentas.** Hipótesis de este experimento: **1.350.000** (V1 645.000 + V2 405.000 + V3 300.000) + **90.000** de PBO = 1.440.000; B0 re-corrido: 0; **acumulado 12.481.500**. **K = 24**. Holdout cerrado.
**Decisión.** (1) Se registra el resultado tal como se ejecutó: escenario formal A, **no concluyente** por la desviación del mínimo efectivo de operaciones (50/75/100 en vez de 30). (2) No se re-corre ni se modifica ningún parámetro; no se encadena EXP-013. (3) El mecanismo (`MIN_CASES_FRACTION` escala con la longitud del TRAIN) queda documentado; cualquier experimento futuro con TRAIN distinto de 2.500 barras debe decidir explícitamente cómo tratarlo. (4) Experimentos de búsqueda seguidos sin avance: **7** (EXP-001, 002, 008, 009, 010, 011, 012; CLAUDE.md pide revisar el rumbo a los 10).
**Próximo paso (propuesta; la decisión es del usuario).** *Opción 1 — "EXP-012b": repetir V1–V3 con el mínimo efectivo de 30 (`MIN_CASES_FRACTION = 0`) y todo lo demás idéntico.* Es la ejecución fiel de lo acordado; con mínimo 30 el diagnóstico de TRAIN indica que se seleccionarían condiciones en 41/43, 25/27 y 14/20 folds (LONG) y 29/43, 17/27 y 10/20 (SHORT). Costo: otras 1.350.000 hipótesis (acumulado 13.831.500 sin PBO) y K = 30, y habría que justificar que no es una exploración post hoc (la desviación quedó registrada antes de re-correr, con su diagnóstico hecho sólo sobre TRAIN). *Opción 2 — no repetir:* cerrar la línea de "escala del objetivo" como no concluyente. *Opción 3 — diseño sin cuello de selección:* evaluar a cada escala las mismas condiciones sin filtro de selección por operaciones (p. ej., las condiciones elegidas en B0), midiendo sólo el lift bruto fuera de muestra. Mientras tanto, el cociente costo/movimiento sigue sin ser el problema principal según EXP-010 y EXP-011.

### EXP-012b — Escala del objetivo con el mínimo efectivo de 30 operaciones (2026-10-06)
**Origen.** Repetición autorizada por el usuario (opción 1) de V1–V3 de EXP-012, que se había ejecutado con un mínimo efectivo de operaciones en TRAIN de 50/75/100 (por `MIN_CASES_FRACTION = 0,01` × barras del TRAIN) en lugar de los 30 acordados, y por eso V2/V3 casi no seleccionaron condiciones (V1: 17 y 12 folds con operaciones de 43; V2: 1 de 27; V3: 0 de 20). La desviación y su diagnóstico (hecho sólo sobre TRAIN) están en la entrada de EXP-012. Es la ejecución fiel de lo acordado, no una variante nueva de la hipótesis. Transparencia: el diagnóstico que motivó la repetición se hizo después de ver los resultados OOS de la corrida deficiente; para limitar la flexibilidad se fijan ahora, antes de correr, todas las reglas, y se agrega una regla de informatividad (abajo).
**Qué cambia: una sola cosa.** `--min-cases-frac 0`: el mínimo efectivo de operaciones es 30 en TRAIN y en VALIDATION para B0, V1, V2 y V3 (antes 30/50/75/100). Test nuevo: `min_cases_required` da 30/50/75/100 con la configuración por defecto y 30/30/30/30 con `MIN_CASES_FRACTION = 0`; la bandera de línea de comandos llega a la configuración. **Todo lo demás idéntico a EXP-012:** variantes B0 (TP 5 %/SL 3 %/H 100), V1 (10 %/6 %/200), V2 (15 %/9 %/300), V3 (20 %/12 %/400); TRAIN/VAL escalados por k (2.500/720, 5.000/1.440, 7.500/2.160, 10.000/2.880 barras; 90/43/27/20 folds; holdout 15 % cerrado, última VALIDATION termina donde empieza); generador aleatorio de profundidad 1, semilla 42, 7.500 condiciones por fold y lado, LONG y SHORT, `filter_mode = both`, `until_exit`, `MIN_P_TP_FIRST = 0,15` y demás filtros, costos, AMBIGUOUS, purga por horizonte. **B0 no se re-corre**: su mínimo efectivo ya era 30 (1 % de 2.500 = 25 < 30), de modo que es el mismo procedimiento y reproduce EXP-002 al dígito (verificado en EXP-012). **La PBO no se re-corre**: es independiente de este filtro (usa su propio mínimo de 30 operaciones por mitad).
**Contabilidad (registrada antes de correr).** Hipótesis nuevas: V1b 7.500 × 43 × 2 = 645.000; V2b 7.500 × 27 × 2 = 405.000; V3b 7.500 × 20 × 2 = 300.000; **total 1.350.000**; PBO 0. **Acumulado: 12.481.500 → 13.831.500.** **K: antes 24, después 30** (V1b–V3b × LONG/SHORT son procedimientos distintos de V1–V3 de EXP-012 porque cambia la regla de selección; las variantes de la primera corrida siguen contando). Umbrales calculados antes de ver los resultados: absoluto = máx(3; Bonferroni(K = 30; g.l.)) = **V1 3,11, V2 3,23, V3 3,35**; relativo (comparaciones contra B0 de la métrica primaria, conservadoramente 12 = las 6 nuevas más las 6 de la primera corrida) = máx(2,5; Bonferroni(12; g.l.)) = **V1 2,77, V2 2,86, V3 2,94**. Reality Check de predictibilidad con K_pred = 14 (B0 × 2 lados + V1–V3 de EXP-012 × 2 + V1b–V3b × 2; las series sin operaciones se ignoran) y de neto con K = 30.
**Reglas de decisión: las mismas de EXP-012** (P1–P6 y escenarios A/B/C/D, con los umbrales de arriba; el lift bruto es la métrica de predictibilidad porque a horizontes largos la línea base sin condición ya gana en LONG y pierde en SHORT por la deriva de BTC), más una regla de **informatividad** fijada ahora: una (variante, lado) es *evaluable* si tiene operaciones OOS en ≥ 10 folds; el escenario A sólo se declara "A informativo" si V1b, V2b y V3b son evaluables en los dos lados; si no, se registra "A no concluyente". En C o D se detiene todo y se presenta al usuario; el holdout no se abre.
**Orden.** Tests ✓ (107) · look-ahead de EXP-012 vigente (el cambio es sólo un umbral de filtro, no toca señales ni salidas) · WFO V1b, V2b, V3b (`--min-cases-frac 0`) · comparación (`run_scale_comparison.py --K 30 --n-comp 12 --tag EXP012b --v-old` con las de EXP-012) · registro y commit. No se mira ningún resultado parcial; no se encadena EXP-013.
**Comandos.** `pixi run python run_research.py --csv "D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv" --walk-forward --wf-train-bars 2500·k --wf-val-bars 720·k --side LONG SHORT --tp TP --sl SL --horizon H --min-cases-frac 0 --cooldown-mode until_exit --filter-mode both --cost-scenario typical --no-events --output results/exp012b/{v1,v2,v3}`.

**Resultados (2026-10-06).** *Regresión:* B0 (el mismo de EXP-012) reproduce EXP-002 al dígito. Mínimo efectivo de operaciones en TRAIN = 30 en las cuatro variantes (verificado por el test del mínimo y porque ahora la selección ya no se concentra en V1). **Cobertura de la selección** (folds con alguna condición seleccionada = folds con operaciones OOS; antes en EXP-012: 17/12, 1/1 y 0/0):

| Variante | folds | LONG | SHORT | condiciones seleccionadas LONG / SHORT | operaciones OOS LONG / SHORT |
|---|---|---|---|---|---|
| B0 | 90 | 89 | 74 | 70.595 / 44.549 | 895.090 / 492.594 |
| V1b | 43 | **41** | **29** | 47.615 / 24.499 | 476.966 / 232.469 |
| V2b | 27 | **25** | **17** | 29.027 / 7.400 | 272.365 / 66.195 |
| V3b | 20 | **14** | **10** | 14.361 / 4.450 | 132.406 / 39.979 |

Las seis (variante, lado) son *evaluables* (≥ 10 folds con operaciones; V3b SHORT justo con 10): el escenario A, si ocurre, es **informativo**.

Métricas (costos `typical`; sus propios folds; "agrupado" = por operación sobre todas las condiciones seleccionadas):

| | B0 LONG | V1b LONG | V2b LONG | V3b LONG | B0 SHORT | V1b SHORT | V2b SHORT | V3b SHORT |
|---|---|---|---|---|---|---|---|---|
| Bruto agrupado | +0,05 % | +0,66 % | +1,96 % | −0,62 % | +0,10 % | −0,92 % | −2,81 % | −3,85 % |
| Neto agrupado `typical` | −0,19 % | +0,41 % | +1,71 % | −0,86 % | −0,15 % | −1,16 % | −3,07 % | −4,11 % |
| Neto agrupado `conservative` | −0,34 % | +0,26 % | +1,56 % | −1,03 % | −0,30 % | −1,31 % | −3,23 % | −4,28 % |
| Media por fold: bruto / neto | +0,09 / −0,15 % | +0,47 / +0,23 % | +1,47 / +1,22 % | +1,03 / +0,78 % | +0,06 / −0,18 % | −0,05 / −0,30 % | −0,94 / −1,18 % | −0,57 / −0,82 % |
| **Lift bruto medio por fold** | +0,05 % | **+0,18 %** | **−0,08 %** | **−0,14 %** | −0,02 % | **+0,005 %** | **−0,22 %** | **+0,25 %** |
| t entre folds: bruto | +0,89 | +1,37 | +2,39 | +0,87 | +0,61 | −0,13 | −1,25 | −0,38 |
| t entre folds: neto | −1,56 | +0,66 | +1,99 | +0,66 | −1,89 | −0,71 | −1,58 | −0,55 |
| t entre folds: **lift bruto** (umbral) | +1,13 | **+1,44** (3,11) | **−0,44** (3,23) | **−0,42** (3,35) | −0,44 | **+0,03** (3,11) | **−0,84** (3,23) | **+0,65** (3,35) |
| t entre folds: lift neto | +1,13 | +1,44 | −0,44 | −0,42 | −0,43 | +0,03 | −0,84 | +0,65 |
| HAC (3·H): bruto / neto / **lift bruto** | +0,19 / −1,99 / +0,04 | +1,25 / +0,56 / **+0,55** | +1,89 / +1,61 / **−0,19** | +0,06 / −0,13 / **−0,26** | +1,23 / −0,89 / −0,12 | −0,48 / −1,01 / **−0,03** | −1,03 / −1,24 / **−0,09** | −0,66 / −0,77 / **+0,14** |
| Folds con neto > 0 / que superan la línea base | 39/89 / 52 | 20/41 / 23 | 17/25 / 11 | 8/14 / 7 | 37/74 / 31 | 12/29 / 12 | 7/17 / 7 | 5/10 / 8 |
| Frecuencia de TP entre resueltas | 36,8 % | 38,7 % | 44,6 % | 28,5 % | 37,7 % | 26,1 % | 12,6 % | 15,5 % |
| t entre folds del lift de P(TP) | +1,53 | +0,94 | +1,12 | −0,25 | +0,53 | +0,43 | +0,29 | +0,45 |
| Operaciones por condición y 30 días | 11,4 | 5,1 | 3,1 | 2,3 | 11,3 | 4,7 | 2,8 | 2,1 |
| Horas entre entradas (por condición) | 63 | 140 | 229 | 311 | 63 | 153 | 259 | 335 |
| Duración media / mediana | 38 / 25 h | 117 / 117 h | 193 / 232 h | 266 / 314 h | 41 / 29 h | 120 / 127 h | 198 / 235 h | 270 / 361 h |
| Costo por operación (`typical`) | 0,241 % | 0,244 % | 0,247 % | 0,243 % | 0,242 % | 0,248 % | 0,253 % | 0,254 % |
| Costo por condición·30 días | 2,76 % | 1,25 % | 0,77 % | 0,57 % | 2,75 % | 1,16 % | 0,69 % | 0,54 % |
| Neto por condición·30 días `typical` | −2,13 % | +1,07 % | +3,51 % | +1,63 % | −1,54 % | −1,61 % | −3,93 % | −3,04 % |

Motivo de salida (`typical`; % · retorno medio): V1b LONG TP 25,8 % (+9,75 %), SL 40,9 % (−6,23 %), NONE 33,3 % (+1,35 %); V2b LONG TP 26,1 % (+14,74 %), SL 32,5 % (−9,23 %), NONE 41,4 % (+2,08 %); V3b LONG TP 16,1 % (+19,73 %), SL 40,5 % (−12,22 %), NONE 43,4 % (+2,10 %); SHORT: V1b TP 17,0 %, SL 48,2 %, NONE 34,8 %; V2b TP 7,2 %, SL 50,1 %, NONE 42,6 %; V3b TP 8,6 %, SL 46,8 %, NONE 44,6 %; AMBIGUOUS ≤ 0,1 % en todas. (B0: NONE 11,8 % LONG / 15,4 % SHORT.)

**Comparación emparejada por calendario V_k − B0** (ventanas de V_k con operaciones de ambos; umbral relativo 2,77 / 2,86 / 2,94):
| | Δ lift bruto por operación | t | HAC de la diferencia | bootstrap p(V > B0) | Δ bruto por operación (t) | Δ línea base sin condición (bruto, sanity) | Descomposición del Δ neto por condición·30 d |
|---|---|---|---|---|---|---|---|
| V1b LONG | +0,19 pp | +1,41 | +0,56 | 0,24 | +0,40 pp (+1,56) | +0,44 pp | +3,20 = operaciones +1,18 + bruto +2,04 + costo −0,01 |
| V2b LONG | −0,12 pp | −0,70 | −0,20 | 0,60 | **+1,39 pp (+2,75)** | +1,08 pp | +5,64 = operaciones +1,55 + bruto +4,11 + costo −0,01 |
| V3b LONG | −0,13 pp | −0,40 | −0,28 | 0,66 | +1,05 pp (+0,97) | +1,52 pp | +3,76 = operaciones +1,70 + bruto +2,07 + costo −0,01 |
| V1b SHORT | +0,09 pp | +0,43 | +0,06 | 0,48 | +0,04 pp (+0,11) | −0,29 pp | −0,08 = operaciones +0,90 + bruto −0,96 + costo −0,01 |
| V2b SHORT | −0,17 pp | −0,62 | −0,02 | 0,50 | −0,78 pp (−1,24) | −0,62 pp | −2,39 = operaciones +1,16 + bruto −3,53 + costo −0,02 |
| V3b SHORT | +0,33 pp | +0,75 | +0,26 | 0,40 | −0,46 pp (−0,34) | −0,97 pp | −1,50 = operaciones +1,25 + bruto −2,73 + costo −0,02 |
La mejora del *bruto* de V2b LONG respecto de B0 (+1,39 pp por operación, t +2,75) **es la deriva y no una señal**: la línea base sin condición con la misma geometría ya sube +1,08 pp entre B0 y V2 (+0,13 % → +1,20 %), y el lift, que descuenta esa línea base, cambia −0,12 pp (t −0,70). Lo mismo en V1b y V3b LONG (Δ bruto +0,40 y +1,05 contra Δ línea base +0,44 y +1,52). En SHORT el bruto cae igual que la línea base (−0,36, −0,70, −1,05 %).
**Reality Check de predictibilidad** (series de lift bruto; K_pred = 14 = B0 + V1–V3 de EXP-012 + V1b–V3b, × 2 lados; T = 57.600 h; las series sin operaciones se ignoran): bloque 1.200 h (principal) p = **0,973** (mejor V1b LONG, p individual 0,27); bloque 300 h p = 0,989. Ninguna serie tiene p individual < 0,26. **Reality Check del protocolo existente** (neto, K = 30, T = 52.183 h): benchmark cero `typical` p = **0,211** (bloque 300 h; mejor V2b LONG, p individual 0,03) y 0,324 (1.200 h); `conservative` 0,287 / 0,404; exceso sobre la línea base `typical` p = 0,978 (300 h) y 0,831 (1.200 h); `conservative` 0,985 / 0,897. Es decir: contra "cero", V2b LONG es el mejor de 30 variantes pero con p corregido = 0,21 (no se rechaza) y, contra la línea base, nada.
**PBO:** no se re-corrió (independiente de este filtro); valen las cifras de EXP-012 (la métrica no descuenta la línea base; refleja la deriva).
**Reglas pre-registradas.** P1: ninguna (los t del lift bruto entre folds van de −0,84 a +1,44 contra umbrales 3,11 / 3,23 / 3,35). P2: ninguna (HAC del lift bruto entre −0,26 y +0,55 < 2). P3: ninguna (t pareado entre −0,70 y +1,41 < 2,77–2,94). P4: no (Reality Check de predictibilidad p = 0,973). P5: ninguna (t del lift de P(TP) entre −0,25 y +1,12). P6: no. Criterio B (t del lift bruto ≥ 2 o diferencia pareada ≥ 2): ninguna. **Escenario A — informativo** (las seis combinaciones evaluables).

**Informe (preguntas del usuario).**
- *¿Aparece evidencia de predictibilidad cuando TP, SL y H se escalan conjuntamente?* **No.** El lift bruto por fold es +0,18 % (V1b LONG), −0,08 % (V2b) y −0,14 % (V3b) en LONG y +0,005 %, −0,22 % y +0,25 % en SHORT, con t entre −0,84 y +1,44 (umbrales de 3,11 a 3,35) y HAC entre −0,26 y +0,55. *¿Alcanza para superar los costos?* Pregunta sin objeto: no hay predictibilidad detectable.
- *Retorno bruto:* crece con la escala sólo en LONG (+0,05 → +0,66 → +1,96 % agrupado) y cae en SHORT, exactamente como la línea base sin condición (LONG +0,13 → +0,56 → +1,20 → +1,65 %, SHORT −0,08 → −1,05 %): es la deriva alcista de BTC acumulada durante la operación, no una señal. *Lift:* ver arriba (≈ 0 a todas las escalas, sin patrón monótono). *Frecuencia de TP:* en LONG 38,7 / 44,6 / 28,5 % y en SHORT 26,1 / 12,6 / 15,5 % contra 37,5 %; pero la referencia que descuenta la deriva es la propia línea base y el lift de P(TP) por fold no es significativo (t entre −0,25 y +1,12). *Duración:* sube de 38–41 h a 117–120 h, 193–198 h y 266–270 h (medianas hasta 361 h). *Turnover:* por condición baja de 11,4 operaciones por 30 días a 5,1 / 3,1 / 2,3 (LONG) y 4,7 / 2,8 / 2,1 (SHORT); las horas entre entradas van de 63 a 140 / 229 / 311 h. *Costos:* por operación sin cambios (0,24–0,25 %); por condición·30 días caen de 2,76 % a 1,25 / 0,77 / 0,57 % (LONG) por operar menos. *Neto:* LONG +0,41 / +1,71 / −0,86 % agrupado y t entre folds +0,66 / +1,99 / +0,66; SHORT −1,16 / −3,07 / −4,11 %. **Los netos positivos de LONG no son evidencia**: la línea base sin condición gana +0,32 / +0,96 / +1,40 % neto con esas geometrías, y la descomposición del cambio respecto de B0 asigna a "bruto" (+2,04, +4,11, +2,07 pp por condición·30 d) la parte que la línea base explica por deriva y a "operar menos" +1,18, +1,55, +1,70 pp. *Robustez:* nada supera ningún umbral; el mejor candidato nominal (V2b LONG, neto t = 1,99) tiene Reality Check p = 0,21 con K = 30 y lift ≈ 0. *Selección múltiple:* K = 30; los umbrales suben al bajar los folds (V3b: 20 folds, 14 y 10 con operaciones: potencia limitada, ver límites).
- *Límites:* V3b SHORT sólo tiene 10 folds con operaciones y V3b LONG 14, por lo que sólo detectaría efectos grandes; el diseño ya no está limitado por el mínimo de operaciones, pero la selección sigue siendo mucho menos densa a escalas grandes (14.361 y 4.450 condiciones seleccionadas en V3b vs 70.595 y 44.549 en B0). Un lift de la magnitud de V1b LONG (+0,18 %/fold) no se distingue de cero con 41 folds.
**Cuentas.** Hipótesis de este experimento: **1.350.000** (V1b 645.000 + V2b 405.000 + V3b 300.000); PBO 0; **acumulado 13.831.500**. **K = 30**. Holdout cerrado.
**Decisión.** (1) Escenario **A informativo**: con el mínimo de 30 operaciones, escalar conjuntamente TP, SL, H, TRAIN y VALIDATION por k = 2, 3, 4 no revela predictibilidad (lift bruto/neto ≈ 0, HAC, bootstrap, Reality Check y consistencia entre escalas negativos). La primera corrida (EXP-012) queda como corrida deficiente conservada en la bitácora; la conclusión vigente es la de EXP-012b. (2) Las mejoras aparentes de bruto/neto en LONG son deriva (la línea base sin condición las reproduce): lección general para cualquier horizonte largo en un activo con tendencia: **sólo el lift es interpretable**. (3) No se encadena EXP-013. (4) Experimentos de búsqueda seguidos sin avance: **8** (EXP-001, 002, 008, 009, 010, 011, 012, 012b); CLAUDE.md pide revisar el rumbo a los 10.
**Próximo paso (propuesta; decide el usuario).** Ocho experimentos de búsqueda sobre BTCUSDT con condiciones técnicas aleatorias (más información, más estructura, otra salida, otra temporalidad, otra escala) no muestran lift bruto detectable, ni en la ventana original ni a escalas mayores. Antes de seguir conviene revisar el rumbo (umbral de CLAUDE.md: 10; estamos en 8). Opciones: (a) cambiar el objeto de estudio y no la búsqueda: otros activos/mercados con historia independiente, o reglas que no sean de entrada (tamaño/gestión, filtros de régimen como *no operar*); (b) una prueba de "techo de información" sin selección (p. ej., predecibilidad de la dirección del retorno con modelos simples sobre las mismas features, medida por lift fuera de muestra) para saber si existe algo que buscar; (c) más validez (CPCV, PBO sobre el lift); (d) dar por cerrada la línea de entradas técnicas simples en BTC y documentar la conclusión. Ninguna se ejecuta sin autorización.

### EXP-013 — Regla de exposición "estar o no estar comprado" en BTC (rama a2 de la opción (a)) (2026-10-06)
**Origen.** Revisión de rumbo tras 8 experimentos de búsqueda de entradas sin avance (sección 0.3, punto 4). El usuario eligió la opción (a) "cambiar el objeto de estudio" y, entre sus dos ramas, la **a2** (reglas que no son de entrada). La otra rama propuesta, a1, consistía en aplicar el mismo procedimiento B0 a ETH, XRP y BNB: K 30 → 36, ≈ 3,9 millones de hipótesis y descarga de datos; queda sin hacer. El usuario decidió además **reiniciar en 0 el contador de experimentos seguidos sin avance**: los 8 de la línea de entradas en BTC (EXP-001, 002, 008, 009, 010, 011, 012, 012b) quedan registrados y éste es el primero de la línea nueva. Al elegir a2 autorizó el **criterio de candidato adaptado** de abajo, incluido el mínimo de 30 entradas.
**Pregunta.** ¿Hay períodos de días o semanas en que conviene no tener BTC, identificables sólo con información pasada? Concretamente: ¿una regla diaria de "comprado o en efectivo" le gana, después de costos, a mantener siempre la misma exposición promedio? Es el filtro "no operar" en su forma más pura. Se aplica a "estar siempre comprado" porque las entradas buscadas hasta ahora no tienen lift que filtrar (EXP-001 a 012b).
**Qué es nuevo respecto de lo anterior.** La salida no es TP/SL/horizonte sino el cambio de estado. La escala es de días a semanas. La referencia no es "entrar en todas las velas" sino una exposición constante igualada. EXP-008 usó features de la misma familia como condiciones de entrada con TP 5 %/SL 3 % (operaciones de ≈ 40 h); no es la misma pregunta.

**Reglas (fijas, sin búsqueda de parámetros; sólo comprado/efectivo, sin SHORT).**
| Regla | "Comprado" si… | Operando (implementado y con tests de causalidad desde EXP-008) |
|---|---|---|
| R1 tendencia corta | el último cierre diario completo está por encima de la media de los últimos 20 cierres diarios | `HTFTrend("1D", 20) > 0` |
| R2 tendencia larga | ídem con 100 días | `HTFTrend("1D", 100) > 0` |
| R3 calma | la volatilidad de las últimas ≈ 24 h es menor que la de las últimas ≈ 240 h | `RelativeVolatility(24, 240) < 1` (ATR de Wilder) |
Valor no definido (NaN) → efectivo. No ocurre en el período evaluado: el calentamiento más largo (100 días) termina antes de la primera ventana; se informa el conteo igual.

**Mecánica (causal).**
- *Revisión diaria.* En la primera vela de cada día UTC presente en los datos (normalmente la de 00:00), la posición pasa a ser el estado de la regla evaluado al cierre de la vela anterior. En las demás velas la posición se mantiene.
- *Ejecución.* La posición de la vela j se decide con datos hasta j−1 y se mantiene de Open[j] a Open[j+1]. En la última vela de cada ventana se mantiene hasta su Close, para no usar precios de la ventana siguiente ni del holdout.
- *Continuidad.* La estrategia es continua entre ventanas: no se liquida al final de cada una. Empieza en efectivo al comienzo de la primera ventana y se liquida al final de la última.
- *Costos.* Cada cambio (entrada o salida) es una orden de mercado: comisión taker + medio spread + slippage del escenario, como fracción del capital, cargada en la vela del cambio. `typical` ≈ 0,125 % por lado (decide). `conservative` = 0,10 % + 0,025 % + 0,03 % + 0,05 × ATR(14)/Close de la vela anterior (robustez). `optimistic` sólo se reporta. Los parámetros son los de siempre; no se cambian.
- *Retornos.* Simples, por vela y sumados (sin reinversión), igual que en el resto de la bitácora.
- *Ventanas.* Las mismas 90 VALIDATION de B0 (`make_folds` con TRAIN 2.500 / VAL 720 sobre BTCUSDT 1h, holdout 15 % cerrado). Período evaluado: velas 3.123 a 67.922, ≈ 2017-12-25 a 2025-05-22, 64.800 h. No hay TRAIN porque no se ajusta nada.

**Benchmark (lo central).** *Exposición constante igualada:* mantener siempre una fracción ē del capital en BTC, sin costos, con ē = exposición promedio de la regla en todo el período evaluado. Rendimiento por vela de la regla menos el del benchmark: `d_j = pos_j·r_j − costo_j − ē·r_j`. Así, la deriva alcista de BTC (que la regla captura en proporción a su exposición) no cuenta como mérito: sólo cuenta acertar *cuándo* estar. ē usa todo el período, pero es sólo la vara de comparación y no interviene en la decisión de la regla. Como información se informan también "comprar y mantener" (ē = 1) y la regla en términos absolutos.

**Métricas.**
- Por ventana w: lift neto `L_w = Σ_{j∈w} d_j` (`typical`) y lift bruto `G_w = Σ_{j∈w} (pos_j − ē)·r_j`.
- t entre ventanas: 90 ventanas, 89 g.l.
- HAC Newey-West sobre la serie horaria d_j con **720 rezagos** (una ventana; los episodios duran días o semanas).

**Criterio de candidato (adaptación de la regla 4, fijada ahora y autorizada por el usuario).** Una regla es candidata si cumple las seis condiciones:
- C1. La media de L_w es > 0, con t entre ventanas ≥ **3,05** (= máx(3; Bonferroni(K = 33; 89 g.l.)) = 3,048).
- C2. El t HAC de d_j (`typical`, 720 rezagos) es ≥ 2.
- C3. Σ L_w > 0 en al menos **4 de 5 tramos** consecutivos de 18 ventanas. Es la traducción de "4 de 5 folds": consistencia entre regímenes.
- C4. El lift neto agrupado (Σ_w L_w) es > 0 también con `conservative`.
- C5. La regla gana en términos absolutos: Σ_j (pos_j·r_j − costo_j) > 0 con `typical` y con `conservative`.
- C6. Hay al menos **30 entradas** (pasajes de efectivo a comprado) en el período. Reemplaza a las 100 operaciones porque cada episodio dura días o semanas.
Una regla es *evaluable* si tiene ≥ 30 entradas y 0 < ē < 1.

**Escenarios (fijados antes de correr; la métrica es `typical`).**
- **A (sin valor de timing):** ninguna regla tiene t entre ventanas ≥ 2 en el lift neto ni en el bruto. Es "A informativo" si las tres son evaluables; si no, se indica cuál no lo es.
- **B (nominal):** alguna regla tiene t ≥ 2 (lift neto o bruto) pero no cumple C1–C6. Se informa, no se persigue y no se encadena.
- **C (candidato):** alguna regla cumple C1–C6. Se frena todo y se presenta al usuario; el holdout no se abre sin su autorización.
- **D (no concluyente):** falla la verificación de causalidad sobre los datos reales (se ejecuta antes de calcular cualquier retorno) o hay un error de cálculo. No se interpreta nada.

*Corrección por pruebas múltiples:* una sola por familia, y decide el umbral Bonferroni de C1 (K = 33). Como información, sin poder de decisión, se informa el Reality Check sobre las tres series d_j, con bloques medios de 1.200 h (principal) y 300 h.

**Contabilidad (antes de correr).**
- Hipótesis nuevas: 3 reglas × 90 ventanas = **270**. Acumulado: 13.831.500 → **13.831.770**.
- **K: 30 → 33.** Mismo activo, mismos datos y misma historia OOS que las 30 variantes anteriores, y cada regla podría reportarse como "el resultado" (regla 7).
- Contador de experimentos seguidos sin avance: reiniciado en 0 por decisión del usuario; éste es el 1.º de la línea nueva.
**Código y tests (antes de correr).** Módulo nuevo `trading_research/exposure.py` (reglas, posiciones diarias, retornos por ventana, costos por cambio, benchmark y métricas) y script `run_exposure.py`. Tests:
1. Causalidad: la posición de las velas 0..k+1 no cambia al truncar los datos en k ni al reemplazar los precios posteriores a k (cortes a distintas horas, con huecos en los datos).
2. La posición sólo cambia en la primera vela de cada día UTC.
3. Regla "siempre comprado": lift ≡ 0, exactamente una entrada y una salida.
4. Costos: cada cambio paga un lado.
5. Las ventanas son idénticas a las de B0.
6. La última vela de cada ventana no usa precios fuera de ella.

Antes de calcular retornos, `run_exposure.py` repite la verificación de causalidad sobre los datos reales (truncar y perturbar en 200 cortes al azar) y aborta si falla.
**Qué NO se hace.**
- No se agregan reglas ni se cambian parámetros después de ver resultados: 20 y 100 días, 24/240 h, revisión diaria, 720 rezagos, 30 entradas y tramos de 18 ventanas quedan fijos.
- No se combinan reglas ni se prueba la versión SHORT.
- No se abre el holdout y no se encadena EXP-014.
**Comando.** `pixi run python run_exposure.py --csv "D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv" --output results/exp013`.
**Preparación hecha antes de correr con datos reales.** Tests: 115 pasan (107 + 8 nuevos en `tests/test_exposure.py`). Se verificó que el test de causalidad detecta una versión adulterada que usa el estado de la misma vela (lo detecta en R3) y que un "canario" que mira el cierre siguiente rompe la invariancia. Prueba en seco del script completo sobre un paseo al azar sintético de 79.909 velas (sin datos reales): corre de punta a punta y da escenario A, con t del lift neto entre −0,56 y +0,88 (no inventa señal en ruido).

---

## 4. Plan

Orden revisado a pedido del usuario (2026-10-04): primero validez estadística del proceso (EXP-003 y EXP-004, hechos), después el resto. La numeración siguiente es provisoria y se puede cambiar según resultados, registrando el motivo. Cada ítem es un experimento separado.

Siguiente (alta prioridad, completa la línea de validez):
1. ~~`procedure_oos_series` + Reality Check sobre las 4 variantes~~ (hecho en EXP-005; SPA queda como extensión).
2. ~~Segunda prueba de look-ahead a nivel de señales~~ (hecho en EXP-006; se corre con `run_lookahead.py` tras cada feature/costo nuevo).
3. ~~Revisión del tratamiento estadístico de operaciones superpuestas~~ (hecho en EXP-007).

Hoja de ruta original, conservada:
4. ~~Features de régimen: tendencia en temporalidades mayores (4h, diario) y volatilidad relativa~~ (hecho en EXP-008: sin mejora OOS).
5. ~~Condiciones con lógica "contexto + disparador" y búsqueda por estados/eventos (idea B)~~ (hecho en EXP-009: sin mejora OOS; breakout queda como variante futura por requerir un operando nuevo).
6. ~~TP/SL proporcionales al ATR~~ (hecho en EXP-010: sin mejora; el horizonte H = 100 no resultó corto, NONE ≤ 15 %).
7. Volumen y hora del día / día de la semana; otras features.
8. Periodicidad de re-search/retraining (ampliar EXP-002).
   *(Nota 2026-10-06: la temporalidad 4h con la misma duración de operación se probó en EXP-011 sin mejora; 1D sigue sin probarse; los objetivos escalados ×2, ×3 y ×4 se probaron en EXP-012/012b sin lift detectable.)*
9. Modelos de costo dependientes de tamaño/precio; spread/slippage dinámicos.
10. Comparación con Genetic Programming.
11. CPCV (con purga + embargo sobre `trade_intervals`), PBO sobre el lift, Deflated Sharpe Ratio para reportar un candidato final.

## 5. Ideas pendientes

### A. Patrones de corto plazo con ventanas cortas (propuesta del usuario)
Idea: en lugar de exigir que una condición funcione durante 10 años, buscar
condiciones que funcionen en el corto plazo y re-buscarlas seguido. Ventana
propuesta: 3–4 meses TRAIN → 1 mes VALIDATION → 1 mes TEST → 2 semanas de
"situación real" (si no hay ningún caso, estirar una semana más).

Evaluación:
- Tiene sentido: los mercados cambian y una regla que se re-optimiza seguido
  puede funcionar aunque ninguna regla fija funcione siempre.
- Lo que se evalúa ya no es cada condición sino el **procedimiento** "buscar en
  los últimos meses y operar las 2 semanas siguientes". Con 9 años de datos
  son unas 200 ventanas de 2 semanas: cada ventana tiene pocos casos, pero el
  total de todas las "situaciones reales" juntas sí alcanza para medir.
- "Situación real" equivale a operar en vivo: las condiciones se eligieron
  sin ver ese período. Es la métrica principal.
- Estirar una semana si no hubo casos es válido porque depende sólo de que no
  aparecieron señales, algo que se sabe en tiempo real. La siguiente ventana
  arranca después de que termina la extendida.
- Riesgos: 3–4 meses de 1h son ~2.500 velas, y con el mínimo de casos actual
  quedarían pocas condiciones; puede hacer falta bajar el mínimo absoluto en
  TRAIN. Con ventanas cortas los costos pesan más.

### B. Condiciones con lógica en lugar de totalmente aleatorias (propuesta del usuario)
Idea: estructurar las condiciones, p. ej. "MACD(12,26) > 0 AND RSI > 15 en las
últimas 5 velas AND régimen alcista → LONG".

Evaluación:
- Reduce mucho el espacio de búsqueda y, con eso, los falsos positivos: cada
  hipótesis tiene una razón de ser y se prueban menos.
- Propuesta de implementación: plantillas "contexto + disparador":
  - contexto (estado lento): régimen de tendencia en una temporalidad mayor,
    nivel de volatilidad;
  - disparador (evento rápido): cruce, pullback, ruptura;
  - dirección coherente: LONG en régimen alcista, SHORT en bajista.
  Los parámetros dentro de cada plantilla se siguen sorteando, pero con rangos acotados.
- Requiere primero features de régimen en temporalidades mayores (EXP-003).

