import pandas as pd
import krippendorff
import numpy as np


df = pd.read_excel("all_results_merged_0.xlsx")

df= df[["ideology_score_all_statements", "ideology_score_05_gemini-2.5-flash"]]
df = df.T.to_numpy()
alpha = krippendorff.alpha(reliability_data=df, level_of_measurement='ordinal')
print(alpha)