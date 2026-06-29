import pandas as pd

df =pd.read_csv("classification_results_051_gemini-2.5-flash.csv")
df2 =pd.read_csv("classification_results_2_051_gemini-2.5-flash.csv")

df3 = pd.concat([df, df2])

print(len(df), len(df2), len(df3))
df3.to_csv("classification_results_051_gemini-2.5-flash_complete.csv", index = False)