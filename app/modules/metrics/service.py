"""Métriques de pilotage : coûts, rentabilité, activité.

Une seule requête par bloc, calculée en base plutôt qu'en Python : à mesure que
le volume monte, remonter toutes les lignes pour les additionner ici deviendrait
le goulot d'étranglement du tableau de bord.

Les rapports antérieurs au 25/08 n'ont pas de coût mesuré. Ils sont comptés
séparément — les inclure à zéro ferait croire à une marge parfaite.
"""
from __future__ import annotations

from sqlalchemy import text

# Valeur d'un crédit, déduite du catalogue : Pro = 50 € pour 120 crédits.
# Sert à valoriser une consommation qui n'a pas donné lieu à un paiement direct.
EURO_PAR_CREDIT = 50 / 120

INTERNES = ("%axial-ia.fr", "%axial.com", "%axial-qa.fr", "%skema.edu",
            "%francedigitale.org")


def _clause_externes(alias: str = "u") -> str:
    return " AND ".join(f"{alias}.email NOT LIKE '{m}'" for m in INTERNES)


def couts(db, jours: int = 30) -> dict:
    r = db.execute(text("""
        SELECT
          count(*)                                   AS rapports,
          count(cout_micro_eur)                      AS rapports_mesures,
          COALESCE(sum(cout_micro_eur), 0)           AS cout_micro,
          COALESCE(avg(cout_micro_eur), 0)           AS cout_moyen_micro,
          COALESCE(max(cout_micro_eur), 0)           AS cout_max_micro,
          COALESCE(avg(duree_secondes), 0)           AS duree_moyenne,
          COALESCE(sum(tokens_entree), 0)            AS tokens_entree,
          COALESCE(sum(tokens_sortie), 0)            AS tokens_sortie
        FROM reports r
        WHERE r.created_at > now() - make_interval(days => :j)
    """), {"j": jours}).mappings().first()
    d = {k: (float(v) if hasattr(v, "as_integer_ratio") or str(type(v)).endswith("Decimal'>") else v)
         for k, v in dict(r).items()}
    d["cout_eur"] = round(d["cout_micro"] / 1_000_000, 2)
    d["cout_moyen_eur"] = round(d["cout_moyen_micro"] / 1_000_000, 4)
    d["cout_max_eur"] = round(d["cout_max_micro"] / 1_000_000, 4)
    d["duree_moyenne"] = int(d["duree_moyenne"])
    d["rapports"] = int(d["rapports"])
    d["rapports_mesures"] = int(d["rapports_mesures"])
    d["non_mesures"] = d["rapports"] - d["rapports_mesures"]
    return d


def par_type(db, jours: int = 30) -> list[dict]:
    """Coût réel par type de rapport, confronté à son prix affiché."""
    from app.modules.billing.catalog import cost_for

    lignes = db.execute(text("""
        SELECT analysis_type,
               count(*)                         AS n,
               count(cout_micro_eur)            AS mesures,
               COALESCE(avg(cout_micro_eur), 0) AS moyen_micro
        FROM reports
        WHERE created_at > now() - make_interval(days => :j)
        GROUP BY analysis_type ORDER BY n DESC
    """), {"j": jours}).mappings().all()
    out = []
    for r in lignes:
        # avg() renvoie un Decimal : le mélanger à un float lève un TypeError.
        # On normalise ici, à la frontière de la base.
        cout = round(float(r["moyen_micro"] or 0) / 1_000_000, 4)
        credits = cost_for(r["analysis_type"])
        revenu = round(credits * EURO_PAR_CREDIT, 2)
        # Sans coût mesuré, une marge de 100 % serait un mensonge : on n'affiche
        # pas de marge plutôt que d'en afficher une fausse.
        mesure = int(r["mesures"] or 0) > 0
        out.append({
            "type": r["analysis_type"], "n": int(r["n"]), "mesures": int(r["mesures"] or 0),
            "cout_moyen_eur": cout if mesure else None,
            "credits": credits, "revenu_eur": revenu,
            "marge_eur": round(revenu - cout, 2) if mesure else None,
            "marge_pct": (round(100 * (revenu - cout) / revenu, 1)
                          if mesure and revenu else None),
        })
    return out


