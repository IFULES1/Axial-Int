"""Envoi de l'email de migration aux utilisateurs de l'ancienne plateforme.

Sécurité par construction :
  * mode simulation par DÉFAUT — il faut `--envoyer` pour qu'un message parte ;
  * envoi par lots avec pause, pour repérer un problème avant d'avoir tout expédié ;
  * journal des envois sur disque : relancer le script ne renvoie jamais deux fois
    au même destinataire.

Le nombre de rapports hérités par adresse est lu dans `legacy_reports`, ce qui
choisit automatiquement la variante du message.

    python3 scripts/envoyer_emails_migration.py                  # simulation
    python3 scripts/envoyer_emails_migration.py --envoyer --lot 10
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

import httpx
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.modules.reports.legacy import LegacyReport

EXPEDITEUR = '"Miradie @Axial" <miradie.buranturu@axial-ia.fr>'
OBJET = "Axial fait peau neuve — tes rapports t'attendent"
JOURNAL = pathlib.Path("/opt/axial-intelligence/var/emails_migration_envoyes.json")

CORPS = """Salut {prenom},

Ça fait un moment que tu n'as pas ouvert Axial. Il s'est passé beaucoup de choses entre-temps : on a entièrement reconstruit la plateforme, et elle est en ligne depuis quelques semaines à l'adresse app.axial-ia.fr.

{bloc_rapports}

Et 50 crédits te sont offerts pour reprendre en main — de quoi produire un ou deux rapports complets, ou tenir une vingtaine d'échanges avec les agents.

CE QUI A CHANGÉ

Axial se souvient de toi. Tu renseignes ton entreprise une fois — activité, positionnement, stade, marché — et chaque analyse part de ce contexte. Fini le fait de réexpliquer qui tu es à chaque question.

Les réponses s'écrivent sous tes yeux. Plus d'attente devant un écran figé : le texte apparaît au fil de sa rédaction, et les sources s'affichent avant même la première phrase.

Chaque affirmation est traçable. Les citations dans le texte sont cliquables : un clic ouvre la source, son extrait et son lien d'origine. Tu peux vérifier, pas seulement lire.

Les rapports sont nettement plus profonds. Une synthèse exécutive mobilise désormais jusqu'à 40 sources, avec une structure de vrai rapport d'analyse — et un export PDF propre.

Tes documents nourrissent les réponses. Glisse un pitch deck, une étude ou un business plan dans la conversation : il alimente directement la réponse qui suit, et reste disponible pour les analyses suivantes.

Des agents travaillent en continu. Configure une veille — concurrents, réglementation, technologies — choisis sa fréquence, et reçois les trouvailles par email sans y penser.

Nouveau : la cartographie des investisseurs. À partir de ton secteur et de ton stade, Axial identifie les fonds et réseaux de business angels réellement pertinents, à partir d'une base propriétaire de plus de 1 600 investisseurs français — puis construit ton ordre d'approche, l'angle de discours par interlocuteur et les objections à préparer. C'est le genre d'analyse qu'aucun outil généraliste ne peut produire.

POUR REPRENDRE

app.axial-ia.fr — crée ton compte avec cette adresse email, tes rapports et tes crédits t'y attendent.

L'inscription prend deux minutes : tu décris ton entreprise, puis tu actives ton essai avec ta carte — 0 € débité aujourd'hui, 14 jours d'essai. Ensuite l'abonnement Pro est à 50 €/mois (120 crédits mensuels), et tu peux l'arrêter en un clic depuis ton espace avant la fin de l'essai.

Si quelque chose coince ou ne te convient pas, réponds simplement à cet email : je lis tout.

Miradie
Axial Intelligence

—
Tu reçois ce message parce que tu as créé un compte sur la première version d'Axial. Si tu ne souhaites plus être contacté, réponds « stop » et je te retire de la liste.
"""

AVEC_RAPPORTS_PLURIEL = ("Tes {n} rapports t'attendent. Ils sont conservés et "
                         "reviennent automatiquement dans ton espace dès que tu crées "
                         "ton compte avec cette même adresse email. Rien à exporter, "
                         "rien à réimporter.")
AVEC_RAPPORT_UN = ("Ton rapport t'attend. Il est conservé et revient automatiquement "
                   "dans ton espace dès que tu crées ton compte avec cette même "
                   "adresse email. Rien à exporter, rien à réimporter.")
SANS_RAPPORT = ("Ton compte de la première version est reconnu : crée le nouveau "
                "avec cette même adresse email et tu retrouves ton espace "
                "immédiatement.")


def destinataires() -> list[dict]:
    """Adresses à contacter, avec leur nombre de rapports hérités."""
    db = SessionLocal()
    counts = dict(db.execute(
        select(LegacyReport.email, func.count(LegacyReport.id)).group_by(LegacyReport.email)
    ).all())
    liste = json.loads(pathlib.Path("/opt/axial-intelligence/var/destinataires.json").read_text())
    return [{"email": e["email"], "prenom": e.get("prenom") or "",
             "n": counts.get(e["email"], 0)} for e in liste]


def deja_envoyes() -> set[str]:
    if not JOURNAL.exists():
        return set()
    return set(json.loads(JOURNAL.read_text()))


def noter(envoyes: set[str]) -> None:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL.write_text(json.dumps(sorted(envoyes), indent=1))


def corps_pour(d: dict) -> str:
    if d["n"] > 1:
        bloc = AVEC_RAPPORTS_PLURIEL.format(n=d["n"])
    elif d["n"] == 1:
        bloc = AVEC_RAPPORT_UN
    else:
        bloc = SANS_RAPPORT
    salutation = d["prenom"].strip() or ""
    return CORPS.format(prenom=salutation, bloc_rapports=bloc).replace("Salut ,", "Salut,")


AMORCES = (
    "Tes {n} rapports t'attendent.", "Ton rapport t'attend.",
    "Ton compte de la première version est reconnu :",
    "Et 50 crédits te sont offerts pour reprendre en main",
    "Axial se souvient de toi.", "Les réponses s'écrivent sous tes yeux.",
    "Chaque affirmation est traçable.", "Les rapports sont nettement plus profonds.",
    "Tes documents nourrissent les réponses.",
    "Des agents travaillent en continu.",
    "Nouveau : la cartographie des investisseurs.",
)


CAMPAGNE = "migration_2026_08"
BASE_PUBLIQUE = "https://app.axial-ia.fr/api"


def jeton_pour(email: str) -> str:
    """Jeton d'ouverture, créé une seule fois par destinataire et campagne."""
    import secrets

    from app.modules.emailing.models import EmailSend

    db = SessionLocal()
    existant = db.scalar(select(EmailSend).where(EmailSend.email == email,
                                                 EmailSend.campaign == CAMPAGNE))
    if existant:
        return existant.token
    jeton = secrets.token_urlsafe(24)
    db.add(EmailSend(token=jeton, email=email, campaign=CAMPAGNE))
    db.commit()
    return jeton


