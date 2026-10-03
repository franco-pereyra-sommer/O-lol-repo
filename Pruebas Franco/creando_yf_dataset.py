#%%

# Numericos
import numpy as np
import pandas as pd

# Para que no rompa con el display
from IPython.display import display

from trading_research.completeness import check_completeness
from trading_research.dataset_update import download_yfinance, check_recovered, merge_datasets

#%%

# --- Parametros ---
asset = "BTC-USD"
interval = "1h"
period = "max"  # yfinance igual va a recortar esto para intervalos intradia (ver abajo)

ruta_csv_viejo = "C:\O lol\Guardado de datos\BTC-USD_int1h_12.31 22.53.54.csv"

#%%

# --- 1) Cargar el dataset viejo y ver que fechas le faltan ---
df_viejo = pd.read_csv(ruta_csv_viejo)
df_viejo["Date"] = pd.to_datetime(df_viejo["Date"], utc=True)

reporte_viejo = check_completeness(df_viejo, date_col="Date", freq=interval, market="continuous")
print(reporte_viejo)

fechas_faltantes = reporte_viejo.missing
print(f"\n{len(fechas_faltantes) = }")

print(f"\n{fechas_faltantes = }")

#%%

# --- 2) Descargar un dataset fresco de Yahoo Finance ---
# Ojo: para intervalos intradia (1h, 5m, etc.) Yahoo NO entrega todo el
# historico aunque period="max" -> 1h trae como maximo los ultimos ~730
# dias. Por eso el dataset nuevo solo puede "rescatar" fechas faltantes
# que caigan dentro de esa ventana reciente; para huecos mas viejos no va
# a servir y hay que buscarlos en otra fuente.
df_nuevo = download_yfinance(asset, interval, period=period)
display(df_nuevo)
print(f"{df_nuevo.shape[0] = }")
print(f"{df_nuevo['Date'].min() = }  ->  {df_nuevo['Date'].max() = }")

#%%

# --- 3) Ver cuales de las fechas faltantes aparecen en el dataset nuevo ---
reporte_recuperacion = check_recovered(fechas_faltantes, df_nuevo, date_col="Date")
print(reporte_recuperacion)

print("\nRecuperadas (estaban faltando y el dataset nuevo SI las tiene):")
display(reporte_recuperacion.recovered)

print("\nSiguen faltando incluso en el dataset nuevo:")
display(reporte_recuperacion.still_missing)

#%%

# --- 4) Combinar viejo + nuevo para maximizar la cobertura ---
# prefer="old": si una misma fecha esta en los dos datasets, se queda el
# valor del viejo (ya revisado); el nuevo solo aporta las fechas que al
# viejo le faltaban.
df_combinado = merge_datasets(df_viejo, df_nuevo, date_col="Date", prefer="old")

print(f"{df_viejo.shape[0] = }")
print(f"{df_nuevo.shape[0] = }")
print(f"{df_combinado.shape[0] = }  (filas nuevas aportadas: {df_combinado.shape[0] - df_viejo.shape[0]})")

reporte_combinado = check_completeness(df_combinado, date_col="Date", freq=interval, market="continuous")
print(f"\n{reporte_combinado}")

fechas_faltantes = reporte_combinado.missing
print(f"\n{len(fechas_faltantes) = }")

print(f"\n{fechas_faltantes = }")

#%%

# --- 5) Guardar el dataset combinado (sin pisar el CSV viejo) ---
# Descomentar cuando el resultado de arriba se vea bien.

ruta_salida = "C:/O lol/Guardado de datos/BTC-USD_int1h_combinado.csv"
df_combinado.to_csv(ruta_salida, index=False)
print(f"Guardado en: {ruta_salida}")

# %%
