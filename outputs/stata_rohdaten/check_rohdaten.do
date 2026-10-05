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
tab1 sample_vorkrieg sample_baseline sample_whitelist api_abbruch

use videos_roh.dta, clear
describe
codebook, compact
isid video_id
tab1 politisch_klass krieg_klass pop_klass pos_klass transkript baseline_stichprobe

merge m:1 channel_id using kanaele_roh.dta
* Erwartung: keine Videos nur in master (_merge == 1); Kanaele nur in using
* (_merge == 2) sind solche ohne Video > 180 s.
tab _merge
assert _merge != 1
