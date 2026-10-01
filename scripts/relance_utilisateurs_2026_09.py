"""Relance des comptes existants selon la dernière étape franchie (fin septembre).

    python scripts/relance_utilisateurs_2026_09.py            # simulation
    python scripts/relance_utilisateurs_2026_09.py --texte    # afficher les messages
    python scripts/relance_utilisateurs_2026_09.py --envoyer  # envoi réel

Trois segments, chacun avec son message, déterminés en base au moment du
lancement (pas de liste figée) :

* ``profil_vide``   — compte ouvert, mémoire d'entreprise jamais remplie ;
* ``sans_rapport``  — profil rempli, des échanges, mais aucun rapport produit ;
* ``dormant``       — au moins un rapport, rien depuis plus d'un mois.

Entre 7 et 31 jours d'inactivité, un utilisateur avec rapport relève des
relances automatiques (``cycle_inactif_j7``, ``cycle_reactivation``,
``cycle_inactif_j30``) et n'est pas relancé ici.

Les profils en anglais reçoivent la version de ``MESSAGES_EN`` quand elle
existe, et rien sinon.

Quiconque a reçu un email hors « rapport prêt » dans les 7 derniers jours est
écarté, pour ne pas empiler les messages. En retour, une relance manuelle
(campagne ``relance_*``) suspend les relances automatiques pendant 7 jours.

Le script peut être relancé quelques jours plus tard : il reprend ceux qui
étaient écartés pour cause d'email récent, sans jamais renvoyer une campagne
déjà reçue.

Chaque segment est une campagne distincte dans ``email_sends``, ce qui permet
de lire l'effet de chaque message séparément dans l'audit d'activation.
"""
import argparse
import sys

sys.path.insert(0, "/opt/axial-intelligence")
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.modules.emailing.envoi import deja_envoye, envoyer, supprime  # noqa: E402

TEST = ("axial-qa", "example.com", "@axial.com", "test")
INTERNES = ("axial-ia.fr", "axial-ial.fr", "francedigitale.org")
EXCLUS_NOMINATIFS = {
    "miradieburanturu@gmail.com", "miradie.buranturukwa@skema.edu",
}

APP = "app.axial-ia.fr"

MESSAGES = {
    "profil_vide": (
        "relance_profil_vide_2026_09",
        "Ton compte Axial est ouvert, il manque juste ton contexte",
        """Hello,

Tu as ouvert ton compte Axial il y a quelques jours, mais ta mémoire d'entreprise est encore vide : Axial ne connaît donc rien de ton projet pour l'instant.

Quatre informations suffisent pour que chaque analyse porte sur ton marché : secteur, stade, concurrents connus, défi principal.

Une fois ton profil rempli, Axial produit une étude de marché ou une étude personnalisée sur ton sujet, et ton premier rapport est offert. Tes {solde} crédits restent disponibles pour la suite.

Pour reprendre : {app}

Si tu as une question, je suis disponible pour qu'on fasse un point.

Miradie B""",
    ),
    "sans_rapport": (
        "relance_sans_rapport_2026_09",
        "Et si tu lançais ton premier rapport Axial ?",
        """Hello,

Tu as déjà échangé avec Axial en conversation, sans lancer de rapport pour l'instant. Les rapports vont beaucoup plus loin : 8 000 à 10 000 mots, jusqu'à 40 sources citées, export PDF.

Trois formats pour commencer :

Une étude de marché ou une étude personnalisée, sur la question de ton choix.

Une analyse concurrentielle, avec tes concurrents directs et leur positionnement.

Une cartographie des investisseurs, avec les fonds filtrés par stade, ticket et secteur.

Il te reste {solde} crédits ; un rapport en consomme 40.

Onglet Rapports : {app}

Si tu as une question ou si tu hésites sur le format, je suis disponible pour qu'on fasse un point.

Miradie B""",
    ),
    "dormant": (
        "relance_dormant_2026_09",
        "Axial a beaucoup changé depuis ton dernier passage",
        """Hello,

Ça fait quelques semaines que tu n'es pas repassé sur Axial, et entre-temps l'application a pas mal changé :

Les rapports ont été refaits : graphiques sur les parties chiffrées, sources citées et vérifiables, export PDF propre.

La cartographie des investisseurs filtre maintenant les fonds par stade, montant recherché et secteur.

Tu peux programmer des agents de veille qui surveillent ton marché et tes concurrents pour toi.

Il te reste {solde} crédits pour tester ces nouveautés : {app}

J'aimerais aussi avoir ton retour de vive voix. Je te propose un échange de 20 minutes sur l'un de ces créneaux :

Lundi 5 octobre à 14h30

Mardi 6 octobre à 10h

Vendredi 9 octobre à 10h

Réponds-moi avec celui qui te convient, je t'envoie l'invitation.

Miradie B""",
    ),
}

