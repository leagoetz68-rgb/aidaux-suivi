# creer_raccourci_collegues.py — Génère un raccourci internet (.url) à distribuer
#   aux collègues. Il ouvre l'adresse du serveur dans leur navigateur par défaut.

import os
import shutil
import socket
import sys

# Sortie console en UTF-8 (évite les erreurs sur les accents / flèches)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))


def ip_locale():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    ip = ip_locale()
    url = f"http://{ip}:5000"

    out_dir = os.path.join(BASE, "Raccourci a distribuer aux collegues")
    os.makedirs(out_dir, exist_ok=True)

    # Copier l'icône à côté du raccourci
    icon_src = os.path.join(BASE, "static", "icon.ico")
    if os.path.exists(icon_src):
        shutil.copy(icon_src, os.path.join(out_dir, "icon.ico"))

    # Fichier .url (raccourci internet standard Windows)
    contenu = (
        "[InternetShortcut]\n"
        f"URL={url}\n"
        "IconFile=icon.ico\n"
        "IconIndex=0\n"
    )
    chemin = os.path.join(out_dir, "Aid'aux suivi.url")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)

    print("=" * 60)
    print("   RACCOURCI COLLÈGUES CRÉÉ")
    print("=" * 60)
    print()
    print(f"   Adresse du serveur : {url}")
    print()
    print("   Fichier créé dans le dossier :")
    print(f"     {out_dir}")
    print()
    print("   → Envoyez le fichier « Aid'aux suivi.url » aux collègues")
    print("     (e-mail, clé USB, dossier partagé).")
    print("   → Ils le déposent sur leur Bureau et double-cliquent dessus.")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
