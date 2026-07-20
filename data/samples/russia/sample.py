import pandas as pd
from youtube_code.config import SAMPLES, RAW
from youtube_code.utils import load_json, save_json

vdf =  load_json(RAW / "sample_russia_ukraine.json")

vdf = [v for v in vdf if "Russland" in v["title"]]
print(len(vdf))
save_json("russia_vids.json", vdf)