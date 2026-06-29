import pandas as pd

df = pd.read_json("channel_list.json")
print(len(df))