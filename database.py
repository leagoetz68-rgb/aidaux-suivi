# database.py — Gestion de la base SQLite (stockage longitudinal des interventions)

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aidaux.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crée les tables si elles n'existent pas."""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS interventions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            client        TEXT,
            intervenant   TEXT,
            date_prevue   TEXT,      -- ISO 'YYYY-MM-DD HH:MM'
            mois          TEXT,      -- 'YYYY-MM' pour regroupement
            duree         TEXT,
            debut_reel    TEXT,
            fin_reelle    TEXT,
            timing        TEXT,
            diff_minutes  REAL,
            type_probleme TEXT,
            source_file   TEXT,
            imported_at   TEXT,
            UNIQUE(client, intervenant, date_prevue)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS imports (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            filename     TEXT,
            imported_at  TEXT,
            rows_added   INTEGER,
            rows_skipped INTEGER,
            period_min   TEXT,
            period_max   TEXT
        )
    """)

    # Index utiles pour les requêtes
    c.execute("CREATE INDEX IF NOT EXISTS idx_interv ON interventions(intervenant)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_mois ON interventions(mois)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_type ON interventions(type_probleme)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_date ON interventions(date_prevue)")

    conn.commit()
    conn.close()


def _build_name_map(conn, column):
    """Map {nom_normalisé: orthographe_canonique} à partir des noms déjà en base."""
    from parser import normalize_name
    rows = conn.execute(
        f"SELECT DISTINCT {column} FROM interventions WHERE {column} IS NOT NULL"
    ).fetchall()
    m = {}
    for r in rows:
        m[normalize_name(r[0])] = r[0]
    return m


def insert_interventions(rows, filename):
    """
    Insère une liste de dicts d'interventions.
    Ignore les doublons (même client + intervenant + date_prevue).
    Canonicalise les noms (fusionne les variantes de casse/accents).
    Retourne (nb_ajoutées, nb_ignorées, period_min, period_max).
    """
    from parser import normalize_name

    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Cartes de canonicalisation (la première orthographe vue gagne)
    map_interv = _build_name_map(conn, "intervenant")
    map_client = _build_name_map(conn, "client")

    def canon(name, m):
        key = normalize_name(name)
        if key not in m:
            m[key] = name  # première occurrence = référence
        return m[key]

    added = 0
    skipped = 0
    dates = []

    for r in rows:
        r["intervenant"] = canon(r["intervenant"], map_interv)
        r["client"] = canon(r["client"], map_client)
        try:
            c.execute("""
                INSERT INTO interventions
                (client, intervenant, date_prevue, mois, duree, debut_reel,
                 fin_reelle, timing, diff_minutes, type_probleme, source_file, imported_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                r["client"], r["intervenant"], r["date_prevue"], r["mois"],
                r["duree"], r["debut_reel"], r["fin_reelle"], r["timing"],
                r["diff_minutes"], r["type_probleme"], filename, now
            ))
            added += 1
            if r["date_prevue"]:
                dates.append(r["date_prevue"])
        except sqlite3.IntegrityError:
            skipped += 1

    period_min = min(dates) if dates else None
    period_max = max(dates) if dates else None

    c.execute("""
        INSERT INTO imports (filename, imported_at, rows_added, rows_skipped, period_min, period_max)
        VALUES (?,?,?,?,?,?)
    """, (filename, now, added, skipped, period_min, period_max))

    conn.commit()
    conn.close()
    return added, skipped, period_min, period_max


def query_interventions(intervenant=None, type_probleme=None, mois=None,
                        date_debut=None, date_fin=None, problems_only=False,
                        limit=None, offset=None):
    """Requête filtrée. Retourne une liste de dicts (lignes)."""
    conn = get_conn()
    c = conn.cursor()

    sql = "SELECT * FROM interventions WHERE 1=1"
    params = []

    if intervenant:
        sql += " AND intervenant = ?"; params.append(intervenant)
    if type_probleme:
        sql += " AND type_probleme = ?"; params.append(type_probleme)
    if mois:
        sql += " AND mois = ?"; params.append(mois)
    if problems_only:
        sql += " AND type_probleme IS NOT NULL"
    if date_debut:
        sql += " AND date_prevue >= ?"; params.append(date_debut + " 00:00")
    if date_fin:
        sql += " AND date_prevue <= ?"; params.append(date_fin + " 23:59")

    sql += " ORDER BY date_prevue ASC"

    if limit is not None:
        sql += " LIMIT ?"; params.append(limit)
        if offset is not None:
            sql += " OFFSET ?"; params.append(offset)

    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    conn.close()
    return rows


