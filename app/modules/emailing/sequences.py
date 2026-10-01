"""Séquences d'emails de cycle de vie.

Chaque séquence est déclarative : une requête d'éligibilité, un objet, un corps.
Le moteur (`executer`) ne connaît que ce contrat, si bien qu'ajouter une
séquence n'oblige jamais à toucher à la logique d'envoi.

Deux garde-fous structurent tout le fichier :

* **Fenêtres bornées des DEUX côtés.** Une séquence « J+2 » ne dit pas « compte
  de plus de 2 jours » mais « compte créé il y a entre 2 et 3 jours ». Une
  fenêtre ouverte aurait, au premier déploiement, arrosé d'un coup tous les
  comptes existants, y compris ceux que Miradie relance à la main.
* **Idempotence par (email, campagne).** Le journal `email_sends` fait foi :
  une personne ne reçoit jamais deux fois la même étape, quel que soit le
  nombre de passages du worker.
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.emailing.envoi import deja_envoye, envoyer, supprime

logger = logging.getLogger("axial.emailing.sequences")

APP = "app.axial-ia.fr"


@dataclass
class Destinataire:
    email: str
    langue: str
    ctx: dict


@dataclass
class Sequence:
    cle: str
    description: str
    requete: str
    sujet: Callable[[str, dict], str]
    corps: Callable[[str, dict], str]


def _fr(langue: str) -> bool:
    return (langue or "fr").lower().startswith("fr")


def _prenom(ctx: dict) -> str:
    """Le prénom si on le connaît, sinon rien — jamais « Bonjour {prenom} » vide."""
    nom = (ctx.get("company_name") or "").strip()
    return nom


def _jour(d: dt.datetime | None, langue: str) -> str:
    if not d:
        return ""
    mois_fr = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
               "août", "septembre", "octobre", "novembre", "décembre"]
    if _fr(langue):
        return f"{d.day} {mois_fr[d.month - 1]}"
    return d.strftime("%-d %B")


# ---------------------------------------------------------------- 1. essai J-3

SQL_ESSAI_J3 = """
SELECT u.email, cp.language, cp.company_name, s.current_period_end, s.plan_key
FROM auth.users u
JOIN user_subscriptions s ON s.user_id = u.id
LEFT JOIN company_profiles cp ON cp.user_id = u.id
WHERE s.status = 'trialing'
  AND s.cancel_at_period_end = false
  AND s.current_period_end BETWEEN now() + interval '2 days'
                               AND now() + interval '3 days'
