"""Monatliche Aufrufe ausgewählter Kanäle (Liniengrafiken).

Liest ``outputs/stata_rohdaten/monthly_views.dta`` (Kanal x Monat, Variable
``views``) und plottet die Aufrufe pro Monat für 16 ausgewählte Kanäle in vier
Gruppen (ÖRR, private Medien/Verlage, alternative Medien, Finanz/Immobilien).
Eine gestrichelte Linie markiert jeweils den Kriegsbeginn (24.02.2022).

Monate ohne Zeile im Datensatz werden als Lücke gezeichnet (nicht als 0 und
nicht interpoliert); einzelne Monate sind durch kleine Marker sichtbar.

Ausgaben (in ``scripts/adhoc/outputs/``):
- ``monthly_views_gruppen.png``: 2x2-Panels, ein Panel je Gruppe, log. y-Achse
  (Kanäle unterschiedlicher Größe innerhalb einer Gruppe vergleichbar).
- ``monthly_views_kanaele.png``: 4x4 Small Multiples, ein Panel je Kanal,
  lineare y-Achse mit eigener Skala (Verlauf je Kanal gut lesbar).
- ``monthly_views_medientyp_summe.png``: ALLE Kanäle des Datensatzes, Views je
  Monat summiert nach ``medientyp`` (oben, log. Skala) plus Anzahl Kanäle mit
  Daten je Monat (unten), weil die Summe stark von der Kanalzusammensetzung
  abhängt. Kanäle ohne ``medientyp`` (derzeit nur Lypix) fallen heraus.
- ``monthly_views_medientyp_index.png``: dieselben Summen als Index (log. Skala,
  zentriertes gleitendes 3-Monats-Mittel; Monate ohne Daten = 0 Views). Oben
  Basis Vorkriegsjahr 2021 (Ø = 100), unten Basis erstes Kriegsjahr
  03/2022-02/2023 (Ø = 100).
- ``monthly_views_rest_medientyp_index.png``: dieselbe Index-Grafik für
  ``outputs/stata_rohdaten/monthly_views_rest.dta`` (gleiche Struktur).
- ``monthly_views_marktanteil_medientyp.png``: Anteil je Medientyp an der
  Summe der Aufrufe, oben Krieg + Rest, darunter getrennt (3-Monats-Mittel).
- ``monthly_views_kriegsanteil_medientyp.png``: Anteil der Kriegsvideo-Aufrufe
  an allen Themenvideo-Aufrufen (Krieg + Rest) je Medientyp.
- ``monthly_views_marktanteil_medientyp_long.png`` und
  ``monthly_views_kriegsanteil_medientyp_long.png``: dieselben zwei Grafiken nur
  mit ``format == "long"`` (ohne Shorts/Livestreams), direkt aus
  ``videos_roh.dta`` + ``kanaele_roh.dta`` berechnet (gleiche Abgrenzung wie
  unten). Enthält die per Ausschluss gesetzten WELT-Videos (``format_derived``).
  Das Laden von ``videos_roh.dta`` dauert einige Minuten.
- ``..._long_vorkrieg.png``: dieselben zwei Long-Grafiken nur für Kanäle mit
  ``sample_vorkrieg == 1`` (Robustheit gegen Selektion auf späteren Erfolg).

Abgrenzung der beiden Datensätze (am 15.10.2026 aus ``videos_roh.dta`` exakt
nachgebildet; das erzeugende Do-File liegt nicht im Repo): ``monthly_views`` =
Videos mit ``rel_russia_ukraine_war_cw == 1``; ``monthly_views_rest`` = Videos
ohne Kriegs-Stichwort, aber mit mindestens einem ``rel_<topic>_cw == 1`` der
übrigen 12 Themen. Beide: alle Formate (inkl. Shorts), Summe der kumulierten
``views`` nach Upload-Monat. Krieg + Rest = alle Themenvideos, nicht alle Videos.
``n_videos`` in den .dta-Dateien ist keine Kanalgröße (konstant) und wird nicht
genutzt.

Aufruf: ``.venv/Scripts/python.exe scripts/adhoc/plot_monthly_views_ausgewaehlte_kanaele.py``
"""
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "outputs" / "stata_rohdaten" / "monthly_views.dta"
INPUT_REST = ROOT / "outputs" / "stata_rohdaten" / "monthly_views_rest.dta"
VIDEOS = ROOT / "outputs" / "stata_rohdaten" / "videos_roh.dta"
KANAELE = ROOT / "outputs" / "stata_rohdaten" / "kanaele_roh.dta"
OUT_DIR = ROOT / "scripts" / "adhoc" / "outputs"