def count_interventions(intervenant=None, type_probleme=None, mois=None,
                        date_debut=None, date_fin=None, problems_only=False):
    conn = get_conn()
    c = conn.cursor()
    sql = "SELECT COUNT(*) FROM interventions WHERE 1=1"
    params = []
    if intervenant:
        sql += " AND intervenant = ?"; params.append(intervenant)
    if type_probleme:
        sql += " AND type_probleme = ?"; params.append(type_probleme)
    if mois:
        sql += " AND mois = ?"; params.append(mois)
    if problems_only:
        sql += " AND type_probleme IS NOT NULL"
    if date_debut:
        sql += " AND date_prevue >= ?"; params.append(date_debut + " 00:00")
    if date_fin:
        sql += " AND date_prevue <= ?"; params.append(date_fin + " 23:59")
    n = c.execute(sql, params).fetchone()[0]
    conn.close()
    return n


def get_stats(intervenant=None, mois=None, date_debut=None, date_fin=None):
    """Retourne les KPIs (total + comptes par type de problème) sur le périmètre filtré."""
    conn = get_conn()
    c = conn.cursor()

    where = "WHERE 1=1"
    params = []
    if intervenant:
        where += " AND intervenant = ?"; params.append(intervenant)
    if mois:
        where += " AND mois = ?"; params.append(mois)
    if date_debut:
        where += " AND date_prevue >= ?"; params.append(date_debut + " 00:00")
    if date_fin:
        where += " AND date_prevue <= ?"; params.append(date_fin + " 23:59")

    total = c.execute(f"SELECT COUNT(*) FROM interventions {where}", params).fetchone()[0]

    rows = c.execute(
        f"SELECT type_probleme, COUNT(*) FROM interventions {where} "
        f"AND type_probleme IS NOT NULL GROUP BY type_probleme", params
    ).fetchall()

    # Non renseigné (N/A) : ni problème, ni OK
    na = c.execute(
        f"SELECT COUNT(*) FROM interventions {where} "
        f"AND type_probleme IS NULL AND COALESCE(timing,'') <> 'OK'", params
    ).fetchone()[0]
    conn.close()

    counts = {r[0]: r[1] for r in rows}
    return {
        "total": total,
        "manquees": counts.get("Manquée", 0),
        "partiels": counts.get("Badgeage partiel", 0),
        "courtes": counts.get("Trop courte", 0),
        "longues": counts.get("Trop longue", 0),
        "na": na,
    }


def get_intervenants():
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT intervenant FROM interventions WHERE intervenant IS NOT NULL "
        "AND intervenant != '' ORDER BY intervenant"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_mois_list():
    """Liste des mois présents (du plus récent au plus ancien)."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT mois FROM interventions WHERE mois IS NOT NULL ORDER BY mois DESC"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_global_info():
    """Infos générales pour la page d'accueil."""
    conn = get_conn()
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM interventions").fetchone()[0]
    nb_interv = c.execute("SELECT COUNT(DISTINCT intervenant) FROM interventions").fetchone()[0]
    nb_clients = c.execute("SELECT COUNT(DISTINCT client) FROM interventions").fetchone()[0]
    nb_mois = c.execute("SELECT COUNT(DISTINCT mois) FROM interventions").fetchone()[0]
    pmin = c.execute("SELECT MIN(date_prevue) FROM interventions").fetchone()[0]
    pmax = c.execute("SELECT MAX(date_prevue) FROM interventions").fetchone()[0]
    conn.close()
    return {
        "total": total, "nb_intervenants": nb_interv, "nb_clients": nb_clients,
        "nb_mois": nb_mois, "period_min": pmin, "period_max": pmax,
    }


