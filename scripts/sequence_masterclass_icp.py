"""Séquence d'activation des participants à la masterclass ICP (septembre 2026).

    python scripts/sequence_masterclass_icp.py            # simulation : ce qui partirait maintenant
    python scripts/sequence_masterclass_icp.py --texte    # afficher les trois messages
    python scripts/sequence_masterclass_icp.py --envoyer  # envoi réel des étapes dues

Trois étapes, chacune ne part que si la précédente est partie depuis assez
longtemps ET que la personne n'a toujours pas de compte :

    J0  — le lien entre la masterclass et Axial, l'invitation ;
    J+3 — un cas d'usage concret : faire vérifier son ICP par Axial ;
    J+7 — dernier message, court, avec une porte de sortie.

Dès qu'un participant crée son compte, il sort de cette séquence et entre dans
les séquences de cycle de vie habituelles (bienvenue, profil incomplet…). Le
script peut donc être relancé chaque jour sans risque : il n'envoie que ce qui
est dû, jamais deux fois la même étape (journal `email_sends`).
"""
import argparse
import datetime as dt
import sys

sys.path.insert(0, "/opt/axial-intelligence")
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.modules.emailing.envoi import deja_envoye, envoyer, supprime  # noqa: E402

# Prénom seulement quand il est certain ; sinon « Hello, » plutôt qu'un
# prénom mal découpé.
PARTICIPANTS = {
    "azzaaittaleb@gmail.com": "",
    "dario.barone@skema.edu": "Dario",
    "chiara.bernardi@skema.edu": "Chiara",
    "maxime.da@skema.edu": "Maxime",
    "donald.olympio@gmail.com": "",
    "fenaux.melissandre@outlook.com": "",
    "thomas.metivier@skema.edu": "Thomas",
    "mrunalmurari15@outlook.com": "",
    "anirudhasingh.naruka@skema.edu": "Anirudha",
    "thithanhlam.nguyen@skema.edu": "",
    "stephanie.baesa@wanadoo.fr": "",
    "virginiapani@gmail.com": "",
    "virgile.weishaupt@skema.edu": "Virgile",
    "xinyan.zhang@skema.edu": "Xinyan",
}

APP = "app.axial-ia.fr"

# (campagne, délai minimum après l'étape précédente, objet, corps)
ETAPES = [
    ("masterclass_icp_j0", None,
     "Suite de la masterclass ICP : passe à la pratique avec Axial",
     """Hello{prenom},

Merci d'avoir participé à la masterclass sur l'ICP. On y a vu qu'un bon profil client idéal se construit à partir du marché réel : les segments qui paient, et ceux qui ne paieront jamais.

Axial t'aide à faire ce travail sur ton propre projet. Tu le décris une fois, secteur, stade, cible pressentie, et Axial produit une étude de marché ou une étude personnalisée : segments, personas, disponibilité à payer, canaux d'acquisition, avec les sources citées.

Ton premier rapport est offert, et il se lance automatiquement dès que ton profil est rempli.

Pour créer ton compte : {app}

Si tu as une question sur ton ICP ou sur l'outil, je suis disponible pour qu'on fasse un point.

Miradie B"""),
    ("masterclass_icp_j3", dt.timedelta(days=3),
     "Ton ICP, vérifié en 10 minutes",
     """Hello{prenom},

Un exercice concret, dans la continuité de la masterclass : prends l'ICP que tu as esquissé, et demande à Axial de le confronter au marché.

Par exemple : « Mon client idéal est une PME industrielle française de 50 à 200 salariés. Quelle est la taille de ce segment, qui le sert déjà, et à quel prix ? »

En retour : des chiffres sourcés, les concurrents qui visent déjà ce segment, et les signaux qui disent si ton hypothèse tient ou s'il faut la resserrer.

Création du compte en deux minutes, premier rapport offert : {app}

Miradie B"""),
    ("masterclass_icp_j7", dt.timedelta(days=4),
     "Dernier message de ma part",
     """Hello{prenom},

Dernier message de ma part sur ce sujet, promis.

Si tu travailles sur un projet en ce moment, Axial peut te faire gagner plusieurs jours de recherche sur ton marché et ton ICP, et le premier rapport ne te coûte rien : {app}

Si le moment ne s'y prête pas, aucun souci, un mot en réponse me suffit. Et si tu as une question, je suis disponible pour qu'on fasse un point.

Miradie B"""),
]