def en_html(texte: str, jeton: str = "") -> str:
    """Version HTML volontairement dépouillée : mêmes mots, mêmes paragraphes.

    Un pixel de suivi ne peut vivre que dans une partie HTML — mais une mise en
    page riche (images, boutons, colonnes) ferait basculer le message en onglet
    « Promotions ». On reste donc sur du texte enrichi.
    """
    import html as _h
    import re

    blocs = []
    for para in texte.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if para in ("CE QUI A CHANGÉ", "POUR REPRENDRE"):
            blocs.append(f'<p style="margin:26px 0 10px;font-weight:700;'
                         f'letter-spacing:.04em;font-size:13px;color:#555">{para}</p>')
            continue
        if para.startswith("—"):
            blocs.append(f'<p style="margin:26px 0 0;font-size:12px;color:#888">'
                         f'{_h.escape(para.lstrip("— ").strip())}</p>')
            continue
        corps = _h.escape(para)
        for amorce in AMORCES:
            motif = re.escape(_h.escape(amorce.replace("{n}", ""))).replace(
                r"\ ", r"\s*\d*\s*")
            corps = re.sub(motif, lambda m: f"<strong>{m.group(0)}</strong>", corps, count=1)
        corps = corps.replace(
            "app.axial-ia.fr",
            '<a href="https://app.axial-ia.fr" style="color:#4F46D6">app.axial-ia.fr</a>', 1)
        blocs.append(f'<p style="margin:0 0 16px">{corps}</p>')
    pixel = (f'<img src="{BASE_PUBLIQUE}/track/{jeton}.gif" width="1" height="1" '
             'alt="" style="display:block;border:0" />') if jeton else ""
    return ('<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,'
            'Helvetica,Arial,sans-serif;font-size:15px;line-height:1.6;color:#1b1d1e;'
            'max-width:600px">' + "".join(blocs) + pixel + "</div>")


def envoyer(d: dict, cle: str) -> tuple[bool, str]:
    from app.modules.emailing.models import EmailSend

    jeton = jeton_pour(d["email"])
    r = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {cle}", "Content-Type": "application/json"},
        json={"from": EXPEDITEUR, "to": [d["email"]], "subject": OBJET,
              "text": corps_pour(d), "html": en_html(corps_pour(d), jeton),
              "reply_to": "miradie.buranturu@axial-ia.fr"},
        timeout=30.0,
    )
    ok = r.status_code < 300
    info = (r.json().get("id") if ok else r.text)[:120]
    if ok:
        db = SessionLocal()
        ligne = db.scalar(select(EmailSend).where(EmailSend.token == jeton))
        if ligne is not None:
            ligne.provider_id = info
            db.commit()
    return ok, info


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--envoyer", action="store_true", help="envoyer réellement")
    p.add_argument("--lot", type=int, default=10, help="taille d'un lot")
    p.add_argument("--pause", type=int, default=60, help="secondes entre deux lots")
    args = p.parse_args()

    cle = get_settings().resend_api_key
    cibles = [d for d in destinataires() if d["email"] not in deja_envoyes()]
    avec = sum(1 for d in cibles if d["n"])
    print(f"{len(cibles)} destinataire(s) — {avec} avec rapports, {len(cibles)-avec} sans")

    if not args.envoyer:
        print("\n=== SIMULATION (aucun message ne part) ===")
        for d in cibles[:3]:
            print(f"\n--- {d['email']} ({d['n']} rapports) ---")
            print(corps_pour(d)[:400] + "…")
        print(f"\n… et {max(0, len(cibles)-3)} autre(s). Ajouter --envoyer pour expédier.")
        return

    envoyes = deja_envoyes()
    for i in range(0, len(cibles), args.lot):
        lot = cibles[i:i + args.lot]
        print(f"\n--- lot {i // args.lot + 1} ({len(lot)} messages) ---")
        for d in lot:
            ok, info = envoyer(d, cle)
            print(f"  {'OK ' if ok else 'ECHEC'} {d['email']:40} {info}")
            if ok:
                envoyes.add(d["email"])
                noter(envoyes)
            time.sleep(1)
        if i + args.lot < len(cibles):
            print(f"  pause {args.pause}s — vérifie les rebonds avant la suite")
            time.sleep(args.pause)
    print(f"\nTerminé : {len(envoyes)} adresse(s) au total dans le journal.")


if __name__ == "__main__":
    main()