def get_imports_history():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM imports ORDER BY imported_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_monthly_evolution():
    """Évolution par mois : total + comptes de problèmes. Pour graphiques."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT mois,
               COUNT(*) as total,
               SUM(CASE WHEN type_probleme='Manquée' THEN 1 ELSE 0 END) as manquees,
               SUM(CASE WHEN type_probleme='Badgeage partiel' THEN 1 ELSE 0 END) as partiels,
               SUM(CASE WHEN type_probleme='Trop courte' THEN 1 ELSE 0 END) as courtes,
               SUM(CASE WHEN type_probleme='Trop longue' THEN 1 ELSE 0 END) as longues,
               SUM(CASE WHEN type_probleme IS NULL AND COALESCE(timing,'') <> 'OK' THEN 1 ELSE 0 END) as na
        FROM interventions WHERE mois IS NOT NULL
        GROUP BY mois ORDER BY mois
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_all():
    """Vide toute la base (réinitialisation)."""
    conn = get_conn()
    conn.execute("DELETE FROM interventions")
    conn.execute("DELETE FROM imports")
    conn.commit()
    conn.close()


def delete_import(import_id):
    """Supprime un import et toutes les interventions issues de ce fichier."""
    conn = get_conn()
    c = conn.cursor()
    row = c.execute("SELECT filename FROM imports WHERE id = ?", (import_id,)).fetchone()
    if not row:
        conn.close()
        return 0
    filename = row[0]
    n = c.execute("DELETE FROM interventions WHERE source_file = ?", (filename,)).rowcount
    c.execute("DELETE FROM imports WHERE id = ?", (import_id,))
    conn.commit()
    conn.close()
    return n


def delete_intervention(interv_id):
    """Supprime une intervention par son id."""
    conn = get_conn()
    n = conn.execute("DELETE FROM interventions WHERE id = ?", (interv_id,)).rowcount
    conn.commit()
    conn.close()
    return n


def get_all_imports():
    """Tous les imports avec le nombre d'interventions encore présentes."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT i.*,
               (SELECT COUNT(*) FROM interventions v WHERE v.source_file = i.filename) as nb_actuel
        FROM imports i ORDER BY i.imported_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────
# Analyses pour rapports (par intervenant, classements)
# ─────────────────────────────────────────────────────────

def stats_par_intervenant(mois=None):
    """
    Stats agrégées par intervenant (optionnellement filtrées sur un mois).
    Retourne une liste de dicts triés par taux de problèmes décroissant.
    """
    conn = get_conn()
    where = "WHERE 1=1"
    params = []
    if mois:
        where += " AND mois = ?"; params.append(mois)

    rows = conn.execute(f"""
        SELECT intervenant,
               COUNT(*) as total,
               SUM(CASE WHEN type_probleme='Manquée' THEN 1 ELSE 0 END) as manquees,
               SUM(CASE WHEN type_probleme='Badgeage partiel' THEN 1 ELSE 0 END) as partiels,
               SUM(CASE WHEN type_probleme='Trop courte' THEN 1 ELSE 0 END) as courtes,
               SUM(CASE WHEN type_probleme='Trop longue' THEN 1 ELSE 0 END) as longues,
               SUM(CASE WHEN type_probleme IS NOT NULL THEN 1 ELSE 0 END) as problemes
        FROM interventions {where}
        GROUP BY intervenant
        ORDER BY intervenant
    """, params).fetchall()
    conn.close()

    out = []
    for r in rows:
        d = dict(r)
        d["taux"] = round(d["problemes"] / d["total"] * 100, 1) if d["total"] else 0
        out.append(d)
    out.sort(key=lambda x: x["taux"], reverse=True)
    return out


