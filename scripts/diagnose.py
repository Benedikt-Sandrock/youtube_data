from pathlib import Path

import pandas as pd


evaluation_file = Path(
    r"E:\PyhcarmProjects\youtube_data"
    r"\outputs\llm\title_classification"
    r"\run_0003_title_evaluation.xlsx"
)

comparison = pd.read_excel(
    evaluation_file,
    sheet_name="all_comparisons",
)

print("\nFinale manuelle Labels:")
print(
    comparison["politics_final_manual"]
    .value_counts(dropna=False)
    .sort_index()
)

print("\nFinales manuelles Label gegen Modell-Titellabel:")
print(
    pd.crosstab(
        comparison["politics_final_manual"],
        comparison["politics_title_model"],
        rownames=["politics_final_manual"],
        colnames=["politics_title_model"],
        dropna=False,
    )
)

final_false_exclusions = comparison.loc[
    comparison["politics_final_manual"].eq(1)
    & comparison["politics_title_model"].eq(0)
].copy()

display_columns = [
    column
    for column in [
        "video_id",
        "title",
        "politics_title_manual",
        "politics_final_manual",
        "politics_title_model",
    ]
    if column in final_false_exclusions.columns
]

print("\nFinal relevante, vom Modell ausgeschlossene Videos:")
print(
    final_false_exclusions[display_columns]
    .to_string(index=False)
)

final_uncertain_exclusions = comparison.loc[
    comparison["politics_final_manual"].eq(-1)
    & comparison["politics_title_model"].eq(0)
].copy()

display_columns = [
    column
    for column in [
        "video_id",
        "title",
        "description",
        "politics_title_manual",
        "politics_final_manual",
        "politics_title_model",
    ]
    if column in final_uncertain_exclusions.columns
]

print(
    final_uncertain_exclusions[display_columns]
    .to_string(index=False)
)