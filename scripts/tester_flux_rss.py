"""Vérifie TOUS les flux RSS (utilisateurs + catalogue) sur le vrai réseau.

Même vérification que la route admin `POST /watches/feeds/verifier`
(`service.verifier_tous`) : un `GET` réel par flux, parse feedparser, compte
des entrées, date du plus récent. Les flux utilisateurs voient leurs colonnes
`derniere_verification_at` / `derniere_erreur` mises à jour en base ; le
catalogue (`data/rss_feeds.csv`) n'est lu qu'en mémoire, jamais écrit ici —
un flux mort du catalogue se corrige à la main dans le CSV après lecture du
tableau.

    doppler run -- .venv/bin/python scripts/tester_flux_rss.py

Code de sortie 1 si au moins un flux est en erreur (utile en CI ou en
vérification manuelle avant de retoucher le catalogue).
"""
from __future__ import annotations

from app.db import SessionLocal
from app.modules.watches import service


def main() -> int:
    with SessionLocal() as db:
        resultats = service.verifier_tous(db)

    resultats.sort(key=lambda r: (r["ok"], r["url"]))  # erreurs d'abord

    largeur_url = max((len(r["url"]) for r in resultats), default=3)
    largeur_url = min(largeur_url, 70)
    en_tete = f"{'ÉTAT':<7} {'HTTP':<5} {'ENTR.':<6} {'URL':<{largeur_url}}  DERNIER / ERREUR"
    print(en_tete)
    print("-" * len(en_tete))

    en_erreur = 0
    for r in resultats:
        etat = "OK" if r["ok"] else "ERREUR"
        if not r["ok"]:
            en_erreur += 1
        url = r["url"] if len(r["url"]) <= largeur_url else r["url"][:largeur_url - 1] + "…"
        detail = r["dernier"] or "" if r["ok"] else (r["erreur"] or "erreur inconnue")
        http = str(r["statut_http"]) if r["statut_http"] is not None else "-"
        print(f"{etat:<7} {http:<5} {r['entrees']:<6} {url:<{largeur_url}}  {detail}")

    print("-" * len(en_tete))
    print(f"{len(resultats)} flux vérifiés, {en_erreur} en erreur.")
    return 1 if en_erreur else 0


if __name__ == "__main__":
    raise SystemExit(main())
