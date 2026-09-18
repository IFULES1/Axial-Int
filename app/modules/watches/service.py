"""Watch service: CRUD, scheduling math, and the run loop used by the worker."""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.modules.watches.models import RssFeed, Watch, WatchRun

logger = logging.getLogger("axial.watches")

_CADENCE_DELTA = {
    "daily": dt.timedelta(days=1),
    "weekly": dt.timedelta(weeks=1),
}

# Vérification d'un flux : un GET explicite (pas `feedparser.parse(url)`, qui
# masque le user-agent et le timeout) suivi d'un parse feedparser du contenu
# reçu — le même parseur que `rss.py` utilise déjà pour lire les entrées.
HTTP_TIMEOUT_VERIFICATION = 10.0
HTTP_TIMEOUT_TITRE = 5.0
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _next_run(cadence: str, base: dt.datetime | None = None) -> dt.datetime | None:
    delta = _CADENCE_DELTA.get(cadence)
    if delta is None:  # manual → no automatic scheduling
        return None
    return (base or _now()) + delta


# --- Vérification des flux --------------------------------------------------

def verifier_flux(url: str, *, timeout: float = HTTP_TIMEOUT_VERIFICATION) -> dict:
    """Vérifie un flux RSS/Atom en le récupérant réellement (spec §3).

    `{url, ok, statut_http, entrees, dernier, erreur}` — plus `titre`, lu au
    passage (réutilisé par l'ajout d'une URL libre pour ne pas refaire un
    second aller-retour réseau). Ne lève jamais : un flux mort renvoie
    `ok=False` avec `erreur` renseignée, il n'arrête pas l'appelant.
    """
    import httpx
    import feedparser

    resultat: dict = {"url": url, "ok": False, "statut_http": None,
                      "entrees": 0, "dernier": None, "erreur": None, "titre": None}
    try:
        reponse = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout,
                            follow_redirects=True)
        resultat["statut_http"] = reponse.status_code
        reponse.raise_for_status()
        parsed = feedparser.parse(reponse.content)
        entrees = list(getattr(parsed, "entries", []) or [])
        # `bozo` seul est trop strict (certains flux valides déclenchent un
        # avertissement mineur du parseur) — on ne le traite en erreur que
        # s'il n'a en plus réussi à lire AUCUNE entrée.
        if getattr(parsed, "bozo", False) and not entrees:
            exc = getattr(parsed, "bozo_exception", None)
            raise ValueError(str(exc) if exc else "flux XML invalide")
        resultat["entrees"] = len(entrees)
        titre_flux = (getattr(parsed, "feed", None) or {}).get("title") if hasattr(parsed, "feed") else None
        resultat["titre"] = (titre_flux or "").strip() or None
        from app.modules.watches.rss import _entry_dt

        dates = [d for d in (_entry_dt(e) for e in entrees) if d is not None]
        resultat["dernier"] = max(dates).isoformat() if dates else None
        resultat["ok"] = True
    except Exception as e:  # noqa: BLE001 — un flux mort ne doit jamais lever
        resultat["erreur"] = str(e) or e.__class__.__name__
    return resultat


def lire_titre_flux(url: str) -> str | None:
    """Best-effort, court (5 s) : utilisé à l'ajout d'une URL libre pour
    enregistrer un titre lisible plutôt que l'URL brute."""
    try:
        return verifier_flux(url, timeout=HTTP_TIMEOUT_TITRE)["titre"]
    except Exception:  # noqa: BLE001 — un titre manquant n'empêche pas l'ajout
        return None


def verifier_tous(db: Session) -> list[dict]:
    """Vérifie TOUS les flux utilisateurs (met à jour `derniere_verification_at`
    et `derniere_erreur`) puis, sans écriture, tous les flux du catalogue.
    Utilisé par la route admin `/watches/feeds/verifier`."""
    from app.modules.watches.catalogue import catalogue

    resultats: list[dict] = []
    for feed in db.scalars(select(RssFeed)):
        r = verifier_flux(feed.url)
        feed.derniere_verification_at = _now()
        feed.derniere_erreur = None if r["ok"] else (r["erreur"] or "erreur inconnue")
        resultats.append(r)
    db.commit()

    deja = {r["url"] for r in resultats}
    for f in catalogue():
        if f["url"] in deja:
            continue
        resultats.append(verifier_flux(f["url"]))
    return resultats


