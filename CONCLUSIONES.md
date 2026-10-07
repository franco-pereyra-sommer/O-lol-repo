# Conclusión: reglas técnicas sobre precios en cripto (2017–2025)

*Línea cerrada el 2026-10-06 por decisión del usuario. Este documento resume lo que se hizo y lo que se puede (y no se puede) concluir. El detalle de cada experimento, con sus números, está en `RESEARCH_LOG.md`.*

## En pocas palabras

**Ninguna regla basada sólo en los precios pasados mostró ganancia en datos que no había visto, después de pagar costos.** Se probó en BTC y, para la regla más prometedora, también en ETH, XRP y BNB.

Además, el problema no son sólo los costos: **ni siquiera antes de costos apareció capacidad de anticipar hacia dónde va el precio**. Lo que a veces parecía ganancia era simplemente que BTC subió mucho en el período. Una regla que está comprada la mitad del tiempo gana la mitad de esa suba, sin acertar nada.

## La pregunta

¿Existen reglas, del tipo "si el RSI cruza tal valor y la media corta supera a la larga, comprar", que cumplan las tres condiciones siguientes?
- Ganan dinero **después de costos**: comisión, spread y deslizamiento de un usuario común de Binance.
- Lo hacen **fuera de muestra**: en datos que no se usaron para elegirlas.
- Lo hacen **de forma consistente** en distintos períodos del mercado, alcistas y bajistas.

## Qué se probó (16 experimentos, EXP-000 a EXP-014)

| Bloque | Experimentos | Qué se probó | Resultado |
|---|---|---|---|
| Punto de partida | EXP-000, 001, 002 | Búsqueda de entradas al azar sobre 9 años de BTC 1h (Binance), con 10 folds y con re-búsqueda mensual (90 folds); LONG y SHORT | Pierde ≈ lo que cuestan los costos (≈ −0,15 % a −0,6 % por operación). No se distingue de "entrar en cualquier vela". |
| ¿Las mediciones son honestas? | EXP-003 a 007 | Filtración entre datos de entrenamiento y de prueba, corrección por probar miles de reglas (Reality Check, PBO), uso de información futura, operaciones superpuestas | Las mediciones son confiables. Se corrigieron dos problemas: un número de confianza inflado y una fuga leve en un escenario de costos. |
| Variantes de la búsqueda de entradas | EXP-008 a 012b | Más información de contexto (tendencia diaria, volatilidad), reglas con estructura "contexto + disparador", otras salidas (proporcionales a la volatilidad), velas de 4 h, objetivos 2, 3 y 4 veces mayores | Ninguna mejora. La capacidad de anticipar la dirección es ≈ 0 en todas; el mejor caso dio t = 1,44 contra un umbral de ≈ 3. |
| Reglas de "estar o no estar comprado" | EXP-013 | Tres reglas fijas (tendencia de 20 y de 100 días, "no operar si está agitado") contra mantener siempre la misma exposición | Ninguna gana con claridad. La de 100 días dio t = 1,76 contra 3,05; "no operar si está agitado" fue claramente peor. |
| Confirmación | EXP-014 | La regla de 100 días, sin tocarla, en ETH, XRP y BNB | **No se confirmó**: algo positiva en ETH y BNB, en contra en XRP; en conjunto t = 0,45. |

El número "t" mide cuán lejos del azar está un resultado. Como se probaron muchas variantes, el proyecto exige t ≥ 3 o más. **Ningún resultado medido contra la referencia correcta ("entrar en cualquier vela" o la exposición constante) llegó a t = 2: el más alto fue 1,93**, en la regla de 100 días en BTC y antes de costos, y no se repitió en otros activos.

## Qué se puede concluir

1. **No hay ventaja después de costos** en ninguna de las variantes probadas. Ninguna se acercó al criterio de "candidato", así que nunca hubo motivo para abrir los datos reservados (holdout).
2. **Tampoco hay ventaja antes de costos.** Por eso bajar los costos (otro nivel de comisión, otro tipo de orden) no lo arreglaría: sólo haría perder menos. El costo de ≈ 0,24 % por operación ida y vuelta es casi todo lo que se pierde.
3. **La aparente ganancia de comprar a plazos largos es la suba de BTC, no la regla.** "Entrar en cualquier vela" o "tener siempre la misma parte invertida" la reproduce. Es la lección metodológica más importante: **siempre hay que comparar contra una referencia con la misma exposición al mercado**, si no se confunde la suba del activo con habilidad.
4. **Lo más parecido a una señal no se repitió.** Era la regla de tendencia de 100 días. Es lo esperable cuando se elige "la mejor de varias": suele deberse en parte a la suerte.
5. **El resultado no depende de un detalle de diseño.** Se mantuvo con varias formas de salida, dos tamaños de vela, objetivos chicos y grandes, más y menos estructura, más y menos información de contexto, y LONG y SHORT.

