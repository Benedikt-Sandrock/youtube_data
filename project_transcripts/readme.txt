Übersicht

1. Determine values for time period and search term in "key_values.py"

2. run "video_search.py" to look for videos in a given period for a given term ("palästina", "israel",...)
    Output: json file with channel ids of all distinct channels that uploaded relevant videos
    -> "channel_ids.json"
    Output 2: json file with video ids, channel ids, publication date, and video title

3. run "channel_all_vids.py" to get all videos for all channels in a given period
    Output: json file with channel id, video id and publication date
    -> "videos_by_channel.json"

4. Run "transcript_download.py" to get all transcripts of the respective videos
    Output: CSV file with video id, transcript, transcript Status


Ergebnisse bei Suche nach "Nahostkonflikt": Monitor, Tagesschau, Newstime, Terra x History, Zeit, faz,
verschiedene andere Kanäle,