def _etat_flux(*, verifie_at, erreur) -> str:
    if verifie_at is None:
        return "inconnu"
    return "erreur" if erreur else "ok"


def feeds_pour_watch(db: Session, user_id: str, watch: Watch) -> list[dict]:
    """Flux visibles sur la fiche d'un agent (spec §3) : ceux de l'utilisateur
    dont la catégorie ∈ `skill.rss_categories`, plus le catalogue de ces
    catégories — chaque flux catalogue reprend l'état d'un flux utilisateur
    de même URL s'il existe, sinon `inconnu` (aucune vérification catalogue
    propre n'est faite ici, `verifier_tous` s'en charge côté admin)."""
    from app.modules.watches import skills
    from app.modules.watches.catalogue import catalogue

    skill = skills.get_skill(watch.skill)
    categories = set(skill.rss_categories)

    mes_flux = list(db.scalars(
        select(RssFeed).where(RssFeed.user_id == uuid.UUID(user_id))
        .order_by(RssFeed.created_at.desc())))
    etat_par_url = {f.url: _etat_flux(verifie_at=f.derniere_verification_at,
                                      erreur=f.derniere_erreur) for f in mes_flux}
    verifie_at_par_url = {f.url: f.derniere_verification_at for f in mes_flux}

    items: list[dict] = []
    vues: set[str] = set()
    for f in mes_flux:
        if f.category not in categories:
            continue
        items.append({
            "url": f.url, "title": f.title, "category": f.category,
            "origine": "moi", "etat": etat_par_url[f.url],
            "derniere_verification_at": f.derniere_verification_at,
        })
        vues.add(f.url)

    for f in catalogue():
        if f["category"] not in categories or f["url"] in vues:
            continue
        items.append({
            "url": f["url"], "title": f["title"] or None, "category": f["category"],
            "origine": "catalogue", "etat": etat_par_url.get(f["url"], "inconnu"),
            "derniere_verification_at": verifie_at_par_url.get(f["url"]),
        })
        vues.add(f["url"])
    return items


# --- CRUD ------------------------------------------------------------------

def amorcer_flux(db: Session, user_id: str, skill_key: str) -> int:
    """Attache les flux du catalogue correspondant au skill, s'il en manque.

    Une veille réglementaire créée par quelqu'un qui n'a aucun flux ne lit
    rien : elle tourne, consomme des crédits, et ne remonte que la recherche
    web. L'utilisateur ne peut pas deviner qu'il devait d'abord ajouter des
    sources — on les lui pose.

    On n'ajoute que ce qui manque : un flux déjà suivi n'est pas dupliqué, et
    un utilisateur qui a délibérément retiré une source ne la voit pas revenir
    dans une catégorie qu'il alimente déjà autrement.
    """
    from app.modules.watches import skills
    from app.modules.watches.catalogue import catalogue

    skill = skills.get_skill(skill_key)
    if not skill:
        return 0
    categories = [c for c in skill.rss_categories if c != "general"]
    deja = {f.url for f in db.scalars(
        select(RssFeed).where(RssFeed.user_id == uuid.UUID(user_id)))}
    couvertes = {f.category for f in db.scalars(
        select(RssFeed).where(RssFeed.user_id == uuid.UUID(user_id)))}
    ajoutes = 0
    for f in catalogue():
        if f["category"] not in categories or f["category"] in couvertes:
            continue
        if f["url"] in deja:
            continue
        db.add(RssFeed(id=uuid.uuid4(), user_id=uuid.UUID(user_id), url=f["url"],
                       title=f["title"], category=f["category"]))
        deja.add(f["url"])
        ajoutes += 1
    if ajoutes:
        db.commit()
        logger.info("Veille : %d flux du catalogue attachés à %s (%s)",
                    ajoutes, user_id, skill_key)
    return ajoutes


