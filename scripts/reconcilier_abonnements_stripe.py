"""Compare chaque abonnement de l'app à son état réel chez Stripe.

    python scripts/reconcilier_abonnements_stripe.py              # liste les écarts, n'écrit rien
    python scripts/reconcilier_abonnements_stripe.py --appliquer  # recopie l'état Stripe

Rattrape les changements survenus avant que le webhook ne traite les
résiliations et les impayés (01/10/2026) : Stripe ne renvoie pas les
événements passés, seul un relevé de l'état actuel les remet d'équerre.
Ne touche ni aux crédits ni à Stripe : seul le miroir `user_subscriptions`
est réécrit, et seulement avec `--appliquer`.
"""
import argparse
import sys

sys.path.insert(0, "/opt/axial-intelligence")
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.modules.billing import service, stripe_gateway  # noqa: E402

CHAMPS = ("status", "cancel_at_period_end", "current_period_end")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--appliquer", action="store_true")
    args = ap.parse_args()

    with SessionLocal() as db:
        lignes = db.execute(text("""
            SELECT s.user_id::text AS user_id, u.email, s.stripe_subscription_id,
                   s.status, s.cancel_at_period_end, s.current_period_end
            FROM user_subscriptions s JOIN auth.users u ON u.id = s.user_id
            WHERE s.stripe_subscription_id IS NOT NULL
            ORDER BY u.email
        """)).mappings().all()

        ecarts = 0
        for l in lignes:
            etat = stripe_gateway.fetch_subscription_state(l["stripe_subscription_id"])
            if etat is None:
                print(f"  ?  {l['email']:40} abonnement introuvable chez Stripe")
                continue
            diff = {c: (l[c], etat.get(c)) for c in CHAMPS if l[c] != etat.get(c)}
            if not diff:
                print(f"  =  {l['email']:40} {l['status']}")
                continue
            ecarts += 1
            detail = " ; ".join(f"{c} : {a} → {b}" for c, (a, b) in diff.items())
            print(f"  ≠  {l['email']:40} {detail}")
            if args.appliquer:
                service.upsert_subscription(db, l["user_id"], **etat)
                print("     corrigé")

        print(f"\n{len(lignes)} abonnement(s) Stripe, {ecarts} écart(s)"
              + ("" if args.appliquer or not ecarts else " — relancer avec --appliquer pour corriger"))


if __name__ == "__main__":
    main()
