#%%

# Numericos
import numpy as np
import pandas as pd

# Para que no rompa con el display
from IPython.display import display

# from trading_research.completeness import check_completeness
# from trading_research.dataset_update import download_yfinance, check_recovered, merge_datasets

ruta_csv_viejo = r"C:\O lol\O lol repo\results\run_BTC_1h_seed7_20261003_165046\results_validation.csv"

#%%

df = pd.read_csv(ruta_csv_viejo)

display(df)
# %%
