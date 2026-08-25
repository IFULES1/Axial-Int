#!/usr/bin/env python3
"""Tableau de bord des relances Axial — lecture seule sur la production.

Rapatrie l'état des campagnes email et des comptes depuis la prod (SSH+Doppler,
aucune écriture sur la base), le croise avec crm/relances.yaml (le journal des
relances manuelles), et génère une page HTML autonome que tu consultes toi-même.

    python scripts/dashboard_relances.py              # génère et ouvre la page
    python scripts/dashboard_relances.py --no-ouvrir  # génère seulement
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import subprocess
import sys
import webbrowser
from pathlib import Path

import yaml

HOTE = "hostinger"
RACINE_DISTANTE = "/opt/axial-intelligence"
RACINE = Path(__file__).resolve().parents[1]
REQUETE = RACINE / "scripts" / "_dashboard_relances_requete.py"
JOURNAL = RACINE / "crm" / "relances.yaml"
SORTIE = RACINE / "crm" / "dashboard_relances.html"

# Mêmes listes que le skill audit-activation-axial, pour rester cohérent
# d'un outil à l'autre sur ce qui compte comme un contact réel.
TEST = ("axial-qa", "example.com", "axial.com", "test.com")
INTERNE = ("axial-ia.fr", "axial-ial.fr", "skema.edu", "francedigitale.org")

SEUIL_PRECHARGEMENT_S = 90
SEUIL_LECTURE_SURE = 3
SEUIL_ESSAI_BIENTOT_J = 14
SEUIL_SILENCE_J = 7

ETAPES = ["Contacté", "Compte créé", "Profil rempli", "Carte posée",
          "Premier usage", "Usage récurrent"]

RANG_LECTURE = {"non_ouvert": 0, "prechargement_probable": 1,
                "incertain": 2, "lecture_sure": 3}
LIBELLE_LECTURE = {
    "non_ouvert": "non ouvert",
    "prechargement_probable": "pré-chargement probable",
    "incertain": "ouverture isolée, incertaine",
    "lecture_sure": "lecture sûre",
}
COULEUR_LECTURE = {
    "non_ouvert": "#9a9a9a",
    "prechargement_probable": "#c98a1f",
    "incertain": "#8a7a1f",
    "lecture_sure": "#1f7a3d",
}


# --------------------------------------------------------------------------
# Récupération des données
# --------------------------------------------------------------------------

def categorie(email: str) -> str:
    e = (email or "").lower()
    if any(t in e for t in TEST) or "test" in e.split("@")[0]:
        return "test"
    if any(i in e for i in INTERNE) or e.startswith("miradie") or e.startswith("admin@"):
        return "interne"
    return "reel"


def recuperer() -> dict:
    distant = f"{RACINE_DISTANTE}/_dashboard_relances_requete.py"
    subprocess.run(["scp", "-q", str(REQUETE), f"{HOTE}:{distant}"], check=True)
    try:
        out = subprocess.run(
            ["ssh", HOTE,
             f"cd {RACINE_DISTANTE} && PYTHONPATH={RACINE_DISTANTE} doppler run "
             f"--config prd -- .venv/bin/python {distant}; rm -f {distant}"],
            capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        sys.exit("Requête distante : délai dépassé (VPS injoignable ?)")
    if "---JSON---" not in out.stdout:
        sys.exit("Requête distante impossible :\n" + (out.stderr or out.stdout)[-1500:])
    return json.loads(out.stdout.split("---JSON---", 1)[1].strip())


def charger_journal() -> dict[str, list[dict]]:
    if not JOURNAL.exists():
        return {}
    brut = yaml.safe_load(JOURNAL.read_text(encoding="utf-8")) or []
    par_email: dict[str, list[dict]] = {}
    for entree in brut:
        par_email.setdefault(entree["email"].lower(), []).append(entree)
    for entrees in par_email.values():
        entrees.sort(key=lambda e: e["date"])
    return par_email


# --------------------------------------------------------------------------
# Calculs
# --------------------------------------------------------------------------

def parse_iso(s: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(s) if s else None


def classer_ouverture(envoye: str | None, ouvert: str | None, fois: int) -> str:
    if not ouvert or not fois:
        return "non_ouvert"
    if fois >= SEUIL_LECTURE_SURE:
        return "lecture_sure"
    s, o = parse_iso(envoye), parse_iso(ouvert)
    if s and o and (o - s).total_seconds() <= SEUIL_PRECHARGEMENT_S:
        return "prechargement_probable"
    return "incertain"


def etape_tunnel(u: dict | None) -> int:
    if not u:
        return 1
    if (u.get("jours_actifs") or 0) >= 2:
        return 6
    if u.get("messages") or u.get("rapports"):
        return 5
    if u.get("abo") in ("trialing", "active"):
        return 4
    if u.get("profil"):
        return 3
    return 2


def construire(data: dict, journal: dict[str, list[dict]]) -> dict:
    users_par_email = {u["email"]: u for u in data["users"].values()}

    contacts: dict[str, dict] = {}
    for e in data["email_sends"]:
        email = e["email"].lower()
        c = contacts.setdefault(
            email, {"email": email, "envois": [], "cat": categorie(email)})
        c["envois"].append({**e, "statut": classer_ouverture(e["envoye"], e["ouvert"], e["fois"])})

    for email, c in contacts.items():
        c["envois"].sort(key=lambda e: e["envoye"] or "")
        c["statut_lecture"] = max((e["statut"] for e in c["envois"]),
                                   key=lambda s: RANG_LECTURE[s])
        u = users_par_email.get(email)
        c["utilisateur"] = u
        c["inscrit"] = u is not None
        c["etape"] = etape_tunnel(u)
        rel = journal.get(email, [])
        c["derniere_relance"] = rel[-1] if rel else None
        c["nb_relances"] = len(rel)

    return {"contacts": contacts, "users_par_email": users_par_email}


def calculer_alertes(construit: dict, journal: dict[str, list[dict]],
                      aujourdhui: dt.date) -> dict:
    contacts = construit["contacts"]
    users_par_email = construit["users_par_email"]

    essais = []
    for email, u in users_par_email.items():
        if categorie(email) != "reel":
            continue
        if u.get("abo") not in ("trialing", "active") or not u.get("fin_essai"):
            continue
        fin_date = parse_iso(u["fin_essai"]).date()
        j = (fin_date - aujourdhui).days
        if j <= SEUIL_ESSAI_BIENTOT_J:
            essais.append({"email": email, "fin": fin_date.isoformat(), "jours": j,
                            "annule": bool(u.get("annule"))})
    essais.sort(key=lambda x: x["jours"])

    promesses = []
    for email, entrees in journal.items():
        derniere = entrees[-1]
        ech = derniere.get("echeance")
        if ech and dt.date.fromisoformat(ech) < aujourdhui:
            promesses.append({
                "email": email, "echeance": ech,
                "prochaine_action": derniere.get("prochaine_action", ""),
                "jours_retard": (aujourdhui - dt.date.fromisoformat(ech)).days})
    promesses.sort(key=lambda x: -x["jours_retard"])

    tiedes = [
        {"email": email, "campagnes": sorted({e["campagne"] for e in c["envois"]})}
        for email, c in contacts.items()
        if c["statut_lecture"] == "lecture_sure" and not c["inscrit"] and not c["nb_relances"]
    ]

    silencieux = []
    for email, u in users_par_email.items():
        if categorie(email) != "reel":
            continue
        if not (u.get("messages") or u.get("rapports")) or not u.get("derniere_activite"):
            continue
        j_silence = (aujourdhui - parse_iso(u["derniere_activite"]).date()).days
        if j_silence < SEUIL_SILENCE_J:
            continue
        rel = journal.get(email, [])
        if rel and (aujourdhui - dt.date.fromisoformat(rel[-1]["date"])).days < SEUIL_SILENCE_J:
            continue
        silencieux.append({"email": email, "jours_silence": j_silence})
    silencieux.sort(key=lambda x: -x["jours_silence"])

    return {"essais": essais, "promesses": promesses, "tiedes": tiedes, "silencieux": silencieux}


# --------------------------------------------------------------------------
# Rendu HTML
# --------------------------------------------------------------------------

def e(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def rendre_alertes(al: dict) -> str:
    blocs = []
    if al["essais"]:
        lignes = "".join(
            f"<li><b>{e(x['email'])}</b> — essai fin {e(x['fin'])} "
            f"({x['jours']} j) {'· annulation déjà programmée' if x['annule'] else ''}</li>"
            for x in al["essais"])
        blocs.append(f"<h3>⏳ Essais qui expirent (≤{SEUIL_ESSAI_BIENTOT_J} j)</h3><ul>{lignes}</ul>")
    if al["promesses"]:
        lignes = "".join(
            f"<li><b>{e(x['email'])}</b> — échéance {e(x['echeance'])} dépassée depuis "
            f"{x['jours_retard']} j : « {e(x['prochaine_action'])} »</li>"
            for x in al["promesses"])
        blocs.append(f"<h3>📌 Relances promises, pas encore faites</h3><ul>{lignes}</ul>")
    if al["tiedes"]:
        lignes = "".join(
            f"<li><b>{e(x['email'])}</b> — lu plusieurs fois ({', '.join(x['campagnes'])}), "
            f"jamais recontacté, pas inscrit</li>"
            for x in al["tiedes"])
        blocs.append(f"<h3>🔥 Contacts tièdes jamais recontactés</h3><ul>{lignes}</ul>")
    if al["silencieux"]:
        lignes = "".join(
            f"<li><b>{e(x['email'])}</b> — silencieux depuis {x['jours_silence']} j</li>"
            for x in al["silencieux"])
        blocs.append(f"<h3>💤 Comptes engagés, maintenant silencieux</h3><ul>{lignes}</ul>")
    if not blocs:
        return '<p class="ok">Rien à signaler aujourd\'hui.</p>'
    return "\n".join(blocs)


def rendre_tunnel(contacts: dict) -> str:
    reels = {em: c for em, c in contacts.items() if c["cat"] == "reel"}
    comptes = {em: c for em, c in reels.items() if c["inscrit"]}
    n = [len(reels)]
    for i in range(2, 7):
        n.append(sum(1 for c in comptes.values() if c["etape"] >= i))
    lignes = []
    precedent = None
    for nom, val in zip(ETAPES, n):
        taux = f" ({val / precedent * 100:.0f}%)" if precedent else ""
        largeur = int(val / max(n[0], 1) * 100)
        lignes.append(
            f'<div class="barre-ligne"><span class="barre-nom">{e(nom)}</span>'
            f'<div class="barre-fond"><div class="barre-remplie" style="width:{largeur}%"></div></div>'
            f'<span class="barre-val">{val}{taux}</span></div>')
        precedent = val
    return "\n".join(lignes)


def rendre_campagnes(contacts: dict) -> str:
    par_campagne: dict[str, dict] = {}
    for c in contacts.values():
        if c["cat"] != "reel":
            continue
        for env in c["envois"]:
            pc = par_campagne.setdefault(env["campagne"], {"n": 0, "ouverts": 0, "surs": 0})
            pc["n"] += 1
            if env["statut"] != "non_ouvert":
                pc["ouverts"] += 1
            if env["statut"] == "lecture_sure":
                pc["surs"] += 1
    lignes = "".join(
        f"<tr><td>{e(camp)}</td><td>{v['n']}</td>"
        f"<td>{v['ouverts']} ({v['ouverts']/v['n']*100:.0f}%)</td>"
        f"<td>{v['surs']} ({v['surs']/v['n']*100:.0f}%)</td></tr>"
        for camp, v in sorted(par_campagne.items()))
    return (
        "<table><thead><tr><th>Campagne</th><th>Envoyés</th>"
        "<th>Ouverts</th><th>Lectures sûres</th></tr></thead>"
        f"<tbody>{lignes}</tbody></table>")


def rendre_table(contacts: dict) -> str:
    lignes = []
    for c in sorted(contacts.values(), key=lambda c: c["envois"][0]["envoye"] or ""):
        if c["cat"] != "reel":
            continue
        campagnes = ", ".join(sorted({env["campagne"] for env in c["envois"]}))
        envoye = (c["envois"][0]["envoye"] or "")[:10]
        statut = c["statut_lecture"]
        rel = c["derniere_relance"]
        rel_txt = f"{rel['date']} ({rel['canal']}) : {e(rel.get('resume',''))}" if rel else "—"
        lignes.append(
            "<tr data-lecture='{st}' data-inscrit='{ins}'>"
            "<td>{email}</td><td>{camp}</td><td>{env}</td>"
            "<td><span class='pastille' style='background:{coul}'></span>{lib}</td>"
            "<td>{ins_txt}</td><td>{etape}</td><td>{rel}</td></tr>".format(
                st=statut, ins="oui" if c["inscrit"] else "non",
                email=e(c["email"]), camp=e(campagnes), env=e(envoye),
                coul=COULEUR_LECTURE[statut], lib=LIBELLE_LECTURE[statut],
                ins_txt="oui" if c["inscrit"] else "non",
                etape=e(ETAPES[c["etape"] - 1]), rel=rel_txt))
    return "".join(lignes)


def rendre_journal(journal: dict[str, list[dict]]) -> str:
    toutes = [(email, ent) for email, ents in journal.items() for ent in ents]
    toutes.sort(key=lambda x: x[1]["date"], reverse=True)
    if not toutes:
        return "<p>Aucune relance manuelle consignée pour l'instant.</p>"
    lignes = "".join(
        f"<tr><td>{e(ent['date'])}</td><td>{e(email)}</td><td>{e(ent['canal'])}</td>"
        f"<td>{e(ent['resume'])}</td>"
        f"<td>{e(ent.get('prochaine_action',''))}"
        f"{' (avant ' + e(ent['echeance']) + ')' if ent.get('echeance') else ''}</td></tr>"
        for email, ent in toutes)
    return (
        "<table><thead><tr><th>Date</th><th>Email</th><th>Canal</th>"
        "<th>Résumé</th><th>Prochaine action</th></tr></thead>"
        f"<tbody>{lignes}</tbody></table>")


PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>Suivi des relances — Axial</title>
<style>
  body {{ font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
          max-width: 980px; margin: 2rem auto; padding: 0 1.5rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 2.5rem; border-bottom: 1px solid #ddd; padding-bottom: .3rem; }}
  h3 {{ font-size: .95rem; margin-bottom: .3rem; }}
  .meta {{ color: #666; font-size: .85rem; }}
  .resume {{ font-size: 1.05rem; margin: .5rem 0 1rem; }}
  .alertes {{ background: #fff6ea; border: 1px solid #f0d9a8; border-radius: 8px; padding: 1rem 1.5rem; }}
  .alertes h3 {{ margin-top: 1rem; }}
  .alertes ul {{ margin: .3rem 0; padding-left: 1.2rem; }}
  .ok {{ color: #1f7a3d; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .85rem; margin-top: .5rem; }}
  th, td {{ text-align: left; padding: .35rem .6rem; border-bottom: 1px solid #eee; }}
  th {{ color: #666; font-weight: 600; }}
  .pastille {{ display: inline-block; width: .6rem; height: .6rem; border-radius: 50%;
               margin-right: .4rem; }}
  .barre-ligne {{ display: flex; align-items: center; gap: .6rem; margin: .3rem 0; font-size: .85rem; }}
  .barre-nom {{ width: 9rem; flex-shrink: 0; }}
  .barre-fond {{ flex: 1; background: #eee; border-radius: 4px; height: .8rem; overflow: hidden; }}
  .barre-remplie {{ background: #4a7fd6; height: 100%; }}
  .barre-val {{ width: 5rem; text-align: right; flex-shrink: 0; color: #555; }}
  select {{ margin: .3rem .3rem .3rem 0; padding: .2rem .4rem; }}
  footer {{ margin-top: 3rem; color: #999; font-size: .75rem; }}
</style></head>
<body>
<h1>Suivi des relances — Axial Intelligence</h1>
<p class="meta">Généré le {genere}</p>
<p class="resume">{resume}</p>

<h2>Actions requises</h2>
<div class="alertes">{alertes}</div>

<h2>Tunnel (contacts réels uniquement)</h2>
{tunnel}

<h2>Par campagne</h2>
{campagnes}

<h2>Contacts</h2>
<label>Lecture :
  <select id="f-lecture" onchange="filtrer()">
    <option value="">toutes</option>
    <option value="lecture_sure">lecture sûre</option>
    <option value="prechargement_probable">pré-chargement probable</option>
    <option value="incertain">incertain</option>
    <option value="non_ouvert">non ouvert</option>
  </select>
</label>
<label>Inscrit :
  <select id="f-inscrit" onchange="filtrer()">
    <option value="">tous</option>
    <option value="oui">oui</option>
    <option value="non">non</option>
  </select>
</label>
<table><thead><tr><th>Email</th><th>Campagne(s)</th><th>Envoyé le</th>
<th>Lecture</th><th>Inscrit</th><th>Étape</th><th>Dernière relance</th></tr></thead>
<tbody id="table-contacts">{table}</tbody></table>

<h2>Journal des relances manuelles</h2>
{journal}

<footer>Lecture seule sur la production · aucune donnée envoyée hors de cette machine ·
seuils : pré-chargement &lt; {seuil_s}s, lecture sûre ≥ {seuil_n} ouvertures</footer>

<script>
function filtrer() {{
  var l = document.getElementById('f-lecture').value;
  var i = document.getElementById('f-inscrit').value;
  document.querySelectorAll('#table-contacts tr').forEach(function(tr) {{
    var okL = !l || tr.dataset.lecture === l;
    var okI = !i || tr.dataset.inscrit === i;
    tr.style.display = (okL && okI) ? '' : 'none';
  }});
}}
</script>
</body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-ouvrir", action="store_true",
                     help="générer le fichier sans ouvrir le navigateur")
    args = ap.parse_args()

    data = recuperer()
    journal = charger_journal()
    construit = construire(data, journal)
    aujourdhui = dt.datetime.now(dt.timezone.utc).date()
    al = calculer_alertes(construit, journal, aujourdhui)

    contacts = construit["contacts"]
    reels = {em: c for em, c in contacts.items() if c["cat"] == "reel"}
    n_inscrits = sum(1 for c in reels.values() if c["inscrit"])
    n_actifs = sum(1 for c in reels.values() if c["etape"] == 6)
    resume = (f"{len(reels)} contactés → {n_inscrits} comptes → {n_actifs} actif(s) · "
              f"{len(al['essais'])} essai(s) à surveiller · "
              f"{len(al['promesses'])} promesse(s) en retard")

    page = PAGE.format(
        genere=aujourdhui.isoformat(),
        resume=e(resume),
        alertes=rendre_alertes(al),
        tunnel=rendre_tunnel(contacts),
        campagnes=rendre_campagnes(contacts),
        table=rendre_table(contacts),
        journal=rendre_journal(journal),
        seuil_s=SEUIL_PRECHARGEMENT_S,
        seuil_n=SEUIL_LECTURE_SURE,
    )
    SORTIE.write_text(page, encoding="utf-8")
    print(f"Généré : {SORTIE}")
    if not args.no_ouvrir:
        webbrowser.open(f"file://{SORTIE}")


if __name__ == "__main__":
    main()
