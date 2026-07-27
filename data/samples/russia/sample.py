import pandas as pd
from pathlib import Path
from youtube_code.config import RAW
import json

INPUT_SAMPLE = Path("videos_wo_shorts_russia_ukraine.json")
METADATA_FILE = RAW / "video_metadata_detailed_total.jsonl"
OUTPUT_FILE = Path("videos_wo_shorts_description.jsonl")

READ_CHUNK_SIZE = 100_000
WRITE_CHUNK_SIZE = 50_000

def merge_description_to_videos():
    # --------------------------------------------------
    # 1. Sample laden
    # --------------------------------------------------
    df = pd.read_json(INPUT_SAMPLE)

    df["video_id"] = df["video_id"].astype(str)

    print(f"Videos im Sample: {len(df):,}")

    sample_video_ids = set(df["video_id"])


    # --------------------------------------------------
    # 2. Metadaten blockweise lesen
    # --------------------------------------------------
    matched_chunks = []

    for chunk_number, chunk in enumerate(
        pd.read_json(
            METADATA_FILE,
            lines=True,
            chunksize=READ_CHUNK_SIZE,
        ),
        start=1,
    ):
        chunk = chunk[["video_id", "description"]].copy()
        chunk["video_id"] = chunk["video_id"].astype(str)

        matched = chunk[chunk["video_id"].isin(sample_video_ids)]

        if not matched.empty:
            matched_chunks.append(matched)

        print(
            f"Chunk {chunk_number}: "
            f"{len(chunk):,} gelesen, "
            f"{len(matched):,} Treffer"
        )


    # --------------------------------------------------
    # 3. Beschreibungen zusammenführen
    # --------------------------------------------------
    if matched_chunks:
        descriptions = pd.concat(
            matched_chunks,
            ignore_index=True,
        )

        descriptions = descriptions.drop_duplicates(
            subset="video_id",
            keep="last",
        )
    else:
        descriptions = pd.DataFrame(
            columns=["video_id", "description"]
        )

    print(f"Gefundene Beschreibungen: {len(descriptions):,}")


    # --------------------------------------------------
    # 4. Merge
    # --------------------------------------------------
    df = df.merge(
        descriptions,
        on="video_id",
        how="left",
        validate="many_to_one",
    )

    print(f"Videos nach Merge: {len(df):,}")
    print(
        f"Fehlende Beschreibungen: "
        f"{df['description'].isna().sum():,}"
    )


    # --------------------------------------------------
    # 5. Blockweise als JSONL speichern
    # --------------------------------------------------
    OUTPUT_FILE.unlink(missing_ok=True)

    for start in range(0, len(df), WRITE_CHUNK_SIZE):
        end = min(start + WRITE_CHUNK_SIZE, len(df))

        df.iloc[start:end].to_json(
            OUTPUT_FILE,
            orient="records",
            lines=True,
            force_ascii=False,
            date_format="iso",
            mode="a",
        )

        print(
            f"Gespeichert: "
            f"{end:,} / {len(df):,}"
        )

    print(f"Datei gespeichert: {OUTPUT_FILE}")


SAMPLE_SIZE = 200
RANDOM_SEED = 40

EXPORT_COLS = ["video_id", "title", "description"]
SAMPLE_OUTPUT = f"description_training_sample_{RANDOM_SEED}.csv"

def create_random_sample(input_file, output_file, columns,random_seed,  sample_size = 200, chunksize = 50_000):
    sampled_chunks = []

    for chunk_number, chunk in enumerate(
        pd.read_json(input_file, lines = True, chunksize = chunksize)
    ):
        chunk = chunk[columns]
        chunk_weighter = chunksize / len(chunk)
        chunk_sample = round(sample_size / chunk_weighter)
        chunk_sample = chunk.sample(
            n= chunk_sample,
            random_state = random_seed + chunk_number,
        )

        sampled_chunks.append(chunk_sample)
    candidates = pd.concat(
        sampled_chunks, ignore_index = True
    )

    sample = candidates.sample(
        n = sample_size,
        random_state = random_seed
    )

    sample.to_csv(output_file, index = False)


# create_random_sample(OUTPUT_FILE, SAMPLE_OUTPUT, EXPORT_COLS, RANDOM_SEED)

df = pd.read_csv("final_selection/final_video_selection_primary.csv")
df = df[df["politics_final"] == 1]
video_ids= df["video_id"].to_list()

with open("final_selection/ids_to_download.json", "w") as f:
    json.dump(video_ids, f, ensure_ascii = False, indent = 2)