"""


def _prix(plan_key: str | None) -> str:
    from app.modules.billing.catalog import PLANS
    for p in PLANS:
        if p["key"] == plan_key and p.get("price_eur") is not None:
            return f"{p['price_eur']} €"
    return ""


def sujet_essai(langue, ctx):
    return ("Ton essai Axial se termine dans 3 jours" if _fr(langue)
            else "Your Axial trial ends in 3 days")


def corps_essai(langue, ctx):
    jour = _jour(ctx.get("current_period_end"), langue)
    prix = _prix(ctx.get("plan_key"))
    if _fr(langue):
        return (
            "Hello,\n\n"
            "Petit point avant que ton essai Axial ne se termine : le premier "
            f"prélèvement de {prix} est prévu le {jour}.\n\n"
            "Si Axial t'est utile, tu n'as rien à faire, ton accès et tes "
            "crédits mensuels continuent.\n\n"
            "Si tu préfères t'arrêter, c'est en deux clics dans Paramètres → "
            f"Facturation → Gérer, sur {APP}. Aucun prélèvement ne partira.\n\n"
            "Et si tu n'as pas encore eu le temps de creuser une vraie question, "
            "dis-le-moi : je préfère décaler ton essai plutôt que te facturer "
            "quelque chose que tu n'as pas pu tester.\n\n"
            "Miradie B"
        )
    return (
        "Hello,\n\n"
        "A quick note before your Axial trial ends: the first charge of "
        f"{prix} is scheduled for {jour}.\n\n"
        "If Axial is useful to you, there is nothing to do, your access and "
        "monthly credits simply continue.\n\n"
        f"If you would rather stop, it takes two clicks on {APP}, under "
        "Settings → Billing → Manage. Nothing will be charged.\n\n"
        "And if you have not had time to dig into a real question yet, just "
        "tell me: I would rather extend your trial than bill you for something "
        "you could not test.\n\n"
        "Miradie B"
    )


# ---------------------------------------------------------------- 2. bienvenue

SQL_BIENVENUE = """
SELECT u.email, cp.language, cp.company_name
FROM auth.users u
LEFT JOIN company_profiles cp ON cp.user_id = u.id
WHERE u.created_at > now() - interval '2 hours'
"""


def sujet_bienvenue(langue, ctx):
    return ("Bienvenue sur Axial : par où commencer" if _fr(langue)
            else "Welcome to Axial: where to start")


def corps_bienvenue(langue, ctx):
    if _fr(langue):
        return (
            "Hello,\n\n"
            "Ton compte Axial est ouvert. Deux minutes pour que la première "
            "réponse vaille quelque chose :\n\n"
            "Renseigne ta mémoire d'entreprise (onglet Mémoire), secteur, "
            "stade, concurrents connus, défi principal. Axial injecte ce "
            "contexte dans chaque analyse : sans lui, tu obtiens une réponse "
            "générique ; avec lui, une réponse sur TON marché.\n\n"
            "Puis pose une vraie question, celle qui traîne depuis des "
            "semaines. Pas « c'est quoi le marché du SaaS RH », mais « mes 5 "
            "concurrents directs en France et leur positionnement respectif ».\n\n"
            f"C'est ici : {APP}\n\n"
            "Si quelque chose coince, réponds à ce message, il arrive "
            "directement chez moi.\n\n"
            "Miradie B"
        )
    return (
        "Hello,\n\n"
        "Your Axial account is open. Two minutes to make the first answer "
        "worth something:\n\n"
        "Fill in your company memory (Memory tab), sector, stage, known "
        "competitors, main challenge. Axial injects that context into every "
        "analysis: without it you get a generic answer; with it, an answer "
        "about YOUR market.\n\n"
        "Then ask a real question, the one that has been nagging for weeks. "
        "Not \"what is the HR SaaS market\", but \"my 5 direct competitors in "
        "France and their respective positioning\".\n\n"
        f"It starts here: {APP}\n\n"
        "If anything gets in the way, just reply to this message, it comes "
        "straight to me.\n\n"
        "Miradie B"
    )


# -------------------------------------------------------- 3. profil incomplet

SQL_PROFIL_INCOMPLET = """
SELECT u.email, cp.language, cp.company_name
FROM auth.users u
LEFT JOIN company_profiles cp ON cp.user_id = u.id
WHERE u.created_at BETWEEN now() - interval '3 days' AND now() - interval '2 days'
  AND (cp.user_id IS NULL OR cp.company_name IS NULL OR cp.sector IS NULL)
"""


def sujet_profil(langue, ctx):
    return ("Il manque 2 minutes pour qu'Axial serve à quelque chose" if _fr(langue)
            else "Two minutes short of Axial being useful")


def corps_profil(langue, ctx):
    if _fr(langue):
        return (
            "Hello,\n\n"
            "Tu as créé ton compte Axial il y a deux jours mais la mémoire "
            "d'entreprise est restée vide, et c'est précisément elle qui fait "
            "la différence entre une réponse d'IA générique et une analyse sur "
            "ton marché.\n\n"
            "Quatre champs suffisent pour commencer : secteur, stade, "
            "concurrents connus, défi principal. Deux minutes, une seule fois.\n\n"
            f"C'est dans l'onglet Mémoire : {APP}\n\n"
            "Si tu as ouvert l'app et que quelque chose t'a arrêté, un écran "
            "confus, une question sans réponse, dis-le-moi franchement en "
            "répondant à ce message. C'est exactement ce que j'ai besoin de "
            "savoir en ce moment.\n\n"
            "Miradie B"
        )
    return (
        "Hello,\n\n"
        "You created your Axial account two days ago, but the company memory "
        "is still empty, and that is exactly what separates a generic AI "
        "answer from an analysis about your market.\n\n"
        "Four fields are enough to start: sector, stage, known competitors, "
        "main challenge. Two minutes, once.\n\n"
        f"It is in the Memory tab: {APP}\n\n"
        "And if you opened the app and something stopped you, a confusing "
        "screen, a question left unanswered, tell me plainly by replying to "
        "this message. That is exactly what I need to know right now.\n\n"
        "Miradie B"
    )


# --------------------------------------------------------- 4. aucune question

SQL_AUCUNE_QUESTION = """
SELECT u.email, cp.language, cp.company_name
FROM auth.users u
JOIN company_profiles cp ON cp.user_id = u.id
WHERE u.created_at BETWEEN now() - interval '4 days' AND now() - interval '3 days'
  AND cp.company_name IS NOT NULL
  AND NOT EXISTS (
        SELECT 1 FROM conversations c
        JOIN messages m ON m.conversation_id = c.id AND m.role = 'user'
        WHERE c.user_id = u.id)
  AND NOT EXISTS (SELECT 1 FROM reports r WHERE r.user_id = u.id)
