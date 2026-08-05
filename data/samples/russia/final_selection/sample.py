import pandas as pd

df = pd.read_csv("final_video_selection_with_reserve.csv")

df = df[df["channel_id"] == "UCQGqiGhMjc_p4lZEhSTb12g"]

df.to_csv("Vermietertagebuch_IDs.csv", index=False)