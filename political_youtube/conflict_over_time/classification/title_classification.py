# import re #only needed if titles are adjusted
import pandas as pd
import torch
from transformers import pipeline
from tqdm import tqdm
import random

# ========================================
# 1. GPU and model setup
# ========================================

device = 0 if torch.cuda.is_available() else -1
print(f"Using {'GPU' if device == 0 else 'CPU'}")

print("Loading model (mDeBERTa-v3)...")

classifier = pipeline(
    "zero-shot-classification",
    model = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
    device = device,
    model_kwargs ={"torch_dtype": torch.float16} if device == 0 else {}
)


# ========================================
# 2. Loading and preparing data
# ========================================

print("Loading JSON file...")
df = pd.read_json("../channel_identification/large_german_channels/video_files/all_videos_50k_channels_sampled.json")
titles = df["title"].tolist()

def clean_text(text):
    return str(text).strip()

titles_clean = [clean_text(t) for t in titles]
seed_number = 41
random.seed(seed_number)

titles_clean = random.sample(titles_clean, 100)
df_titles = pd.DataFrame(titles_clean, columns=["title"])
df_titles.to_excel(f"video_titles_sample_{seed_number}.xlsx", engine = "openpyxl")

# ========================================
# 3. Classification
# ========================================

results = []
batch_size = 32

print(f"Starting classification of {len(titles_clean)} titles...")

for i in tqdm(range(0, len(titles_clean), batch_size)):
    batch_texts = titles_clean[i : i + batch_size]
    batch_raw_texts = titles[i : i + batch_size]
    first_pass_results = classifier(
        batch_texts,
        candidate_labels =["Politik", "Nicht-Politik"],
        hypothesis_template = "Dieses Video behandelt das Thema {}."
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
            "category": res["labels"][0],
            "politik_confidence": politik_confidence,
            "is_politics": 1 if res["labels"][0] == "Politik" else 0
        })


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

output_df = pd.DataFrame(results)
output_df.to_json(f"classified_videos_{seed_number}.json", orient = "records", indent = 4, force_ascii= False)
print("Done. Results saved.")