# Gruppe -> Kanalnamen (exakt wie im Datensatz)
GRUPPEN = {
    "Öffentlich-rechtlich": ["tagesschau", "ZDFheute Nachrichten", "phoenix", "ARTEde", "MrWissen2go"],
    "Private Medien / Verlage": ["BILD", "WELT Nachrichtensender", "ntv Nachrichten", "DER SPIEGEL"],
    "Alternative Medien": ["DIE WELTWOCHE", "Gegenpol", "DACH Medien", "COMPACT-TV"],
    "Finanz / Immobilien": ["Vermietertagebuch - Alexander Raue", "GELDDRUCKER", "Aktien mit Kopf"],
}
# Feste kategoriale Reihenfolge (validierte Default-Palette), innerhalb jeder Gruppe neu ab Slot 1
SERIEN_FARBEN = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
# Eine Farbe je Gruppe für die Small Multiples
GRUPPEN_FARBEN = dict(zip(GRUPPEN, SERIEN_FARBEN))

KRIEGSBEGINN = pd.Timestamp("2022-02-24")
GRID = "#e4e3dd"
TEXT_MUTED = "#5c5c58"


def lade_daten() -> pd.DataFrame:
    df = pd.read_stata(INPUT)
    kanaele = [k for ks in GRUPPEN.values() for k in ks]
    fehlend = set(kanaele) - set(df["kanal_name"])
    if fehlend:
        raise ValueError(f"Kanäle nicht im Datensatz: {sorted(fehlend)}")
    return df[df["kanal_name"].isin(kanaele)]


def monatsreihe(df: pd.DataFrame, kanal: str, monate: pd.DatetimeIndex) -> pd.Series:
    """Views (Mio.) eines Kanals auf vollständigem Monatsraster; fehlende Monate = NaN (Lücke)."""
    s = df.loc[df["kanal_name"] == kanal].set_index("monat")["views"] / 1e6
    return s.reindex(monate)


def style_achse(ax) -> None:
    ax.axvline(KRIEGSBEGINN, color="#7a7a75", linestyle="--", linewidth=1, zorder=1)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(labelsize=8)


