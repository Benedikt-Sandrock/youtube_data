import yt_dlp
import os
import time
import random
import pandas as pd

def download_videos_clean(video_ids, output_path):
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    failed_ids = []
    archive_file = os.path.join(output_path, 'download_archive.txt')
    error_log_file = os.path.join(output_path, 'failed_downloads.txt')

    downloaded_already = set()
    if os.path.exists(archive_file):
        with open(archive_file, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >1:
                    downloaded_already.add(parts[1])

    ydl_opts = {
        'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
        'outtmpl': f'{output_path}/%(id)s.%(ext)s',
        'download_archive': archive_file,

        'quiet': True,  # Unterdrückt die meisten Standard-Ausgaben
        'no_warnings': True,  # Unterdrückt JS- und SABR-Warnungen
        'ignoreerrors': True,  # Verhindert den Abbruch bei einem Fehler
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        print(f"Starte Download-Prozess für {len(video_ids)} Videos...")

        for index, v_id in enumerate(video_ids):
            if v_id in downloaded_already:
                print(f"Übersprüungen: ID {v_id} bereits heruntergeladen.")
                continue

            url = f"https://www.youtube.com/watch?v={v_id}"
            ydl.download([url])

            # 3. Wir prüfen direkt im Ordner, ob eine Datei existiert, die mit der ID beginnt
            dateien_im_ordner = os.listdir(output_path)
            erfolg = any(v_id in datei for datei in dateien_im_ordner)

            if erfolg:
                print(f"✅ ERFOLG: ID {v_id} ist jetzt lokal gespeichert.")
            else:
                # Falls keine Datei mit der ID gefunden wurde, ist es ein echter Fehler
                print(f"❌ FEHLER: ID {v_id} konnte nicht geladen werden (evtl. gesperrt).")
                failed_ids.append(v_id)

            if index < len(video_ids) -1:
                pause = random.uniform(20,40)
                print(f"Pause: {pause:.2f} Sekunden")
                time.sleep(pause)

    # Am Ende schreiben wir alle Fehler in eine Datei
    if failed_ids:
        with open(error_log_file, 'w') as f:
            for f_id in failed_ids:
                f.write(f"{f_id}\n")
        print(f"\nFertig! {len(failed_ids)} Videos sind fehlgeschlagen. Liste siehe '{error_log_file}'.")
    else:
        print("\nAlle Videos wurden erfolgreich verarbeitet!")


if __name__ == "__main__":

    output_path = r"C:\Users\bened\Desktop\youtube_video_downloads"
    file_path = "../../project_transcripts/Transcript files/youtube_transkripte_2.csv"
    df = pd.read_csv(file_path)
    v_ids_download = df["video_id"].head(50).tolist()

    download_videos_clean(v_ids_download, output_path)



