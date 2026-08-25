#!/usr/bin/env python3
"""Rattrapage des crédits de bienvenue passés de 20 à 40.

Les comptes ouverts avant le changement ont reçu 20 crédits. Leur en devoir 40
et ne rien faire reviendrait à traiter différemment deux personnes selon leur
date d'inscription. Le script ajoute la différence et prévient les intéressés.

Simulation par défaut.

    python scripts/rattrapage_credits.py
    python scripts/rattrapage_credits.py --envoyer
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.modules.billing.service import FREE_BETA_CREDITS  # noqa: E402
from app.modules.emailing.envoi import deja_envoye, envoyer, supprime  # noqa: E402

ANCIENNE_DOTATION = 20
ACTION = "rattrapage_bienvenue"
CAMPAGNE = "rattrapage_credits_2026_08"
OBJET = "20 crédits de plus sur ton compte Axial"

CORPS = """Hello {prenom},

Petit message pour te dire que je viens d'ajouter {montant} crédits sur ton compte Axial.

La raison : les crédits offerts à l'inscription passent de 20 à 40, parce que 20 ne suffisaient pas à produire un rapport complet — le cœur de l'app restait fermé. Tu t'es inscrit avant ce changement, donc tu recevais moins que les nouveaux arrivants. C'est corrigé.

Tu as maintenant {solde} crédits, de quoi lancer une étude de marché complète.

C'est ici : app.axial-ia.fr

Miradie"""


def concernes(db) -> list[dict]:
    """Comptes dont la dotation de bienvenue est restée à l'ancien montant."""
    return [dict(r) for r in db.execute(text("""
        SELECT u.id, u.email,
               COALESCE((SELECT sum(delta) FROM credit_events e
                         WHERE e.user_id = u.id AND e.action = 'essai_bienvenue'), 0) AS dotation,
               COALESCE((SELECT sum(delta) FROM credit_events e
                         WHERE e.user_id = u.id AND e.action = :action), 0) AS deja,
               COALESCE(b.trial_credits + b.free_credits + b.purchased_credits, 0) AS solde
        FROM auth.users u
        LEFT JOIN credit_balances b ON b.user_id = u.id
        ORDER BY u.created_at
    """), {"action": ACTION}).mappings().all()
        if r["dotation"] == ANCIENNE_DOTATION and r["deja"] == 0]


def prenoms() -> dict[str, str]:
    import json
    import pathlib

    for chemin in ("/opt/axial-intelligence/var/destinataires.json",
                   "var/destinataires.json"):
        f = pathlib.Path(chemin)
        if f.exists():
            return {e["email"].lower(): (e.get("prenom") or "").strip()
                    for e in json.loads(f.read_text())}
    return {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--envoyer", action="store_true", help="créditer et prévenir")
    args = ap.parse_args()
    montant = FREE_BETA_CREDITS - ANCIENNE_DOTATION

    with SessionLocal() as db:
        lot = concernes(db)
        index = prenoms()
        print(f"Dotation : {ANCIENNE_DOTATION} → {FREE_BETA_CREDITS} "
              f"(rattrapage de {montant} crédits)\n")
        if not lot:
            print("Aucun compte à rattraper.")
            return
        if not args.envoyer:
            print(f"MODE SIMULATION — {len(lot)} compte(s) :\n")
            for c in lot:
                print(f"   {c['email']:34} {c['solde']} → {c['solde'] + montant} crédits")
            return

        from app.modules.billing import service as billing

        for c in lot:
            uid = str(c["id"])
            balance = billing.get_or_create_balance(db, uid)
            balance.purchased_credits += montant
            billing._log_event(db, uid, montant, ACTION)
            db.commit()
            nouveau = c["solde"] + montant
            etat = "crédité"
            if not supprime(db, c["email"]) and not deja_envoye(db, c["email"], CAMPAGNE):
                texte = CORPS.format(prenom=index.get(c["email"], ""),
                                     montant=montant, solde=nouveau)
                texte = texte.replace("Hello ,", "Hello,")
                ok, info = envoyer(db, c["email"], CAMPAGNE, OBJET, texte,
                                   langue="fr", simulation=False)
                etat += " · email " + ("envoyé" if ok else f"non envoyé ({info})")
            else:
                etat += " · email ignoré (désinscrit ou déjà envoyé)"
            print(f"   {c['email']:34} {c['solde']} → {nouveau}  {etat}")


if __name__ == "__main__":
    main()
