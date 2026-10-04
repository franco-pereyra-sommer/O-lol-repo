# Proyecto: investigación de condiciones de entrada (trading)

## Objetivo
Encontrar condiciones de entrada que tengan retorno neto positivo, después de
costos, **fuera de muestra** y de forma consistente en distintos regímenes de
mercado. La herramienta es exploratoria: no ejecuta órdenes reales ni se
conecta a exchanges para operar.

## Entorno
- Windows. Python vía Pixi: correr siempre `pixi run python ...` (o
  `pixi run pytest -q`) desde la raíz del repo.
- Datos en `D:\O lol\Guardado de datos\` (CSV con columnas Date, Open, High, Low, Close, Volume).
- Historia larga: `pixi run python -m trading_research.binance_data --symbol BTCUSDT --interval 1h --out "<ruta>.csv"`.

## Modo de trabajo autónomo
El usuario autorizó a Claude a decidir qué probar, modificar el código y
correr experimentos sin pedir permiso en cada paso, siguiendo este ciclo:

1. Leer `RESEARCH_LOG.md` (glosario, reglas de decisión y bitácora).
2. Elegir el próximo experimento según la bitácora y las reglas.
3. Escribir la hipótesis en la bitácora ANTES de correr.
4. Hacer el cambio de código (con tests si toca la lógica) y correr `pixi run pytest -q`.
5. Correr el experimento en walk-forward.
6. Registrar resultado, lectura, decisión y próximo paso en `RESEARCH_LOG.md`.
7. Hacer commit de código + bitácora con un mensaje `EXP-NNN: ...`.

## Reglas que no se rompen
- Decidir sólo con métricas walk-forward fuera de muestra. No inspeccionar
  precios crudos ni gráficos para elegir hipótesis.
- El holdout final se abre sólo para un candidato que cumpla los criterios de
  `RESEARCH_LOG.md`, una vez por candidato, y se registra aunque dé mal.
- Llevar la cuenta acumulada de hipótesis probadas.
- Ningún cambio puede introducir look-ahead: el test
  `test_no_lookahead_truncation_invariance` tiene que seguir pasando, y toda
  feature nueva necesita un test de causalidad equivalente.
- No bajar los costos para "hacer que algo funcione".
- Leer resúmenes (`wf_summary.csv`, `grid_summary.csv`, `meta.json`), no los
  CSV completos de resultados ni `events.csv.gz`, salvo que haga falta.

## Cuándo frenar y preguntar al usuario
- Antes de abrir el holdout.
- Si un candidato cumple los criterios (para mostrárselo).
- Si hace falta instalar algo nuevo, descargar datos de otra fuente o cambiar los costos.
- Después de 10 experimentos seguidos sin avance, para revisar el rumbo.
