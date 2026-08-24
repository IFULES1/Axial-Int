#!/usr/bin/env python3
"""Contrôle des séquences d'emails de cycle de vie.

Simulation par défaut : affiche qui recevrait quoi, sans rien envoyer. C'est le
mode qu'on veut avoir sous les yeux avant chaque changement de texte.

    python scripts/sequences_emails.py                    # simulation, tout
    python scripts/sequences_emails.py --sequence cycle_essai_j3
    python scripts/sequences_emails.py --apercu cycle_essai_j3   # lire le texte
    python scripts/sequences_emails.py --envoyer          # envoi réel
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal  # noqa: E402
from app.modules.emailing.envoi import deja_envoye, supprime  # noqa: E402
from app.modules.emailing.sequences import SEQUENCES, eligibles, executer  # noqa: E402


def apercu(cle: str, langue: str) -> None:
    seq = next((s for s in SEQUENCES if s.cle == cle), None)
    if seq is None:
        print(f"Séquence inconnue : {cle}")
        return
    import datetime as dt
    ctx = {"company_name": "Ta boîte", "solde": 8, "plan_key": "pro",
           "current_period_end": dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3)}
    print(f"=== {seq.cle} [{langue}] — {seq.description}")
    print(f"Objet : {seq.sujet(langue, ctx)}\n")
    print(seq.corps(langue, ctx))
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--envoyer", action="store_true", help="envoi réel (sinon simulation)")
    ap.add_argument("--sequence", help="ne traiter qu'une séquence")
    ap.add_argument("--apercu", help="afficher le texte d'une séquence sans requêter la base")
    ap.add_argument("--langue", default="fr")
    args = ap.parse_args()

    if args.apercu:
        if args.apercu == "toutes":
            for s in SEQUENCES:
                apercu(s.cle, args.langue)
        else:
            apercu(args.apercu, args.langue)
        return

    with SessionLocal() as db:
        if not args.envoyer:
            print("MODE SIMULATION — aucun email ne part.\n")
            for seq in SEQUENCES:
                if args.sequence and seq.cle != args.sequence:
                    continue
                try:
                    cibles = eligibles(db, seq)
                except Exception as e:  # noqa: BLE001
                    print(f"{seq.cle:26} ERREUR {e}"[:160])
                    continue
                # La simulation doit montrer EXACTEMENT ce que l'envoi ferait :
                # une liste qui ignore les désinscrits et les envois déjà faits
                # donne une fausse alerte à chaque relecture, et finit par ne
                # plus être lue du tout.
                retenus, ecartes = [], []
                for c in cibles:
                    if supprime(db, c.email):
                        ecartes.append((c.email, "désinscrit"))
                    elif deja_envoye(db, c.email, seq.cle):
                        ecartes.append((c.email, "déjà envoyé"))
                    else:
                        retenus.append(c)
                print(f"{seq.cle:26} {len(retenus):3} à envoyer  — {seq.description}")
                for c in retenus:
                    print(f"    → {c.email}  [{c.langue}]")
                for email, motif in ecartes:
                    print(f"      ({email} — {motif})")
            return

        journal = executer(db, simulation=False, seulement=args.sequence)
        envoyes = sum(1 for j in journal if j.get("envoye"))
        for j in journal:
            etat = "OK  " if j.get("envoye") else "----"
            print(f"{etat} {j.get('sequence'):26} {j.get('email', '')} {j.get('info', '')}"[:150])
        print(f"\n{envoyes} email(s) envoyé(s) sur {len(journal)} candidat(s).")


if __name__ == "__main__":
    main()
