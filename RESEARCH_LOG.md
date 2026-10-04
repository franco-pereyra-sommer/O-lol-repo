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
| `net_return` (neto) | El bruto descontando comisión (en cada lado), slippage (en cada lado) y medio spread al entrar y medio al salir. Con los valores actuales, unos 0,32 % por operación completa. |
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
   - retorno neto OOS agrupado de todos los folds > 0 con t ≥ 3, usando cooldown `until_exit`;
   - al menos 100 operaciones OOS en total.
5. **Una sola variable por experimento** cuando sea posible, para saber qué causó el cambio.
6. **Un resultado negativo también se registra.** Descartar ideas es parte del avance.

---

## 3. Bitácora

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
Resultado:
- Split único TRAIN/VAL/TEST: miles de condiciones probadas en varias grillas; ninguna sobrevive de forma creíble. La única que pasó un TEST tuvo t ≈ 0,19 (indistinguible de 0) y fue 1 de 288 evaluadas.
- Walk-forward 4 folds (TP 5 %, SL 3 %, 100 velas, `until_exit`, filtro `both`): LONG con OOS > 0 en 1/4 folds; SHORT en 0/4.
- Con una serie aleatoria de 80.000 velas, el procedimiento no "encuentra" nada (control correcto).
Lectura: dos años de datos alcanzan para un solo régimen por segmento; no se puede distinguir una señal de un efecto del régimen del mercado.
Decisión: pasar a historia larga de Binance (desde 2017) y evaluar todo en walk-forward.
Próximo paso: EXP-001 — descargar BTCUSDT 1h de Binance y repetir la línea base y el walk-forward LONG/SHORT con la configuración actual, como punto de referencia.
