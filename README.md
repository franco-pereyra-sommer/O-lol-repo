# Investigación exploratoria de condiciones de entrada (v0.1)

Herramienta de investigación: genera condiciones de entrada, detecta cuándo se
habrían cumplido y mide estadísticamente qué pasó con el precio después.
**No ejecuta operaciones ni se conecta a exchanges.**

## Uso

```bash
pip install -r requirements.txt
python run_research.py                                   # BTC 1h desde Yahoo Finance
python run_research.py --csv "../Guardado de datos/BTC-USD_int1h_12.31 22.53.54.csv"
python run_research.py --depth 2 --seed 7                # condiciones complejas
python run_research.py --depth 2 --run-test              # evaluar TEST (una sola vez, al final)
python -m pytest -q                                      # tests
```

Todos los parámetros están en `trading_research/config.py` (`ResearchConfig`).

## Opciones de línea de comandos

`python run_research.py --help` lista todas. Las más usadas:

| Opción | Qué hace |
|---|---|
| `--tp 0.05 0.08` | Take profit (fracción). Varios valores → grilla |
| `--sl 0.02 0.03` | Stop loss (fracción). Varios valores → grilla |
| `--horizon 30 100` | Horizonte máximo en velas. Varios valores → grilla |
| `--cooldown-mode fixed\|until_exit` | `fixed`: cooldown de `--cooldown` velas; `until_exit`: no re-entrar mientras la operación anterior siga abierta |
| `--filter-mode absolute\|lift\|both` | Umbrales fijos, mejora sobre la línea base del segmento, o ambos |
| `--min-lift-p-tp 0.03` / `--min-lift-return 0` | Umbrales del modo lift |
| `--pool-size 150` | Piezas simples usadas para construir las condiciones complejas |
| `--commission --slippage --spread` | Costos por lado |

Con más de una combinación de TP/SL/horizonte se crea `results/grid_<fecha>/`
con una carpeta por combinación y `grid_summary.csv` comparándolas. Datos e
indicadores se calculan una sola vez. Ojo: cada combinación extra multiplica la
cantidad de hipótesis probadas.

En modo `lift` una condición puede pasar con retorno absoluto negativo (mejora
sobre "entrar siempre", pero no gana plata). `both` exige las dos cosas.

## Flujo

```
DataSource → OHLC → FeatureStore (indicadores, velas, retornos)
          → Condition (árbol) → señal bool en t → entradas (t+1, cooldown, purga)
          → OutcomeTable (TP/SL/NONE/AMBIGUOUS, MFE/MAE, costos) → estadísticas
Etapa 1 (simples, TRAIN) → pool → Etapa 2 (complejas, TRAIN) → filtros
          → VALIDATION → filtros → [TEST] → results/run_…/
```

| Módulo | Responsabilidad |
|---|---|
| `config.py` | todos los parámetros; se guardan con cada corrida |
| `data.py` | `DataSource` (yfinance, CSV), normalización, detección de huecos |
| `indicators.py` | SMA, EMA, RSI (Wilder), MACD, ATR (Wilder) + registro |
| `features.py` | operandos (precio, indicador, vela, retorno, ATR/Close, constante) y caché |
| `conditions.py` | árbol de expresión: Compare, Cross, And, Or, Not, Then, OccurredWithin |
| `condition_generator.py` | generación aleatoria reproducible, etapas 1 y 2 |
| `entry_detector.py` | entrada en `Open[t+1]`, cooldown por condición, purga de horizonte |
| `outcome_evaluator.py` | tabla de resultados por vela de entrada |
| `statistics.py` | métricas por condición, línea base, IC de Wilson |
| `validation.py` | split cronológico, filtros, generador walk-forward (preparado) |
| `search.py` | orquestación, guardado y recarga |

## Decisiones de arquitectura

- **Resultado precalculado por vela.** El resultado de una operación sólo
  depende de la vela de entrada, no de la condición. Se calcula una vez para
  todas las velas y cada condición indexa esa tabla. 800 condiciones corren en
  unos 4 s.
- **Condiciones como árboles**, con clave canónica (`A AND B` = `B AND A`)
  para deduplicar, `to_dict`/`condition_from_dict` para serializar y
  `describe()` para mostrar.
- **Umbrales por cuantiles de TRAIN.** No hay rangos fijos por indicador: el
  umbral de `RSI(17) < x` es un cuantil sorteado de la distribución de RSI(17)
  en TRAIN. Los operandos no estacionarios (MACD en unidades de precio) sólo
  se comparan contra 0 o contra su señal.
