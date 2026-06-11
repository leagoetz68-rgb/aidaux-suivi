# app.py — Application de suivi Aid'aux (Flask + SQLite)

import io
import os
import tempfile

from flask import Flask, jsonify, render_template, request, send_file, session, redirect, url_for

import database as db
from parser import parse_csv_to_rows

app = Flask(__name__)
app.secret_key = "aidaux-suivi-secret-2026"
db.init_db()
# Identifiants de connexion
APP_USERNAME = "aidaux"
APP_PASSWORD = "AidAux2931&&"

@app.before_request
def check_login():
    if request.endpoint in ("login", "static"):
        return
    if not session.get("logged_in"):
        return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form["username"] == APP_USERNAME and request.form["password"] == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("page_accueil"))
        error = "Identifiants incorrects"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Libellés et couleurs des types de problèmes (partagés)
PROBLEM_TYPES = ["Manquée", "Badgeage partiel", "Trop courte", "Trop longue"]


def fmt_date_fr(iso):
    """'2026-05-04 09:00' → '04/05/2026 09:00'."""
    if not iso:
        return ""
    try:
        d, h = iso.split(" ")
        y, m, j = d.split("-")
        return f"{j}/{m}/{y} {h}"
    except Exception:
        return iso


def fmt_diff(val):
    if val is None:
        return ""
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.0f} min"


# ─────────────────────────────────────────────────────────
# PAGES (rendu serveur)
# ─────────────────────────────────────────────────────────

@app.route("/")
def page_accueil():
    return render_template("accueil.html", page="accueil")


@app.route("/import")
def page_import():
    return render_template("import.html", page="import")


@app.route("/interventions")
def page_interventions():
    return render_template("interventions.html", page="interventions")


@app.route("/intervenants")
def page_intervenants():
    return render_template("intervenants.html", page="intervenants")


@app.route("/mensuel")
def page_mensuel():
    return render_template("mensuel.html", page="mensuel")


@app.route("/rapports")
def page_rapports():
    return render_template("rapports.html", page="rapports")


# ─────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    files = request.files.getlist("file")
    results = []

    for f in files:
        if not f.filename.lower().endswith(".csv"):
            results.append({"filename": f.filename, "error": "Pas un fichier CSV"})
            continue

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        f.save(tmp.name)
        tmp.close()
        try:
            rows = parse_csv_to_rows(tmp.name)
            added, skipped, pmin, pmax = db.insert_interventions(rows, f.filename)
            results.append({
                "filename": f.filename,
                "added": added,
                "skipped": skipped,
                "period_min": fmt_date_fr(pmin),
                "period_max": fmt_date_fr(pmax),
            })
        except Exception as e:
            results.append({"filename": f.filename, "error": str(e)})
        finally:
            os.unlink(tmp.name)

    return jsonify({"results": results})


@app.route("/api/accueil")
def api_accueil():
    info = db.get_global_info()
    info["period_min"] = fmt_date_fr(info["period_min"])
    info["period_max"] = fmt_date_fr(info["period_max"])
    stats = db.get_stats()
    evolution = db.get_monthly_evolution()
    imports = db.get_imports_history()[:5]
    for imp in imports:
        imp["period_min"] = fmt_date_fr(imp["period_min"])
        imp["period_max"] = fmt_date_fr(imp["period_max"])
    return jsonify({
        "info": info,
        "stats": stats,
        "evolution": evolution,
        "imports": imports,
    })


@app.route("/api/stats")
def api_stats():
    intervenant = request.args.get("intervenant") or None
    mois = request.args.get("mois") or None
    date_debut = request.args.get("date_debut") or None
    date_fin = request.args.get("date_fin") or None

    stats = db.get_stats(intervenant, mois, date_debut, date_fin)
    total = stats["total"]

    def pct(n):
        return round(n / total * 100, 1) if total else 0

    return jsonify({
        "total": total,
        "manquees": {"count": stats["manquees"], "pct": pct(stats["manquees"])},
        "partiels": {"count": stats["partiels"], "pct": pct(stats["partiels"])},
        "courtes_longues": {
            "count": stats["courtes"] + stats["longues"],
            "pct": pct(stats["courtes"] + stats["longues"]),
        },
    })


