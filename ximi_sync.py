"""
ximi_sync.py - Import automatique des interventions et badgeages depuis l'API Ximi.

Fonctionnement :
1. rafraichir_cache() parcourt l'API api/interventions/all page par page et garde
   en base (table ximi_interventions) les interventions récentes. L'API ne sait
   pas filtrer par date : on reprend là où on s'était arrêté à chaque appel.
2. synchroniser() récupère les badgeages (api/checkInOut), les relie aux
   interventions, applique les mêmes règles que Ximi, puis enregistre le
   résultat dans la table interventions (comme un import CSV).

Règles Ximi (vérifiées sur les imports CSV existants) :
  - Event 0 = arrivée, Event 1 = départ
  - aucun badgeage et intervention terminée -> "Manquée"
  - départ seul -> "Arrivée inconnue" ; arrivée seule -> "Départ inconnu"
  - écart = durée réelle - durée prévue (minutes)
      écart < -15  -> "Trop courte"
      écart >= 15  -> "Trop longue"
      sinon        -> "OK"
"""
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import database as db
import ximi
from parser import classify_problem, is_excluded

PARIS = ZoneInfo("Europe/Paris")
JOURS_CACHE_AVANT = 45   # on garde les interventions des 45 derniers jours
SEUIL_MINUTES = 15
STATUT_ANNULE = -3


def maintenant():
    """Heure de Paris sans fuseau (même format que les dates Ximi)."""
    return datetime.now(PARIS).replace(tzinfo=None)


def _dt(texte):
    """'2026-09-25T13:29:19.667' -> datetime (ou None)."""
    if not texte:
        return None
    try:
        return datetime.fromisoformat(str(texte)[:19])
    except ValueError:
        return None


def _hms(minutes):
    minutes = int(round(minutes))
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


# ─────────────────────────────────────────────────────────
# Tables
# ─────────────────────────────────────────────────────────