def plot_gruppen(df: pd.DataFrame, monate: pd.DatetimeIndex) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True, sharey=True)
    for ax, (gruppe, kanaele) in zip(axes.flat, GRUPPEN.items()):
        for kanal, farbe in zip(kanaele, SERIEN_FARBEN):
            s = monatsreihe(df, kanal, monate)
            ax.plot(s.index, s.values, color=farbe, linewidth=1.6, marker="o",
                    markersize=2.5, label=kanal)
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(
            lambda v, _: f"{v:g}".replace(".", ",")))
        style_achse(ax)
        ax.set_title(gruppe, loc="left", fontsize=11)
        ax.legend(frameon=False, fontsize=8, loc="lower right")
    for ax in axes[:, 0]:
        ax.set_ylabel("Aufrufe (Mio., log. Skala)")
    fig.suptitle("Aufrufe pro Monat nach Kanalgruppe (gestrichelt: Kriegsbeginn)",
                 x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    out = OUT_DIR / "monthly_views_gruppen.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_kanaele(df: pd.DataFrame, monate: pd.DatetimeIndex) -> Path:
    fig, axes = plt.subplots(4, 4, figsize=(16, 12), sharex=True)
    for row, (gruppe, kanaele) in zip(axes, GRUPPEN.items()):
        farbe = GRUPPEN_FARBEN[gruppe]
        for ax, kanal in zip(row, kanaele):
            s = monatsreihe(df, kanal, monate)
            ax.plot(s.index, s.values, color=farbe, linewidth=1.6, marker="o", markersize=2.5)
            ax.set_ylim(bottom=0)
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(
                lambda v, _: f"{v:g}".replace(".", ",")))
            style_achse(ax)
            ax.set_title(kanal, loc="left", fontsize=9.5)
        row[0].set_ylabel(gruppe, fontsize=10, color=TEXT_MUTED)
        for ax in row[len(kanaele):]:
            ax.set_visible(False)
    # Ausgeblendete Panels nehmen den x-Achsen-Beschriftungen nicht den Platz weg
    for ax in axes.flat:
        if ax.get_visible():
            ax.xaxis.set_tick_params(labelbottom=True)
    fig.suptitle("Aufrufe pro Monat je Kanal (Mio., eigene y-Skala je Panel; gestrichelt: Kriegsbeginn)",
                 x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    out = OUT_DIR / "monthly_views_kanaele.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


MEDIENTYPEN = {1: "ÖRR", 2: "Traditionelle Medien", 3: "Partei / Politiker",
               4: "Creator & alternative Medien"}


def plot_medientyp_summe() -> Path:
    df = pd.read_stata(INPUT).dropna(subset=["medientyp"])
    monate = pd.date_range(df["monat"].min(), df["monat"].max(), freq="MS")
    agg = df.groupby(["medientyp", "monat"]).agg(views=("views", "sum"),
                                                  n_kanaele=("kanal_name", "nunique"))

    fig, (ax, ax_n) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1.3]})
    for (code, label), farbe in zip(MEDIENTYPEN.items(), SERIEN_FARBEN):
        g = agg.loc[code].reindex(monate)
        n_kanaele = df.loc[df["medientyp"] == code, "kanal_name"].nunique()
        ax.plot(g.index, g["views"] / 1e6, color=farbe, linewidth=2,
                label=f"{label} ({n_kanaele} Kanäle)")
        ax_n.plot(g.index, g["n_kanaele"].fillna(0), color=farbe, linewidth=1.6)

    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
    ax.set_ylabel("Aufrufe (Mio., log. Skala)")
    ax.set_title("Summe der Aufrufe pro Monat nach Medientyp (gestrichelt: Kriegsbeginn)",
                 loc="left", fontsize=13)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax_n.set_ylabel("Kanäle mit Daten", fontsize=9)
    ax_n.set_ylim(bottom=0)
    for a in (ax, ax_n):
        style_achse(a)
    fig.tight_layout()
    out = OUT_DIR / "monthly_views_medientyp_summe.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


INDEX_BASEN = {
    "Basis: Vorkriegsjahr 2021 (Ø = 100)": ("2021-01-01", "2021-12-01"),
    "Basis: erstes Kriegsjahr 03/2022–02/2023 (Ø = 100)": ("2022-03-01", "2023-02-01"),
}


def plot_medientyp_index(input_path: Path = INPUT) -> Path:
    df = pd.read_stata(input_path).dropna(subset=["medientyp"])
    monate = pd.date_range(df["monat"].min(), df["monat"].max(), freq="MS")
    # Monat x Medientyp; Monate ohne Kanal mit Daten = 0 Views
    wide = (df.pivot_table(index="monat", columns="medientyp", values="views", aggfunc="sum")
              .reindex(monate).fillna(0))
    geglaettet = wide.rolling(3, center=True, min_periods=2).mean()

    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    for ax, (titel, (von, bis)) in zip(axes, INDEX_BASEN.items()):
        basis = wide.loc[von:bis].mean()
        index = geglaettet / basis * 100
        for (code, label), farbe in zip(MEDIENTYPEN.items(), SERIEN_FARBEN):
            ax.plot(index.index, index[code], color=farbe, linewidth=2, label=label)
        ax.axhline(100, color="#7a7a75", linewidth=0.8)
        ax.axvspan(pd.Timestamp(von), pd.Timestamp(bis) + pd.offsets.MonthEnd(0),
                   color="#efeee9", zorder=0)
        ax.set_yscale("log")
        ax.yaxis.set_major_locator(mticker.LogLocator(subs=(1, 2, 5)))
        ax.yaxis.set_minor_locator(mticker.NullLocator())
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
        ax.set_ylabel("Index (log. Skala)")
        ax.set_title(titel, loc="left", fontsize=11)
        style_achse(ax)
    axes[0].legend(frameon=False, fontsize=9, loc="upper left")
    fig.suptitle("Summe der Aufrufe nach Medientyp als Index "
                 "(gleitendes 3-Monats-Mittel; grau: Basiszeitraum; gestrichelt: Kriegsbeginn)",
                 x=0.01, ha="left", fontsize=12)
    fig.tight_layout()
    out = OUT_DIR / f"{input_path.stem}_medientyp_index.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


