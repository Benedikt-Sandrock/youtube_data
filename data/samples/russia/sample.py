import pandas as pd
from youtube_code.config import SAMPLES, RAW
from youtube_code.utils import load_json, save_json

vdf =  load_json(RAW / "sample_russia_ukraine.json")