"""


def sujet_question(langue, ctx):
    return ("Une question pour démarrer ?" if _fr(langue)
            else "One question to get started?")


def corps_question(langue, ctx):
    nom = _prenom(ctx)
    cible = nom or ("ta boîte" if _fr(langue) else "your company")
    if _fr(langue):
        return (
            "Hello,\n\n"
            "Tu as tout configuré sur Axial, profil, contexte, mais tu n'as "
            "encore posé aucune question. C'est souvent l'étape la plus dure : "
            "savoir par quoi commencer.\n\n"
            "Trois questions qui donnent un résultat exploitable dès le "
            "premier essai :\n\n"
            f"Qui sont les 5 concurrents directs de {cible} et comment se "
            "différencient-ils ?\n\n"
            "Quels leviers GTM prioriser dans les 6 prochains mois, et "
            "pourquoi ceux-là ?\n\n"
            "Quels risques réglementaires vont me tomber dessus dans les 18 "
            "mois ?\n\n"
            f"Copie-colle celle qui te parle : {APP}\n\n"
            "Et si aucune ne correspond, réponds-moi avec ta vraie question, "
            "je te dis honnêtement si Axial est le bon outil pour elle.\n\n"
            "Miradie B"
        )
    return (
        "Hello,\n\n"
        "You set everything up on Axial, profile, context, but you have not "
        "asked a question yet. That is often the hardest step: knowing where "
        "to start.\n\n"
        "Three questions that give you something usable on the first try:\n\n"
        f"Who are {cible}'s 5 direct competitors, and how do they "
        "differentiate?\n\n"
        "Which go-to-market levers should I prioritise over the next 6 months, "
        "and why those?\n\n"
        "Which regulatory changes will hit me in the next 18 months?\n\n"
        f"Copy whichever speaks to you: {APP}\n\n"
        "And if none of them fits, reply with your real question, I will tell "
        "you honestly whether Axial is the right tool for it.\n\n"
        "Miradie B"
    )


# ------------------------------------------------------------ 5. crédits bas

SQL_CREDITS_BAS = """
SELECT u.email, cp.language, cp.company_name,
       (b.trial_credits + b.free_credits + b.purchased_credits) AS solde
FROM auth.users u
JOIN credit_balances b ON b.user_id = u.id
LEFT JOIN company_profiles cp ON cp.user_id = u.id
WHERE (b.trial_credits + b.free_credits + b.purchased_credits) BETWEEN 1 AND 15
  AND EXISTS (SELECT 1 FROM reports r WHERE r.user_id = u.id)
