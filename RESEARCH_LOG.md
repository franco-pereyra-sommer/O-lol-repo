# Registro de investigación

Objetivo: encontrar condiciones de entrada que, después de costos, tengan
retorno esperado positivo **fuera de muestra** y de forma **consistente** en
distintos períodos del mercado. Encontrar "algo que funcionó en el pasado" no
alcanza: con miles de pruebas, siempre aparece algo por azar.

Este archivo tiene tres partes:
1. Glosario: qué significa cada valor de los resultados y cómo se calcula.
2. Reglas de decisión, fijadas ANTES de ver resultados.
3. Bitácora de experimentos: qué se probó, qué dio, qué se decidió y qué sigue.

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
5. **Una sola variable por experimento** cuando sea posible, para saber qué causó el cambio.
6. **Un resultado negativo también se registra.** Descartar ideas es parte del avance.

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

### EXP-004 — White Reality Check + PBO (2026-10-04) [EN CURSO]
Hipótesis (escrita antes de la corrida definitiva de `run_pbo.py`): en el espacio de búsqueda actual (7.500 condiciones simples, TP 5 %/SL 3 %/100 velas, `until_exit`, costos `typical`, 16 bloques del período de desarrollo, holdout fuera) la PBO es ≥ 0,5 y el retorno neto medio de la mejor condición IN-sample es negativo o ~0 OUT-of-sample, porque no hay información en las condiciones y el costo (~0,25 %) empuja todo hacia abajo. Un piloto con 1.500 condiciones LONG (ya corrido, cuenta como 1.500 hipótesis) dio PBO 0,62, mejor IN +0,68 % → OUT −0,27 %. Corrida definitiva: LONG y SHORT × 7.500 = 15.000 hipótesis (acumulado: 1.516.500).

---

## 4. Plan

Orden previsto (se puede cambiar según resultados, registrando el motivo):

1. **EXP-001** — Descargar BTCUSDT 1h de Binance (desde 2017). Línea base y walk-forward LONG y SHORT con la configuración actual y costos `typical`. Es la referencia contra la que se compara todo lo demás.
2. **EXP-002** — Walk-forward de ventanas cortas (idea A). Se implementa antes de seguir agregando features, para que todos los experimentos posteriores se evalúen igual.
3. **EXP-003** — Features de régimen: tendencia en temporalidades mayores (4h, diario) y volatilidad relativa. Son requisito para la idea B.
4. **EXP-004** — Condiciones con lógica (idea B): plantillas "contexto + disparador" en lugar de combinaciones totalmente aleatorias.
5. **EXP-005** — TP/SL proporcionales al ATR.
6. **EXP-006** — Volumen y hora del día / día de la semana.

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

