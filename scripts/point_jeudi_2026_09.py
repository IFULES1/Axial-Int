"""Deux emails personnels : essai prolongé + proposition de point jeudi 10/09.

    python scripts/point_jeudi_2026_09.py            # simulation
    python scripts/point_jeudi_2026_09.py --envoyer  # envoi réel

Passe par `envoi.envoyer` pour garder journal, pixel et désinscription — même
pour deux messages écrits à la main : un email dont on ne sait pas s'il a été
ouvert n'aide pas à décider de la suite.
"""
import argparse
import sys

sys.path.insert(0, "/opt/axial-intelligence")
from app.db import SessionLocal  # noqa: E402
from app.modules.emailing.envoi import deja_envoye, envoyer, supprime  # noqa: E402

CAMPAGNE = "point_jeudi_2026_09"

MESSAGES = [
    {
        "email": "christian@eqonx.com",
        "langue": "en",
        "objet": "Your Axial trial is back on — 15 minutes next week?",
        "corps": """Hi Christian,

An apology first: Axial was unreachable from Thursday 3rd to Monday 7th because of a deployment error on my side. Your trial has been extended until 17 September.

I saw you came back on Tuesday. I'd like your take on the reports you produced — and on what stopped you at the card screen. Would Monday 14th or Tuesday 15th work, morning or afternoon? Fifteen minutes. Tell me the slot and I'll send an invite.

Miradie""",
    },
    {
        "email": "soumeya@optimpharma.fr",
        "langue": "fr",
        "objet": "Ton essai Axial est prolongé — 15 minutes la semaine prochaine ?",
        "corps": """Bonjour Soumeya,

Ton essai Axial est prolongé jusqu'au 17 septembre. Tes 22 études de l'ancienne plateforme et tes 70 crédits t'attendent.

Tu n'as pas encore ouvert l'application, et je préfère comprendre pourquoi plutôt que te relancer par email. Lundi 14 ou mardi 15, matin ou après-midi, ça t'irait ? Quinze minutes pour faire le point. Dis-moi le créneau et je t'envoie l'invitation.

Miradie""",
    },
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--envoyer", action="store_true")
    args = ap.parse_args()
    print(f"{'ENVOI RÉEL' if args.envoyer else 'SIMULATION'} — {len(MESSAGES)} message(s)")
    with SessionLocal() as db:
        for m in MESSAGES:
            e = m["email"]
            if supprime(db, e):
                print(f"  ---- {e} : désinscrit, ignoré")
                continue
            if deja_envoye(db, e, CAMPAGNE):
                print(f"  ---- {e} : déjà envoyé, ignoré")
                continue
            if not args.envoyer:
                print(f"  {e:32} [{m['langue']}] {m['objet']}")
                continue
            envoye, info = envoyer(db, e, CAMPAGNE, m["objet"], m["corps"],
                                   langue=m["langue"], simulation=False)
            print(f"  {'OK  ' if envoye else '----'} {e:32} {info}")


if __name__ == "__main__":
    main()