"""


def sujet_credits(langue, ctx):
    return ("Il te reste peu de crédits Axial" if _fr(langue)
            else "You are running low on Axial credits")


def corps_credits(langue, ctx):
    solde = ctx.get("solde", 0)
    if _fr(langue):
        return (
            "Hello,\n\n"
            f"Il te reste {solde} crédits sur Axial, de quoi tenir une "
            "conversation, pas un rapport complet (un rapport en consomme 40).\n\n"
            "Deux options, sans urgence : une recharge ponctuelle à partir de "
            "20 €, ou un abonnement mensuel qui recrédite automatiquement.\n\n"
            f"Tout est dans l'onglet Crédits : {APP}\n\n"
            "Si tu hésites sur le format qui correspond à ton usage, réponds à "
            "ce message, je te réponds moi-même.\n\n"
            "Miradie B"
        )
    return (
        "Hello,\n\n"
        f"You have {solde} credits left on Axial, enough for a conversation, "
        "not a full report (a report costs 40).\n\n"
        "Two options, no rush: a one-off top-up from €20, or a monthly plan "
        "that re-credits automatically.\n\n"
        f"It is all in the Credits tab: {APP}\n\n"
        "If you are unsure which format fits your usage, reply to this message "
        "and I will answer you myself.\n\n"
        "Miradie B"
    )


# ------------------------------------------------ 6. relances d'inactivité
#
# Trois relances à 7 jours, 14 jours et 1 mois sans activité (décision Miradie,
# 30/09). « Activité » = dernier message, dernier rapport, ou à défaut la
# création du compte : un compte ouvert puis laissé en l'état est inactif lui
# aussi. Fenêtres d'un jour, bornées des deux côtés comme partout ailleurs.
#
# Deux sorties de l'échelle, en plus de la désinscription (vérifiée par le
# moteur avant chaque envoi) : revenir dans l'app, qui repousse la date de
# dernière activité hors des fenêtres ; ou avoir reçu une relance manuelle
# (campagne `relance_*`) dans les 7 derniers jours, pour ne pas doubler un
# message écrit à la main.

_SQL_INACTIF = """
WITH activite AS (
    SELECT u.id, u.email,
           GREATEST(u.created_at,
                    (SELECT max(c.last_message_at) FROM conversations c WHERE c.user_id = u.id),
                    (SELECT max(r.created_at) FROM reports r WHERE r.user_id = u.id)) AS derniere
    FROM auth.users u
)
SELECT a.email, cp.language, cp.company_name,
       COALESCE(b.trial_credits + b.free_credits + b.purchased_credits, 0) AS solde
FROM activite a
LEFT JOIN company_profiles cp ON cp.user_id = a.id
LEFT JOIN credit_balances b ON b.user_id = a.id
WHERE a.derniere BETWEEN now() - interval '{fin} days' AND now() - interval '{debut} days'
  AND NOT EXISTS (SELECT 1 FROM email_sends e
                  WHERE e.email = lower(a.email)
                    AND e.campaign LIKE 'relance\\_%'
                    AND e.sent_at > now() - interval '7 days')
