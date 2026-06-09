import os
import pandas as pd


def collect_transcript_files(directory, output_file):
    dataframes: list[pd.DataFrame] = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".csv"):
                path = os.path.join(root, file)

                try:
                    df = pd.read_csv(path)
                    dataframes.append(df)

                except Exception as e:
                    print(f"Error: {e}")

    if not dataframes:
        print("No CSV files found.")
        return

    combined_df = pd.concat(dataframes, ignore_index = True)

    unique_df = combined_df.drop_duplicates(
        subset = "video_id",
        keep = "first"
    )

    unique_df.to_csv(output_file, index = False)

    print(f"{len(unique_df)} unique videos saved.")

target_dir = "../Transcript files"

collect_transcript_files(target_dir, "all_transcripts.csv")


