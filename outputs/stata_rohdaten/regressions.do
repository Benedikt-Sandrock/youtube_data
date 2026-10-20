use "videos_kriegspraemie.dta", clear

* ln(x+1): Videos mit 0 Views/Likes/Kommentaren bleiben in der Stichprobe
gen ln_view_count = ln(view_count + 1)
gen ln_like_count = ln(like_count + 1)
gen ln_comment_count = ln(comment_count + 1)


* ===== KANALTYP =====
* alt_kanal (alist) mischt politische Alternativmedien und Finanzkanaele
* -> Aufteilung per channel_id (Titel teils leer bzw. mit Leerzeichen am Ende)
* 0 = Mainstream (clist), 1 = alternativ politisch, 2 = alternativ Finanzen
gen kanal_typ = 0
replace kanal_typ = 2 if alt_kanal == 1
replace kanal_typ = 1 if inlist(channel_id, ///
    "UC-qQ1TNcFK3DqD7jEK5D_jg", /// Martin Lejeune
    "UCbanHTRuGv2Fi7flpO735yw", /// Hallo Meinung
    "UCiTKi7Ahf3E2yMGpmIxSvgw", /// Deutschland Kurier
    "UCnk0-FU1ybs9MpWg8g3yqMw", /// Politik & Co
    "UCq-b0dwW97YRZWgSCikWQRA") /// DIE WELTWOCHE
    | inlist(channel_id, ///
    "UCthYpKoujTMmDX75fGr5o8A", /// Mathias von Gersdorff
    "UCyH9w3VhfZPdjH28VFeoHUA")  // Kontrafunk
label define kanal_typ 0 "Mainstream" 1 "alt. politisch" 2 "alt. Finanzen"
label values kanal_typ kanal_typ
label variable kanal_typ "Kanaltyp"
tab channel_title kanal_typ if kanal_typ > 0


* ===== GEWICHTE =====
* channel_weight = 1 / Anzahl Videos des Kanals IN DER JEWEILIGEN SCHAETZSTICHPROBE
* -> jeder Kanal geht mit Gesamtgewicht 1 ein. Vor jeder gewichteten Regression
* mit derselben if-Bedingung neu aufrufen.
capture program drop mkweight
program define mkweight
    syntax [if]
    marksample touse
    capture drop channel_weight
    tempvar n_s
    bysort channel_id: egen `n_s' = total(`touse')
    gen channel_weight = 1/`n_s' if `touse'
end


tab format kanal_typ
tab news_show kanal_typ
tab special_show kanal_typ


* ===== WAR PREMIUM =====
reghdfe view_count rel_russia_ukraine_war_core##kanal_typ if news_show == 0 & format == "long", ///
absorb(channel_id) cluster(channel_id)

reghdfe view_count rel_russia_ukraine_war_core##kanal_typ duration_sec if news_show == 0 ///
& format == "long", absorb(channel_id monat) cluster(channel_id)

reghdfe view_count rel_russia_ukraine_war_cw##kanal_typ if news_show == 0 & format == "long", ///
absorb(channel_id) cluster(channel_id)

reghdfe view_count rel_russia_ukraine_war_cw##kanal_typ duration_sec if news_show == 0 ///
& format == "long", absorb(channel_id monat) cluster(channel_id)
* Gesamtpraemie je Kanaltyp (Haupteffekt + Interaktion)
lincom 1.rel_russia_ukraine_war_cw + 1.rel_russia_ukraine_war_cw#1.kanal_typ
lincom 1.rel_russia_ukraine_war_cw + 1.rel_russia_ukraine_war_cw#2.kanal_typ

preserve
drop if rel_politics_general_cw == 0 & rel_russia_ukraine_war_cw == 0

mkweight if news_show == 0 & format == "long" & view_count < .
reghdfe view_count rel_russia_ukraine_war_cw##kanal_typ duration_sec ///
 if news_show == 0 & format == "long" [aw = channel_weight], absorb(channel_id monat) ///
 cluster(channel_id)
lincom 1.rel_russia_ukraine_war_cw + 1.rel_russia_ukraine_war_cw#1.kanal_typ
lincom 1.rel_russia_ukraine_war_cw + 1.rel_russia_ukraine_war_cw#2.kanal_typ

restore


* Getrennt nach Kanaltyp (0 = Mainstream, 1 = alt. politisch, 2 = alt. Finanzen)
forvalues k = 0/2 {
    di as text _n "----- kanal_typ = `k' -----"
    reghdfe view_count rel_russia_ukraine_war_cw duration_sec ///
     if news_show == 0 & format == "long" & kanal_typ == `k', absorb(channel_id monat) ///
     cluster(channel_id)
}

reghdfe view_count rel_russia_ukraine_war_cw duration_sec ///
 if news_show == 0 & format == "long" & post_war == 1 & monat <=748, absorb(channel_id monat) ///
 cluster(channel_id)



* ===== POST WAR EFFECT =====
reghdfe view_count rel_russia_ukraine_war_cw duration_sec ///
 if news_show == 0 & format == "long" & post_war == 1 & monat > 748 & monat <= 754, absorb(channel_id monat) ///
 cluster(channel_id)

* DiD um den Kriegsbeginn: Feb. 2022 (745) vor/nach dem 24.02. bzw. Feb.+Maerz 2022 (745/746)
* Gleiche Stichprobe wie oben (long, keine ganzen Sendungen), Cluster auf Kanalebene
reghdfe view_count kanal_typ##post_war if monat == 745 ///
 & news_show == 0 & format == "long", noabsorb cluster(channel_id)

reghdfe view_count kanal_typ##post_war if (monat == 745 | monat == 746) ///
 & news_show == 0 & format == "long", ///
 absorb(channel_id) cluster(channel_id)

mkweight if (monat == 745 | monat == 746) & news_show == 0 & format == "long" & view_count < .
reghdfe ln_view_count kanal_typ##post_war if (monat == 745 | monat == 746) ///
 & news_show == 0 & format == "long" ///
 [aw = channel_weight], ///
 absorb(channel_id) cluster(channel_id)
* Gesamteffekt nach Kriegsbeginn je Kanaltyp
lincom 1.post_war + 1.kanal_typ#1.post_war
lincom 1.post_war + 2.kanal_typ#1.post_war


preserve

rename rel_russia_ukraine_war_core war_core
rename rel_russia war_cw
rename rel_energy_core energy_core
rename rel_energy energy_cw
egen diff_topic = rowmax(rel*)
egen war_energy = rowmax(war_cw energy_cw)
egen both_topics = rowtotal(diff_topic war_energy)
gen only_war_energy = max(war_energy- diff_topic, 0)
