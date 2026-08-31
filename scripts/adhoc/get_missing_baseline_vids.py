import pandas as pd

from youtube_code.store import video_registry, screening_state_store
from youtube_code.config import OUTPUTS

df = pd.read_csv(OUTPUTS /"segment_analysis" / "channel_video_populism.csv")

channels = set(df["channel_id"].tolist())
print(len(channels))


df2 = pd.read_csv(OUTPUTS / "segment_analysis" / "channel_classification_ideology.csv")
done = set(df2["channel_id"].tolist())

need = channels - done
print(len(need))

