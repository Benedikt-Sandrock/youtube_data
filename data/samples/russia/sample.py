import pandas as pd
from pathlib import Path
import json

with open("channels_sample.json", "r") as f, open("channels_screened.json") as f2:
    data = json.load(f)
    data2 = json.load(f2)

missing_channels = [c for c in data if c not in data2]
print(len(missing_channels))
print(missing_channels)

# channels_sample = set()
# with open("sample_50k_channels_russia_ukraine_wo_shorts.jsonl", "r", encoding = "utf-8") as f:
#     for line in f:
#         line = line.strip()
#         if not line:
#             continue
#         r = json.loads(line)
#         cid = r.get("channel_id", "")
#         channels_sample.add(cid)

# df = pd.read_csv("longitudinal_screening_state.csv", usecols = ["channel_id"])
# df2 = pd.read_json("sample_50k_channels_russia_ukraine_wo_shorts.jsonl", lines = True)

# channels_screened = df["channel_id"].to_list()
# channels_sample = df2["channel_id"].to_list()

# channels_screened = set(channels_screened)
# channels_screened = list(channels_screened)
# channels_sample = set(channels_sample)
# channels_sample = list(channels_sample)

# with open("channels_sample.json", "w", encoding = "utf-8") as f:
#     json.dump(channels_sample, f, ensure_ascii = False, indent = 2)

# print(len(channels_screened), len(channels_sample))

# channels_missing = channels_sample - channels_screened
# channels_missing = [c for c in channels_sample if c not in channels_screened]
# print(len(channels_missing))

from scripts.create_video_samples import METADATA_PATH
from youtube_code.config import RAW
import re
from youtube_code.utils import load_json,save_json


import json
from pathlib import Path

# SAMPLE_FILE = RAW / "sample_50k_channels_russia_ukraine.jsonl"
# METADATA_FILE = RAW / "video_metadata_detailed_total.jsonl"
# OUT_FILE = "sample_50k_channels_russia_ukraine.jsonl"
# OUT_FILE_FILTERED = "sample_50k_channels_russia_ukraine_wo_shorts.jsonl"
#
# def create_sample_file():
#     sample_ids = set()
#
#     with open(SAMPLE_FILE, encoding = "utf-8") as f:
#         for line in f:
#             line = line.strip()
#             if line:
#                 sample_ids.add(str(json.loads(line)["video_id"]))
#
#     print(f"Video IDs in sample: {len(sample_ids)}")
#
#
#     found = set()
#     n_read = n_written = n_double = 0
#
#     with open(METADATA_FILE, encoding = "utf-8") as fin, open(OUT_FILE, "w", encoding = "utf-8") as fout:
#         for line in fin:
#             line = line.strip()
#             if not line:
#                 continue
#
#             r = json.loads(line)
#             n_read += 1
#
#             video_id = str(r.get("video_id", ""))
#
#             if video_id not in sample_ids:
#                 continue
#
#             if video_id in found:
#                 n_double +=1
#             found.add(video_id)
#
#             fout.write(json.dumps(r, ensure_ascii = False) + "\n")
#             n_written +=1
#
#     missing = sample_ids - found
#
#     print(f"Metadata read: {n_read}")
#     print(f"Written: {n_written}")
#
#     print(f"Missing: {len(missing)}")
#
#
#     n = k = 0
#     with open(OUT_FILE, encoding="utf-8") as fin, open(OUT_FILE_FILTERED, "w", encoding="utf-8") as fout:
#         for line in fin:
#             r = json.loads(line)
#             n += 1
#             m = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", r.get("duration") or "")
#             if m:
#                 d, h, mi, s = (int(x or 0) for x in m.groups())
#                 if d*86400 + h*3600 + mi*60 + s < 60:
#                     k += 1
#                     continue
#             fout.write(json.dumps(r, ensure_ascii=False) + "\n")
#
#     print(f"{n:,} gelesen, {k:,} unter 60s gestrichen, {n-k:,} behalten")
#
# politics_vids = []
#
# with open(OUT_FILE_FILTERED, encoding= "utf-8") as f:
#     for line in f:
#         line = line.strip()
#         if not line:
#             continue
#         r = json.loads(line)
#         tag = str(r.get("topic_categories", ""))
#         if "Politics" in tag:
#             politics_vids.append(r)
#
# print(len(politics_vids))