"""

SQL_INACTIF_J7 = _SQL_INACTIF.format(debut=7, fin=8)
SQL_REACTIVATION = _SQL_INACTIF.format(debut=14, fin=15)
SQL_INACTIF_J30 = _SQL_INACTIF.format(debut=30, fin=31)

# Ce qui a changé récemment dans l'app, repris tel quel dans la relance à 7
# jours. À tenir à jour à chaque livraison visible par les utilisateurs : un
# email automatique qui annonce des « nouveautés » vieilles de deux mois se
# voit tout de suite.
NOUVEAUTES_FR = [
    "La cartographie des investisseurs se règle maintenant sur ta levée : "
    "nombre d'investisseurs souhaité, montant recherché et stade, pour une "
    "liste mieux ciblée.",
    "Les agents de veille affichent leurs sources, des flux RSS vérifiés, et "
    "surveillent ton marché et tes concurrents en continu.",
]
NOUVEAUTES_EN = [
    "Investor mapping now adapts to your round: number of investors wanted, "
    "amount raised and stage, for a better-targeted list.",
    "Monitoring agents now show their sources, verified RSS feeds, and keep "
    "an eye on your market and competitors continuously.",
]


def sujet_inactif_j7(langue, ctx):
    return ("Du nouveau sur Axial depuis ta dernière visite" if _fr(langue)
            else "What's new on Axial since your last visit")


def corps_inactif_j7(langue, ctx):
    solde = ctx.get("solde", 0)
    if _fr(langue):
        return (
            "Hello,\n\n"
            "Depuis ton dernier passage sur Axial, plusieurs nouveautés sont "
            "arrivées :\n\n"
            + "\n\n".join(NOUVEAUTES_FR) + "\n\n"
            "Et toujours : une étude de marché ou une étude personnalisée sur la "
            "question de ton choix, avec les sources citées et un export PDF.\n\n"
            f"Il te reste {solde} crédits pour les essayer : {APP}\n\n"
            "Si tu as une question, je suis disponible pour qu'on fasse un point.\n\n"
            "Miradie B"
        )
    return (
        "Hello,\n\n"
        "Since your last visit to Axial, a few things have landed:\n\n"
        + "\n\n".join(NOUVEAUTES_EN) + "\n\n"
        "And as always: a market study or a custom study on the question of "
        "your choice, with cited sources and a PDF export.\n\n"
        f"You have {solde} credits left to try them: {APP}\n\n"
        "If you have any question, I am happy to set up a quick call.\n\n"
        "Miradie B"
    )


def sujet_reactivation(langue, ctx):
    return ("Deux semaines sans Axial : tout va bien ?" if _fr(langue)
            else "Two weeks without Axial: everything all right?")


def corps_reactivation(langue, ctx):
    if _fr(langue):
        return (
            "Hello,\n\n"
            "Ça fait deux semaines que tu n'es pas passé sur Axial, et "
            "j'aimerais comprendre pourquoi.\n\n"
            "Une réponse qui t'a déçu ? Un besoin qui n'était pas là ? Trop de "
            "temps pour obtenir le rapport ? Un mot en réponse à ce message "
            "m'aide beaucoup : Axial est jeune, et ces retours orientent "
            "directement les prochaines améliorations.\n\n"
            "Et si la semaine a simplement été chargée, tes crédits "
            f"t'attendent : {APP}\n\n"
            "Miradie B"
        )
    return (
        "Hello,\n\n"
        "It has been two weeks since you last used Axial, and I would like to "
        "understand why.\n\n"
        "An answer that disappointed you? A need that was not really there? "
        "Reports taking too long? One line in reply helps a lot: Axial is "
        "young, and this feedback directly shapes the next improvements.\n\n"
        f"And if the week was simply busy, your credits are waiting: {APP}\n\n"
        "Miradie B"
    )


def sujet_inactif_j30(langue, ctx):
    return ("Un mois sans Axial : on en parle ?" if _fr(langue)
            else "A month without Axial: shall we talk?")


def corps_inactif_j30(langue, ctx):
    solde = ctx.get("solde", 0)
    if _fr(langue):
        return (
            "Hello,\n\n"
            "Ça fait un mois que tu n'es pas repassé sur Axial. Plutôt qu'un "
            "email de plus, je te propose un échange de 20 minutes pour avoir "
            "ton retour et voir si Axial peut t'aider sur ton projet actuel.\n\n"
            "Je suis disponible le lundi après-midi, le mardi matin ou le "
            "vendredi matin : réponds-moi avec le jour et l'heure qui te "
            "conviennent, je t'envoie l'invitation.\n\n"
            f"Tes {solde} crédits restent disponibles sur {APP}\n\n"
            "Miradie B"
        )
    return (
        "Hello,\n\n"
        "It has been a month since you last used Axial. Rather than one more "
        "email, I would like to offer you a 20-minute call to hear your "
        "feedback and see whether Axial can help with your current project.\n\n"
        "I am available on Monday afternoons, Tuesday mornings and Friday "
        "mornings: reply with the day and time that suit you and I will send "
        "an invite.\n\n"
        f"Your {solde} credits are still available on {APP}\n\n"
        "Miradie B"
    )


# Version en production jusqu'à la validation des relances 7 / 14 / 30 j :
# servie tant que RELANCES_INACTIVITE_V2 est à false dans Doppler. À
# supprimer une fois la v2 allumée et validée.

SQL_REACTIVATION_V1 = """
SELECT u.email, cp.language, cp.company_name
FROM auth.users u
LEFT JOIN company_profiles cp ON cp.user_id = u.id
WHERE EXISTS (SELECT 1 FROM reports r WHERE r.user_id = u.id)
  AND COALESCE((SELECT max(c.last_message_at) FROM conversations c WHERE c.user_id = u.id),
               (SELECT max(r.created_at) FROM reports r WHERE r.user_id = u.id))
      BETWEEN now() - interval '15 days' AND now() - interval '14 days'