def revenus(db) -> dict:
    """Ce qui est réellement encaissé, distinct de ce qui est consommé."""
    r = db.execute(text("""
        SELECT
          count(*) FILTER (WHERE status = 'active')   AS abonnes,
          count(*) FILTER (WHERE status = 'trialing') AS essais,
          count(*) FILTER (WHERE status = 'trialing'
                             AND cancel_at_period_end) AS essais_annules,
          count(*) FILTER (WHERE status = 'past_due')  AS impayes
        FROM user_subscriptions
    """)).mappings().first()
    d = dict(r)
    # 50 €/mois : le seul plan payant réellement souscrit à ce jour.
    d["mrr_eur"] = d["abonnes"] * 50
    d["mrr_potentiel_eur"] = (d["essais"] - d["essais_annules"]) * 50
    return d


def activite(db, jours: int = 30) -> dict:
    ext = _clause_externes()
    r = db.execute(text(f"""
        SELECT
          (SELECT count(*) FROM auth.users u WHERE {ext})                       AS comptes,
          (SELECT count(*) FROM auth.users u WHERE {ext}
             AND u.created_at > now() - make_interval(days => :j))              AS nouveaux,
          (SELECT count(DISTINCT r.user_id) FROM reports r
             JOIN auth.users u ON u.id = r.user_id WHERE {ext}
             AND r.created_at > now() - make_interval(days => :j))              AS actifs_rapport,
          (SELECT count(DISTINCT c.user_id) FROM conversations c
             JOIN messages m ON m.conversation_id = c.id AND m.role = 'user'
             JOIN auth.users u ON u.id = c.user_id WHERE {ext}
             AND m.created_at > now() - make_interval(days => :j))              AS actifs_question,
          (SELECT count(*) FROM company_profiles cp
             JOIN auth.users u ON u.id = cp.user_id
             WHERE {ext} AND cp.company_name IS NOT NULL)                       AS profils_remplis
    """), {"j": jours}).mappings().first()
    d = dict(r)
    d["actifs"] = max(d["actifs_rapport"], d["actifs_question"])
    d["taux_activation"] = (round(100 * d["actifs"] / d["comptes"], 1)
                            if d["comptes"] else 0)
    return d


def delai_premier_rapport(db) -> dict:
    """Temps entre l'inscription et le premier rapport réellement produit.

    C'est la métrique d'activation la plus honnête : elle ne compte ni les
    rapports restaurés de l'ancienne app, ni les comptes internes.
    """
    ext = _clause_externes()
    r = db.execute(text(f"""
        WITH premiers AS (
          SELECT u.id, u.created_at AS inscrit,
                 min(r.created_at) AS premier
          FROM auth.users u
          LEFT JOIN reports r ON r.user_id = u.id
               AND NOT EXISTS (SELECT 1 FROM legacy_reports l
                               WHERE l.imported_for = u.id
                                 AND l.title = left(r.title, 500))
          WHERE {ext}
          GROUP BY u.id, u.created_at
        )
        SELECT count(*) FILTER (WHERE premier IS NOT NULL) AS avec,
               count(*) FILTER (WHERE premier IS NULL)     AS sans,
               COALESCE(avg(EXTRACT(EPOCH FROM (premier - inscrit)))
                        FILTER (WHERE premier IS NOT NULL), 0) AS moyenne_s
        FROM premiers
    """)).mappings().first()
    d = dict(r)
    d["moyenne_s"] = float(d["moyenne_s"] or 0)
    d["moyenne_heures"] = round(d["moyenne_s"] / 3600, 1)
    return d


