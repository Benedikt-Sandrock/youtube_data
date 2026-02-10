import subprocess
import shutil
import yt_dlp
import sys

def check_my_setup():
    print("--- Diagnose-Check für dein Video-Projekt ---")
    all_clear = True

    # 1. FFmpeg Check
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        try:
            version = subprocess.check_output(["ffmpeg", "-version"], stderr=subprocess.STDOUT).decode()
            first_line = version.split('\n')[0]
            print(f"✅ FFmpeg gefunden: {first_line}")
        except Exception:
            print("⚠️ FFmpeg ist zwar im Pfad, aber nicht ausführbar.")
            all_clear = False
    else:
        print("❌ FFmpeg wurde NICHT gefunden. (Wichtig für das Zusammenfügen von Video & Audio)")
        all_clear = False

    # 2. yt-dlp Check
    try:
        yt_dlp_version = yt_dlp.version.__version__
        print(f"✅ yt-dlp ist installiert (Version {yt_dlp_version})")
    except ImportError:
        print("❌ yt-dlp ist nicht in deinem venv installiert. Nutze: pip install yt-dlp")
        all_clear = False

    # 3. Netzwerk- & YouTube-Check (Testet eine beliebige ID)
    if all_clear:
        print("--- Teste YouTube-Verbindung (nur Metadaten) ---")
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                # Wir laden nur Metadaten von einem Test-Video, kein Download
                info = ydl.extract_info("aqz-KE-bpKQ", download=False)
                print(f"✅ Verbindung zu YouTube steht. Test-Video erkannt: '{info['title'][:30]}...'")
        except Exception as e:
            print(f"❌ YouTube-Verbindung fehlgeschlagen. Grund: {str(e)[:100]}")
            all_clear = False

    print("---------------------------------------------")
    if all_clear:
        print("🚀 ALLES BEREIT! Du kannst mit dem Download-Skript starten.")
    else:
        print("❌ Bitte behebe die oben genannten Fehler, bevor du startest.")

if __name__ == "__main__":
    check_my_setup()