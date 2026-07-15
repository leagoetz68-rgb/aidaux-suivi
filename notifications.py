# notifications.py — Envoi du rappel hebdomadaire par email aux intervenants n'ayant pas badgé

import os
from collections import defaultdict
from datetime import datetime, timedelta

import requests

import database as db

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
EXPEDITEUR_EMAIL = os.environ.get("EXPEDITEUR_EMAIL", "lea.goetz@aidaux.fr")
EXPEDITEUR_NOM = os.environ.get("EXPEDITEUR_NOM", "Aid'Aux")
APP_URL = os.environ.get("APP_URL", "https://aidaux-suivi.onrender.com")

INTERVALLE_HEBDO_JOURS = 7


def fmt_date_fr(iso):
    if not iso:
        return ""
    try:
        d, h = iso.split(" ")
        y, m, j = d.split("-")
        return f"{j}/{m}/{y} {h}"
    except Exception:
        return iso


def envoyer_mail(destinataire, sujet, corps):
    if not BREVO_API_KEY:
        raise RuntimeError("BREVO_API_KEY non configurée")

    reponse = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={
            "sender": {"name": EXPEDITEUR_NOM, "email": EXPEDITEUR_EMAIL},
            "to": [{"email": destinataire}],
            "subject": sujet,
            "textContent": corps,
        },
        timeout=10,
    )
    if reponse.status_code >= 300:
        raise RuntimeError(f"Brevo a refusé l'envoi ({reponse.status_code}) : {reponse.text}")


def envoyer_rappel_hebdomadaire(date_debut=None, date_fin=None):
    """
    Regroupe par intervenant toutes les interventions 'Manquée' jamais
    notifiées et envoie un seul email récapitulatif à chacun, en simple
    rappel (sans lien vers un questionnaire).
    Marque les interventions comme notifiées.

    date_debut / date_fin ('YYYY-MM-DD') limitent la relance à une période
    donnée (ex : aujourd'hui, cette semaine) au lieu de reprendre tout
    l'historique jamais notifié.

    Retourne la liste des envois effectués (ou en erreur).
    """
    manquees = db.get_unnotified_manquees(date_debut, date_fin)
    if not manquees:
        return []

    emails = db.get_intervenant_emails()
    par_intervenant = defaultdict(list)
    for m in manquees:
        par_intervenant[m["intervenant"]].append(m)

    resultats = []
    notifies_ids = []

    for intervenant, items in par_intervenant.items():
        email = emails.get(intervenant)
        if not email:
            resultats.append({"intervenant": intervenant, "error": "Aucun email enregistré"})
            continue

        ids = [it["id"] for it in items]

        lignes = "\n".join(
            f"- chez {it['client']}, le {fmt_date_fr(it['date_prevue'])}" for it in items
        )
        corps = (
            f"Bonjour {intervenant},\n\n"
            f"Nous constatons une absence de badgeage concernant les interventions "
            f"suivantes :\n\n"
            f"{lignes}\n\n"
            f"Nous vous rappelons que le badgeage à l'arrivée et au départ de chaque "
            f"prestation est obligatoire afin d'assurer le suivi du temps de travail, "
            f"la fiabilité de la paie ainsi que la traçabilité des interventions auprès "
            f"des bénéficiaires.\n\n"
            f"Nous vous remercions de bien vouloir vérifier votre badgeage et de "
            f"contacter l'agence dans les meilleurs délais afin de régulariser la "
            f"situation si nécessaire.\n\n"
            f"Nous comptons sur votre vigilance lors de vos prochaines interventions.\n\n"
            f"Cordialement,\n"
            f"La Direction\n"
        )
        try:
            envoyer_mail(email, "Absence de badgeage", corps)
            resultats.append({"intervenant": intervenant, "email": email, "nb": len(items)})
            notifies_ids.extend(ids)
        except Exception as e:
            resultats.append({"intervenant": intervenant, "error": str(e)})

    db.marquer_rappel_envoye(notifies_ids)
    return resultats


def verifier_et_envoyer_rappel_hebdomadaire():
    """
    Déclenche l'envoi du rappel hebdomadaire si au moins
    INTERVALLE_HEBDO_JOURS jours se sont écoulés depuis le dernier envoi
    (ou si aucun envoi n'a jamais eu lieu). Ne couvre que les interventions
    manquées des 7 derniers jours, pas tout l'historique jamais notifié.
    Conçu pour être appelé à chaque requête ou via un cron : le coût est
    négligeable si la date n'est pas atteinte.
    """
    dernier = db.get_meta("dernier_envoi_hebdo")
    maintenant = datetime.now()
    if dernier:
        try:
            dernier_dt = datetime.strptime(dernier, "%Y-%m-%d %H:%M:%S")
            if maintenant - dernier_dt < timedelta(days=INTERVALLE_HEBDO_JOURS):
                return None
        except Exception:
            pass

    date_debut = (maintenant - timedelta(days=INTERVALLE_HEBDO_JOURS)).strftime("%Y-%m-%d")
    date_fin = maintenant.strftime("%Y-%m-%d")
    db.set_meta("dernier_envoi_hebdo", maintenant.strftime("%Y-%m-%d %H:%M:%S"))
    return envoyer_rappel_hebdomadaire(date_debut, date_fin)
