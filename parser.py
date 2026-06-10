# parser.py — Lecture et transformation du CSV Ximi en DataFrame analysable

import pandas as pd
import re
import unicodedata


# Formats de date possibles dans les exports Ximi
DATE_FORMATS = ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"]


def parse_date(val):
    """Parse une date Ximi en datetime, quel que soit le format (avec/sans secondes)."""
    if pd.isna(val):
        return pd.NaT
    s = str(val).strip()
    if not s:
        return pd.NaT
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(s, format=fmt)
        except (ValueError, TypeError):
            continue
    # Dernier recours : laisser pandas deviner (jour en premier)
    return pd.to_datetime(s, dayfirst=True, errors="coerce")


# Pseudo-intervenants / clients à exclure (formation, temps salarié, etc.)
# Comparaison sur le nom normalisé (sans accent, minuscules).
EXCLUDED_NAMES = {
    "formation, salarie",
}


def is_excluded(intervenant, client):
    """True si la ligne ne correspond pas à une vraie intervention (formation, etc.)."""
    return (normalize_name(intervenant) in EXCLUDED_NAMES
            or normalize_name(client) in EXCLUDED_NAMES)


def normalize_name(name):
    """
    Normalise un nom pour la comparaison (détection de doublons) :
    minuscules, sans accents, espaces réduits. Ne sert PAS à l'affichage.
    """
    if not name:
        return ""
    s = str(name).strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def parse_diff(val):
    """Convertit ±HH:MM:SS en minutes signées (float). Retourne None si vide."""
    if pd.isna(val) or str(val).strip() == "":
        return None
    val = str(val).strip()
    sign = -1 if val.startswith("-") else 1
    val = val.lstrip("+-").strip()
    parts = val.split(":")
    try:
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        return sign * (h * 60 + m + s / 60)
    except Exception:
        return None


def classify_problem(timing):
    if pd.isna(timing):
        return None
    t = str(timing).strip()
    if t == "Manquée":
        return "Manquée"
    if t in ("Arrivée inconnue", "Départ inconnu"):
        return "Badgeage partiel"
    if t == "Trop courte":
        return "Trop courte"
    if t == "Trop longue":
        return "Trop longue"
    return None


def parse_csv(filepath):
    """
    Lit le CSV Ximi (latin-1, séparateur virgule).
    Retourne un dict avec :
      - 'df_all'      : toutes les interventions valides
      - 'df_problems' : interventions avec un type_probleme non None
      - 'intervenants': liste triée des intervenants uniques
      - 'date_min'    : date minimale (str)
      - 'date_max'    : date maximale (str)
      - 'filename'    : nom du fichier
    """
    df = pd.read_csv(filepath, encoding="latin-1", sep=";", dtype=str)

    # Supprimer les lignes TOTAL (Client vide ou NaN)
    df = df[df["Client"].notna() & (df["Client"].str.strip() != "")]

    # Nettoyer les colonnes de base
    df["Intervenant"] = df["Intervenant"].str.strip()
    df["Client"] = df["Client"].str.strip()
    df["Timing"] = df["Timing"].str.strip() if "Timing" in df.columns else ""

    # Parser la date prévue (tous formats)
    df["date_prevue"] = df["Date"].apply(parse_date)

    # Diff en minutes
    df["diff_minutes"] = df["Diff."].apply(parse_diff) if "Diff." in df.columns else None

    # Classer le type de problème
    df["type_probleme"] = df["Timing"].apply(classify_problem)

    # Colonnes propres pour l'affichage
    df["debut_reel"] = df["Début réel"].str.strip() if "Début réel" in df.columns else ""
    df["fin_reelle"] = df["Fin réelle"].str.strip() if "Fin réelle" in df.columns else ""

    df_problems = df[df["type_probleme"].notna()].copy()

    dates_valides = df["date_prevue"].dropna()
    date_min = dates_valides.min().strftime("%d/%m/%Y") if not dates_valides.empty else "-"
    date_max = dates_valides.max().strftime("%d/%m/%Y") if not dates_valides.empty else "-"

    intervenants = sorted(df["Intervenant"].dropna().unique().tolist())

    return {
        "df_all": df,
        "df_problems": df_problems,
        "intervenants": intervenants,
        "date_min": date_min,
        "date_max": date_max,
    }


def parse_csv_to_rows(filepath):
    """
    Lit un CSV Ximi et retourne une liste de dicts prêts pour la base de données.
    Chaque dict contient les champs normalisés d'une intervention.
    """
    df = pd.read_csv(filepath, encoding="latin-1", sep=";", dtype=str)
    df = df[df["Client"].notna() & (df["Client"].str.strip() != "")]

    df["Intervenant"] = df["Intervenant"].str.strip()
    df["Client"] = df["Client"].str.strip()
    df["Timing"] = df["Timing"].str.strip() if "Timing" in df.columns else ""

    df["date_prevue"] = df["Date"].apply(parse_date)
    df["diff_minutes"] = df["Diff."].apply(parse_diff) if "Diff." in df.columns else None
    df["type_probleme"] = df["Timing"].apply(classify_problem)
    df["debut_reel"] = df["Début réel"].str.strip() if "Début réel" in df.columns else ""
    df["fin_reelle"] = df["Fin réelle"].str.strip() if "Fin réelle" in df.columns else ""

    rows = []
    for _, row in df.iterrows():
        # Ignorer les pseudo-interventions (formation, temps salarié…)
        if is_excluded(row.get("Intervenant", ""), row.get("Client", "")):
            continue

        dp = row["date_prevue"]
        if pd.isna(dp):
            date_iso, mois = None, None
        else:
            date_iso = dp.strftime("%Y-%m-%d %H:%M")
            mois = dp.strftime("%Y-%m")

        def clean(v):
            if pd.isna(v):
                return ""
            return str(v).strip()

        diff = row["diff_minutes"]
        if pd.isna(diff) if diff is not None else True:
            diff = None

        rows.append({
            "client": clean(row["Client"]),
            "intervenant": clean(row["Intervenant"]),
            "date_prevue": date_iso,
            "mois": mois,
            "duree": clean(row.get("Durée", "")),
            "debut_reel": clean(row.get("debut_reel", "")),
            "fin_reelle": clean(row.get("fin_reelle", "")),
            "timing": clean(row["Timing"]),
            "diff_minutes": diff,
            "type_probleme": row["type_probleme"] if row["type_probleme"] else None,
        })

    return rows