def lade_krieg_rest() -> pd.DataFrame:
    """Views je Monat x Medientyp, Spalten ``krieg`` und ``rest`` (fehlende Monate = 0)."""
    teile = {}
    for name, pfad in (("krieg", INPUT), ("rest", INPUT_REST)):
        df = pd.read_stata(pfad).dropna(subset=["medientyp"])
        teile[name] = df.groupby(["monat", "medientyp"])["views"].sum()
    wide = pd.concat(teile, axis=1).fillna(0)
    monate = pd.date_range(wide.index.get_level_values("monat").min(),
                           wide.index.get_level_values("monat").max(), freq="MS")
    full = pd.MultiIndex.from_product([monate, list(MEDIENTYPEN)], names=["monat", "medientyp"])
    return wide.reindex(full, fill_value=0)


def glaetten(wide: pd.DataFrame) -> pd.DataFrame:
    """Zentriertes gleitendes 3-Monats-Mittel je Medientyp (Spalten = Medientyp)."""
    return wide.rolling(3, center=True, min_periods=2).mean()


TOPICS_REST = ["politics_general", "corona_pandemic", "migration", "economy_general", "energy",
               "climate", "gender", "mideast", "iran", "eu", "usa", "education"]


def lade_krieg_rest_videos(fmt: str = "long", nur_vorkrieg: bool = False) -> pd.DataFrame:
    """Wie ``lade_krieg_rest``, aber direkt aus ``videos_roh.dta`` und nur Format ``fmt``.

    Abgrenzung identisch zu ``monthly_views``/``monthly_views_rest`` (Krieg =
    ``rel_russia_ukraine_war_cw == 1``; Rest = sonst mindestens ein
    ``rel_<topic>_cw == 1``); ``medientyp`` aus ``kanaele_roh.dta``.
    ``nur_vorkrieg``: nur Kanäle mit ``sample_vorkrieg == 1``.
    """
    rel = [f"rel_{t}_cw" for t in TOPICS_REST]
    v = pd.read_stata(VIDEOS, convert_categoricals=False,
                      columns=["channel_id", "monat", "views", "format",
                               "rel_russia_ukraine_war_cw", *rel])
    v = v[v["format"] == fmt]
    k = pd.read_stata(KANAELE, convert_categoricals=False,
                      columns=["channel_id", "medientyp", "sample_vorkrieg"])
    if nur_vorkrieg:
        k = k[k["sample_vorkrieg"] == 1]
    v = v.merge(k, on="channel_id").dropna(subset=["medientyp"])
    v["monat"] = v["monat"].astype("datetime64[ns]")
    krieg = v["rel_russia_ukraine_war_cw"] == 1
    rest = ~krieg & v[rel].eq(1).any(axis=1)
    teile = {name: v[m].groupby(["monat", "medientyp"])["views"].sum()
             for name, m in (("krieg", krieg), ("rest", rest))}
    wide = pd.concat(teile, axis=1).fillna(0)
    monate = pd.date_range("2021-01-01", wide.index.get_level_values("monat").max(), freq="MS")
    full = pd.MultiIndex.from_product([monate, list(MEDIENTYPEN)], names=["monat", "medientyp"])
    return wide.reindex(full, fill_value=0)


