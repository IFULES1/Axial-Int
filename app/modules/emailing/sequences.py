"""Séquences d'emails de cycle de vie.

Chaque séquence est déclarative : une requête d'éligibilité, un objet, un corps.
Le moteur (`executer`) ne connaît que ce contrat, si bien qu'ajouter une
séquence n'oblige jamais à toucher à la logique d'envoi.

Deux garde-fous structurent tout le fichier :

* **Fenêtres bornées des DEUX côtés.** Une séquence « J+2 » ne dit pas « compte
  de plus de 2 jours » mais « compte créé il y a entre 2 et 3 jours ». Une
  fenêtre ouverte aurait, au premier déploiement, arrosé d'un coup tous les
  comptes existants — y compris ceux que Miradie relance à la main.
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
        return "—"
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
    return "—"


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
            "Si Axial t'est utile, tu n'as rien à faire — ton accès et tes "
            "crédits mensuels continuent.\n\n"
            "Si tu préfères t'arrêter, c'est en deux clics dans Paramètres → "
            f"Facturation → Gérer, sur {APP}. Aucun prélèvement ne partira.\n\n"
            "Et si tu n'as pas encore eu le temps de creuser une vraie question, "
            "dis-le-moi : je préfère décaler ton essai plutôt que te facturer "
            "quelque chose que tu n'as pas pu tester.\n\n"
            "Miradie"
        )
    return (
        "Hello,\n\n"
        "A quick note before your Axial trial ends: the first charge of "
        f"{prix} is scheduled for {jour}.\n\n"
        "If Axial is useful to you, there is nothing to do — your access and "
        "monthly credits simply continue.\n\n"
        f"If you would rather stop, it takes two clicks on {APP}, under "
        "Settings → Billing → Manage. Nothing will be charged.\n\n"
        "And if you have not had time to dig into a real question yet, just "
        "tell me: I would rather extend your trial than bill you for something "
        "you could not test.\n\n"
        "Miradie"
    )


# ---------------------------------------------------------------- 2. bienvenue

SQL_BIENVENUE = """
SELECT u.email, cp.language, cp.company_name
FROM auth.users u
LEFT JOIN company_profiles cp ON cp.user_id = u.id
WHERE u.created_at > now() - interval '2 hours'
"""


def sujet_bienvenue(langue, ctx):
    return ("Bienvenue sur Axial — par où commencer" if _fr(langue)
            else "Welcome to Axial — where to start")


def corps_bienvenue(langue, ctx):
    if _fr(langue):
        return (
            "Hello,\n\n"
            "Ton compte Axial est ouvert. Deux minutes pour que la première "
            "réponse vaille quelque chose :\n\n"
            "Renseigne ta mémoire d'entreprise (onglet Mémoire) — secteur, "
            "stade, concurrents connus, défi principal. Axial injecte ce "
            "contexte dans chaque analyse : sans lui, tu obtiens une réponse "
            "générique ; avec lui, une réponse sur TON marché.\n\n"
            "Puis pose une vraie question, celle qui traîne depuis des "
            "semaines. Pas « c'est quoi le marché du SaaS RH », mais « mes 5 "
            "concurrents directs en France et leur positionnement respectif ».\n\n"
            f"C'est ici : {APP}\n\n"
            "Si quelque chose coince, réponds à ce message — il arrive "
            "directement chez moi.\n\n"
            "Miradie"
        )
    return (
        "Hello,\n\n"
        "Your Axial account is open. Two minutes to make the first answer "
        "worth something:\n\n"
        "Fill in your company memory (Memory tab) — sector, stage, known "
        "competitors, main challenge. Axial injects that context into every "
        "analysis: without it you get a generic answer; with it, an answer "
        "about YOUR market.\n\n"
        "Then ask a real question, the one that has been nagging for weeks. "
        "Not \"what is the HR SaaS market\", but \"my 5 direct competitors in "
        "France and their respective positioning\".\n\n"
        f"It starts here: {APP}\n\n"
        "If anything gets in the way, just reply to this message — it comes "
        "straight to me.\n\n"
        "Miradie"
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
            "d'entreprise est restée vide — et c'est précisément elle qui fait "
            "la différence entre une réponse d'IA générique et une analyse sur "
            "ton marché.\n\n"
            "Quatre champs suffisent pour commencer : secteur, stade, "
            "concurrents connus, défi principal. Deux minutes, une seule fois.\n\n"
            f"C'est dans l'onglet Mémoire : {APP}\n\n"
            "Si tu as ouvert l'app et que quelque chose t'a arrêté — un écran "
            "confus, une question sans réponse — dis-le-moi franchement en "
            "répondant à ce message. C'est exactement ce que j'ai besoin de "
            "savoir en ce moment.\n\n"
            "Miradie"
        )
    return (
        "Hello,\n\n"
        "You created your Axial account two days ago, but the company memory "
        "is still empty — and that is exactly what separates a generic AI "
        "answer from an analysis about your market.\n\n"
        "Four fields are enough to start: sector, stage, known competitors, "
        "main challenge. Two minutes, once.\n\n"
        f"It is in the Memory tab: {APP}\n\n"
        "And if you opened the app and something stopped you — a confusing "
        "screen, a question left unanswered — tell me plainly by replying to "
        "this message. That is exactly what I need to know right now.\n\n"
        "Miradie"
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
            "Tu as tout configuré sur Axial — profil, contexte — mais tu n'as "
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
            "Et si aucune ne correspond, réponds-moi avec ta vraie question — "
            "je te dis honnêtement si Axial est le bon outil pour elle.\n\n"
            "Miradie"
        )
    return (
        "Hello,\n\n"
        "You set everything up on Axial — profile, context — but you have not "
        "asked a question yet. That is often the hardest step: knowing where "
        "to start.\n\n"
        "Three questions that give you something usable on the first try:\n\n"
        f"Who are {cible}'s 5 direct competitors, and how do they "
        "differentiate?\n\n"
        "Which go-to-market levers should I prioritise over the next 6 months, "
        "and why those?\n\n"
        "Which regulatory changes will hit me in the next 18 months?\n\n"
        f"Copy whichever speaks to you: {APP}\n\n"
        "And if none of them fits, reply with your real question — I will tell "
        "you honestly whether Axial is the right tool for it.\n\n"
        "Miradie"
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
            f"Il te reste {solde} crédits sur Axial — de quoi tenir une "
            "conversation, pas un rapport complet (un rapport en consomme 40).\n\n"
            "Deux options, sans urgence : une recharge ponctuelle à partir de "
            "20 €, ou un abonnement mensuel qui recrédite automatiquement.\n\n"
            f"Tout est dans l'onglet Crédits : {APP}\n\n"
            "Si tu hésites sur le format qui correspond à ton usage, réponds à "
            "ce message, je te réponds moi-même.\n\n"
            "Miradie"
        )
    return (
        "Hello,\n\n"
        f"You have {solde} credits left on Axial — enough for a conversation, "
        "not a full report (a report costs 40).\n\n"
        "Two options, no rush: a one-off top-up from €20, or a monthly plan "
        "that re-credits automatically.\n\n"
        f"It is all in the Credits tab: {APP}\n\n"
        "If you are unsure which format fits your usage, reply to this message "
        "and I will answer you myself.\n\n"
        "Miradie"
    )


# ------------------------------------------------------------ 6. réactivation

SQL_REACTIVATION = """
SELECT u.email, cp.language, cp.company_name
FROM auth.users u
LEFT JOIN company_profiles cp ON cp.user_id = u.id
WHERE EXISTS (SELECT 1 FROM reports r WHERE r.user_id = u.id)
  AND COALESCE((SELECT max(c.last_message_at) FROM conversations c WHERE c.user_id = u.id),
               (SELECT max(r.created_at) FROM reports r WHERE r.user_id = u.id))
      BETWEEN now() - interval '15 days' AND now() - interval '14 days'
