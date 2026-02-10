#identification of channels
published_after_ident = "2023-09-07T00:00:00Z"
published_before_ident = "2023-10-07T00:00:00Z"

from datetime import datetime
start_date = datetime(2020, 1, 1)
final_end_date = datetime(2022, 1, 1)
#period of analysis
published_after_analysis = "2022-10-07T00:00:00Z"
published_before_analysis = "2025-10-07T00:00:00Z"

query_list = ["Bundestagswahl", "USA Wahl"]

#query_list = ["Nahostkonflikt", "Gaza-Krieg", "Israel Palästina Konflikt", "Palästina Israel Konflikt"] #schon durchgelaufen monatsweise

ziel_directory = f"../JSON Files"



if __name__ == "__main__":
    import json
    #with open("../JSON Files/videos_keywords_total_3years.json", "r", encoding = "utf-8") as f:
    #    data = json.load(f)

    with open("../../JSON Files/channel_metadata.json", "r", encoding ="utf-8") as f:
        metadata = json.load(f)

    big_channels = []
    for channel in metadata:
        if channel["Views"] >= 100000:
            big_channels.append(channel)
    print(len(metadata))
    print(len(big_channels))
    print(big_channels)
    # import json
    # from googleapiclient.discovery import build
    # api_key = "AIzaSyBUg0XIryem2_WtenRUKDA1bwLsiDzMLYE"
    # youtube = build('youtube', 'v3', developerKey=api_key)
    # with open("../JSON Files/channel_ids_classified/all_channel_ids_classified_german_3years.json", "r", encoding ="utf-8") as f:
    #     data = json.load(f)

    # channel_id_to_name(youtube, data)


    # with open("../JSON Files/channel_ids_classified/all_channel_ids_german.json", "r", encoding = "utf-8") as f:
    #       data = set(json.load(f))
    #
    # print(len(data))
    import pandas as pd
    import json

    total_file = "../../Transcript files/youtube_transkripte_2.csv"
    json_file = "../../JSON Files/videos_keywords_total_3years.json"
    output_news = "../Transcript files/transcripts_news_channels.csv"
    output_other = "../Transcript files/transcript_other_channels.csv"

    def separate_news_channels(total_file, json_file, output_news, output_other):
        news_channels = ["UC5NOEUbkLheQcaaRldYW5GA", "UC7n_Hml4hw5H4G-HP8QPeKw", "UCACdxU3VrJIJc7ujxtHWs1w",
                         "UCcPcua2PF7hzik2TeOBx3uw", "UCd-qzAx-BRnIoKtU1DCvfMQ", "UCZMsvbAhhRblVGXmEXW8TSA",
                         "UCxU1a-2vec6ljU43I0F2Jwg", "UC_YnP7DDnKzkkVl3BaHiZoQ", "UCCjkK_Qk9BUytDlAzz0iCZw",
                         "UC9utdGh-KP1loBSadGnP1rg", "UCLVeraZYXhwxDCs2ynLbnzA", ]
        df_transcripts = pd.read_csv(total_file)
        with open(json_file, "r", encoding = "utf-8") as f:
            metadata_list = json.load(f)

        df_combined = pd.DataFrame(metadata_list)

        #df_combined = pd.merge(df_transcripts, df_metadata, on = "video_id", how = "inner")
        is_news = df_combined["channel_id"].isin(news_channels)
        df_news = df_combined[is_news]
        df_others = df_combined[~is_news]

        #df_news.to_csv(output_news, index = False)
        #df_others.to_csv(output_other, index = False)

        print(f"News Videos: {len(df_news)}")
        print(f"Andere Videos: {len(df_others)}")
    #separate_news_channels(total_file, json_file, output_news, output_other)




    # #for item in data:
    # #    if item.get("video_id") in videolist:
    # #        count += 1
    # #print(count)
    # import os
    # import json
    # videos_total_file = "../JSON Files/videos_by_channel_total_german_2.json"
    #
    # if os.path.exists(videos_total_file):
    #     with open(videos_total_file, "r", encoding = "utf-8") as f:
    #         videos_total = json.load(f)
    # else:
    #     videos_total = []
    #
    # processed_channel_ids = {v["channel_id"] for v in videos_total}
    # print(f"Bereits verarbeitete Channels: {len(processed_channel_ids)}")
    #
    #
    # # print(processed_channel_ids)
    # # api_key = "AIzaSyBUg0XIryem2_WtenRUKDA1bwLsiDzMLYE"
    # # from googleapiclient.discovery import build
    # #
    # # youtube = build('youtube', 'v3', developerKey=api_key)
    # # from help_functions import channel_id_to_name
    # # channel_id_to_name(youtube,processed_channel_ids)
    #
    # komisch = processed_channel_ids - data
    # print(komisch)
    #
    # # data.add("UCXYKYEYgk1ntGNJgJv9JhNA")
    # # data.add("UCVaDYNXdsfzACUsHGHB4CMw")
    #
    # # with open("../JSON Files/channel_ids_classified/all_channel_ids_german.json", "w", encoding="utf-8") as f:
    # #     json.dump(sorted(data), f, ensure_ascii=False, indent= 2)
    # from help_functions import load_set, safe_json
    # foreign_channels = load_set("../JSON Files/monthly/channel_ids_classified/all_channel_ids_foreign_monthly.json")
    # german_channels = load_set("../JSON Files/monthly/channel_ids_classified/all_channel_ids_german_monthly.json")
    # ref_foreign = load_set("../JSON Files/channel_ids_classified/all_channel_ids_foreign_3years.json")
    # ref_german = load_set("../JSON Files/channel_ids_classified/all_channel_ids_german_3years.json")
    # print(len(ref_foreign))
    # print(len(ref_german))
    # ref_foreign.update(foreign_channels)
    # ref_german.update(german_channels)
    #
    # print(len(ref_foreign))
    # print(len(ref_german))
    # safe_json("../JSON Files/channel_ids_classified/all_channel_ids_foreign_3years.json", ref_foreign)
    # safe_json("../JSON Files/channel_ids_classified/all_channel_ids_german_3years.json", ref_german)