@app.route("/api/interventions")
def api_interventions():
    intervenant = request.args.get("intervenant") or None
    type_probleme = request.args.get("type_probleme") or None
    mois = request.args.get("mois") or None
    date_debut = request.args.get("date_debut") or None
    date_fin = request.args.get("date_fin") or None
    page = int(request.args.get("page", 1))
    per_page = 25

    total = db.count_interventions(intervenant, type_probleme, mois,
                                   date_debut, date_fin, problems_only=True)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    rows = db.query_interventions(
        intervenant, type_probleme, mois, date_debut, date_fin,
        problems_only=True, limit=per_page, offset=(page - 1) * per_page
    )

    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "date_prevue": fmt_date_fr(r["date_prevue"]),
            "intervenant": r["intervenant"],
            "client": r["client"],
            "type_probleme": r["type_probleme"],
            "timing": r["timing"],
            "diff_minutes": fmt_diff(r["diff_minutes"]),
            "debut_reel": r["debut_reel"],
            "fin_reelle": r["fin_reelle"],
        })

    return jsonify({"rows": out, "total": total, "page": page, "total_pages": total_pages})


@app.route("/api/intervenants")
def api_intervenants():
    return jsonify(db.get_intervenants())


@app.route("/api/mois")
def api_mois():
    return jsonify(db.get_mois_list())


@app.route("/api/export")
def api_export():
    import csv
    intervenant = request.args.get("intervenant") or None
    type_probleme = request.args.get("type_probleme") or None
    mois = request.args.get("mois") or None
    date_debut = request.args.get("date_debut") or None
    date_fin = request.args.get("date_fin") or None

    rows = db.query_interventions(intervenant, type_probleme, mois,
                                  date_debut, date_fin, problems_only=True)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date prévue", "Intervenant", "Client", "Type de problème",
                "Timing Ximi", "Diff. (minutes)", "Début réel", "Fin réelle"])
    for r in rows:
        w.writerow([fmt_date_fr(r["date_prevue"]), r["intervenant"], r["client"],
                    r["type_probleme"], r["timing"], fmt_diff(r["diff_minutes"]),
                    r["debut_reel"], r["fin_reelle"]])

    return send_file(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        mimetype="text/csv", as_attachment=True,
        download_name="interventions_problemes.csv",
    )


@app.route("/api/reset", methods=["POST"])
def api_reset():
    db.clear_all()
    return jsonify({"ok": True})


@app.route("/api/imports")
def api_imports():
    imports = db.get_all_imports()
    for i in imports:
        i["period_min"] = fmt_date_fr(i["period_min"])
        i["period_max"] = fmt_date_fr(i["period_max"])
    return jsonify(imports)


@app.route("/api/delete_import", methods=["POST"])
def api_delete_import():
    import_id = request.json.get("id")
    n = db.delete_import(import_id)
    return jsonify({"deleted": n})


@app.route("/api/delete_intervention", methods=["POST"])
def api_delete_intervention():
    interv_id = request.json.get("id")
    n = db.delete_intervention(interv_id)
    return jsonify({"deleted": n})


# ── Rapports par intervenant ──

@app.route("/api/stats_intervenants")
def api_stats_intervenants():
    mois = request.args.get("mois") or None
    data = db.stats_par_intervenant(mois=mois)
    moyenne = round(sum(s["taux"] for s in data) / len(data), 1) if data else 0
    return jsonify({"intervenants": data, "moyenne_taux": moyenne})


@app.route("/api/detail_intervenant")
def api_detail_intervenant():
    nom = request.args.get("intervenant")
    if not nom:
        return jsonify({"error": "Intervenant manquant"}), 400
    return jsonify(db.detail_intervenant(nom))


# ── Suivi mensuel ──

@app.route("/api/mensuel")
def api_mensuel():
    return jsonify({
        "mois": db.stats_mensuelles_detaillees(),
        "top_clients": db.top_clients_problemes(limit=10),
    })


# ── Export PowerPoint ──

@app.route("/api/rapport_pptx")
def api_rapport_pptx():
    import reports
    sections = request.args.get("sections", "synthese,classements,intervenants,mensuel").split(",")
    sections = [s.strip() for s in sections if s.strip()]
    mois = request.args.get("mois") or None
    intervenants = request.args.getlist("intervenant") or None

    buf = reports.generer_rapport(sections, mois=mois, intervenants=intervenants)
    suffixe = f"_{mois}" if mois else ""
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        as_attachment=True,
        download_name=f"rapport_aidaux{suffixe}.pptx",
    )


if __name__ == "__main__":
    # HOST=0.0.0.0 → accessible depuis le réseau local (mode serveur partagé)
    # HOST non défini → 127.0.0.1 (local uniquement)
    host = os.environ.get("AIDAUX_HOST", "127.0.0.1")
    debug = host == "127.0.0.1"  # pas de mode debug en réseau
    app.run(debug=debug, host=host, port=5000)
