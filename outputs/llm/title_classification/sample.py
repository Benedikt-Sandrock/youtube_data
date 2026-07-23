import pandas as pd

df = pd.read_csv("run_0003.csv")
dfs = pd.read_csv("run_0004.csv")

df =pd.concat([dfs,df])

df.to_csv("run_0003_complete.csv", index = False)