def plot_marktanteil(kr: pd.DataFrame | None = None, suffix: str = "") -> Path:
    kr = lade_krieg_rest() if kr is None else kr.copy()
    kr["gesamt"] = kr["krieg"] + kr["rest"]
    panels = {"Alle Themenvideos (Krieg + Rest)": "gesamt",
              "Nur Kriegsvideos": "krieg",
              "Nur übrige Themenvideos (Rest)": "rest"}

    fig, axes = plt.subplots(3, 1, figsize=(12, 11), sharex=True, sharey=True)
    for ax, (titel, spalte) in zip(axes, panels.items()):
        summen = glaetten(kr[spalte].unstack("medientyp"))
        anteile = summen.div(summen.sum(axis=1), axis=0) * 100
        for (code, label), farbe in zip(MEDIENTYPEN.items(), SERIEN_FARBEN):
            ax.plot(anteile.index, anteile[code], color=farbe, linewidth=2, label=label)
        ax.set_ylim(0, 100)
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
        ax.set_ylabel("Anteil an Aufrufen")
        ax.set_title(titel, loc="left", fontsize=11)
        style_achse(ax)
    axes[0].legend(frameon=False, fontsize=9, loc="upper left", ncol=2)
    fig.suptitle("Marktanteil je Medientyp an den Aufrufen von Themenvideos "
                 "(gleitendes 3-Monats-Mittel; gestrichelt: Kriegsbeginn)",
                 x=0.01, ha="left", fontsize=12)
    fig.tight_layout()
    if suffix:
        fig.texts[-1].set_text(fig.texts[-1].get_text() + f" – {suffix}")
    out = OUT_DIR / f"monthly_views_marktanteil_medientyp{'_' + suffix if suffix else ''}.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_kriegsanteil(kr: pd.DataFrame | None = None, suffix: str = "") -> Path:
    kr = lade_krieg_rest() if kr is None else kr
    krieg = glaetten(kr["krieg"].unstack("medientyp"))
    gesamt = glaetten((kr["krieg"] + kr["rest"]).unstack("medientyp"))
    anteil = krieg / gesamt * 100

    fig, ax = plt.subplots(figsize=(12, 5.5))
    for (code, label), farbe in zip(MEDIENTYPEN.items(), SERIEN_FARBEN):
        ax.plot(anteil.index, anteil[code], color=farbe, linewidth=2, label=label)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.set_ylabel("Anteil Kriegsvideos an Aufrufen")
    ax.set_title("Anteil der Kriegsvideo-Aufrufe an allen Themenvideo-Aufrufen je Medientyp "
                 "(gleitendes 3-Monats-Mittel; gestrichelt: Kriegsbeginn)", loc="left", fontsize=12)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    style_achse(ax)
    fig.tight_layout()
    if suffix:
        ax.set_title(ax.get_title(loc="left") + f" – {suffix}", loc="left", fontsize=12)
    out = OUT_DIR / f"monthly_views_kriegsanteil_medientyp{'_' + suffix if suffix else ''}.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    df = lade_daten()
    monate = pd.date_range(df["monat"].min(), df["monat"].max(), freq="MS")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for out in (plot_gruppen(df, monate), plot_kanaele(df, monate), plot_medientyp_summe(),
                plot_medientyp_index(), plot_medientyp_index(INPUT_REST),
                plot_marktanteil(), plot_kriegsanteil()):
        print(f"Gespeichert: {out}")
    # Robustheit ohne Shorts/Livestreams (liest videos_roh.dta, dauert einige Minuten)
    kr_long = lade_krieg_rest_videos("long")
    for out in (plot_marktanteil(kr_long, "long"), plot_kriegsanteil(kr_long, "long")):
        print(f"Gespeichert: {out}")
    # Robustheit gegen Selektion auf späteren Erfolg: nur Kanäle mit sample_vorkrieg == 1
    kr_vk = lade_krieg_rest_videos("long", nur_vorkrieg=True)
    for out in (plot_marktanteil(kr_vk, "long_vorkrieg"), plot_kriegsanteil(kr_vk, "long_vorkrieg")):
        print(f"Gespeichert: {out}")


if __name__ == "__main__":
    main()