def create_watch(db: Session, user_id: str, *, name: str, query: str,
                 analysis_type: str, cadence: str, skill: str = "concurrentielle",
                 email_recipients: list[str] | None) -> Watch:
    watch = Watch(
        id=uuid.uuid4(), user_id=uuid.UUID(user_id), name=name, query=query,
        analysis_type=analysis_type, cadence=cadence, skill=skill,
        email_recipients=email_recipients, next_run_at=_next_run(cadence),
    )
    db.add(watch)
    db.commit()
    db.refresh(watch)
    return watch


def list_watches(db: Session, user_id: str) -> list[Watch]:
    stmt = select(Watch).where(Watch.user_id == uuid.UUID(user_id)).order_by(Watch.created_at.desc())
    return list(db.scalars(stmt))


def list_runs(db: Session, user_id: str, watch_id: str, limit: int = 20) -> list[WatchRun]:
    """Dated finding history for one watch (newest first). Authz via ownership."""
    _own_watch(db, user_id, watch_id)
    stmt = (select(WatchRun).where(WatchRun.watch_id == uuid.UUID(watch_id))
            .order_by(WatchRun.created_at.desc()).limit(limit))
    return list(db.scalars(stmt))


def list_activity(db: Session, user_id: str, limit: int = 30) -> list:
    """Global run history across ALL the user's agents (newest first), with the
    agent name and its skill — the 'which skills ran' log."""
    stmt = (select(WatchRun, Watch.name, Watch.skill)
            .join(Watch, Watch.id == WatchRun.watch_id)
            .where(Watch.user_id == uuid.UUID(user_id))
            .order_by(WatchRun.created_at.desc()).limit(limit))
    return list(db.execute(stmt).all())


def _feeds_for(db: Session, user_id: str, categories: list[str]) -> list[RssFeed]:
    stmt = select(RssFeed).where(RssFeed.user_id == uuid.UUID(user_id), RssFeed.active.is_(True))
    if categories:
        stmt = stmt.where(RssFeed.category.in_(categories))
    return list(db.scalars(stmt))


def _prior_seen_urls(db: Session, watch_id) -> set[str]:
    """Every RSS url this watch already consumed — so we never re-report an article."""
    seen: set[str] = set()
    for urls in db.scalars(select(WatchRun.new_article_urls).where(WatchRun.watch_id == watch_id)):
        if urls:
            seen.update(urls)
    return seen


def _own_watch(db: Session, user_id: str, watch_id: str) -> Watch:
    watch = db.get(Watch, uuid.UUID(watch_id))
    if not watch or str(watch.user_id) != user_id:
        raise AppError("Veille introuvable.", 404, code="not_found")
    return watch


def set_status(db: Session, user_id: str, watch_id: str, status: str) -> Watch:
    watch = _own_watch(db, user_id, watch_id)
    watch.status = status
    watch.next_run_at = _next_run(watch.cadence) if status == "active" else None
    db.commit()
    db.refresh(watch)
    return watch


def delete_watch(db: Session, user_id: str, watch_id: str) -> None:
    db.delete(_own_watch(db, user_id, watch_id))
    db.commit()


# --- Execution (called by the worker or a manual trigger) ------------------

def _email_body(name: str, veille: dict) -> str:
    delta = veille.get("delta") or "Aucune nouveauté significative depuis la dernière veille."
    full = veille.get("full_report") or ""
    return (f"# Veille : {name}\n\n"
            f"## 🆕 Nouveautés depuis la dernière veille\n\n{delta}\n\n"
            f"---\n\n## 📊 Point complet actualisé\n\n{full}")


