import pandas as pd
import re
from pathlib import Path

nr_series = []
for i in range(96, 126):
    i = str(i).zfill(4)
    nr_series.append(i)

BATCH_NR = nr_series

BATCH_DIR = Path("batches")
CODE_DIR = Path("codierung")

if len(BATCH_NR) > 1:
    OUT_NAME = "batch_" + BATCH_NR[0]+ "_" + BATCH_NR[-1] + "_results.xlsx"
else:
    OUT_NAME = "batch_" + BATCH_NR[0] + "_results.xlsx"


current_id = None
data = []
dfs = []
current_text_lines = []

segment_pattern = re.compile(r"^###\s+SEGMENT\s+(\S+)")

for nr in BATCH_NR:
    BATCH_NAME = "batch_" + nr + ".txt"
    CODE_NAME = "batch_" + nr + ".jsonl"
    BATCH_PATH = BATCH_DIR / BATCH_NAME
    CODE_PATH = CODE_DIR / CODE_NAME

    with open(BATCH_PATH, "r", encoding = "utf-8") as f:
        for line in f:
            match = segment_pattern.match(line)
            if match:
                if current_id is not None:
                    full_text = " ".join(current_text_lines).strip()
                    data.append({"segment_id": current_id, "text": full_text})
                current_id = match.group(1)
                current_text_lines = []

            else:
                cleaned_line = line.strip()
                if cleaned_line:
                    current_text_lines.append(cleaned_line)

        if current_id is not None:
            full_text = " ".join(current_text_lines).strip()
            data.append({"segment_id": current_id, "text": full_text})

    temp_df = pd.read_json(CODE_PATH, lines = True)
    dfs.append(temp_df)

df = pd.DataFrame(data)
df2 = pd.concat(dfs, ignore_index = True)
df = pd.merge(df, df2, on = "segment_id", how = "outer")
df["kodierbar"] = df["kodierbar"].replace({True: 1, False: 0})
print(df.head())
df.to_excel(OUT_NAME, index = False)




