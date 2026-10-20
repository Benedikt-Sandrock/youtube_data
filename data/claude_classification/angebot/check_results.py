import pandas as pd
import re
from pathlib import Path

BATCH_NR = "0001"

BATCH_DIR = Path("batches")
CODE_DIR = Path("codierung")

BATCH_NAME = "batch_" + BATCH_NR + ".txt"
CODE_NAME =  "batch_" + BATCH_NR + ".jsonl"
OUT_NAME = "batch_" + BATCH_NR + "_results.xlsx"

BATCH_PATH = BATCH_DIR / BATCH_NAME
CODE_PATH = CODE_DIR / CODE_NAME

current_id = None
data = []
current_text_lines = []

segment_pattern = re.compile(r"^###\s+SEGMENT\s+(\S+)")

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

df = pd.DataFrame(data)
print(df.head())

df2 = pd.read_json(CODE_PATH, lines = True)
df = pd.merge(df, df2, on = "segment_id", how = "outer")

df.to_excel(OUT_NAME, index = False)