def a_un_compte(db, email: str) -> bool:
    return db.execute(text("SELECT 1 FROM auth.users WHERE lower(email) = :e"),
                      {"e": email}).first() is not None


def envoye_le(db, email: str, campagne: str) -> dt.datetime | None:
    return db.execute(text("SELECT min(sent_at) FROM email_sends "
                           "WHERE email = :e AND campaign = :c"),
                      {"e": email, "c": campagne}).scalar()


def etape_due(db, email: str):
    """La prochaine étape à envoyer maintenant, ou (None, motif)."""
    now = dt.datetime.now(dt.timezone.utc)
    precedente = None
    for campagne, delai, objet, corps in ETAPES:
        if deja_envoye(db, email, campagne):
            precedente = envoye_le(db, email, campagne)
            continue
        if delai is None:
            return (campagne, objet, corps), ""
        if precedente and now - precedente >= delai:
            return (campagne, objet, corps), ""
        reste = delai - (now - precedente) if precedente else delai
        return None, f"{campagne} dans {reste.days} j {reste.seconds // 3600} h"
    return None, "séquence terminée"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--envoyer", action="store_true")
    ap.add_argument("--texte", action="store_true", help="afficher les messages et sortir")
    args = ap.parse_args()

    if args.texte:
        for campagne, delai, objet, corps in ETAPES:
            print(f"=== {campagne} (après {delai or 'lancement'})\nObjet : {objet}\n")
            print(corps.format(prenom=" Prénom", app=APP), "\n")
        return

    # Pas d'envoi le week-end : une relance reçue un dimanche est lue le lundi
    # sous une pile d'autres messages. L'étape due part au premier passage du
    # lundi, et l'étape suivante se cale sur cette nouvelle date.
    if dt.datetime.now(dt.timezone.utc).weekday() >= 5 and args.envoyer:
        print("Week-end : aucun envoi, les étapes dues partiront lundi.")
        return

    with SessionLocal() as db:
        a_envoyer, ecartes = [], []
        for email, prenom in PARTICIPANTS.items():
            if supprime(db, email):
                ecartes.append((email, "désinscrit"))
            elif a_un_compte(db, email):
                ecartes.append((email, "compte créé, relève des séquences de cycle de vie"))
            else:
                etape, motif = etape_due(db, email)
                if etape:
                    a_envoyer.append((email, prenom, etape))
                else:
                    ecartes.append((email, motif))

        print(f"{'ENVOI RÉEL' if args.envoyer else 'SIMULATION'} — {len(a_envoyer)} email(s) dus\n")
        for email, prenom, (campagne, _, _) in a_envoyer:
            print(f"  {campagne:20} {email:36} {prenom or '(sans prénom)'}")
        for email, motif in ecartes:
            print(f"      ({email} — {motif})")
        if not args.envoyer:
            print("\nRelancer avec --envoyer pour expédier.")
            return
        ok = 0
        for email, prenom, (campagne, objet, corps) in a_envoyer:
            envoye, info = envoyer(db, email, campagne, objet,
                                   corps.format(prenom=f" {prenom}" if prenom else "", app=APP),
                                   langue="fr", simulation=False)
            ok += 1 if envoye else 0
            print(f"  {'✓' if envoye else '✗'} {email} {info or ''}")
        print(f"\n{ok}/{len(a_envoyer)} envoyés.")


if __name__ == "__main__":
    main()