def init_tables():
    conn = db.get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ximi_interventions (
            id          BIGINT PRIMARY KEY,
            debut       TEXT,
            fin         TEXT,
            statut      INTEGER,
            intervenant TEXT,
            client      TEXT,
            vu_le       TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ximi_etat (
            cle    TEXT PRIMARY KEY,
            valeur TEXT
        )
    """)
    conn.commit()


def _get_etat(conn, cle, defaut=None):
    row = conn.execute("SELECT valeur FROM ximi_etat WHERE cle = ?", (cle,)).fetchone()
    return row["valeur"] if row else defaut


def _set_etat(conn, cle, valeur):
    conn.execute("""
        INSERT INTO ximi_etat (cle, valeur) VALUES (?, ?)
        ON CONFLICT (cle) DO UPDATE SET valeur = excluded.valeur
    """, (cle, str(valeur)))


# ─────────────────────────────────────────────────────────
# 1) Cache des interventions
# ─────────────────────────────────────────────────────────

def rafraichir_cache(budget_secondes=25):
    """Lit des pages de l'API jusqu'à épuisement du budget de temps.
    Reprend là où le dernier appel s'est arrêté."""
    t0 = time.time()
    conn = db.get_conn()
    offset = int(_get_etat(conn, "offset", 0))
    limite_basse = (maintenant() - timedelta(days=JOURS_CACHE_AVANT)).strftime("%Y-%m-%d")
    limite_haute = (maintenant() + timedelta(days=1)).strftime("%Y-%m-%d")
    vu_le = maintenant().strftime("%Y-%m-%d %H:%M:%S")
    pages = 0
    tour_termine = False
    if offset == 0:
        _set_etat(conn, "debut_tour", vu_le)

    while time.time() - t0 < budget_secondes:
        res = ximi.get("api/interventions/all", {"Top": 1000, "Offset": offset})
        items = res.get("Results", [])
        pages += 1
        for it in items:
            debut = (it.get("Start") or "").replace("T", " ")[:16]
            if not (limite_basse <= debut < limite_haute):
                continue
            conn.execute("""
                INSERT INTO ximi_interventions (id, debut, fin, statut, intervenant, client, vu_le)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    debut = excluded.debut, fin = excluded.fin, statut = excluded.statut,
                    intervenant = excluded.intervenant, client = excluded.client,
                    vu_le = excluded.vu_le
            """, (
                it["Id"], debut, (it.get("End") or "").replace("T", " ")[:16],
                it.get("Status"),
                ((it.get("Agent") or {}).get("DisplayName") or "").strip(),
                ((it.get("Client") or {}).get("DisplayName") or "").strip(),
                vu_le,
            ))
        offset += len(items)
        if not res.get("HasMoreRows") or not items:
            tour_termine = True
            break

    if tour_termine:
        # Un tour complet est fini : on supprime les interventions qui n'existent
        # plus dans Ximi (non revues depuis le début de ce tour) et on recommence.
        debut_tour = _get_etat(conn, "debut_tour", vu_le)
        conn.execute("DELETE FROM ximi_interventions WHERE vu_le < ?", (debut_tour,))
        conn.execute("DELETE FROM ximi_interventions WHERE debut < ?", (limite_basse,))
        _set_etat(conn, "dernier_tour_complet", vu_le)
        _set_etat(conn, "offset", 0)
    else:
        _set_etat(conn, "offset", offset)

    conn.commit()
    resultat = {
        "pages_lues": pages,
        "tour_termine": tour_termine,
        "dernier_tour_complet": _get_etat(conn, "dernier_tour_complet"),
    }
    conn.close()
    return resultat


# ─────────────────────────────────────────────────────────
# 2) Badgeages et classification
# ─────────────────────────────────────────────────────────

def _badgeages_depuis(date_debut, budget_secondes=20):
    """Retourne {InterventionId: {"arrivee": datetime, "depart": datetime}}."""
    t0 = time.time()
    par_intervention = {}
    offset = 0
    complet = False
    while time.time() - t0 < budget_secondes:
        res = ximi.get("api/checkInOut", {
            "lastModification": date_debut.strftime("%Y-%m-%d"),
            "Top": 1000, "Offset": offset,
        })
        items = res.get("Results", [])
        for b in items:
            quand = _dt(b.get("Time"))
            iid = b.get("InterventionId")
            if not quand or not iid:
                continue
            d = par_intervention.setdefault(iid, {"arrivee": None, "depart": None})
            if str(b.get("Event")) == "0":
                if d["arrivee"] is None or quand < d["arrivee"]:
                    d["arrivee"] = quand
            elif str(b.get("Event")) == "1":
                if d["depart"] is None or quand > d["depart"]:
                    d["depart"] = quand
        offset += len(items)
        if not res.get("HasMoreRows") or not items:
            complet = True
            break
    return par_intervention, complet


def classer(debut, fin, arrivee, depart, now):
    """Applique les règles Ximi. Retourne (timing, diff_minutes)."""
    if arrivee is None and depart is None:
        return ("Manquée" if fin <= now else ""), None
    if arrivee is None:
        return "Arrivée inconnue", None
    if depart is None:
        return ("Départ inconnu" if fin <= now else ""), None

    reel = (depart - arrivee).total_seconds() / 60
    if reel < 0:
        reel += 1440
    prevu = (fin - debut).total_seconds() / 60
    diff = round(reel - prevu, 2)
    if diff < -SEUIL_MINUTES:
        return "Trop courte", diff
    if diff >= SEUIL_MINUTES:
        return "Trop longue", diff
    return "OK", diff


def synchroniser(jours=14):
    """Calcule et enregistre les interventions des `jours` derniers jours."""
    conn = db.get_conn()
    if not _get_etat(conn, "dernier_tour_complet"):
        conn.close()
        return {"pret": False,
                "message": "Première lecture du planning Ximi en cours : relancez la synchronisation."}

    now = maintenant()
    depuis = (now - timedelta(days=jours)).replace(hour=0, minute=0, second=0, microsecond=0)
    badges, badges_complets = _badgeages_depuis(depuis - timedelta(days=1))

    lignes = conn.execute("""
        SELECT id, debut, fin, statut, intervenant, client
        FROM ximi_interventions
        WHERE debut >= ? AND debut <= ? AND statut <> ?
    """, (depuis.strftime("%Y-%m-%d %H:%M"), now.strftime("%Y-%m-%d %H:%M"), STATUT_ANNULE)).fetchall()
    conn.close()

    rows = []
    for l in lignes:
        if is_excluded(l["intervenant"], l["client"]):
            continue
        debut, fin = _dt(l["debut"]), _dt(l["fin"])
        if not debut or not fin:
            continue
        b = badges.get(l["id"], {})
        arrivee, depart = b.get("arrivee"), b.get("depart")
        timing, diff = classer(debut, fin, arrivee, depart, now)
        rows.append({
            "client": l["client"],
            "intervenant": l["intervenant"],
            "date_prevue": debut.strftime("%Y-%m-%d %H:%M"),
            "mois": debut.strftime("%Y-%m"),
            "duree": _hms((fin - debut).total_seconds() / 60),
            "debut_reel": arrivee.strftime("%H:%M:%S") if arrivee else "",
            "fin_reelle": depart.strftime("%H:%M:%S") if depart else "",
            "timing": timing,
            "diff_minutes": diff,
            "type_probleme": classify_problem(timing),
        })

    nom_import = f"API Ximi {now.strftime('%d/%m/%Y %H:%M')}"
    ajoutees, mises_a_jour, pmin, pmax = db.insert_interventions(rows, nom_import) if rows else (0, 0, None, None)
    return {
        "pret": True,
        "interventions_traitees": len(rows),
        "ajoutees": ajoutees,
        "mises_a_jour": mises_a_jour,
        "periode": [pmin, pmax],
        "badgeages_complets": badges_complets,
    }
