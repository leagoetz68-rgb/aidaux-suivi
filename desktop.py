# desktop.py — Lance Aid'aux suivi dans une vraie fenêtre d'application (pywebview)
#               Le serveur Flask tourne en arrière-plan et s'arrête à la fermeture.

import os
import re
import socket
import threading
import time

import webview

from app import app
import reports

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"

ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "icon.ico")


class Api:
    """Fonctions appelables depuis le JavaScript de la page (fenêtre native)."""

    def generer_rapport(self, sections, mois, intervenants):
        """Génère le PowerPoint et ouvre un dialogue 'Enregistrer sous'."""
        try:
            buf = reports.generer_rapport(
                sections,
                mois=mois or None,
                intervenants=intervenants or None,
            )
            data = buf.getvalue()

            # Nom de fichier proposé
            nom = "rapport_aidaux"
            if intervenants and len(intervenants) == 1:
                nom = "rapport_" + re.sub(r"[^A-Za-z0-9]+", "_", intervenants[0]).strip("_")
            if mois:
                nom += "_" + mois
            nom += ".pptx"

            win = webview.active_window()
            result = win.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=nom,
                file_types=("Présentation PowerPoint (*.pptx)", "Tous les fichiers (*.*)"),
            )
            if not result:
                return {"ok": False, "cancelled": True}
            chemin = result[0] if isinstance(result, (list, tuple)) else result
            with open(chemin, "wb") as f:
                f.write(data)
            return {"ok": True, "path": chemin}
        except Exception as e:
            return {"ok": False, "error": str(e)}


def port_occupe(host, port):
    """Teste si le port est déjà utilisé (une instance tourne peut-être déjà)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def run_flask():
    # use_reloader=False : indispensable hors du thread principal
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)


def attendre_serveur(timeout=15):
    fin = time.time() + timeout
    while time.time() < fin:
        if port_occupe(HOST, PORT):
            return True
        time.sleep(0.2)
    return False


if __name__ == "__main__":
    # Démarrer Flask seulement si aucune instance n'écoute déjà
    if not port_occupe(HOST, PORT):
        threading.Thread(target=run_flask, daemon=True).start()
        attendre_serveur()

    # Fenêtre native (avec le pont JavaScript ↔ Python pour la sauvegarde)
    webview.create_window(
        "Aid'aux suivi",
        URL,
        width=1400,
        height=900,
        min_size=(1000, 650),
        js_api=Api(),
    )
    # Le paramètre icon n'existe pas sur toutes les versions/plateformes
    try:
        webview.start(icon=ICON)
    except TypeError:
        webview.start()