# INPUT_SAMPLE = Path(RAW / "sample_50k_channels_russia_ukraine.jsonl")
# METADATA_FILE = Path(RAW / "video_metadata_detailed_total.jsonl")
# OUTPUT_FILE = Path("all_videos_w_description.jsonl")
#
# LOG_EVERY = 250_000
#
#
# def iter_jsonl(path):
#     """Liest eine JSONL zeilenweise, ohne die Datei komplett zu laden."""
#     with open(path, "r", encoding="utf-8") as f:
#         for line_number, line in enumerate(f, start=1):
#             line = line.strip()
#             if not line:
#                 continue
#             try:
#                 yield json.loads(line)
#             except json.JSONDecodeError:
#                 print(f"  Warnung: {path.name} Zeile {line_number} unlesbar - übersprungen")
#
#
# def merge_description_to_videos():
#     # --------------------------------------------------
#     # 1. Durchlauf: video_ids des Samples sammeln
#     # --------------------------------------------------
#     sample_video_ids = set()
#     n_sample = 0
#
#     for record in iter_jsonl(INPUT_SAMPLE):
#         n_sample += 1
#         sample_video_ids.add(str(record["video_id"]))
#
#         if n_sample % LOG_EVERY == 0:
#             print(f"Sample gelesen: {n_sample:,}")
#
#     print(f"Videos im Sample: {n_sample:,} ({len(sample_video_ids):,} eindeutige IDs)")
#
#     # --------------------------------------------------
#     # 2. Durchlauf: Metadaten streamen, nur Treffer behalten
#     # --------------------------------------------------
#     descriptions = {}
#     n_meta = 0
#
#     for record in iter_jsonl(METADATA_FILE):
#         n_meta += 1
#         video_id = str(record.get("video_id", ""))
#
#         # letztes Vorkommen gewinnt (entspricht drop_duplicates(keep="last"))
#         if video_id in sample_video_ids:
#             descriptions[video_id] = record.get("description")
#
#         if n_meta % LOG_EVERY == 0:
#             print(f"Metadaten gelesen: {n_meta:,} - Treffer bisher: {len(descriptions):,}")
#
#     print(f"Metadaten gesamt: {n_meta:,}")
#     print(f"Gefundene Beschreibungen: {len(descriptions):,}")
#
#     # --------------------------------------------------
#     # 3. Durchlauf: Sample erneut streamen und angereichert schreiben
#     # --------------------------------------------------
#     n_written = 0
#     n_missing = 0
#
#     tmp_file = OUTPUT_FILE.with_suffix(OUTPUT_FILE.suffix + ".tmp")
#
#     with open(tmp_file, "w", encoding="utf-8") as out:
#         for record in iter_jsonl(INPUT_SAMPLE):
#             video_id = str(record["video_id"])
#             description = descriptions.get(video_id)
#
#             if description is None:
#                 n_missing += 1
#
#             record["description"] = description
#             out.write(json.dumps(record, ensure_ascii=False) + "\n")
#
#             n_written += 1
#             if n_written % LOG_EVERY == 0:
#                 print(f"Geschrieben: {n_written:,} / {n_sample:,}")
#
#     tmp_file.replace(OUTPUT_FILE)  # atomarer Abschluss
#
#     print(f"Videos nach Merge: {n_written:,}")
#     print(f"Fehlende Beschreibungen: {n_missing:,}")
#     print(f"Datei gespeichert: {OUTPUT_FILE}")
#
#
# merge_description_to_videos()

#
# SAMPLE_SIZE = 200
# RANDOM_SEED = 40
#
# EXPORT_COLS = ["video_id", "title", "description"]
# SAMPLE_OUTPUT = f"description_training_sample_{RANDOM_SEED}.csv"
#
# def create_random_sample(input_file, output_file, columns,random_seed,  sample_size = 200, chunksize = 50_000):
#     sampled_chunks = []
#
#     for chunk_number, chunk in enumerate(
#         pd.read_json(input_file, lines = True, chunksize = chunksize)
#     ):
#         chunk = chunk[columns]
#         chunk_weighter = chunksize / len(chunk)
#         chunk_sample = round(sample_size / chunk_weighter)
#         chunk_sample = chunk.sample(
#             n= chunk_sample,
#             random_state = random_seed + chunk_number,
#         )
#
#         sampled_chunks.append(chunk_sample)
#     candidates = pd.concat(
#         sampled_chunks, ignore_index = True
#     )
#
#     sample = candidates.sample(
#         n = sample_size,
#         random_state = random_seed
#     )
#
#     sample.to_csv(output_file, index = False)
#
#
# # create_random_sample(OUTPUT_FILE, SAMPLE_OUTPUT, EXPORT_COLS, RANDOM_SEED)
#
# df = pd.read_csv("final_selection/final_video_selection_primary.csv")
# df = df[df["politics_final"] == 1]
# video_ids= df["video_id"].to_list()
#
# with open("final_selection/ids_to_download.json", "w") as f:
#     json.dump(video_ids, f, ensure_ascii = False, indent = 2)
#
# import pandas as pd
# from pathlib import Path
# import json
#
# STATE_FILE = Path(r"C:\Users\bened\PycharmProjects\youtube_data\data\samples\russia\longitudinal_screening_state.csv")
#
# state = pd.read_csv(
#     STATE_FILE,
#     dtype={"video_id": "string"},
#     low_memory=False,
# )
# state["politics_final"] = pd.to_numeric(state["politics_final"], errors="coerce").astype("Int8")
#
# political_video_ids = set(state.loc[state["politics_final"] == 1, "video_id"])
# political_video_ids = sorted(political_video_ids)
#
# with open("political_ids.json", "w", encoding = "utf-8") as f:
#     json.dump(political_video_ids, f, ensure_ascii = False, indent = 2)
#
# print(f"{len(political_video_ids):,} politische Videos.")