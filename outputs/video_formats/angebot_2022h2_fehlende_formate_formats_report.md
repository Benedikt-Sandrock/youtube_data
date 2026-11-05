# Video-Formate: angebot_2022h2_fehlende_formate

- Lauf: 2026-11-03T10:37:18
- Kanalliste: `C:\Users\bened\PycharmProjects\youtube_data\data\channel_lists\video_formats\angebot_2022h2_fehlende_formate.csv` (5 Kanaele)
- Fenster: 2022-04-28T00:00:00Z bis 2022-06-29T23:59:59Z
- API-Aufrufe in diesem Lauf: 953
- Abgebrochen: nein

## Formate je Kanal (dieser Lauf)

| Kanal | short | long | live | davon neu (s/l/live) | abgeschnitten -> yt-dlp | unvollstaendig | Konflikte | nicht abrufbar | Registry im Fenster | Registry ohne Format |
| --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| WELT Nachrichtensender | 0 | 0 | 139 | 0/0/0 | long, live | long | 0 | 0 | 1625 | 1486 |
| MMnewsTV | 0 | 23 | 0 | 0/0/0 | - | - | 0 | 0 | 25 | 2 |
| BILD | 44 | 678 | 49 | 0/0/0 | - | - | 0 | 0 | 772 | 1 |
| ARTEde | 1 | 17 | 0 | 0/0/0 | - | - | 0 | 0 | 19 | 1 |

**Unvollstaendig** (yt-dlp-Tab endete vor dem Fensteranfang, Registry kennt aeltere Videos ohne Format, Toleranz 50; Status `unvollstaendig`, Folgelauf fragt erneut ab):

- WELT Nachrichtensender: long: Tab endet 2024-03-26, 1486 aeltere Registry-Videos ohne Format

*Registry ohne Format*: Videos, die schon vor dem Lauf in der Registry im Fenster lagen, aber in keiner Format-Playlist auftauchen (geloescht/privat oder Abdeckungsluecke). *nicht abrufbar*: in der Playlist gelistet, aber per videos.list nicht (mehr) abrufbar - kein Format gespeichert.

## Dauer-Plausibilitaet

- Shorts laenger als erlaubt (60 s bis 14.10.2024, danach 180 s): 0
- Normale Videos <= 60 s: 29
- Ohne Dauer: 0

## HEAD-Validierung (/shorts/<id>)

Nicht durchgefuehrt (HEAD_CHECK_SAMPLE = 0 oder keine Ergebnisse).
