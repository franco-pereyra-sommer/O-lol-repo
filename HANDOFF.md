# Handoff para la conversación siguiente (2026-10-06)

Este archivo existe para retomar el trabajo en una conversación nueva sin perder contexto. **Lo que decide es `RESEARCH_LOG.md` (sección 0 y reglas de la sección 2); acá sólo está lo que el log no dice** (acuerdos hechos de palabra, trampas del entorno y la decisión pendiente). Si algo de acá contradice al log o a `CLAUDE.md`, mandan ellos.

## 0. Actualización (2026-10-06, después de EXP-013) — leer primero
- Lo que sigue abajo (secciones 1 a 8) se escribió **antes** de EXP-013 y quedó desactualizado en lo que dice de la rama pendiente; lo vigente es esto y la sección 0 del log.
- El usuario eligió la **rama a2** y **reiniciar en 0 el contador de experimentos seguidos sin avance**. Se preregistró y corrió **EXP-013**: tres reglas fijas de "comprado o en efectivo" (tendencia de 20 y 100 días, calma 24/240 h) contra exposición constante igualada. Resultado: **escenario A informativo**, sin candidato. R2 (tendencia de 100 días) quedó como observación: positiva en los 5 tramos, pero con t 1,76 contra 3,05. R3 es significativamente peor que la exposición constante.
- Cuentas: **K = 33**, **13.831.770 hipótesis**, contador sin avance = 1, holdout cerrado, sin push. Código nuevo: `trading_research/exposure.py`, `run_exposure.py`, `tests/test_exposure.py` (115 tests pasan).
- **Próximo paso sin decidir** (opciones en la entrada EXP-013 del log): cerrar la línea, confirmar R2 tal cual en otros activos (requiere autorización de datos y costos) o la rama a1.

## 1. Qué decidió el usuario
- Eligió la **opción (a) de la sección 0.3 del log: cambiar el objeto de estudio** (no seguir buscando entradas técnicas aleatorias sobre BTCUSDT 1h).
- **No se definió todavía qué rama ni qué diseño.** Esa es la primera tarea de la conversación nueva: proponer el diseño y **preguntar** antes de correr nada.
- Contexto: 8 experimentos de búsqueda seguidos sin avance (EXP-001, 002, 008, 009, 010, 011, 012, 012b). CLAUDE.md pide revisar el rumbo a los 10; la revisión se hizo ahora por decisión del usuario. Confirmar con el usuario si el contador de "sin avance" se reinicia con el cambio de objeto.

## 2. Estado en pocas líneas
- Repo `D:\O lol\O-lol-repo`, rama `main`, **sin push** (nunca se hizo; no hacerlo sin que lo pida).
- Último experimento: **EXP-012b** (commit `e7843fe`). 14 experimentos, **13.831.500 hipótesis acumuladas, K = 30**, 107 tests pasan, **holdout cerrado**, ningún candidato.
- Hallazgo central: con BTCUSDT 1h/4h, TP/SL de 5 % a 20 %, entradas aleatorias, de régimen o estructuradas, no hay lift bruto detectable; el neto ≈ −costo. Lo que parece ganancia en LONG a horizontes largos es la **deriva alcista de BTC**: la línea base "entrar en cada vela" lo reproduce. **Sólo el lift contra esa línea base es interpretable.**
- Datos locales: sólo `D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv` (+ caché `binance_cache\BTCUSDT`). No hay otros activos descargados.

## 3. Acuerdos de trabajo (dichos en el chat; sólo parte está en CLAUDE.md)
- **No hacer push.** Commits autorizados con mensaje `EXP-NNN: ...` (código + bitácora).
- **Holdout cerrado.** Se abre sólo con autorización explícita, una vez por candidato; si algo cumple los criterios, frenar y mostrarlo.
- **Costos:** no bajarlos. `typical` decide; `conservative` es robustez. Cambiar costos, bajar datos nuevos o instalar dependencias requiere autorización.
- **Preregistrar antes de correr** en `RESEARCH_LOG.md`: hipótesis, cantidad de hipótesis nuevas, K antes/después y reglas de decisión (escenarios A–D).
- **No modificar umbrales, reglas, TRAIN/VAL, mínimo de operaciones ni cantidad de condiciones después de ver resultados.** Si hace falta, se registra como desviación y se repite con autorización (así se hizo EXP-012 → EXP-012b).
- **No encadenar experimentos automáticamente** (nada de "y ahora EXP-013" ni combinar cosas sin decisión). Si una decisión necesaria no está definida: frenar y preguntar.
- Leer resúmenes (`wf_summary.csv`, `meta.json`, `comparison.json`), no los CSV completos.
- Franco no sigue los detalles técnicos: **responder en español, sin jerga, y dejar el log (sección 0) suficiente para guiarlo.** Si se agrega algo, no borrar lo que ya está.

