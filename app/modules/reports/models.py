"""Report model — a persisted, exportable analysis output."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, DateTime, String, Text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy import false as sa_false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# JSONB on PostgreSQL, plain JSON elsewhere (tests on SQLite).
JSONType = JSON().with_variant(JSONB(), "postgresql")

# --- Statuts d'un rapport (spec §1) ----------------------------------------
# La migration 0023 n'a volontairement posé AUCUN CHECK en base : une nouvelle
# valeur ne doit pas coûter une migration. La contrepartie est que cette
# constante est le seul point de passage autorisé — toute écriture de `statut`
# passe par l'une de ces valeurs, et `STATUTS` est ce que les tests vérifient.
EN_COURS = "en_cours"
TERMINE = "termine"
ECHEC = "echec"
DEGRADE = "degrade"
ANNULE = "annule"
SOURCES_INSUFFISANTES = "sources_insuffisantes"

STATUTS: tuple[str, ...] = (EN_COURS, TERMINE, ECHEC, DEGRADE, ANNULE,
                            SOURCES_INSUFFISANTES)
# Statuts terminaux : la tâche ne tourne plus, le front arrête son polling.
STATUTS_TERMINAUX: tuple[str, ...] = tuple(s for s in STATUTS if s != EN_COURS)

# Étapes du moteur, dans l'ordre (spec §1).
ETAPES: tuple[str, ...] = ("recherche", "selection", "couverture", "redaction",
                           "finalisation")


class Report(Base):
    __tablename__ = "reports"
    # Index unique nommé (et non `unique=True` sur la colonne) : la migration
    # 0023 le crée en CONCURRENTLY sous ce nom, et une contrainte inline
    # produirait un objet de nom différent — l'autogenerate signalerait un
    # écart permanent entre le modèle et la base.
    __table_args__ = (
        Index("ux_reports_jeton_partage", "jeton_partage", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(SAUuid, index=True, nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(64), default="synthese_executive")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")  # markdown
    sources: Mapped[list | None] = mapped_column(JSONType)
    # Visualisations préparées à l'archivage (forme `viz.pipeline.Viz`) :
    # spec du modèle, type choisi, Vega-Lite compilé, statut, empreinte.
    viz: Mapped[list | None] = mapped_column(JSONType)
    # Coût de production. Nullable : les rapports antérieurs au 25/08 n'ont
    # jamais été mesurés, et un zéro les ferait passer pour gratuits dans les
    # moyennes.
    tokens_entree: Mapped[int | None] = mapped_column(Integer)
    tokens_sortie: Mapped[int | None] = mapped_column(Integer)
    cout_micro_eur: Mapped[int | None] = mapped_column(Integer)
    modele: Mapped[str | None] = mapped_column(String(64))
    # Séparé du coût modèle : autre cause (angles × fournisseurs), autre courbe.
    cout_recherche_micro_eur: Mapped[int | None] = mapped_column(Integer)
    appels_recherche: Mapped[int | None] = mapped_column(Integer)
    duree_secondes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc)
    )

    # --- Génération suivie par identifiant (spec §1) -----------------------
    # La ligne est créée AU LANCEMENT, contenu vide, et se remplit au fil des
    # étapes. Le défaut `termine` / `progression=100` vaut pour les rapports
    # antérieurs (ils n'ont jamais été suivis) autant que pour les imports
    # hérités, qui ne passent par aucun moteur.
    # Valeurs : en_cours | termine | echec | degrade | annule |
    # sources_insuffisantes.
    statut: Mapped[str] = mapped_column(
        String(32), default="termine", server_default="termine", nullable=False)
    # Étape courante du moteur : recherche | selection | redaction | finalisation.
    etape: Mapped[str | None] = mapped_column(String(32))
    # 0-100 réels (comptes de sources, sections détectées) — plus de battement
    # fictif à +3 % côté front.
    progression: Mapped[int] = mapped_column(
        Integer, default=100, server_default="100", nullable=False)
    # Contexte libre de l'étape : sources trouvées, section en cours, message,
    # et `raison` pour un rapport dégradé (truncated_generation, llm_unavailable,
    # empty_generation, investors_unavailable, couverture_partielle).
    detail: Mapped[dict | None] = mapped_column(JSONType)
    # La question d'origine, conservée pour « Modifier et relancer » : le titre
    # est produit par le modèle et ne permet pas de rejouer la demande.
    question: Mapped[str | None] = mapped_column(Text)
    termine_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # Drapeau de Stop, lu par la tâche entre deux étapes et pendant le flux du
    # modèle. Un booléen en base plutôt qu'un événement en mémoire : la tâche
    # tourne dans un thread avec sa propre session, et le bouton peut être
    # cliqué depuis un autre onglet.
    annulation_demandee: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa_false(), nullable=False)

    # --- Gestion des rapports (spec §4) ------------------------------------
    archived_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    pinned_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # Mêmes dossiers que les conversations. ON DELETE SET NULL (et non CASCADE
    # comme `conversations.project_id`) : supprimer un dossier ne doit pas
    # détruire des rapports payés — ils retombent simplement « sans dossier ».
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        SAUuid, ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    # Partage public : 22 caractères aléatoires, l'URL n'est pas devinable.
    # Nullable + unique : les rapports non partagés ne se collisionnent pas
    # (les NULL n'entrent pas en collision dans un index unique PostgreSQL).
    jeton_partage: Mapped[str | None] = mapped_column(String(32))
    partage_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
