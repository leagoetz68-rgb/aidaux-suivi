# make_icon.py — Génère icon.ico depuis le logo SVG complet (texte + symbole)

import subprocess, sys, os, time

subprocess.run([sys.executable, "-m", "pip", "install", "Pillow", "-q"], check=False)
from PIL import Image

base      = os.path.dirname(os.path.abspath(__file__))
ico_path  = os.path.join(base, "static", "icon.ico")
preview   = os.path.join(base, "static", "icon_preview.png")
tmp_png   = os.path.join(base, "static", "icon_tmp.png")
html_path = os.path.join(base, "static", "_icon_render.html")

# Rendre le SVG complet à grande taille (largeur fixe, hauteur auto)
with open(html_path, "w", encoding="utf-8") as f:
    f.write("""<!DOCTYPE html>
<html><head><style>
  * { margin:0; padding:0; }
  body { background:white; }
  img { width:1000px; height:auto; display:block; }
</style></head>
<body><img src="logo.svg"></body></html>""")

candidates = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
browser = next((p for p in candidates if os.path.exists(p)), None)
if not browser:
    sys.exit("Edge ou Chrome introuvable.")

# Hauteur = 1000 * 267/374 ≈ 714
subprocess.run([
    browser, "--headless=new", "--disable-gpu", "--no-sandbox",
    f"--screenshot={tmp_png}", "--window-size=1000,720", "--hide-scrollbars",
    f"file:///{html_path.replace(chr(92), '/')}",
], capture_output=True, timeout=30)

time.sleep(1)
if not os.path.exists(tmp_png):
    sys.exit("Capture échouée.")

src = Image.open(tmp_png).convert("RGBA")
print(f"Capture brute : {src.size}")

# Rogner aux contours réels du logo (zone non blanche)
bbox = src.convert("RGB").getbbox()
print(f"Bbox contenu : {bbox}")
if bbox:
    src = src.crop(bbox)
print(f"Après rognage : {src.size}")

# Placer le logo entier (sans le déformer) au centre d'un carré blanc
w, h = src.size
side = max(w, h) + 40  # marge
canvas = Image.new("RGBA", (side, side), (255, 255, 255, 255))
canvas.paste(src, ((side - w) // 2, (side - h) // 2), src)

# Sauver un aperçu PNG pour vérification
canvas.save(preview)
print(f"Aperçu sauvé : {preview}")

# Générer l'ICO multi-tailles
sizes = [256, 128, 64, 48, 32, 16]
frames = [canvas.resize((s, s), Image.LANCZOS) for s in sizes]
frames[0].save(ico_path, format="ICO",
               sizes=[(s, s) for s in sizes],
               append_images=frames[1:])

for p in [tmp_png, html_path]:
    try: os.remove(p)
    except: pass

print(f"Icône créée : {ico_path}")
