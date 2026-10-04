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

*Esta sección es el punto de entrada para quien no siguió el trabajo. Se actualiza al cerrar cada experimento. Última actualización: 2026-10-04, tras cerrar EXP-007. El detalle de cada experimento está en la sección 3 (bitácora); acá sólo se resume y se señala dónde mirar.*

### 0.1 En pocas palabras
- **Qué se busca:** reglas de entrada (por ejemplo "RSI cruza tal valor y la media corta supera a la larga") que den ganancia **después de costos**, en datos que la regla **no vio** al elegirse, y de forma repetible en distintos períodos del mercado.
- **Dónde estamos:** con BTCUSDT 1h (2017-2026) **ninguna variante probada gana dinero fuera de muestra** (EXP-001, 002, 005). No hay "candidato" y el tramo final de datos reservado (holdout) **sigue sin abrirse**.
- **Qué se hizo además:** una buena parte del trabajo fue **comprobar que las mediciones son honestas** (que no se "espíe" el futuro, que no se confunda suerte con señal, que los números de confianza no estén inflados). Eso es lo que cubren EXP-003 a EXP-007 (todas terminadas). Esa infraestructura es la que permitirá creer en un resultado positivo si algún día aparece.

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
- Terminados: EXP-000 a EXP-007 (ver 0.2). En curso: ninguno.
- **Pendiente de la tabla original** (sección 4, Plan): features de régimen (tendencia en 4h/diario, volatilidad); condiciones "contexto + disparador"; TP/SL proporcionales al ATR; volumen y hora del día; periodicidad de re-búsqueda; modelos de costo dinámicos; comparación con Genetic Programming; CPCV, PBO sobre el lift y Deflated Sharpe. Nada de esto se descartó; cada uno se evalúa como experimento separado.
- La numeración vieja (EXP-003 = régimen, EXP-004 = contexto+disparador) **ya fue reemplazada** en la sección 4.

**4. Próximo experimento (propuesta, la decisión es tuya).**
1. ~~Cerrar EXP-007~~ (hecho: cooldown `until_exit`; deciden el t entre folds y el HAC, nunca el t entre operaciones).
2. Volver a lo experimental. Lo más coherente con el plan es **features de régimen** (tendencia en temporalidades mayores y volatilidad relativa), porque son el requisito de "contexto + disparador". Tras agregarlas hay que correr `run_lookahead.py` (regla de EXP-006) y comparar contra las 4 variantes con el Reality Check (K sube a 5, 6…).
3. Alternativa si prefieres más validez antes de más capacidad: CPCV o PBO sobre el lift.
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

---

## 4. Plan

Orden revisado a pedido del usuario (2026-10-04): primero validez estadística del proceso (EXP-003 y EXP-004, hechos), después el resto. La numeración siguiente es provisoria y se puede cambiar según resultados, registrando el motivo. Cada ítem es un experimento separado.

Siguiente (alta prioridad, completa la línea de validez):
1. ~~`procedure_oos_series` + Reality Check sobre las 4 variantes~~ (hecho en EXP-005; SPA queda como extensión).
2. ~~Segunda prueba de look-ahead a nivel de señales~~ (hecho en EXP-006; se corre con `run_lookahead.py` tras cada feature/costo nuevo).
3. ~~Revisión del tratamiento estadístico de operaciones superpuestas~~ (hecho en EXP-007).

Hoja de ruta original, conservada:
4. Features de régimen: tendencia en temporalidades mayores (4h, diario) y volatilidad relativa (era EXP-003).
5. Condiciones con lógica "contexto + disparador" y búsqueda por estados/eventos (idea B).
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

