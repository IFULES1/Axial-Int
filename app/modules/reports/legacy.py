"""Legacy reports from the previous platform, restored on sign-in.

Rather than migrating dormant accounts wholesale, the reports of the old
platform are parked here keyed by **email**. The first time someone registers or
logs in with a matching address, their reports land in their new account — and
the rows are marked as imported so it never happens twice.

Nothing is destroyed: an imported row keeps its record here.
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base

logger = logging.getLogger("axial.reports.legacy")


class LegacyReport(Base):
    __tablename__ = "legacy_reports"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), index=True)
    legacy_id: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    analysis_type: Mapped[str | None] = mapped_column(String(64))
    legacy_created_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    imported_for: Mapped[uuid.UUID | None] = mapped_column(SAUuid)


def pending_count(db: Session, email: str) -> int:
    """How many legacy reports are waiting for this address."""
    stmt = select(LegacyReport).where(
        LegacyReport.email == (email or "").strip().lower(),
        LegacyReport.imported_at.is_(None),
    )
    return len(list(db.scalars(stmt)))


def is_known(db: Session, email: str) -> bool:
    """True if this address produced anything on the previous platform.

    Used to let returning users back in even when their address would fail the
    professional-email policy: they were customers before that rule existed.
    """
    address = (email or "").strip().lower()
    if not address:
        return False
    try:
        stmt = select(LegacyReport.id).where(LegacyReport.email == address).limit(1)
        if db.scalar(stmt) is not None:
            return True
    except Exception:  # table absente (migration pas encore jouée)
        pass
    # Une adresse contactée par la campagne de migration est tout aussi
    # « connue », même sans rapport à restaurer : sur 42 destinataires, 25
    # n'avaient rien produit et seraient restés dans le silence complet.
    try:
        from app.modules.emailing.models import EmailSend

        stmt = select(EmailSend.id).where(EmailSend.email == address).limit(1)
        return db.scalar(stmt) is not None
    except Exception:
        return False


# Crédits offerts, une seule fois, à un utilisateur de l'ancienne plateforme qui
# revient — s'ajoutent aux crédits de bienvenue standards.
RETURN_BONUS_CREDITS = 30
RETURN_BONUS_ACTION = "retour_migration"


def grant_return_bonus(db: Session, user_id: str, email: str) -> int:
    """Offer the returning-user credits, once. Returns the amount granted."""
    from app.modules.billing import service as billing

    if not is_known(db, email):
        return 0
    try:
        already = any(e.action == RETURN_BONUS_ACTION
                      for e in billing.list_events(db, user_id, limit=200))
        if already:
            return 0
        balance = billing.get_or_create_balance(db, user_id)
        balance.purchased_credits += RETURN_BONUS_CREDITS
        billing._log_event(db, user_id, RETURN_BONUS_CREDITS, RETURN_BONUS_ACTION)
        db.commit()
        logger.info("Bonus retour (%d crédits) accordé à %s",
                    RETURN_BONUS_CREDITS, email)
        return RETURN_BONUS_CREDITS
    except Exception as e:  # noqa: BLE001 — jamais bloquant pour la connexion
        db.rollback()
        logger.warning("Bonus retour impossible pour %s : %s", email, e)
        return 0


def restore_for(db: Session, user_id: str, email: str) -> int:
    """Copy this address's legacy reports into the user's account.

    Idempotent and best-effort: called on every sign-in, it must never break
    authentication if anything goes wrong.
    """
    from app.modules.reports.models import Report

    address = (email or "").strip().lower()
    if not address:
        return 0
    try:
        rows = list(db.scalars(
            select(LegacyReport).where(LegacyReport.email == address,
                                       LegacyReport.imported_at.is_(None))
        ))
        if not rows:
            return 0
        now = dt.datetime.now(dt.timezone.utc)
        uid = uuid.UUID(user_id)
        for row in rows:
            db.add(Report(
                id=uuid.uuid4(), user_id=uid,
                # `reports.title` est plus court que le champ hérité.
                title=(row.title or "Rapport (version précédente)")[:300],
                content=row.content or "",
                analysis_type=row.analysis_type or "synthese_executive",
                sources=None,
                created_at=row.legacy_created_at or now,
            ))
            row.imported_at = now
            row.imported_for = uid
        db.commit()
        logger.info("Restauré %d rapport(s) hérité(s) pour %s", len(rows), address)
        return len(rows)
    except Exception as e:  # noqa: BLE001 — never block a login
        db.rollback()
        logger.warning("Restauration des rapports hérités échouée pour %s : %s",
                       address, e)
        return 0


def verifier_une_fois(db: Session, user_id: str, email: str) -> dict:
    """Import hérité + bonus de retour, une seule fois par compte.

    `restore_for` et `grant_return_bonus` tournaient à CHAQUE authentification
    (inscription, connexion ET réinitialisation de mot de passe) : deux
    requêtes sur `legacy_reports` et une lecture de 200 événements de crédit
    par connexion, pour deux opérations qui ne peuvent aboutir qu'une fois.
    `credit_balances.legacy_verifie_at` note que le passage a eu lieu ; les
    connexions suivantes ne touchent plus à ces tables.

    Le marqueur est posé même quand rien n'a été restauré : « cette adresse n'a
    rien sur l'ancienne plateforme » est un résultat définitif, pas un échec à
    retenter. Best-effort par construction — ne bloque jamais une connexion.
    """
    from app.modules.billing import service as billing

    try:
        balance = billing.get_or_create_balance(db, user_id)
        if balance.legacy_verifie_at is not None:
            return {"restaures": 0, "bonus": 0, "deja_verifie": True}
    except Exception as e:  # noqa: BLE001 — jamais bloquant pour la connexion
        db.rollback()
        logger.warning("Marqueur d'import hérité illisible pour %s : %s", user_id, e)
        return {"restaures": 0, "bonus": 0, "deja_verifie": False}

    restaures = restore_for(db, user_id, email)
    bonus = grant_return_bonus(db, user_id, email)

    try:
        # Rechargé : les deux appels ci-dessus font leur propre commit (et un
        # rollback en cas d'échec), ce qui détache l'objet lu plus haut.
        balance = billing.get_or_create_balance(db, user_id)
        balance.legacy_verifie_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
    except Exception as e:  # noqa: BLE001 — jamais bloquant pour la connexion
        db.rollback()
        logger.warning("Marqueur d'import hérité non posé pour %s : %s", user_id, e)

    return {"restaures": restaures, "bonus": bonus, "deja_verifie": False}
