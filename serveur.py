# serveur.py — Lance Aid'aux suivi en mode SERVEUR RÉSEAU (accès depuis les autres PC)
#               À utiliser sur le PC du bureau qui sert de serveur.

import socket
import sys

from waitress import serve

from app import app

PORT = 5000


def afficher(texte):
    """Affiche un texte sans jamais planter (console absente en mode pythonw)."""
    if sys.stdout is None:
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        print(texte)
    except Exception:
        pass


def ip_locale():
    """Adresse IP de ce PC sur le réseau local."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # ne se connecte pas vraiment, sert à trouver l'IP
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    ip = ip_locale()
    afficher(
        "=" * 60 + "\n"
        "   AID'AUX SUIVI — SERVEUR RÉSEAU DÉMARRÉ\n"
        + "=" * 60 + "\n\n"
        "   Sur CE PC          :  http://localhost:5000\n"
        f"   Pour les COLLÈGUES :  http://{ip}:5000\n\n"
        "   → Donnez cette 2e adresse aux collègues (même réseau).\n"
        "   → Laissez cette fenêtre OUVERTE tant qu'ils utilisent l'app.\n"
        "   → Fermez cette fenêtre pour arrêter le serveur.\n\n"
        + "=" * 60
    )
    serve(app, host="0.0.0.0", port=PORT, threads=8)
