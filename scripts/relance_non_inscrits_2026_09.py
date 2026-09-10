"""Deuxième relance des contacts de l'ancienne plateforme sans compte.

    python scripts/relance_non_inscrits_2026_09.py            # simulation
    python scripts/relance_non_inscrits_2026_09.py --texte    # afficher le message
    python scripts/relance_non_inscrits_2026_09.py --envoyer  # envoi réel

Même mécanique que la relance d'août : journal `email_sends`, liste de
suppression, désinscription en un clic, pixel d'ouverture. Ce qui change :
la campagne, le message, et une liste d'exclusions nominatives — les contacts
avec qui Miradie échange déjà directement ne reçoivent pas un message
automatique par-dessus la conversation.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, "/opt/axial-intelligence")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # scripts/ n'est pas un paquet
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.modules.emailing.envoi import deja_envoye, envoyer, supprime  # noqa: E402
from relance_non_inscrits import INTERNES, prenoms  # noqa: E402

CAMPAGNE = "relance_2026_09"
OBJET = "Axial : un rapport complet offert, sans carte"

# Échanges en cours de vive voix : pas de relance automatique par-dessus.
EXCLUS_NOMINATIFS = {
    "henry.tran@hec.edu", "henry.tran2020@gmail.com", "henry.tran@lumierequantum.com",
    "sabinjohan@gmail.com",
    # Prénoms hérités de l'ancienne base manifestement faux : un « Hello Pellero »
    # fait plus de mal qu'un silence. Retirés à la demande de Miradie (07/09).
    "calebmeinerad@gmail.com", "steveny1989@gmail.com", "v.pellero@dugas.fr",
    "tiphanie.doye@trinity-asia.com",
    # Même personne sur deux adresses : on garde valerie.doye71@gmail.com, la
    # seule qui a ouvert les messages précédents.
    "valerie.doye@keystonecybersecurity.fr",
}

CORPS = """Hello {prenom},

Depuis mon dernier message, Axial a pas mal bougé, et une chose en particulier te concerne : tu peux maintenant générer ton premier rapport complet sans carte bancaire.

Concrètement, à l'inscription :

40 crédits offerts, et une étude de marché ou une cartographie concurrentielle complète offerte en plus — jusqu'à 40 sources citées, 8 000 à 10 000 mots, exportable en PDF.

Aucune carte demandée pendant l'essai. Tu testes sur ton vrai sujet, tu décides ensuite.

Deux premiers utilisateurs ont produit leurs études cette semaine ; leurs retours sont dans la version que tu vas ouvrir.

C'est ici : app.axial-ia.fr

Si ce n'est pas pour toi, un mot suffit et je ne reviens plus. Si tu préfères qu'on en parle 15 minutes, dis-moi un créneau.

Miradie"""


def destinataires(db) -> list[str]:
    rows = db.execute(text("""
        SELECT DISTINCT e.email
        FROM email_sends e
        WHERE e.campaign = 'migration_2026_08'
          AND e.email NOT IN (SELECT email FROM email_suppressions)
          AND e.email NOT IN (SELECT lower(email) FROM auth.users)
        ORDER BY e.email
    """)).scalars().all()
    return [e for e in rows if e not in INTERNES and e not in EXCLUS_NOMINATIFS]


def corps_pour(email: str, index: dict[str, str]) -> str:
    prenom = index.get(email, "")
    return CORPS.format(prenom=prenom).replace("Hello ,", "Hello,")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--envoyer", action="store_true")
    ap.add_argument("--texte", action="store_true", help="afficher le message et sortir")
    args = ap.parse_args()

    if args.texte:
        print(f"Objet : {OBJET}\n\n{CORPS.format(prenom='Prénom')}")
        return

    index = prenoms()
    with SessionLocal() as db:
        cibles = [e for e in destinataires(db)
                  if not supprime(db, e) and not deja_envoye(db, e, CAMPAGNE)]
        print(f"{'ENVOI RÉEL' if args.envoyer else 'SIMULATION'} — {len(cibles)} destinataire(s)")
        for e in cibles:
            print(f"  {e:44} {index.get(e, '') or '(sans prénom)'}")
        if not args.envoyer:
            print("\nRelancer avec --envoyer pour expédier.")
            return
        ok = 0
        for e in cibles:
            envoye, info = envoyer(db, e, CAMPAGNE, OBJET, corps_pour(e, index),
                                   langue="fr", simulation=False)
            ok += 1 if envoye else 0
            print(f"  {'✓' if envoye else '✗'} {e} {info or ''}")
        print(f"\n{ok}/{len(cibles)} envoyés.")


if __name__ == "__main__":
    main()
