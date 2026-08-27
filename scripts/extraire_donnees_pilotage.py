"""Extraction de toutes les données de pilotage, en lecture seule."""
import json, sys
sys.path.insert(0, '/opt/axial-intelligence')
from sqlalchemy import text
from app.db import SessionLocal

db = SessionLocal()
def rows(sql, **p):
    return [dict(r) for r in db.execute(text(sql), p).mappings().all()]

INTERNES = "u.email NOT LIKE '%axial-ia.fr' AND u.email NOT LIKE '%axial.com' AND u.email NOT LIKE '%axial-qa.fr' AND u.email NOT LIKE '%skema.edu' AND u.email NOT LIKE '%francedigitale.org'"

data = {}

data["utilisateurs"] = rows(f"""
SELECT u.email,
       u.created_at::date::text                          AS inscrit_le,
       u.last_sign_in_at::date::text                     AS derniere_connexion,
       CASE WHEN {INTERNES} THEN 'client' ELSE 'interne' END AS categorie,
       cp.company_name, cp.sector, cp.funding_stage, cp.target_market, cp.language,
       (SELECT count(*) FROM auth.sessions s WHERE s.user_id=u.id) AS sessions,
       (SELECT count(*) FROM reports r WHERE r.user_id=u.id) AS rapports_total,
       (SELECT count(*) FROM reports r WHERE r.user_id=u.id
          AND NOT EXISTS (SELECT 1 FROM legacy_reports l WHERE l.imported_for=u.id
                          AND l.title=left(r.title,500))) AS rapports_produits,
       (SELECT count(*) FROM conversations c JOIN messages m ON m.conversation_id=c.id
          AND m.role='user' WHERE c.user_id=u.id) AS questions,
       (SELECT count(*) FROM documents d WHERE d.user_id=u.id) AS documents,
       (SELECT count(*) FROM user_connections k WHERE k.user_id=u.id) AS outils,
       (SELECT count(*) FROM watches w WHERE w.user_id=u.id) AS veilles,
       COALESCE(b.trial_credits+b.free_credits+b.purchased_credits,0) AS solde_credits,
       b.trial_expires_at::date::text AS essai_expire_le,
       COALESCE(s.status,'aucun') AS abonnement,
       s.cancel_at_period_end AS renouvellement_bloque
FROM auth.users u
LEFT JOIN company_profiles cp ON cp.user_id=u.id
LEFT JOIN credit_balances b ON b.user_id=u.id
LEFT JOIN user_subscriptions s ON s.user_id=u.id
ORDER BY u.created_at""")

data["rapports"] = rows("""
SELECT u.email, r.created_at::text AS produit_le, r.analysis_type AS type,
       length(r.content) AS caracteres,
       CASE WHEN jsonb_typeof(r.sources::jsonb) = 'array'
            THEN jsonb_array_length(r.sources::jsonb) ELSE 0 END AS sources,
       r.duree_secondes, r.modele, r.tokens_entree, r.tokens_sortie,
       ROUND(COALESCE(r.cout_micro_eur,0)/1000000.0, 4) AS cout_modele_eur,
       ROUND(COALESCE(r.cout_recherche_micro_eur,0)/1000000.0, 4) AS cout_recherche_eur,
       r.appels_recherche,
       EXISTS (SELECT 1 FROM legacy_reports l WHERE l.imported_for=r.user_id
               AND l.title=left(r.title,500)) AS restaure
FROM reports r JOIN auth.users u ON u.id=r.user_id ORDER BY r.created_at""")

data["emails"] = rows("""
SELECT campaign AS campagne, count(*) AS envoyes,
       count(opened_at) AS ouvertures_apparentes,
       count(*) FILTER (WHERE open_count >= 3) AS lectures_reelles,
       count(*) FILTER (WHERE opened_at IS NULL) AS jamais_ouverts,
       min(sent_at)::date::text AS premier_envoi
FROM email_sends GROUP BY campaign ORDER BY min(sent_at)""")

data["revenus"] = rows("""
SELECT u.email, s.plan_key AS plan, s.status AS statut,
       s.cancel_at_period_end AS annule_en_fin_de_periode,
       s.current_period_end::date::text AS fin_periode,
       s.stripe_subscription_id IS NOT NULL AS stripe_reel
FROM user_subscriptions s JOIN auth.users u ON u.id=s.user_id""")

data["credits"] = rows("""
SELECT u.email, e.action, e.delta, e.created_at::date::text AS le
FROM credit_events e JOIN auth.users u ON u.id=e.user_id ORDER BY e.created_at""")

data["couts_agreges"] = rows("""
SELECT 'rapports' AS poste, count(*) AS lignes, count(cout_micro_eur) AS mesurees,
       ROUND(COALESCE(sum(cout_micro_eur),0)/1000000.0,4) AS cout_modele_eur,
       ROUND(COALESCE(sum(cout_recherche_micro_eur),0)/1000000.0,4) AS cout_recherche_eur
FROM reports
UNION ALL SELECT 'conversations', count(*), count(cout_micro_eur),
       ROUND(COALESCE(sum(cout_micro_eur),0)/1000000.0,4), 0 FROM messages
UNION ALL SELECT 'veilles', count(*), count(cout_micro_eur),
       ROUND(COALESCE(sum(cout_micro_eur),0)/1000000.0,4),
       ROUND(COALESCE(sum(cout_recherche_micro_eur),0)/1000000.0,4) FROM watch_runs""")

print("---JSON---")
print(json.dumps(data, ensure_ascii=False, default=str))
