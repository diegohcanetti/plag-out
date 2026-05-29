import pandas as pd
import numpy as np

df = pd.DataFrame({
    'date': pd.to_datetime(['2026-01-01', '2026-01-02']),
    'temp_max': [25.0, np.nan]
})

for _, row in df.iterrows():
    print("row temp_max type:", type(row['temp_max']), "value:", repr(row['temp_max']))

