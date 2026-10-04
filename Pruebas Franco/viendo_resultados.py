#%%

# Numericos
import numpy as np
import pandas as pd

# Para que no rompa con el display
from IPython.display import display

# from trading_research.completeness import check_completeness
# from trading_research.dataset_update import download_yfinance, check_recovered, merge_datasets

#%%

ruta = r"C:\O lol\O lol repo\results\grid_20261003_200434\run_BTC_1h_seed41_tp0.05_sl0.03_h100_20261003_200855\results_test.csv"

df = pd.read_csv(ruta)

display(df)

# %%