def couts_totaux(db, jours: int = 30) -> dict:
    """Coût complet : rapports + conversations + veilles + structure.

    Chaque poste porte son nombre de lignes mesurées : un total calculé sur
    une base partiellement instrumentée doit dire sur quoi il porte, sinon il
    se lit comme un total réel.
    """
    from app.config import get_settings

    postes = {}
    for nom, table in (("rapports", "reports"), ("conversations", "messages"),
                       ("veilles", "watch_runs")):
        r = db.execute(text(f"""
            SELECT count(*) AS lignes,
                   count(cout_micro_eur) AS mesurees,
                   COALESCE(sum(cout_micro_eur), 0) AS modele_micro,
                   COALESCE(sum({'cout_recherche_micro_eur'
                                 if table != 'messages' else '0'}), 0) AS recherche_micro
            FROM {table}
            WHERE created_at > now() - make_interval(days => :j)
        """), {"j": jours}).mappings().first()
        modele = float(r["modele_micro"] or 0)
        recherche = float(r["recherche_micro"] or 0)
        postes[nom] = {
            "lignes": int(r["lignes"]), "mesurees": int(r["mesurees"] or 0),
            "cout_modele_eur": round(modele / 1_000_000, 4),
            "cout_recherche_eur": round(recherche / 1_000_000, 4),
            "cout_eur": round((modele + recherche) / 1_000_000, 4),
        }

    variable = round(sum(p["cout_eur"] for p in postes.values()), 4)
    fixe = get_settings().couts_fixes_mensuels_eur or 0.0
    # Ramené à la fenêtre : comparer un coût fixe mensuel à 7 jours de coût
    # variable donnerait un total qui ne veut rien dire.
    fixe_fenetre = round(fixe * jours / 30, 2) if fixe else None
    return {
        "postes": postes,
        "variable_eur": variable,
        "fixe_mensuel_eur": fixe or None,
        "fixe_sur_fenetre_eur": fixe_fenetre,
        "total_eur": round(variable + (fixe_fenetre or 0), 2) if fixe else None,
        "point_mort_abonnes": (int(-(-fixe // 50)) if fixe else None),
        "instrumentation_complete": all(
            p["lignes"] == p["mesurees"] for p in postes.values()),
    }


def tableau(db, jours: int = 30) -> dict:
    return {
        "fenetre_jours": jours,
        "couts": couts(db, jours),
        "couts_totaux": couts_totaux(db, jours),
        "par_type": par_type(db, jours),
        "revenus": revenus(db),
        "activite": activite(db, jours),
        "premier_rapport": delai_premier_rapport(db),
        "euro_par_credit": round(EURO_PAR_CREDIT, 4),
    }


# ---------------------------------------------------------------- export brut
# Une seule définition des requêtes d'export, partagée par l'API et le script
# d'extraction : deux copies divergeraient à la première évolution du schéma.

_CLAUSE_INTERNES = (
    "u.email NOT LIKE '%axial-ia.fr' AND u.email NOT LIKE '%axial.com' "
    "AND u.email NOT LIKE '%axial-qa.fr' AND u.email NOT LIKE '%skema.edu' "
    "AND u.email NOT LIKE '%francedigitale.org'"
)

_REQUETES = {
    "utilisateurs": f"""
        SELECT u.email,
               u.created_at::date::text AS inscrit_le,
               u.last_sign_in_at::date::text AS derniere_connexion,
               CASE WHEN {_CLAUSE_INTERNES} THEN 'client' ELSE 'interne' END AS categorie,
               cp.company_name, cp.sector, cp.funding_stage, cp.target_market, cp.language,
               (SELECT count(*) FROM auth.sessions s WHERE s.user_id = u.id) AS sessions,
               (SELECT count(*) FROM reports r WHERE r.user_id = u.id) AS rapports_total,
               (SELECT count(*) FROM reports r WHERE r.user_id = u.id
                  AND NOT EXISTS (SELECT 1 FROM legacy_reports l
                                  WHERE l.imported_for = u.id
                                    AND l.title = left(r.title, 500))) AS rapports_produits,
               (SELECT count(*) FROM conversations c
                  JOIN messages m ON m.conversation_id = c.id AND m.role = 'user'
                  WHERE c.user_id = u.id) AS questions,
               (SELECT count(*) FROM documents d WHERE d.user_id = u.id) AS documents,
               (SELECT count(*) FROM user_connections k WHERE k.user_id = u.id) AS outils,
               (SELECT count(*) FROM watches w WHERE w.user_id = u.id) AS veilles,
               COALESCE(b.trial_credits + b.free_credits + b.purchased_credits, 0) AS solde_credits,
               b.trial_expires_at::date::text AS essai_expire_le,
               COALESCE(s.status, 'aucun') AS abonnement,
               s.cancel_at_period_end AS renouvellement_bloque
        FROM auth.users u
        LEFT JOIN company_profiles cp ON cp.user_id = u.id
        LEFT JOIN credit_balances b ON b.user_id = u.id
        LEFT JOIN user_subscriptions s ON s.user_id = u.id
        ORDER BY u.created_at
    """,
    "rapports": """
        SELECT u.email, r.created_at::text AS produit_le, r.analysis_type AS type,
               length(r.content) AS caracteres,
               -- jsonb_array_elements explose sur une valeur scalaire : on teste
               -- le type avant, sinon un seul rapport mal formé casse l'export.
               CASE WHEN jsonb_typeof(r.sources::jsonb) = 'array'
                    THEN jsonb_array_length(r.sources::jsonb) ELSE 0 END AS sources,
               r.duree_secondes, r.modele, r.tokens_entree, r.tokens_sortie,
               ROUND(COALESCE(r.cout_micro_eur, 0) / 1000000.0, 4) AS cout_modele_eur,
               ROUND(COALESCE(r.cout_recherche_micro_eur, 0) / 1000000.0, 4) AS cout_recherche_eur,
               r.appels_recherche,
               EXISTS (SELECT 1 FROM legacy_reports l WHERE l.imported_for = r.user_id
                       AND l.title = left(r.title, 500)) AS restaure
        FROM reports r JOIN auth.users u ON u.id = r.user_id
        ORDER BY r.created_at
    """,
    "emails": """
        SELECT campaign AS campagne, count(*) AS envoyes,
               count(opened_at) AS ouvertures_apparentes,
               count(*) FILTER (WHERE open_count >= 3) AS lectures_reelles,
               count(*) FILTER (WHERE opened_at IS NULL) AS jamais_ouverts,
               min(sent_at)::date::text AS premier_envoi
        FROM email_sends GROUP BY campaign ORDER BY min(sent_at)
    """,
    "revenus": """
        SELECT u.email, s.plan_key AS plan, s.status AS statut,
               s.cancel_at_period_end AS annule_en_fin_de_periode,
               s.current_period_end::date::text AS fin_periode,
               s.stripe_subscription_id IS NOT NULL AS stripe_reel
        FROM user_subscriptions s JOIN auth.users u ON u.id = s.user_id
    """,
    "credits": """
        SELECT u.email, e.action, e.delta, e.created_at::date::text AS le
        FROM credit_events e JOIN auth.users u ON u.id = e.user_id
        ORDER BY e.created_at
    """,
}


def export(db) -> dict:
    """Toutes les données de pilotage, en lecture seule, prêtes pour un tableur.

    Les dates sont déjà converties en texte côté base : un tableur qui reçoit
    un horodatage ISO avec fuseau l'affiche mal une fois sur deux.
    """
    import datetime as _dt

    sortie = {"extrait_le": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")}
    for nom, sql in _REQUETES.items():
        sortie[nom] = [
            {k: (float(v) if hasattr(v, "quantize") else v) for k, v in r.items()}
            for r in db.execute(text(sql)).mappings().all()
        ]
    sortie["couts_agreges"] = couts_totaux(db, jours=3650)["postes"]
    sortie["tableau"] = tableau(db, jours=30)
    return sortie