## 4. Las dos ramas de la opción (a) (notas de Claude, no decisiones)
**a1. Otros activos/mercados.**
- Cripto altamente correlacionado con BTC aporta poca historia realmente independiente; mercados distintos (acciones, FX, materias primas) darían más independencia pero necesitan otra fuente de datos (EXP-000 usó Yahoo).
- Requiere **autorización** para descargar datos y para definir costos del nuevo activo (hoy el modelo de costos `typical`/`conservative` está pensado para BTCUSDT).
- Para K: otro activo = otra historia OOS, o sea otra familia (regla 7, condición (i)); definir si se corrige por separado o en conjunto antes de correr.

**a2. Reglas que no son de entrada** (filtros "no operar" según régimen, tamaño/gestión de posición).
- Hay que definir **qué se mide y contra qué**. Cualquier regla sesgada a LONG hereda la deriva de BTC: el benchmark tiene que estar **igualado en exposición** (mismo tiempo en el mercado) o se confunde deriva con habilidad.
- El criterio de candidato de la regla 4 está pensado para entradas con TP/SL; habría que decidir si se adapta (y registrarlo antes de correr).

## 5. Infraestructura reutilizable
- `run_research.py` (WFO; banderas `--regime-features`, `--search-mode`, `--exit-mode`, `--csv-timeframe`, `--wf-train-bars/--wf-val-bars`, `--min-cases-frac`), `run_reality_check.py`, `run_pbo.py`, `run_lookahead.py`, `run_*_comparison.py`, `run_sanity_*.py`. Los módulos están en `trading_research/`.
- **Mínimo efectivo de operaciones = `max(30, 1 % de las barras del segmento)`.** Con otra longitud de TRAIN hay que decidirlo explícitamente (`--min-cases-frac 0` da 30).
- Toda feature, costo o regla nueva: test de causalidad (truncar/perturbar el futuro) y `run_lookahead.py`.

## 6. Trampas del entorno
- Siempre `pixi run python ...` y `pixi run pytest -q` desde la raíz. Python 3.11 (no repetir las mismas comillas dentro de un f-string).
- Salida con flechas o acentos: `PYTHONIOENCODING=utf-8` (sino cp1252 rompe el print).
- pandas 3: el índice datetime puede venir en µs; usar `as_unit("ns")` al alinear.
- Heredocs de bash con comillas simples o backticks se rompen: escribir scripts a archivo.
- Al insertar entradas en `RESEARCH_LOG.md` por script, usar el marcador `"\n---\n\n## 4. Plan"`; **no** la cadena suelta `"## 4. Plan"` (aparece en el texto de la introducción y una vez borró entradas por error).

## 7. Prompt sugerido para abrir la conversación nueva
> Leé `CLAUDE.md`, `HANDOFF.md` y la sección 0 de `RESEARCH_LOG.md`. Elegí la opción (a) (cambiar el objeto de estudio). Antes de correr nada: proponeme las dos ramas (a1 otros activos/mercados, a2 reglas que no son de entrada) con un diseño concreto de cada una, qué requeriría mi autorización y el K resultante, y preguntame cuál elijo. No abras el holdout, no hagas push, no encadenes experimentos, y preregistrá todo en el log antes de ejecutar.

## 8. Si hace falta más detalle
La conversación anterior completa está en `C:\Users\Franco\.claude\projects\D--O-lol-O-lol-repo\3b4a8313-f295-4df8-8e0c-01a9d8bce5ae.jsonl` (es grande; usarla sólo para buscar un detalle puntual, no para leerla entera).