- **Comparaciones sólo dentro de la misma escala** (precio con precio, RSI con
  RSI, MACD con la señal del mismo MACD…), para evitar condiciones absurdas
  como `RSI > EMA`.
- **Línea base.** Cada segmento reporta el resultado de entrar en *todas* las
  velas. Una condición sólo es interesante si mejora esa línea base.
- **SHORT** ya está previsto en `PositionSide`; agregarlo implica invertir
  TP/SL y High/Low en `outcome_evaluator`.

## Ambigüedades de la especificación y cómo se resolvieron

1. **Horizontes que cruzan segmentos.** Una entrada al final de TRAIN mediría
   su resultado con precios de VALIDATION. Esas entradas se **descartan
   (purga)** y se cuentan en `n_dropped_horizon`. Los indicadores sí se
   calculan sobre la serie completa porque son causales.
2. **AMBIGUOUS y el retorno esperado.** La clasificación queda como AMBIGUOUS,
   pero E[R] necesita un número. `AMBIGUOUS_RETURN_POLICY="worst"` (asume SL)
   por defecto; también se reporta `mean_net_return_excl_ambiguous`.
3. **NONE.** Retorno = cierre de la última vela del horizonte (salida por tiempo).
4. **Gaps.** Si una vela abre por debajo del SL, se llena en la apertura. El TP
   se llena en el nivel, sin asumir mejora.
5. **MFE/MAE** se miden sobre todo el horizonte aunque TP/SL cierren antes:
   describen el camino del precio, no la operación.
6. **"Exactamente en t_ent + Δt"** = cierre de la vela `e+Δt-1`, es decir Δt
   velas después de la apertura de entrada.
7. **`A THEN B within N` ≡ `B AND (A ocurrió en [t-N, t-1])`.** Son
   matemáticamente equivalentes. Se mantienen ambos nodos por legibilidad
   (hay un test que verifica la equivalencia). "Previas N velas" excluye la
   vela actual.
8. **Profundidad.** Las hojas valen 1; AND/OR/NOT/THEN suman 1;
   `OccurredWithin` es un modificador y no suma. Con el
   `MAX_CONDITION_DEPTH = 1` pedido **la etapa 2 no genera nada**: usar
   `--depth 2` o más para combinaciones.
9. **Costos.** La comisión se cobra en cada lado, el slippage es adverso en
   cada lado y el spread se paga mitad al entrar y mitad al salir.
10. **Cooldown y solapamiento.** Con cooldown (10) menor que el horizonte (30),
    las operaciones de una misma condición se solapan, así que sus resultados
    no son independientes y el `t` reportado sobreestima la evidencia. Para
    operaciones sin solapamiento usar `--cooldown-mode until_exit`. La línea
    base siempre entra en todas las velas, en cualquier modo.
11. **Selección del pool de la etapa 2.** Hace falta algún criterio, y se usa
    la mejora sobre la línea base en P(TP_FIRST), sólo con TRAIN. No es un
    ranking de estrategias.
12. **"Expected return > 0"** usa el retorno **neto** por defecto
    (`EXPECTED_RETURN_BASIS`).
13. **Velas faltantes.** Ventanas y horizontes se cuentan en velas, no en
    tiempo de reloj. `data.quality_report` informa los huecos. El CSV de BTC
    2024-2025 tiene 5, el mayor de unos 4 días.
14. **Yahoo 1h** sólo ofrece unos 730 días, lo que limita el tamaño del TEST.
    La capa de datos permite cambiar de fuente sin tocar el resto.

## Salida (`results/run_<asset>_<tf>_seed<seed>_<fecha>/`)

`config.json`, `meta.json` (cantidad de hipótesis evaluadas, segmentos,
huecos), `baselines.json`, `conditions.json` (árboles recargables con
`search.load_conditions`), `results_train|validation|test.csv` (una fila por
condición) y `events.csv.gz` (una fila por entrada).

## Advertencia

Con cientos de hipótesis, algunas pasan TRAIN y VALIDATION por azar. Ejemplo
real con el CSV incluido (seed 42, depth 2): 800 condiciones, 14 pasan TRAIN,
1 pasa VALIDATION (retorno neto medio +1.27 %, t ≈ 3.3) y en TEST da −0.57 %.