"""


def sujet_reactivation_v1(langue, ctx):
    return ("Deux semaines sans Axial : tout va bien ?" if _fr(langue)
            else "Two weeks without Axial: everything all right?")


def corps_reactivation_v1(langue, ctx):
    if _fr(langue):
        return (
            "Hello,\n\n"
            "Ça fait deux semaines que tu n'es pas passé sur Axial. Je ne "
            "t'écris pas pour te relancer mécaniquement : j'aimerais surtout "
            "savoir pourquoi.\n\n"
            "Une réponse qui t'a déçu ? Un besoin qui n'était pas là ? Trop de "
            "temps pour obtenir le rapport ? Un mot en réponse à ce message "
            "m'aide plus que tu ne l'imagines, Axial est jeune, et c'est "
            "exactement là-dessus que je le corrige.\n\n"
            "Et si c'est juste que la semaine a été chargée, tes crédits "
            f"t'attendent : {APP}\n\n"
            "Miradie B"
        )
    return (
        "Hello,\n\n"
        "It has been two weeks since you last used Axial. I am not writing to "
        "nudge you mechanically, mostly I would like to know why.\n\n"
        "An answer that disappointed you? A need that was not really there? "
        "Reports taking too long? One line in reply helps me more than you "
        "would think, Axial is young, and this is exactly what I fix it on.\n\n"
        f"And if the week was simply busy, your credits are waiting: {APP}\n\n"
        "Miradie B"
    )


def _sequences() -> list[Sequence]:
    from app.config import get_settings

    socle = [
        Sequence("cycle_bienvenue", "À l'ouverture du compte (dans l'heure)",
                 SQL_BIENVENUE, sujet_bienvenue, corps_bienvenue),
        Sequence("cycle_profil_incomplet", "J+2 sans mémoire d'entreprise remplie",
                 SQL_PROFIL_INCOMPLET, sujet_profil, corps_profil),
        Sequence("cycle_aucune_question", "J+3 : profil rempli, aucune question posée",
                 SQL_AUCUNE_QUESTION, sujet_question, corps_question),
        Sequence("cycle_essai_j3", "J-3 avant la fin de l'essai payant",
                 SQL_ESSAI_J3, sujet_essai, corps_essai),
        Sequence("cycle_credits_bas", "Solde entre 1 et 15 crédits après un rapport",
                 SQL_CREDITS_BAS, sujet_credits, corps_credits),
    ]
    if not get_settings().relances_inactivite_v2:
        return socle + [
            Sequence("cycle_reactivation", "14 jours sans activité après un premier rapport",
                     SQL_REACTIVATION_V1, sujet_reactivation_v1, corps_reactivation_v1),
        ]
    return socle + [
        Sequence("cycle_inactif_j7", "7 jours sans activité",
                 SQL_INACTIF_J7, sujet_inactif_j7, corps_inactif_j7),
        # Clé historique conservée : elle porte les envois déjà faits à 14 jours.
        Sequence("cycle_reactivation", "14 jours sans activité",
                 SQL_REACTIVATION, sujet_reactivation, corps_reactivation),
        Sequence("cycle_inactif_j30", "1 mois sans activité",
                 SQL_INACTIF_J30, sujet_inactif_j30, corps_inactif_j30),
    ]


# Lu au démarrage du processus : basculer RELANCES_INACTIVITE_V2 dans Doppler
# demande un redémarrage du worker.
SEQUENCES: list[Sequence] = _sequences()


def eligibles(db: Session, seq: Sequence) -> list[Destinataire]:
    rows = db.execute(text(seq.requete)).mappings().all()
    sortie = []
    for r in rows:
        email = (r.get("email") or "").lower().strip()
        if not email:
            continue
        sortie.append(Destinataire(email=email,
                                   langue=(r.get("language") or "fr"),
                                   ctx=dict(r)))
    return sortie


def executer(db: Session, simulation: bool = True,
             seulement: str | None = None) -> list[dict]:
    """Passe toutes les séquences. Retourne un journal exploitable en CLI."""
    journal = []
    for seq in SEQUENCES:
        if seulement and seq.cle != seulement:
            continue
        try:
            cibles = eligibles(db, seq)
        except Exception as e:  # noqa: BLE001 — une séquence cassée n'arrête pas les autres
            logger.warning("Séquence %s : requête en échec : %s", seq.cle, e)
            journal.append({"sequence": seq.cle, "erreur": str(e)[:200]})
            continue
        for d in cibles:
            if supprime(db, d.email) or deja_envoye(db, d.email, seq.cle):
                continue
            sujet = seq.sujet(d.langue, d.ctx)
            texte = seq.corps(d.langue, d.ctx)
            ok, info = envoyer(db, d.email, seq.cle, sujet, texte,
                               langue=d.langue, simulation=simulation)
            journal.append({"sequence": seq.cle, "email": d.email,
                            "langue": d.langue, "sujet": sujet,
                            "envoye": ok, "info": info})
            if ok:
                logger.info("Séquence %s envoyée à %s", seq.cle, d.email)
    return journal
