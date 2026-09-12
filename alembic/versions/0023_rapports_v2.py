"""Rapports v2 : socle backend.

Quatre familles de changements, quatre causes distinctes :

* `reports.statut` / `etape` / `progression` / `detail` / `question` /
  `termine_at` / `annulation_demandee` — la génération devient suivie par
  identifiant (spec §1). La ligne est créée au lancement et se remplit au fil
  des étapes : le front reprend une génération en cours après un rechargement,
  et le bouton Stop a enfin un endroit où écrire son intention. Les rapports
  existants prennent `termine` / `progression=100` par le `server_default` :
  ils sont tous terminés par construction, aucun n'a jamais été suivi.
* `reports.archived_at` / `pinned_at` / `project_id` / `jeton_partage` /
  `partage_at` — rangement, dossiers (les mêmes `projects` que les
  conversations) et partage public (spec §4). `project_id` est en ON DELETE
  SET NULL et non CASCADE comme `conversations.project_id` : supprimer un
  dossier ne doit pas détruire des rapports payés.
* `report_feedback` — « Votre avis » renvoyait vers un Google Form : le retour
  partait chez Google sans l'identifiant du rapport, donc sans moyen de relire
  le document incriminé (spec §3).
* `credit_events` index unique partiel + `credit_balances.legacy_verifie_at` —
  deux garde-fous que le code applicatif ne peut pas tenir seul : le premier
  rapport offert se vérifiait par un SELECT avant l'INSERT (deux appels
  simultanés passaient tous les deux), et l'import des rapports hérités
  tournait à chaque connexion faute d'endroit où noter qu'il avait eu lieu
  (spec §5.4 et §5.5).

Revision ID: 0023_rapports_v2
Revises: 0022_conversations_v2
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023_rapports_v2"
down_revision = "0022_conversations_v2"
branch_labels = None
depends_on = None


INDEX_PROJET = "ix_reports_project_id"
INDEX_PARTAGE = "ux_reports_jeton_partage"
INDEX_IDEMPOTENCE = "ux_reports_cle_idempotence"
INDEX_OFFERT = "ux_credit_events_premier_rapport_offert"
# Doit rester égal à `app.modules.analysis.onboarding.ACTION` ; le test
# `test_rapports_v2.test_action_offerte_identique_partout` le vérifie.
ACTION_OFFERT = "premier_rapport_offert"

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _index(*, creer: bool, nom: str, table: str, colonnes: list[str],
           unique: bool = False, where: str | None = None) -> None:
    """Crée (ou retire) un index sans verrouiller la table en écriture.

    `CREATE INDEX` ordinaire prend un SHARE sur la table pendant toute la
    construction — les écritures sont bloquées. `reports` et surtout
    `credit_events` ne feront que grossir, et `credit_events` est écrit à
    chaque message d'agent : un verrou sur cette table gèle l'application.
    `CONCURRENTLY` ne peut pas tourner dans une transaction, d'où
    l'`autocommit_block` (même construction qu'en 0022). SQLite (tests) ne
    connaît pas `CONCURRENTLY` mais connaît les index partiels.
    """
    postgres = op.get_bind().dialect.name == "postgresql"
    options: dict = {}
    if where:
        options["postgresql_where"] = sa.text(where)
        options["sqlite_where"] = sa.text(where)

    def _appliquer() -> None:
        if creer:
            op.create_index(nom, table, colonnes, unique=unique,
                            **options,
                            **({"postgresql_concurrently": True} if postgres else {}))
        else:
            op.drop_index(nom, table_name=table,
                          **({"postgresql_concurrently": True} if postgres else {}))

    if postgres:
        with op.get_context().autocommit_block():
            _appliquer()
    else:
        _appliquer()


def _dedoublonner_offert() -> None:
    """Retire les `premier_rapport_offert` en double AVANT l'index unique.

    L'index répare une course `SELECT`-puis-`INSERT` qui existait déjà sur
    `main` (`onboarding.deja_offert`). Si cette course a produit un doublon en
    production, `CREATE UNIQUE INDEX CONCURRENTLY` échoue — et comme il tourne
    en `autocommit_block`, il laisse derrière lui un index INVALID à supprimer
    à la main avant de pouvoir réessayer. Autant nettoyer ici : la ligne la
    plus ANCIENNE est gardée (c'est celle qui a réellement offert le rapport,
    les suivantes sont des rejeux), les autres partent.

    PostgreSQL seulement : `ctid` n'existe pas ailleurs, et SQLite (tests) ne
    peut pas produire le doublon — l'index y est créé dans la même transaction
    sur une base neuve.
    """
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(sa.text(f"""
        DELETE FROM credit_events e
        USING (
            SELECT user_id, min(created_at) AS premier
            FROM credit_events
            WHERE action = '{ACTION_OFFERT}'
            GROUP BY user_id HAVING count(*) > 1
        ) d
        WHERE e.action = '{ACTION_OFFERT}'
          AND e.user_id = d.user_id
          AND e.created_at > d.premier
    """))
    # Deux lignes exactement à la même microseconde : `created_at` ne les
    # départage pas. Le `ctid` (adresse physique) le fait toujours.
    op.execute(sa.text(f"""
        DELETE FROM credit_events e
        WHERE e.action = '{ACTION_OFFERT}'
          AND e.ctid <> (
              SELECT min(i.ctid) FROM credit_events i
              WHERE i.action = '{ACTION_OFFERT}' AND i.user_id = e.user_id
          )
    """))


def upgrade() -> None:
    # --- reports : génération suivie (§1) ---------------------------------
    op.add_column("reports", sa.Column(
        "statut", sa.String(length=32), nullable=False, server_default="termine"))
    op.add_column("reports", sa.Column("etape", sa.String(length=32), nullable=True))
    op.add_column("reports", sa.Column(
        "progression", sa.Integer(), nullable=False, server_default="100"))
    op.add_column("reports", sa.Column(
        "detail", _JSON, nullable=True))
    op.add_column("reports", sa.Column("question", sa.Text(), nullable=True))
    op.add_column("reports", sa.Column(
        "termine_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reports", sa.Column(
        "annulation_demandee", sa.Boolean(), nullable=False,
        server_default=sa.false()))

    # --- reports : gestion (§4) -------------------------------------------
    op.add_column("reports", sa.Column(
        "archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reports", sa.Column(
        "pinned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reports", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_reports_project_id", "reports", "projects",
                          ["project_id"], ["id"], ondelete="SET NULL")
    op.add_column("reports", sa.Column(
        "jeton_partage", sa.String(length=32), nullable=True))
    op.add_column("reports", sa.Column(
        "partage_at", sa.DateTime(timezone=True), nullable=True))
    # --- idempotence : une COLONNE, pas une clé dans le JSON `detail` ------
    # La clé d'idempotence vivait dans `detail` et se relisait par un SELECT :
    # deux requêtes concurrentes portant la même clé lisaient toutes deux
    # « rien », créaient deux lignes et débitaient deux fois. Une colonne avec
    # un index unique `(user_id, cle_idempotence)` transforme la course en
    # `IntegrityError`, que le moteur rattrape pour rendre la ligne existante.
    # Les NULL n'entrent pas en collision dans un index unique PostgreSQL :
    # les rapports sans clé (offert, admin, import hérité) ne se gênent pas.
    op.add_column("reports", sa.Column(
        "cle_idempotence", sa.String(length=64), nullable=True))
    _index(creer=True, nom=INDEX_PROJET, table="reports", colonnes=["project_id"])
    _index(creer=True, nom=INDEX_PARTAGE, table="reports",
           colonnes=["jeton_partage"], unique=True)
    _index(creer=True, nom=INDEX_IDEMPOTENCE, table="reports",
           colonnes=["user_id", "cle_idempotence"], unique=True)

    # --- report_feedback (§3) ---------------------------------------------
    op.create_table(
        "report_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.Integer(), nullable=True),
        sa.Column("motif", sa.String(length=32), nullable=False),
        sa.Column("commentaire", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_report_feedback_report_id", "report_feedback", ["report_id"])
    op.create_index("ix_report_feedback_user_id", "report_feedback", ["user_id"])
    op.create_index("ix_report_feedback_created_at", "report_feedback", ["created_at"])

    # --- rapport offert : un seul par compte (§5.4) ------------------------
    # Index PARTIEL : le registre reste append-only pour toutes les autres
    # actions (un compte a bien plusieurs `agent_message`).
    _dedoublonner_offert()
    _index(creer=True, nom=INDEX_OFFERT, table="credit_events",
           colonnes=["user_id"], unique=True,
           where=f"action = '{ACTION_OFFERT}'")

    # --- import hérité : une seule fois par compte (§5.5) ------------------
    op.add_column("credit_balances", sa.Column(
        "legacy_verifie_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("credit_balances", "legacy_verifie_at")
    _index(creer=False, nom=INDEX_OFFERT, table="credit_events", colonnes=["user_id"])

    op.drop_index("ix_report_feedback_created_at", table_name="report_feedback")
    op.drop_index("ix_report_feedback_user_id", table_name="report_feedback")
    op.drop_index("ix_report_feedback_report_id", table_name="report_feedback")
    op.drop_table("report_feedback")

    _index(creer=False, nom=INDEX_IDEMPOTENCE, table="reports",
           colonnes=["user_id", "cle_idempotence"])
    _index(creer=False, nom=INDEX_PARTAGE, table="reports", colonnes=["jeton_partage"])
    _index(creer=False, nom=INDEX_PROJET, table="reports", colonnes=["project_id"])
    op.drop_constraint("fk_reports_project_id", "reports", type_="foreignkey")
    op.drop_column("reports", "cle_idempotence")
    op.drop_column("reports", "partage_at")
    op.drop_column("reports", "jeton_partage")
    op.drop_column("reports", "project_id")
    op.drop_column("reports", "pinned_at")
    op.drop_column("reports", "archived_at")

    op.drop_column("reports", "annulation_demandee")
    op.drop_column("reports", "termine_at")
    op.drop_column("reports", "question")
    op.drop_column("reports", "detail")
    op.drop_column("reports", "progression")
    op.drop_column("reports", "etape")
    op.drop_column("reports", "statut")