"""


def sujet_reactivation(langue, ctx):
    return ("Deux semaines sans Axial — tout va bien ?" if _fr(langue)
            else "Two weeks without Axial — everything all right?")


def corps_reactivation(langue, ctx):
    if _fr(langue):
        return (
            "Hello,\n\n"
            "Ça fait deux semaines que tu n'es pas passé sur Axial. Je ne "
            "t'écris pas pour te relancer mécaniquement : j'aimerais surtout "
            "savoir pourquoi.\n\n"
            "Une réponse qui t'a déçu ? Un besoin qui n'était pas là ? Trop de "
            "temps pour obtenir le rapport ? Un mot en réponse à ce message "
            "m'aide plus que tu ne l'imagines — Axial est jeune, et c'est "
            "exactement là-dessus que je le corrige.\n\n"
            "Et si c'est juste que la semaine a été chargée, tes crédits "
            f"t'attendent : {APP}\n\n"
            "Miradie"
        )
    return (
        "Hello,\n\n"
        "It has been two weeks since you last used Axial. I am not writing to "
        "nudge you mechanically — mostly I would like to know why.\n\n"
        "An answer that disappointed you? A need that was not really there? "
        "Reports taking too long? One line in reply helps me more than you "
        "would think — Axial is young, and this is exactly what I fix it on.\n\n"
        f"And if the week was simply busy, your credits are waiting: {APP}\n\n"
        "Miradie"
    )


SEQUENCES: list[Sequence] = [
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
    Sequence("cycle_reactivation", "14 jours sans activité après un premier rapport",
             SQL_REACTIVATION, sujet_reactivation, corps_reactivation),
]


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
