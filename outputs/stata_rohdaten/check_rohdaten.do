* check_rohdaten.do - Pruefung des Stata-Rohdatensatzes
* erzeugt von src/youtube_code/step6_auswertung/export_stata_rohdaten.py
* Ausfuehren im Ordner outputs/stata_rohdaten (cd dorthin).

clear all
set more off

use kanaele_roh.dta, clear
describe
codebook, compact
isid channel_id
tab medientyp, missing
tab kanaltyp medientyp, missing
tab kanaltyp sample_vorkrieg if sample_whitelist == 1
tab1 sample_vorkrieg sample_baseline sample_whitelist sample_kern api_abbruch format_liste
tab format_status, missing

use videos_roh.dta, clear
describe
codebook, compact
isid video_id
tab1 min_dauer post_war politisch_klass pop_klass pos_klass transkript baseline_stichprobe
tab format format_klass, missing
tab1 news_show special_show pk_sitzung, missing
* LLM-Analysen (pop_*, pos_*) nur mit min_dauer == 1 (siehe Codebuch)
tab pop_klass min_dauer

merge m:1 channel_id using kanaele_roh.dta
* Erwartung: keine Videos nur in master (_merge == 1); Kanaele nur in using
* (_merge == 2) sind solche ganz ohne Video in der Registry.
tab _merge
assert _merge != 1
