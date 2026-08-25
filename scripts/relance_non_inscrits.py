#!/usr/bin/env python3
"""Relance des contactés de la campagne de migration restés sans compte.

Simulation par défaut. Réutilise le moteur d'envoi des séquences : même
journal, même liste de suppression, même désinscription en un clic, même
garantie d'unicité par (email, campagne).

    python scripts/relance_non_inscrits.py                 # simulation
    python scripts/relance_non_inscrits.py --envoyer       # envoi réel
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.modules.emailing.envoi import deja_envoye, envoyer, supprime  # noqa: E402

CAMPAGNE = "relance_2026_08"
OBJET = "Axial : ce qui a changé depuis mon dernier message"

# Adresses internes à ne jamais relancer.
INTERNES = {"miradieburanturu@gmail.com"}

CORPS = """Hello {prenom},

Je t'avais écrit il y a quelques jours pour la nouvelle version d'Axial. Tu ne l'as pas encore ouverte — pas de souci, je reviens vers toi une seule fois.

Ce qui a changé depuis :

L'app est entièrement bilingue. Tu peux l'utiliser en anglais de bout en bout, et les analyses répondent dans la langue de ta question.

Les rapports sont plus profonds, avec jusqu'à 40 sources citées pour une étude de marché.

Un nouveau type d'analyse : la veille réglementaire, avec le calendrier des échéances et les obligations qui te concernent.

Tu peux déposer ton deck ou tes documents directement dans la conversation, et Axial s'en sert pour répondre.

Tes 50 crédits t'attendent, de quoi reprendre en main l'application.

C'est ici : app.axial-ia.fr

Si Axial ne correspond pas à ton besoin, dis-le-moi en une ligne — c'est utile aussi, et je ne te relancerai plus.

Miradie"""


def prenoms() -> dict[str, str]:
    """Prénoms de la campagne de migration, indexés par adresse."""
    import json
    import pathlib

    for chemin in ("/opt/axial-intelligence/var/destinataires.json",
                   "var/destinataires.json"):
        f = pathlib.Path(chemin)
        if f.exists():
            return {e["email"].lower(): (e.get("prenom") or "").strip()
                    for e in json.loads(f.read_text())}
    return {}


def destinataires(db) -> list[str]:
    """Contactés par la migration, sans compte, non désinscrits."""
    rows = db.execute(text("""
        SELECT DISTINCT e.email
        FROM email_sends e
        WHERE e.campaign = 'migration_2026_08'
          AND e.email NOT IN (SELECT email FROM email_suppressions)
          AND e.email NOT IN (SELECT lower(email) FROM auth.users)
        ORDER BY e.email
    """)).scalars().all()
    return [e for e in rows if e not in INTERNES]


def corps_pour(email: str, index: dict[str, str]) -> str:
    """Message personnalisé. Sans prénom connu, « Hello, » plutôt qu'un trou."""
    prenom = index.get(email, "")
    return CORPS.format(prenom=prenom).replace("Hello ,", "Hello,")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--envoyer", action="store_true")
    ap.add_argument("--texte", action="store_true", help="afficher le message et sortir")
    args = ap.parse_args()

    if args.texte:
        print(f"Objet : {OBJET}\n")
        print(corps_pour("exemple", {"exemple": "Alessandro"}))
        return

    with SessionLocal() as db:
        index = prenoms()
        cibles = destinataires(db)
        retenus = [e for e in cibles
                   if not supprime(db, e) and not deja_envoye(db, e, CAMPAGNE)]
        if not args.envoyer:
            print(f"MODE SIMULATION — {len(retenus)} envoi(s) partiraient :\n")
            manquants = [e for e in retenus if not index.get(e)]
            for e in retenus:
                print(f"   → {e:44} Hello {index.get(e) or '(sans prénom)'},")
            if manquants:
                print(f"\n   {len(manquants)} adresse(s) sans prénom → « Hello, » :")
                for e in manquants:
                    print("     ", e)
            return

        ok = 0
        for e in retenus:
            envoye, info = envoyer(db, e, CAMPAGNE, OBJET, corps_pour(e, index),
                                   langue="fr", simulation=False)
            print(f"{'OK  ' if envoye else '----'} {e:44} {info}"[:130])
            ok += 1 if envoye else 0
        print(f"\n{ok} email(s) envoyé(s) sur {len(retenus)}.")


if __name__ == "__main__":
    main()
