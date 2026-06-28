# import re #only needed if titles are adjusted
import pandas as pd
import torch
from transformers import pipeline
from tqdm import tqdm
import time


# ========================================
# 1. Loading and preparing data
# ========================================
seed_number = 41
#test set:
#df = pd.read_excel(f"video_titles_sample_{seed_number}.xlsx")

#complete dateset:
df = pd.read_json(f"../channel_identification/large_german_channels/video_files/all_videos_50k_channels_sampled.json")
print(len(df))

titles_clean = df["title"].tolist()

# print("Loading JSON file...")
# df = pd.read_json("../channel_identification/large_german_channels/video_files/all_videos_50k_channels_sampled.json")
# titles = df["title"].tolist()
#
# def clean_text(text):
#     return str(text).strip()
#
# titles_clean = [clean_text(t) for t in titles]
# seed_number = 41
# random.seed(seed_number)
#
# titles_clean = random.sample(titles_clean, 100)
# df_titles = pd.DataFrame(titles_clean, columns=["title"])
#df_titles.to_excel(f"video_titles_sample_{seed_number}.xlsx", engine = "openpyxl")

# ========================================
# 2. GPU and model setup
# ========================================

device = 0 if torch.cuda.is_available() else -1
print(f"Using {'GPU' if device == 0 else 'CPU'}")


# models_to_test = [
#     "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
#     "Sahajtomar/German_Zeroshot_Model",
#     "facebook/bart-large-mnli"
# ]

model_label = {
    "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli": "mDeBERTa-v3",
    # "sahajtomar/German_Zeroshot": "German_Zeroshot",
    # "facebook/bart-large-mnli": "bart_large",
    # "vicgalle/xlm-roberta-large-xnli-anli": "XLM_RoBERTa_Large"
}

for model, label in model_label.items():
    print(f"Loading model {label}...")

    start_time = time.time()

    classifier = pipeline(
        "zero-shot-classification",
        model = model,
        device = device,
        model_kwargs ={"torch_dtype": torch.float16} if device == 0 else {}
    )


# ========================================
# 3. Classification
# ========================================

    results = []
    checkpoint_interval = 1000
    last_checkpoint_at = 0
    batch_size = 32
    if model == "facebook/bart-large-mnli":
        batch_size = 16

    print(f"Starting classification of {len(titles_clean)} titles...")

    for i in tqdm(range(0, len(titles_clean), batch_size)):
        batch_texts = titles_clean[i : i + batch_size]
        #batch_raw_texts = titles[i : i + batch_size]
        first_pass_results = classifier(
            batch_texts,
            candidate_labels =["Politik", "Nicht-Politik"],
            hypothesis_template = "In diesem Video geht es um {}."
            #hypothesis_template = "Dieses Video behandelt das Thema {}."
        )

        if not isinstance(first_pass_results, list):
            first_pass_results = [first_pass_results]


# ========================================
# Use this block if only political/non-political must be classified
# ========================================

        for res in first_pass_results:
            pol_index = res['labels'].index("Politik")
            politik_confidence = res['scores'][pol_index]

            results.append({
                "title": res["sequence"],
                #"category": res["labels"][0],
                f"{label}_politik_confidence": politik_confidence,
                f"{label}_is_politics": 1 if res["labels"][0] == "Politik" else 0
            })

        if i - last_checkpoint_at >= checkpoint_interval:
            temp_df = pd.DataFrame(results)
            # Wir speichern mit dem aktuellen Index im Namen, um nichts zu überschreiben
            temp_df.to_csv(f"checkpoint_progress_{label}.csv", index=False)
            last_checkpoint_at = i  # Update den Tracker
            print(f"\nCheckpoint saved at title {i}.")
# ========================================
# Block is only needed when leaning must be classified
# ========================================

    # #collecting titles for second run
    # political_texts = []
    # political_indices = []  #saves at which point in the batch the title was placed
    #
    # for idx, res in enumerate(first_pass_results):
    #     top_label = res["labels"][0]
    #     top_score = res["scores"][0]
    #
    #     if top_label == "Politik" and top_score > 0.9:
    #         political_texts.append(batch_texts[idx])
    #         political_indices.append(idx)
    #
    # second_pass_dict = {}
    # if political_texts: #only if political titles are found in this batch
    #     second_pass_results = classifier(
    #         political_texts,
    #         candidate_labels = ["linksaußen", "Mitte-Links", "Mitte-Rechts", "rechtsaußen"],
    #         hypothesis_template = "Die politische Tendenz dieses Titels ist {}"
    #     )
    #
    #     if not isinstance(second_pass_results, list):
    #         second_pass_results = [second_pass_results]
    #
    #     for j, pass_res in enumerate(second_pass_results):
    #         original_idx = political_indices[j]
    #         second_pass_dict[original_idx] = pass_res["labels"][0]
    #
    # for idx, res in enumerate(first_pass_results):
    #     top_label = res['labels'][0]
    #     top_score = res['scores'][0]
    #     final_label = "Unpolitisch"
    #     orientation = "N/A"
    #
    #     if idx in second_pass_dict:
    #         final_label = "Politik"
    #         orientation = second_pass_dict[idx]
    #
    #     results.append({
    #         "original_title": batch_raw_texts[idx],
    #         "is_political": final_label,
    #         "confidence": top_score,
    #         "orientation": orientation
    #     })
    duration = time.time() - start_time
    print(f"Classification using {label} took {duration:.2f} seconds to run.")

    output_df = pd.DataFrame(results)
    df = pd.merge(df, output_df, on ="title")
    #output_df.to_json(f"classified_videos_{seed_number}.json", orient = "records", indent = 4, force_ascii= False)
    print(f"Results for model {model} saved.")

df.to_csv(f"results_all_models_{seed_number}.csv", index = False)