# Versions anglaises, pour les profils dont la langue est l'anglais. Un segment
# sans version anglaise n'envoie rien à ces profils plutôt qu'un texte français.
MESSAGES_EN = {
    "dormant": (
        "relance_dormant_2026_09",
        "Axial has changed a lot since your last visit",
        """Hello,

It has been a few weeks since you last used Axial, and the app has changed quite a bit in the meantime:

Reports have been rebuilt: charts on the quantitative sections, cited and verifiable sources, a clean PDF export.

Investor mapping now filters funds by stage, amount raised and sector.

You can set up monitoring agents that keep an eye on your market and competitors for you.

You have {solde} credits left to try these updates: {app}

I would also like to hear your feedback directly. Would one of these 20-minute slots work for you?

Monday 5 October at 2:30 pm

Tuesday 6 October at 10 am

Friday 9 October at 10 am

Just reply with the one that suits you and I will send an invite.

Miradie B""",
    ),
}


# Messages écrits pour une personne précise, à partir de ce qu'elle a fait
# dans l'app (01/10). Prioritaires sur le message du segment ; une seule
# campagne pour les quatre, pour lire leur effet d'un bloc.
CAMPAGNE_PERSO = "relance_perso_2026_10"
MESSAGES_PERSO = {
    "chloe.lecossec@live-for-good.org": (
        "Ton compte Axial est prêt, il ne manque que ton projet",
        """Hello Chloé,

Tu as ouvert ton compte Axial le 16 septembre, mais nous n'avons pas encore fait connaissance : ta mémoire d'entreprise est vide, et Axial ne sait donc rien de ton projet.

Quatre informations suffisent : ton secteur, ton stade, tes concurrents connus et ton défi principal. Dès qu'elles sont renseignées, Axial produit automatiquement une première étude de marché sur ton projet, offerte, et tes 100 crédits restent intacts pour la suite.

Pour reprendre : {app}

Si tu as une question, je suis disponible pour qu'on fasse un point.

Miradie B"""),
    "lenamendy06@gmail.com": (
        "Ta levée de 500 k€ : des investisseurs mieux ciblés pour STARTZUP",
        """Hello,

Le 16 septembre, tu as interrogé Axial sur ta levée de 500 k€ pour STARTZUP, en te demandant si un positionnement Hire-Train-Deploy changeait les fonds à viser, et quelles personnes contacter.

Depuis, la cartographie des investisseurs a été refaite : elle tient compte du montant recherché, du stade et du nombre d'investisseurs que tu veux obtenir. Elle couvre les fonds, mais aussi les réseaux de business angels.

Avec tes 92 crédits, tu peux lancer cette cartographie (40 crédits) directement sur ta levée, dans l'onglet Rapports : {app}

Si tu as une question, je suis disponible pour qu'on fasse un point.

Miradie B"""),
    "s.gorjux@skyted.io": (
        "Skyted : de quoi préparer ta levée sur Axial",
        """Hello,

Ta dernière étude de marché sur Axial date du 26 août. Comme tu prépares une levée de fonds pour Skyted, deux évolutions de ces dernières semaines devraient t'intéresser :

La cartographie des investisseurs se règle désormais sur ta levée : stade, montant recherché et nombre d'investisseurs souhaité.

Les rapports ont été refaits : graphiques sur les parties chiffrées, sources citées et vérifiables, export PDF propre.

Il te reste 70 crédits, de quoi lancer une cartographie complète : {app}

J'aimerais aussi avoir ton retour sur ta première étude. Je te propose un échange de 20 minutes sur l'un de ces créneaux :

Lundi 5 octobre à 14h30

Mardi 6 octobre à 10h

Vendredi 9 octobre à 10h

Réponds-moi avec celui qui te convient, je t'envoie l'invitation.

Miradie B"""),
    "christian@eqonx.com": (
        "EQON Nexus: what has changed since your FenneQ study",
        """Hi Christian,

Since your FenneQ market study at the end of August, Axial has changed quite a bit:

Reports have been rebuilt: charts on the quantitative sections, cited and verifiable sources, a clean PDF export.

Investor mapping now adapts to your round: stage, amount raised and number of investors wanted, which matters at pre-seed.

You have 30 credits left. A full report costs 40, so if you would like to run a new study or an investor mapping for EQON Nexus, just tell me and I will top up your account.

I would also value your feedback on the two studies you ran. Would one of these 20-minute slots work for you?

Monday 5 October at 2:30 pm

Tuesday 6 October at 10 am

Friday 9 October at 10 am

Just reply with the one that suits you and I will send an invite.

Miradie B"""),
}


def message(seg: str, langue: str | None, email: str = ""):
    if email in MESSAGES_PERSO:
        objet, corps = MESSAGES_PERSO[email]
        return (CAMPAGNE_PERSO, objet, corps)
    if (langue or "fr").lower().startswith("en"):
        return MESSAGES_EN.get(seg)
    return MESSAGES[seg]