def run_watch(db: Session, watch: Watch) -> bool:
    """Run one cumulative veille pass for a watch: gather RSS + web sources, apply
    the agent's rolling memory, produce delta + full report, archive as a WatchRun
    and email. Returns True on success. Never raises to the scheduler."""
    uid = str(watch.user_id)
    try:
        from app.modules.billing import service as billing
        from app.modules.memory import service as memory
        from app.modules.watches import engine, rss, skills
        from app.modules.watches.email import send_email
        from app.shared import search as web_search

        if not billing.check_credits(db, uid, "run_agent_veille")["affordable"]:
            logger.info("Watch %s skipped: insufficient credits", watch.id)
            _reschedule(db, watch, produced=False)
            return False

        # Rempli par l'orchestrateur : le coût de recherche d'une veille suit le
        # nombre d'angles du skill, pas le nombre d'exécutions.
        appels_recherche: dict[str, int] = {}
        skill = skills.get_skill(watch.skill)

        # 1. Sources: fresh RSS (new since last run) + web search on the skill's angle.
        feeds = _feeds_for(db, uid, skill.rss_categories)
        articles = rss.fetch_new_articles(
            feeds, since=watch.last_run_at, seen_urls=_prior_seen_urls(db, watch.id))
        try:
            query = skill.web_query_template.format(subject=watch.query)
            # Six résultats sur un angle unique, c'était le même défaut que les
            # rapports : ce que la recherche ne trouve pas, le modèle le comble.
            angles = [query] + [f"{watch.query} — {a}" for a in skill.angles_web()]
            web_results = web_search.search_multi(angles, top_k=12,
                                                  requete_de_rang=query,
                                                  compteur=appels_recherche)
        except Exception as e:  # noqa: BLE001 — web is optional, RSS may carry the run
            logger.warning("Watch %s web search failed: %s", watch.id, e)
            web_results = []

        # 2. Cumulative generation (rolling memory → delta + full + updated memory).
        company_context = memory.build_context(db, uid)
        veille = engine.generate_veille(
            skill=skill, subject=watch.query, rolling_state=watch.rolling_state,
            rss_articles=articles, web_results=web_results,
            company_context=company_context,
        )

        # 3. Archive the run + advance the rolling memory.
        from app.modules.billing.couts import cout_micro_eur, cout_recherche_micro_eur

        mesure = veille.get("mesure")
        entree = getattr(mesure, "input_tokens", 0) or 0
        sortie = getattr(mesure, "output_tokens", 0) or 0
        modele = getattr(mesure, "model", None)
        db.add(WatchRun(
            id=uuid.uuid4(), watch_id=watch.id,
            tokens_entree=entree or None, tokens_sortie=sortie or None,
            modele=modele,
            cout_micro_eur=(cout_micro_eur(modele, entree, sortie) if modele else None) or None,
            appels_recherche=sum(v for k, v in appels_recherche.items()
                                 if not k.startswith("_")) or None,
            cout_recherche_micro_eur=cout_recherche_micro_eur(appels_recherche) or None,
            delta_content=veille.get("delta") or "",
            full_content=veille.get("full_report") or "",
            rolling_state=veille.get("rolling_state"),
            sources=veille.get("sources"),
            new_article_urls=[a["url"] for a in articles],
            had_changes=bool(veille.get("had_changes", True)),
        ))
        if veille.get("rolling_state"):
            watch.rolling_state = veille["rolling_state"]

        # 4. Charge credits + email the digest.
        billing.consume_credits(db, uid, "run_agent_veille", is_admin=False)  # 5 crédits / run
        from app.modules.memory import service as memory_service

        wants_email = memory_service.get_notification_prefs(db, uid).get("findings", True)
        if watch.email_recipients and wants_email:
            corps = _email_body(watch.name, veille)
            # Les graphiques du rapport de veille passent par le même moteur
            # que ceux des rapports ; l'email les reçoit en image hébergée.
            from app.modules.viz import service as viz_service

            vizs = viz_service.preparer_sans_faute(db, corps)
            db.commit()
            send_email(watch.email_recipients, f"[Axial · Veille] {watch.name}", corps, vizs)

        _reschedule(db, watch, produced=True)
        return True
    except Exception:
        logger.exception("Watch %s run failed", watch.id)
        _reschedule(db, watch, produced=False)
        return False


def _reschedule(db: Session, watch: Watch, *, produced: bool) -> None:
    now = _now()
    if produced:
        watch.last_run_at = now
    watch.next_run_at = _next_run(watch.cadence, base=now) if watch.status == "active" else None
    db.commit()


def run_due_watches(db: Session) -> int:
    """Run every active watch whose next_run_at is in the past. Worker entrypoint."""
    stmt = select(Watch).where(
        Watch.status == "active",
        Watch.next_run_at.is_not(None),
        Watch.next_run_at <= _now(),
    )
    due = list(db.scalars(stmt))
    for watch in due:
        run_watch(db, watch)
    return len(due)
