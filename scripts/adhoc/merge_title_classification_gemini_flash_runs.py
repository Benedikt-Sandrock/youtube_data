import pandas as pd

df = pd.read_csv("run_0002.csv")
df2 = pd.read_csv("run_0003.csv")
print(len(df), len(df2))

df = pd.concat([df, df2])

df.to_csv("run_0002.csv")
print(len(df))