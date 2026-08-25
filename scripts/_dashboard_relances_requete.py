"""Requête lecture seule exécutée sur le VPS (via SSH+Doppler) par
dashboard_relances.py. Aucune écriture. Copié sur le VPS, exécuté, supprimé.
"""
import datetime as dt
import json

from sqlalchemy import text

from app.db import SessionLocal

db = SessionLocal()


def rows(sql, **p):
    return list(db.execute(text(sql), p))


users = {
    str(i): {"email": e.lower(), "cree": c.isoformat() if c else None}
    for i, e, c in rows("SELECT id, email, created_at FROM auth.users")
}

for uid, nom in rows("SELECT user_id, company_name FROM company_profiles"):
    if str(uid) in users:
        users[str(uid)]["profil"] = bool(nom)

for uid, statut, plan, fin, annule in rows(
        "SELECT user_id, status, plan_key, current_period_end, "
        "cancel_at_period_end FROM user_subscriptions"):
    if str(uid) in users:
        users[str(uid)]["abo"] = statut
        users[str(uid)]["plan"] = plan
        users[str(uid)]["fin_essai"] = fin.isoformat() if fin else None
        users[str(uid)]["annule"] = bool(annule)

for uid, n in rows("""SELECT c.user_id, count(m.id) FROM conversations c
                      JOIN messages m ON m.conversation_id = c.id AND m.role='user'
                      GROUP BY c.user_id"""):
    if str(uid) in users:
        users[str(uid)]["messages"] = n

for uid, n in rows("SELECT user_id, count(*) FROM reports GROUP BY user_id"):
    if str(uid) in users:
        users[str(uid)]["rapports"] = n

for uid, n, jours, dernier in rows("""
        SELECT user_id, count(*), count(DISTINCT date_trunc('day', created_at)),
               max(created_at)
        FROM credit_events WHERE delta < 0 GROUP BY user_id"""):
    if str(uid) in users:
        users[str(uid)]["debits"] = n
        users[str(uid)]["jours_actifs"] = jours
        users[str(uid)]["derniere_activite"] = dernier.isoformat() if dernier else None

email_sends = [
    {"email": e, "campagne": c, "envoye": s.isoformat() if s else None,
     "ouvert": o.isoformat() if o else None, "fois": n or 0}
    for e, c, s, o, n in rows(
        "SELECT email, campaign, sent_at, opened_at, open_count FROM email_sends "
        "ORDER BY sent_at")
]

suppressions = [
    {"email": e, "motif": r, "cree": c.isoformat() if c else None}
    for e, r, c in rows(
        "SELECT email, reason, created_at FROM email_suppressions ORDER BY created_at")
]

print("---JSON---")
print(json.dumps({
    "users": users, "email_sends": email_sends, "suppressions": suppressions,
    "maintenant": dt.datetime.now(dt.timezone.utc).isoformat(),
}, ensure_ascii=False))