SQL = """
SELECT lower(u.email) AS email,
       cp.company_name, cp.language,
       COALESCE(b.trial_credits + b.free_credits + b.purchased_credits, 0) AS solde,
       (SELECT count(*) FROM conversations c
          JOIN messages m ON m.conversation_id = c.id AND m.role = 'user'
         WHERE c.user_id = u.id) AS msgs,
       (SELECT count(*) FROM reports r WHERE r.user_id = u.id) AS rapports,
       GREATEST((SELECT max(c.last_message_at) FROM conversations c WHERE c.user_id = u.id),
                (SELECT max(r.created_at) FROM reports r WHERE r.user_id = u.id),
                u.created_at) AS derniere_activite,
       EXISTS (SELECT 1 FROM email_sends e
                WHERE e.email = lower(u.email)
                  AND e.campaign NOT LIKE 'rapport_pret%'
                  AND e.sent_at > now() - interval '7 days') AS mail_recent
FROM auth.users u
LEFT JOIN company_profiles cp ON cp.user_id = u.id
LEFT JOIN credit_balances b ON b.user_id = u.id
WHERE u.created_at < now() - interval '3 days'
ORDER BY u.created_at
"""


def segment(r) -> tuple[str | None, str]:
    """Retourne (segment, motif d'exclusion éventuel)."""
    jours = r["jours"]
    if jours < 7:
        return None, "actif ces 7 derniers jours"
    if not r["company_name"]:
        return "profil_vide", ""
    if r["rapports"] == 0:
        return ("sans_rapport", "") if r["msgs"] > 0 else ("profil_vide", "")
    # Entre 7 et 31 jours, les relances automatiques d'inactivité (7, 14 et
    # 30 jours) s'en chargent : un message manuel ferait doublon.
    if jours <= 31:
        return None, "relances automatiques d'inactivité (7 / 14 / 30 j)"
    return "dormant", ""


def cibles(db):
    rows = db.execute(text(SQL)).mappings().all()
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    retenus, ecartes = [], []
    for r in rows:
        r = dict(r)
        e = r["email"]
        if any(t in e for t in TEST) or any(i in e for i in INTERNES) \
                or e.startswith("miradie") or e in EXCLUS_NOMINATIFS:
            continue
        r["jours"] = (now - r["derniere_activite"]).days
        seg, motif = segment(r)
        if seg is None:
            ecartes.append((e, motif))
            continue
        msg = message(seg, r["language"], r["email"])
        if msg is None:
            ecartes.append((e, f"profil en anglais, pas de version anglaise pour {seg}"))
            continue
        campagne = msg[0]
        if supprime(db, e):
            ecartes.append((e, "désinscrit"))
        elif deja_envoye(db, e, campagne):
            ecartes.append((e, "déjà relancé"))
        elif r["mail_recent"]:
            ecartes.append((e, "email reçu il y a moins de 7 jours"))
        else:
            retenus.append((seg, r))
    return retenus, ecartes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--envoyer", action="store_true")
    ap.add_argument("--texte", action="store_true", help="afficher les messages et sortir")
    args = ap.parse_args()

    if args.texte:
        for email, (objet, corps) in MESSAGES_PERSO.items():
            print(f"=== {email} ({CAMPAGNE_PERSO})\nObjet : {objet}\n")
            print(corps.format(solde="NN", app=APP), "\n")
        for seg, (campagne, objet, corps) in [*MESSAGES.items(),
                                              *((f"{k} [en]", v) for k, v in MESSAGES_EN.items())]:
            print(f"=== {seg} ({campagne})\nObjet : {objet}\n")
            print(corps.format(solde="NN", app=APP), "\n")
        return

    with SessionLocal() as db:
        retenus, ecartes = cibles(db)
        print(f"{'ENVOI RÉEL' if args.envoyer else 'SIMULATION'} — {len(retenus)} destinataire(s)\n")
        for seg, r in retenus:
            print(f"  {seg:13} {(r['language'] or 'fr')[:2]} {r['email']:42} solde={r['solde']:<4} "
                  f"msg={r['msgs']:<3} rapports={r['rapports']:<3} inactif {r['jours']} j")
        for e, motif in ecartes:
            print(f"      ({e} — {motif})")
        if not args.envoyer:
            print("\nRelancer avec --envoyer pour expédier.")
            return
        ok = 0
        for seg, r in retenus:
            campagne, objet, corps = message(seg, r["language"], r["email"])
            envoye, info = envoyer(db, r["email"], campagne, objet,
                                   corps.format(solde=r["solde"], app=APP),
                                   langue="fr", simulation=False)
            ok += 1 if envoye else 0
            print(f"  {'✓' if envoye else '✗'} {r['email']} {info or ''}")
        print(f"\n{ok}/{len(retenus)} envoyés.")


if __name__ == "__main__":
    main()
