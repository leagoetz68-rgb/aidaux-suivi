# notifications.py — Envoi du rappel hebdomadaire par email aux intervenants n'ayant pas badgé
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

        lignes = ", ".join(
            f"chez {it['client']} le {fmt_date_fr(it['date_prevue'])}" for it in items
        )
        corps = (
            f"Bonjour {intervenant},\n\n"
            f"Nous constatons une absence de badgeage concernant l'intervention "
            f"{lignes}.\n\n"
            f"Le badgeage à l'arrivée et au départ de chaque prestation est "
            f"obligatoire afin d'assurer le suivi du temps de travail, la "
            f"fiabilité de la paie ainsi que la traçabilité des interventions "
            f"auprès des bénéficiaires.\n\n"
            f"Merci de contacter l'agence dans les meilleurs délais afin de "
            f"régulariser cette situation.\n\n"
            f"Nous vous invitons par ailleurs à vérifier régulièrement votre "
            f"badgeage au cours de la journée, et à nous prévenir par SMS dès "
            f"qu'une anomalie est constatée (badgeage manquant à l'arrivée, au "
            f"départ, ou sur l'ensemble de l'intervention).\n\n"
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