def detail_intervenant(intervenant):
    """Détail complet d'un intervenant : stats globales + évolution mensuelle."""
    conn = get_conn()

    glob = conn.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN type_probleme='Manquée' THEN 1 ELSE 0 END) as manquees,
               SUM(CASE WHEN type_probleme='Badgeage partiel' THEN 1 ELSE 0 END) as partiels,
               SUM(CASE WHEN type_probleme='Trop courte' THEN 1 ELSE 0 END) as courtes,
               SUM(CASE WHEN type_probleme='Trop longue' THEN 1 ELSE 0 END) as longues,
               SUM(CASE WHEN type_probleme IS NOT NULL THEN 1 ELSE 0 END) as problemes,
               SUM(CASE WHEN type_probleme IS NULL AND COALESCE(timing,'') <> 'OK' THEN 1 ELSE 0 END) as na,
               COUNT(DISTINCT client) as nb_clients
        FROM interventions WHERE intervenant = ?
    """, (intervenant,)).fetchone()

    evo = conn.execute("""
        SELECT mois, COUNT(*) as total,
               SUM(CASE WHEN type_probleme='Manquée' THEN 1 ELSE 0 END) as manquees,
               SUM(CASE WHEN type_probleme='Badgeage partiel' THEN 1 ELSE 0 END) as partiels,
               SUM(CASE WHEN type_probleme='Trop courte' THEN 1 ELSE 0 END) as courtes,
               SUM(CASE WHEN type_probleme='Trop longue' THEN 1 ELSE 0 END) as longues,
               SUM(CASE WHEN type_probleme IS NULL AND COALESCE(timing,'') <> 'OK' THEN 1 ELSE 0 END) as na
        FROM interventions WHERE intervenant = ? AND mois IS NOT NULL
        GROUP BY mois ORDER BY mois
    """, (intervenant,)).fetchall()

    conn.close()
    g = dict(glob)
    g["taux"] = round(g["problemes"] / g["total"] * 100, 1) if g["total"] else 0
    return {"global": g, "evolution": [dict(r) for r in evo]}


def top_clients_problemes(mois=None, limit=10):
    """Clients les plus impactés par des problèmes."""
    conn = get_conn()
    where = "WHERE type_probleme IS NOT NULL"
    params = []
    if mois:
        where += " AND mois = ?"; params.append(mois)
    rows = conn.execute(f"""
        SELECT client, COUNT(*) as problemes
        FROM interventions {where}
        GROUP BY client ORDER BY problemes DESC LIMIT ?
    """, params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def stats_mensuelles_detaillees():
    """Évolution mensuelle avec taux + variation. Pour le suivi mensuel."""
    evo = get_monthly_evolution()
    out = []
    prev_taux = None
    for e in evo:
        probs = e["manquees"] + e["partiels"] + e["courtes"] + e["longues"]
        taux = round(probs / e["total"] * 100, 1) if e["total"] else 0
        variation = None if prev_taux is None else round(taux - prev_taux, 1)
        out.append({**e, "problemes": probs, "taux": taux, "variation": variation})
        prev_taux = taux
    return out
# ─────────────────────────────────────────────────────────
# Analyses financières et alertes
# ─────────────────────────────────────────────────────────

def impact_financier(mois=None, date_debut=None, date_fin=None):
    """
    Calcule l'impact financier estimé des anomalies.
    - Manquées : durée prévue entière
    - Trop courtes : diff_minutes manquantes
    - Badgeage partiel : 30 min par défaut
    Taux : aide ménagère 12.02€ (<01/06/2026), 12.31€ (≥01/06/2026) / auxiliaire 13€
    """
    from datetime import datetime as dt
    conn = get_conn()
    where = "WHERE type_probleme IS NOT NULL"
    params = []
    if mois:
        where += " AND mois = ?"; params.append(mois)
    if date_debut:
        where += " AND date_prevue >= ?"; params.append(date_debut + " 00:00")
    if date_fin:
        where += " AND date_prevue <= ?"; params.append(date_fin + " 23:59")

    rows = conn.execute(f"""
        SELECT type_probleme, diff_minutes, duree, date_prevue
        FROM interventions {where}
    """, params).fetchall()
    conn.close()

    total_minutes = 0
    detail = {"Manquée": 0, "Trop courte": 0, "Badgeage partiel": 0, "Trop longue": 0}
    cout_detail = {"Manquée": 0.0, "Trop courte": 0.0, "Badgeage partiel": 0.0, "Trop longue": 0.0}

    for r in rows:
        tp, diff, duree, date_str = r[0], r[1], r[2], r[3]
        # Taux horaire selon date
        taux = 12.02
        if date_str:
            try:
                if dt.strptime(date_str[:10], "%Y-%m-%d") >= dt(2026, 6, 1):
                    taux = 12.31
            except Exception:
                pass

        minutes = 0
        if tp == "Manquée":
            try:
                parts = duree.split(":")
                minutes = int(parts[0]) * 60 + int(parts[1])
            except Exception:
                minutes = 60
        elif tp == "Trop courte":
            minutes = abs(diff) if diff else 0
        elif tp == "Badgeage partiel":
            minutes = 30

        detail[tp] = detail.get(tp, 0) + minutes
        cout_detail[tp] = cout_detail.get(tp, 0.0) + round(minutes / 60 * taux, 2)
        total_minutes += minutes

    taux_ref = 12.31
    return {
        "total_minutes": round(total_minutes),
        "total_heures": round(total_minutes / 60, 1),
        "cout_estime": round(sum(cout_detail.values()), 2),
        "taux_horaire": taux_ref,
        "detail_minutes": detail,
        "detail_cout": cout_detail,
    }


def risque_facturation(mois=None):
    """Interventions à risque de facturation incorrecte (Manquées + Badgeage partiel)."""
    conn = get_conn()
    where = "WHERE type_probleme IN ('Manquée', 'Badgeage partiel')"
    params = []
    if mois:
        where += " AND mois = ?"; params.append(mois)
    rows = conn.execute(f"""
        SELECT intervenant, client, date_prevue, type_probleme, duree
        FROM interventions {where}
        ORDER BY type_probleme, date_prevue DESC
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def alertes_cloture(mois=None):
    """Interventions prioritaires à vérifier avant clôture de paie."""
    conn = get_conn()
    where = "WHERE type_probleme IN ('Manquée', 'Badgeage partiel', 'Trop courte')"
    params = []
    if mois:
        where += " AND mois = ?"; params.append(mois)
    rows = conn.execute(f"""
        SELECT intervenant, client, date_prevue, type_probleme, duree, diff_minutes
        FROM interventions {where}
        ORDER BY
            CASE type_probleme
                WHEN 'Manquée' THEN 1
                WHEN 'Badgeage partiel' THEN 2
                WHEN 'Trop courte' THEN 3
            END,
            date_prevue DESC
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def comparaison_periodes(mois1, mois2):
    """Compare deux mois : anomalies, taux, impact financier."""
    def stats_mois(mois):
        conn = get_conn()
        row = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN type_probleme='Manquée' THEN 1 ELSE 0 END) as manquees,
                   SUM(CASE WHEN type_probleme='Badgeage partiel' THEN 1 ELSE 0 END) as partiels,
                   SUM(CASE WHEN type_probleme='Trop courte' THEN 1 ELSE 0 END) as courtes,
                   SUM(CASE WHEN type_probleme='Trop longue' THEN 1 ELSE 0 END) as longues
            FROM interventions WHERE mois = ?
        """, (mois,)).fetchone()
        conn.close()
        if not row or row[0] == 0:
            return None
        d = dict(row)
        d["problemes"] = d["manquees"] + d["partiels"] + d["courtes"] + d["longues"]
        d["taux"] = round(d["problemes"] / d["total"] * 100, 1) if d["total"] else 0
        d["mois"] = mois
        impact = impact_financier(mois=mois)
        d["cout_estime"] = impact["cout_estime"]
        d["total_heures"] = impact["total_heures"]
        return d

    s1 = stats_mois(mois1)
    s2 = stats_mois(mois2)
    if not s1 or not s2:
        return {"error": "Données manquantes pour l'un des mois"}
    return {
        "mois1": s1,
        "mois2": s2,
        "variation_taux": round(s2["taux"] - s1["taux"], 1),
        "variation_cout": round(s2["cout_estime"] - s1["cout_estime"], 2),
        "variation_problemes": s2["problemes"] - s1["problemes"],
    }
