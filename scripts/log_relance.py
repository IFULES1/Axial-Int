#!/usr/bin/env python3
"""Consigner une relance manuelle (WhatsApp, email perso, téléphone).

Ajoute une entrée à crm/relances.yaml. Le fichier est append-only : chaque
échange est une ligne, jamais réécrite après coup. Le tableau de bord ne
retient que l'entrée la plus récente par email pour ses alertes.

    python scripts/log_relance.py --email x@y.fr --canal whatsapp \
        --resume "dit qu'elle regarde la semaine prochaine" \
        --prochaine-action "relancer si rien d'ici là" --echeance 2026-09-01

    python scripts/log_relance.py --email x@y.fr --canal tel --resume "injoignable"
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[1]
FICHIER = RACINE / "crm" / "relances.yaml"
ENTETE = (
    "# Journal des relances manuelles (WhatsApp, email perso, téléphone).\n"
    "# Append-only : une entrée par échange, jamais modifiée après coup.\n"
    "# Alimenté par scripts/log_relance.py, lu par scripts/dashboard_relances.py.\n"
    "# Une ligne = un échange réel. La \"prochaine_action\"/\"echeance\" de l'entrée\n"
    "# la plus récente pour un email pilote les alertes du tableau de bord.\n"
)
CANAUX = ("whatsapp", "email", "tel", "autre")


def charger() -> list[dict]:
    if not FICHIER.exists():
        return []
    brut = yaml.safe_load(FICHIER.read_text(encoding="utf-8"))
    return brut or []


def enregistrer(entrees: list[dict]) -> None:
    corps = yaml.safe_dump(
        entrees, allow_unicode=True, sort_keys=False, default_flow_style=False)
    FICHIER.write_text(ENTETE + "\n" + corps, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--canal", required=True, choices=CANAUX)
    ap.add_argument("--resume", required=True, help="ce qui s'est dit, en une phrase")
    ap.add_argument("--date", default=None,
                     help="AAAA-MM-JJ, défaut : aujourd'hui")
    ap.add_argument("--prochaine-action", default=None,
                     help="ce qui est prévu ensuite, si quelque chose l'est")
    ap.add_argument("--echeance", default=None,
                     help="AAAA-MM-JJ, si une échéance a été fixée")
    args = ap.parse_args()

    for champ, valeur in (("--date", args.date), ("--echeance", args.echeance)):
        if valeur:
            try:
                dt.date.fromisoformat(valeur)
            except ValueError:
                sys.exit(f"{champ} doit être au format AAAA-MM-JJ, reçu : {valeur!r}")

    entree = {
        "email": args.email.strip().lower(),
        "date": args.date or dt.date.today().isoformat(),
        "canal": args.canal,
        "resume": args.resume,
    }
    if args.prochaine_action:
        entree["prochaine_action"] = args.prochaine_action
    if args.echeance:
        entree["echeance"] = args.echeance

    entrees = charger()
    entrees.append(entree)
    enregistrer(entrees)
    print(f"Consigné : {entree['email']} — {entree['canal']} le {entree['date']}")


if __name__ == "__main__":
    main()
