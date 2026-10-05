# -*- coding: utf-8 -*-
"""
export_metadata_kanalliste_nachscraping.py

Stellt die Kanalliste fuer metadata_collection.py (CHECK_CHANNELS_MODE = True,
DETAILED = True) nach dem yt-dlp-Nachscraping zusammen: alle Kanaele, fuer
die seit einem Vorher-Snapshot (nachscraping_snapshot_vorher*.csv aus
vergleich_nachscraping.py: Testlauf WELT/OE24, Teil 1, Teil 2) neue Videos
in der Registry stehen. Die neuen Videos haben nur video_id/channel_id/
published_at/title, aber weder view_count noch video_details.

Ausgabe: outputs/segment_analysis/datenluecken_quartale/
metadata_nachscraping_kanaele.csv (channel_id, title, quelle, n_neu,
n_neu_ohne_views, n_kanal_ohne_details). Laedt alle video_details-IDs ->
dauert einige Minuten.

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/export_metadata_kanalliste_nachscraping.py
"""
import sqlite3, pandas as pd
from pathlib import Path
O=Path("outputs/segment_analysis/datenluecken_quartale")
con=sqlite3.connect("file:data/store/video_registry.sqlite?mode=ro",uri=True)
details=set(pd.read_sql_query("SELECT video_id FROM video_details",con).video_id)
rows=[]
for snap in sorted(O.glob("nachscraping_snapshot_vorher*.csv")):
    s=pd.read_csv(snap); cids=s.channel_id.unique().tolist()
    q=",".join("?"*len(cids))
    reg=pd.read_sql_query(f"SELECT video_id,channel_id,channel_title,view_count FROM videos WHERE channel_id IN ({q})",con,params=cids)
    neu=reg[~reg.video_id.isin(set(s.video_id))]
    for cid,g in reg.groupby("channel_id"):
        n=g[~g.video_id.isin(set(s.video_id))]
        if len(n):
            rows.append(dict(channel_id=cid,title=g.channel_title.iloc[0],quelle=snap.stem.replace("nachscraping_snapshot_vorher","") or "_test",
              n_neu=len(n),n_neu_ohne_views=int(n.view_count.isna().sum()),n_kanal_ohne_details=int((~g.video_id.isin(details)).sum())))
df=pd.DataFrame(rows).sort_values("n_neu",ascending=False)
print(df.to_string(index=False)); print(df[["n_neu","n_neu_ohne_views","n_kanal_ohne_details"]].sum())
df.to_csv(O/"metadata_nachscraping_kanaele.csv",index=False,encoding="utf-8")
