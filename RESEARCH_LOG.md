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

*Esta sección es el punto de entrada para quien no siguió el trabajo. Se actualiza al cerrar cada experimento. Última actualización: 2026-10-05, tras cerrar EXP-009. El detalle de cada experimento está en la sección 3 (bitácora); acá sólo se resume y se señala dónde mirar.*

### 0.1 En pocas palabras
- **Qué se busca:** reglas de entrada (por ejemplo "RSI cruza tal valor y la media corta supera a la larga") que den ganancia **después de costos**, en datos que la regla **no vio** al elegirse, y de forma repetible en distintos períodos del mercado.
- **Dónde estamos:** con BTCUSDT 1h (2017-2026) **ninguna variante probada gana dinero fuera de muestra** (EXP-001, 002, 005). No hay "candidato" y el tramo final de datos reservado (holdout) **sigue sin abrirse**.
- **Qué se hizo además:** una buena parte del trabajo fue **comprobar que las mediciones son honestas** (que no se "espíe" el futuro, que no se confunda suerte con señal, que los números de confianza no estén inflados). Eso es lo que cubren EXP-003 a EXP-007 (todas terminadas); EXP-008 y EXP-009 usaron esa infraestructura para probar las dos primeras ideas de búsqueda nuevas (más información de contexto; búsqueda estructurada), ambas sin mejora. Esa infraestructura es la que permitirá creer en un resultado positivo si algún día aparece.

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
- Terminados: EXP-000 a EXP-009 (ver 0.2). En curso: ninguno.
- **Pendiente de la tabla original** (sección 4, Plan): TP/SL proporcionales al ATR; volumen y hora del día; periodicidad de re-búsqueda; modelos de costo dinámicos; comparación con Genetic Programming; CPCV, PBO sobre el lift y Deflated Sharpe. Nada de esto se descartó; cada uno se evalúa como experimento separado.
- La numeración vieja (EXP-003 = régimen, EXP-004 = contexto+disparador) **ya fue reemplazada** en la sección 4. Las features de régimen (la "EXP-003 original") se probaron en EXP-008 y la estructura "contexto + disparador" (la "EXP-004 original") en EXP-009: ninguna mejoró.

**4. Próximo experimento (propuesta, la decisión es tuya).**
1. ~~Cerrar EXP-007~~ (hecho: cooldown `until_exit`; deciden el t entre folds y el HAC, nunca el t entre operaciones).
2. ~~Features de régimen~~ (hecho en EXP-008: no mejoran la generalización; quedan implementadas y apagadas por defecto).
3. ~~Contexto + disparador~~ (hecho en EXP-009: no mejora; el generador queda implementado y apagado por defecto).
4. **Lo que sigue lo decidís vos.** Hay 4 experimentos de búsqueda seguidos sin avance (EXP-001, 002, 008, 009; CLAUDE.md pide revisar el rumbo a los 10). Lo único que ninguno cambió es la relación entre el costo (≈ 0,25 % por operación) y el recorrido por operación (TP 5 % / SL 3 % / horizonte 100 velas sobre BTC 1h). Opciones: (a) mover esa relación: TP/SL mayores o proporcionales al ATR, horizontes más largos, temporalidades más lentas; (b) ampliar a otros activos (más historia independiente); (c) más validez estadística (CPCV, PBO sobre el lift); (d) frenar la búsqueda de reglas de entrada y revisar el objetivo del proyecto. Cada una es un experimento separado y suma variantes (K).
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
- **El holdout sigue cerrado.** Contador acumulado de hipótesis (condiciones evaluadas): 4.291.500 al cierre de EXP-009. K (variantes en el Reality Check) = 8.
- Toda feature nueva: test de causalidad por truncación/perturbación del futuro y `run_lookahead.py` (EXP-006).

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
| Variantes / configuraciones (procedimientos completos) | 8 al cierre de EXP-009 (EXP-001, EXP-002, EXP-008-régimen y EXP-009-estructurada, cada uno LONG/SHORT; eran 4 antes de EXP-008 y 6 antes de EXP-009) | **Sí: K** | Son las que se comparan contra el mismo OOS y entre las que se podría reportar "la mejor". |
| Experimentos | 10 (EXP-000 a EXP-009) | **No** | Unidad de organización: un experimento puede tener 0, 1 o varias variantes, y variantes de experimentos distintos sobre los mismos datos compiten igual. |
| Hipótesis acumuladas | 4.291.500 (al cierre de EXP-009) | **No** | Contador de transparencia sobre cuánto se exploró; no entra en ningún test porque esa exploración está absorbida en TRAIN. Usarlo en Bonferroni sobreestimaría la corrección en unos seis órdenes de magnitud. |
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

### EXP-010 — Salidas TP/SL proporcionales al ATR vs TP/SL fijos [EN CURSO] (2026-10-06)
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
6. TP/SL proporcionales al ATR.
7. Volumen y hora del día / día de la semana; otras features.
8. Periodicidad de re-search/retraining (ampliar EXP-002).
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

