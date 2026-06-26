from youtube_code.config import OUTPUT_GEMINI, SAMPLES
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

IDEOLOGY_BINS = [-0.01, 3.5, 7.5, 10.01]
IDEOLOGY_LABELS = ["Left", "Center", "Right"]

POPULISM_BINS = [-0.01, 3, 7, 10.01]
POPULISM_LABELS = ["Low", "Middle", "High"]

kw = pd.read_json(SAMPLES / "combined" / "kw_vids.json")
sent = pd.read_csv(OUTPUT_GEMINI / "classification_combined" / "classification_results_0_gemini-2.5-flash.csv")
channel_df = pd.read_excel(OUTPUT_GEMINI/ "channel_results_051.xlsx")


df = pd.merge(kw, sent, on = "video_id", how = "inner")
df2 = pd.merge(df, channel_df[["channel_title", "ideology_channel_mean", "populism_channel_mean"]], on = "channel_title", how = "left")
# l = [kw, sent, channel_df, df, df2]
# for w in l:
#     print(len(w))

df2["ideology_group"] = pd.cut(df2["ideology_channel_mean"], bins = IDEOLOGY_BINS, labels=IDEOLOGY_LABELS, include_lowest=True)
df2["populism_group"] = pd.cut(df2["populism_channel_mean"], bins = POPULISM_BINS, labels=POPULISM_LABELS, include_lowest=True)


df2["month"] = df["published_at"].dt.to_period("M")
df2 = df2[(df2["month"] > "2023-07") & (df2["month"] < "2026-01")]
#df2.to_csv("sentiment_merged.csv", index = False)


sentiment_vars= {"israel_regierung": "Israeli Government", "palaestinenser_zivil": "Palestinian Civilians", "hamas": "Hamas", "westliche_staaten": "Western States"}

for var, name in sentiment_vars.items():
    df_ideology = df2.groupby(['month', 'ideology_group'])[var].mean().reset_index()
    df_populism = df2.groupby(['month', 'populism_group'])[var].mean().reset_index()

    df_ideology['month_str'] = df_ideology['month'].astype(str)
    df_populism['month_str'] = df_populism['month'].astype(str)

    # df_ideology[var] = df_ideology.groupby('ideology_group')[var] \
    #     .transform(lambda x: x.ewm(span=3, adjust=False).mean())
    #
    # df_populism[var] = (df_populism.groupby("populism_group")[var].
    #                     transform(lambda x: x.ewm(span = 3, adjust = False).mean()))

    # Plot 1: Ideologie
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df_ideology, x='month_str', y=var, hue='ideology_group', marker='o')
    plt.title(f'Average sentiment: {name} (by ideology)')
    plt.xticks(rotation=45)
    plt.ylabel('Sentiment Score')
    plt.xlabel('Month')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.show()

    # Plot 2: Populismus
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df_populism, x='month_str', y=var, hue='populism_group', marker='o')
    plt.title(f'Average Sentiment: {name} (by populism)')
    plt.xticks(rotation=45)
    plt.ylabel('Sentiment Score')
    plt.xlabel('Month')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.show()

