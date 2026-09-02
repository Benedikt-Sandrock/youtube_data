import pandas as pd

from youtube_code.store.llm_run_store import get_runs
from youtube_code.store.screening_state_store import get_state
from youtube_code.config import OUTPUTS

SOURCE = "segment_analysis_active"
PROMPT = "IDEOLOGIE_I"

runs = get_runs(source = SOURCE)
print(len(runs))
runs = runs[(runs["prompt_id"] == PROMPT)]
results_path = str(runs.loc[runs["prompt_version"] == "v1", "results_path"].iloc[0])

df = pd.read_csv(results_path)
done = set(df["video_id"].tolist())

df = get_state(politics_final=1)
print(len(df))

possible = set(df["video_id"].tolist())

still = possible - done

print(len(still))
df = pd.DataFrame(still, columns = ["video_id"])
df.to_csv(OUTPUTS / "temp" / "baselinetodo.csv", index = False)

