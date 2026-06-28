import pandas as pd
df = pd.read_csv("ml/data/training_data.csv")
print(df.nlargest(5, "pct_change_next")[["item_name", "chaos_value", "collected_at", "pct_change_next"]])
print()
print(df.nsmallest(5, "pct_change_next")[["item_name", "chaos_value", "collected_at", "pct_change_next"]])