## Qué NO se puede concluir (límites)

Esto **no** demuestra que sea imposible ganar en cripto. Demuestra que **este tipo de reglas, en estas condiciones**, no lo logró. Quedó afuera:
- **Otra información:** sólo se usaron precios y derivados de ellos (medias, RSI, MACD, ATR, retornos, forma de las velas, tendencia y volatilidad). No se usaron volumen, hora del día, tasas de financiamiento de futuros, libro de órdenes, datos on-chain ni noticias.
- **Otros métodos:** las reglas fueron simples (una comparación, o "contexto + disparador"). No se probaron modelos estadísticos o de aprendizaje automático.
- **Otras escalas:** operaciones de horas a semanas con velas de 1 h y 4 h. No se probaron minutos ni plazos de varios meses.
- **Otros mercados:** cripto spot de Binance. ETH, XRP y BNB se usaron sólo para confirmar una regla. No se probaron acciones, monedas, materias primas ni estrategias que comparan muchas monedas entre sí.
- **Otro tipo de estrategia:** no se probaron hacer de mercado, arbitraje ni cobrar financiamiento.
- **El futuro:** el período evaluado va de diciembre de 2017 a mayo de 2025. Un período distinto podría comportarse distinto, para bien o para mal.

Este trabajo **no evalúa ni recomienda ninguna forma de invertir**. Sólo dice que estas reglas no agregaron valor sobre una exposición constante en el período estudiado.

## Cómo se cuidó que los números sean creíbles

- **Walk-forward:** cada regla se elegía con un tramo del pasado y se medía en el tramo siguiente, que no había visto. Se repitió hasta 90 veces a lo largo de los años.
- **Datos reservados (holdout) nunca abiertos:** desde el 22-05-2025 hasta octubre de 2026 en BTC, ETH, XRP y BNB. Siguen intactos.
- **Pruebas de que nada mira el futuro:** truncar y alterar los datos posteriores no cambia ninguna decisión. Hay 118 tests automáticos.
- **Corrección por haber probado muchas cosas:** se llevó la cuenta de 13.832.030 condiciones evaluadas y 36 variantes completas del procedimiento (K). Los umbrales subieron en consecuencia, y se usaron Reality Check y PBO para no confundir suerte con señal.
- **Preregistro:** cada experimento se escribió en el log antes de correrlo, con sus reglas de decisión, y no se cambiaron después de ver resultados. Cuando hubo un error propio (EXP-012), se registró y se repitió con autorización (EXP-012b) en lugar de arreglarlo sobre la marcha.
- **Costos no rebajados:** decidía el escenario `typical`; `conservative` se usaba como prueba de robustez.

## Números finales

| | |
|---|---|
| Experimentos | 16 (EXP-000 a EXP-014, incluido EXP-012b) |
| Condiciones evaluadas (acumulado) | 13.832.030 |
| Variantes completas del procedimiento (K) | 36 |
| Candidatos | 0 |
| Holdout | Nunca abierto (BTC, ETH, XRP y BNB desde 2025-05-22 14:00 UTC) |
| Tests automáticos | 118 |

## Qué queda para reutilizar

- **Búsqueda y validación:** `run_research.py`, que hace búsqueda de condiciones y walk-forward con purga, varios escenarios de costos y salidas fijas o por volatilidad.
- **Herramientas contra la suerte y el uso del futuro:** `run_reality_check.py`, `run_pbo.py` y `run_lookahead.py`.
- **Reglas de exposición:** `run_exposure.py` y `run_exposure_confirm.py` (módulo `trading_research/exposure.py`). Comparan contra exposición constante y combinan varios activos.
- **Datos:** `trading_research/binance_data.py` baja historia de cualquier par de Binance. Los datos de BTC, ETH, XRP y BNB en 1 h están en `D:\O lol\Guardado de datos`.

## Si algún día se retoma

- Tiene que ser con **información distinta**, no con otra regla sobre los mismos precios. Ejemplos: el financiamiento de los futuros perpetuos, que Binance publica en la misma fuente; el volumen y la hora del día; o una prueba con modelos simples de si existe algo que predecir.
- Hace falta un **diseño preregistrado** y autorización para datos nuevos.
- La cuenta de K y de hipótesis continúa desde los valores de arriba.
- **El holdout sigue reservado:** se puede usar una sola vez, para un candidato que cumpla los criterios.