def impact_financier_par_intervenant(mois=None):
    """Impact financier estimé des anomalies, groupé par intervenant."""
    from datetime import datetime as dt
    conn = get_conn()
    where = "WHERE type_probleme IS NOT NULL"
    params = []
    if mois:
        where += " AND mois = ?"; params.append(mois)

    rows = conn.execute(f"""
        SELECT intervenant, type_probleme, diff_minutes, duree, date_prevue
        FROM interventions {where}
        ORDER BY intervenant
    """, params).fetchall()
    conn.close()

    intervenants = {}
    for r in rows:
        nom = r[0]
        tp, diff, duree, date_str = r[1], r[2], r[3], r[4]

        taux = 12.02
        if date_str:
            try:
                if dt.strptime(date_str[:10], "%Y-%m-%d") >= dt(2026, 6, 1):
                    taux = 12.31
            except Exception:
                pass

        minutes = 0
        if tp == "Manquée":
            try:
                parts = duree.split(":")
                minutes = int(parts[0]) * 60 + int(parts[1])
            except Exception:
                minutes = 60
        elif tp == "Trop courte":
            minutes = abs(diff) if diff else 0
        elif tp == "Badgeage partiel":
            minutes = 30

        if nom not in intervenants:
            intervenants[nom] = {"intervenant": nom, "total_minutes": 0, "cout_estime": 0.0,
                                  "manquees": 0, "partiels": 0, "courtes": 0, "longues": 0}
        intervenants[nom]["total_minutes"] += minutes
        intervenants[nom]["cout_estime"] += round(minutes / 60 * taux, 2)
        if tp == "Manquée": intervenants[nom]["manquees"] += 1
        elif tp == "Badgeage partiel": intervenants[nom]["partiels"] += 1
        elif tp == "Trop courte": intervenants[nom]["courtes"] += 1
        elif tp == "Trop longue": intervenants[nom]["longues"] += 1

    result = list(intervenants.values())
    for r in result:
        r["cout_estime"] = round(r["cout_estime"], 2)
        r["total_heures"] = round(r["total_minutes"] / 60, 1)
    result.sort(key=lambda x: x["cout_estime"], reverse=True)
    return result
