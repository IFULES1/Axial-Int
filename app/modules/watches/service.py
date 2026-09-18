"""Watch service: CRUD, scheduling math, and the run loop used by the worker."""
from __future__ import annotations

import datetime as dt
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import httpx
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
# Revue tour 1, Q2 : `timeout=5.0` donnait 5 s à CHAQUE phase (connect, read,
# write, pool) et `follow_redirects=True` reconduisait ce budget à chaque
# saut — un site lent à connecter puis à répondre pouvait bloquer l'ajout
# d'une URL libre 15-20 s. `httpx.Timeout(5.0, connect=2.0)` borne la
# connexion à 2 s ; `max_redirects=3` borne le nombre de sauts suivis.
HTTP_TIMEOUT_TITRE = httpx.Timeout(5.0, connect=2.0)
MAX_REDIRECTS_TITRE = 3
# Revue tour 2 : `httpx.get(..., follow_redirects=True)` (fonction de module)
# ne sait pas borner le nombre de sauts suivis — un flux pathologique qui
# redirige en boucle tournait jusqu'à la limite interne d'httpx (20). Borné
# à 5 sur le chemin de vérification standard aussi (`_get_flux` passe
# systématiquement par un `httpx.Client`, qui le permet).
MAX_REDIRECTS_VERIFICATION = 5
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# Revue tour 1, Q1 : parallélisme borné pour `verifier_tous` — 8 GET en vol
# au maximum, chaque future bornée à 12 s (le GET lui-même est déjà borné à
# `HTTP_TIMEOUT_VERIFICATION`, la marge couvre l'attente de thread).
VERIF_MAX_WORKERS = 8
VERIF_TIMEOUT_FUTURE = 12.0
VERIF_LIMITE_PAR_APPEL = 60  # borne haute pour que la route admin reste sous ~60 s

# Revue tour 1, Q6 : un flux jamais vérifié, ou vérifié il y a plus de 7 j,
# déclenche une vérification d'arrière-plan des flux du user au premier
# chargement de sa fiche agent — sans quoi rien (hors script/route admin)
# n'alimente jamais l'état affiché et tous les points restent gris.
SEUIL_REVERIFICATION = dt.timedelta(days=7)
_verification_en_cours: set[str] = set()
_verification_lock = threading.Lock()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _next_run(cadence: str, base: dt.datetime | None = None) -> dt.datetime | None:
    delta = _CADENCE_DELTA.get(cadence)
    if delta is None:  # manual → no automatic scheduling
        return None
    return (base or _now()) + delta


# --- Vérification des flux --------------------------------------------------

def _get_flux(url: str, *, timeout, max_redirects: int) -> httpx.Response:
    """Le GET qu'utilisent `verifier_flux` et `lire_titre_flux`.

    Toujours via un `httpx.Client` de courte durée : `httpx.get(...)`
    (fonction de module) ne sait pas borner le nombre de redirections
    suivies, et un flux pathologique qui redirige en boucle tournerait
    jusqu'à la limite par défaut d'httpx (20) plutôt que celle demandée ici.
    """
    with httpx.Client(timeout=timeout, follow_redirects=True,
                      max_redirects=max_redirects) as client:
        return client.get(url, headers={"User-Agent": USER_AGENT})


def verifier_flux(url: str, *, timeout=HTTP_TIMEOUT_VERIFICATION,
                  max_redirects: int = MAX_REDIRECTS_VERIFICATION) -> dict:
    """Vérifie un flux RSS/Atom en le récupérant réellement (spec §3).

    `{url, ok, statut_http, entrees, dernier, erreur}` — plus `titre`, lu au
    passage (réutilisé par l'ajout d'une URL libre pour ne pas refaire un
    second aller-retour réseau). Ne lève jamais : un flux mort renvoie
    `ok=False` avec `erreur` renseignée, il n'arrête pas l'appelant.
    """
    import feedparser

    resultat: dict = {"url": url, "ok": False, "statut_http": None,
                      "entrees": 0, "dernier": None, "erreur": None, "titre": None}
    try:
        reponse = _get_flux(url, timeout=timeout, max_redirects=max_redirects)
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
    """Best-effort, court : utilisé à l'ajout d'une URL libre pour enregistrer
    un titre lisible plutôt que l'URL brute. Connexion bornée à 2 s, lecture
    totale à 5 s, au plus 3 redirections suivies (Q2)."""
    try:
        return verifier_flux(url, timeout=HTTP_TIMEOUT_TITRE,
                             max_redirects=MAX_REDIRECTS_TITRE)["titre"]
    except Exception:  # noqa: BLE001 — un titre manquant n'empêche pas l'ajout
        return None


def verifier_tous(db: Session, *, limit: int | None = None,
                  max_workers: int = VERIF_MAX_WORKERS,
                  timeout_future: float = VERIF_TIMEOUT_FUTURE) -> dict:
    """Vérifie les flux (utilisateurs d'abord, puis catalogue) en parallèle,
    borné, et rend la main vite (Q1 — un GET séquentiel de 46+ flux à 10 s
    pièce dépassait le timeout nginx et perdait tout le lot au premier
    worker recyclé).

    - Parallélisme : `max_workers` requêtes en vol (`ThreadPoolExecutor`).
    - Chaque flux utilisateur est commité dès que SON résultat arrive, pas à
      la fin du lot.
    - `limit` borne le nombre de flux traités dans CET appel ; `reste`
      indique combien restent à traiter (la route admin s'en sert pour ne
      jamais dépasser ~60 s par appel). Le script CLI appelle sans `limit`.
    - Le catalogue n'est jamais écrit (seuls les `RssFeed` le sont).

    Renvoie `{"resultats": [...], "reste": N}`.
    """
    from app.modules.watches.catalogue import catalogue

    flux_utilisateurs = list(db.scalars(select(RssFeed)))
    urls_utilisateurs = {f.url for f in flux_utilisateurs}
    entrees_catalogue = [f for f in catalogue() if f["url"] not in urls_utilisateurs]

    # Flux utilisateurs d'abord : ce sont eux qu'on écrit, et en cas de lot
    # tronqué par `limit` ils priment sur le catalogue (jamais persisté).
    a_traiter: list[tuple[str, RssFeed | None]] = (
        [(f.url, f) for f in flux_utilisateurs] + [(f["url"], None) for f in entrees_catalogue]
    )
    total = len(a_traiter)
    lot = a_traiter[:limit] if limit else a_traiter
    reste = max(0, total - len(lot))

    resultats: list[dict] = []
    # Revue tour 2 : `with ThreadPoolExecutor(...)` attend TOUS les threads à
    # la sortie du bloc (`shutdown(wait=True)` implicite), ce qui annule le
    # bornage de `future.result(timeout=...)` — un flux qui ne répond jamais
    # bloquait quand même la fonction jusqu'à ce qu'il abandonne de
    # lui-même. Executor créé sans `with` ; `shutdown(wait=False)` dans le
    # `finally` rend la main dès que le dernier `.result(timeout=...)` a
    # tranché, sans attendre les threads encore en vol (abandonnés à
    # l'interpréteur, comme n'importe quelle requête réseau qui traîne).
    executor = ThreadPoolExecutor(max_workers=max_workers)
    try:
        soumis = [(url, feed, executor.submit(verifier_flux, url)) for url, feed in lot]
        for url, feed, future in soumis:
            try:
                r = future.result(timeout=timeout_future)
            except FutureTimeoutError:
                r = {"url": url, "ok": False, "statut_http": None, "entrees": 0,
                     "dernier": None, "erreur": "délai de vérification dépassé", "titre": None}
            except Exception as e:  # noqa: BLE001 — jamais fatal pour le lot
                r = {"url": url, "ok": False, "statut_http": None, "entrees": 0,
                     "dernier": None, "erreur": str(e), "titre": None}
            resultats.append(r)
            if feed is not None:
                feed.derniere_verification_at = _now()
                feed.derniere_erreur = None if r["ok"] else (r["erreur"] or "erreur inconnue")
                db.commit()  # par flux (Q1), pas un seul commit final
    finally:
        executor.shutdown(wait=False)

    return {"resultats": resultats, "reste": reste}


def _flux_a_reverifier(mes_flux: list[RssFeed]) -> bool:
    seuil = _now() - SEUIL_REVERIFICATION

    def _aware(valeur: dt.datetime) -> dt.datetime:
        # SQLite (tests) rend un datetime naïf même pour une colonne
        # `DateTime(timezone=True)` — Postgres (prod) le rend déjà aware.
        # Sans cette normalisation, la comparaison lève sur SQLite.
        return valeur if valeur.tzinfo is not None else valeur.replace(tzinfo=dt.timezone.utc)

    return any(f.derniere_verification_at is None or _aware(f.derniere_verification_at) < seuil
              for f in mes_flux)


def _lancer_fil_verification(cible, *, user_id: str) -> None:
    """Indirection SEULE responsable de démarrer le fil démon de la
    vérification d'arrière-plan (Q6) — factorisée pour que les tests la
    substituent (exécution synchrone, ou simple comptage) sans jamais
    monkeypatcher `threading.Thread` lui-même : ce dernier est aussi ce que
    `ThreadPoolExecutor` utilise en interne pour SES propres threads
    (`verifier_tous`/`verifier_tous_pour`), et le patcher globalement les
    casse."""
    threading.Thread(target=cible, daemon=True, name=f"verif-flux-{user_id}").start()


def _verifier_utilisateur_en_arriere_plan(user_id: str) -> None:
    """Q6 : lancé en fil démon, best effort, depuis `GET /watches/{id}/feeds`
    quand au moins un flux de l'utilisateur n'a jamais été vérifié ou l'a été
    il y a plus de 7 jours. Rien d'autre (pas de cron) n'alimente ces deux
    colonnes hors script local / route admin — sans ça, un utilisateur qui
    n'a jamais ouvert Pilotage verrait tous ses points gris indéfiniment.

    Ouvre sa PROPRE session (jamais celle, liée à la requête, de l'appelant :
    elle serait fermée avant que ce fil ait fini). Un verrou en mémoire
    évite de relancer une vérification déjà en cours pour ce user_id (la
    fiche agent peut être rechargée plusieurs fois avant que le premier
    passage ne se termine).
    """
    with _verification_lock:
        if user_id in _verification_en_cours:
            return
        _verification_en_cours.add(user_id)

    def _run() -> None:
        from app.db import SessionLocal

        try:
            with SessionLocal() as db_arriere_plan:
                mes_flux = list(db_arriere_plan.scalars(
                    select(RssFeed).where(RssFeed.user_id == uuid.UUID(user_id))))
                verifier_tous_pour(db_arriere_plan, mes_flux)
        except Exception:  # noqa: BLE001 — best effort, ne doit jamais remonter
            logger.warning("Vérification d'arrière-plan des flux de %s échouée",
                           user_id, exc_info=True)
        finally:
            with _verification_lock:
                _verification_en_cours.discard(user_id)

    _lancer_fil_verification(_run, user_id=user_id)


def verifier_tous_pour(db: Session, flux: list[RssFeed], *,
                       max_workers: int = VERIF_MAX_WORKERS,
                       timeout_future: float = VERIF_TIMEOUT_FUTURE) -> list[dict]:
    """Même mécanique que `verifier_tous` (parallèle, bornée, commit par
    flux) mais sur une liste de `RssFeed` déjà choisie par l'appelant —
    factorisée pour que la vérification d'arrière-plan (Q6, tous les flux
    d'UN utilisateur) et `verifier_tous` (TOUS les flux) partagent le même
    code d'exécution."""
    resultats: list[dict] = []
    # Revue tour 2 : même correction que `verifier_tous` — pas de `with`
    # (qui attendrait tous les threads à la sortie), `shutdown(wait=False)`
    # en sortie pour rendre la main dès le dernier `.result(timeout=...)`.
    executor = ThreadPoolExecutor(max_workers=max_workers)
    try:
        soumis = [(f, executor.submit(verifier_flux, f.url)) for f in flux]
        for feed, future in soumis:
            try:
                r = future.result(timeout=timeout_future)
            except FutureTimeoutError:
                r = {"url": feed.url, "ok": False, "erreur": "délai de vérification dépassé"}
            except Exception as e:  # noqa: BLE001
                r = {"url": feed.url, "ok": False, "erreur": str(e)}
            feed.derniere_verification_at = _now()
            feed.derniere_erreur = None if r.get("ok") else (r.get("erreur") or "erreur inconnue")
            db.commit()
            resultats.append(r)
    finally:
        executor.shutdown(wait=False)
    return resultats


def _etat_flux(*, verifie_at, erreur) -> str:
    if verifie_at is None:
        return "inconnu"
    return "erreur" if erreur else "ok"


def feeds_pour_watch(db: Session, user_id: str, watch: Watch) -> list[dict]:
    """Flux visibles sur la fiche d'un agent (spec §3) : ceux de l'utilisateur
    (actifs — Q3, même filtre que `_feeds_for`) dont la catégorie ∈
    `skill.rss_categories`, plus le catalogue de ces catégories — chaque flux
    catalogue reprend l'état d'un flux utilisateur de même URL s'il existe
    PARMI CEUX AFFICHÉS (Q4 : un flux personnel classé hors des catégories du
    skill ne doit pas prêter son état à l'entrée catalogue de même URL),
    sinon `inconnu`.

    Déclenche aussi, best effort, la vérification d'arrière-plan des flux de
    l'utilisateur si nécessaire (Q6)."""
    from app.modules.watches import skills
    from app.modules.watches.catalogue import catalogue

    skill = skills.get_skill(watch.skill)
    categories = set(skill.rss_categories)

    mes_flux = list(db.scalars(
        select(RssFeed).where(RssFeed.user_id == uuid.UUID(user_id), RssFeed.active.is_(True),
                              RssFeed.category.in_(categories))
        .order_by(RssFeed.created_at.desc())))
    etat_par_url = {f.url: _etat_flux(verifie_at=f.derniere_verification_at,
                                      erreur=f.derniere_erreur) for f in mes_flux}
    verifie_at_par_url = {f.url: f.derniere_verification_at for f in mes_flux}

    items: list[dict] = []
    vues: set[str] = set()
    # Les flux du catalogue sont attachés au compte à la création de l'agent :
    # ils restent « catalogue » à l'écran, « ajouté par vous » ne vaut que pour
    # une URL libre.
    urls_catalogue = {c["url"] for c in catalogue()}
    for f in mes_flux:
        items.append({
            "url": f.url, "title": f.title, "category": f.category,
            "origine": "catalogue" if f.url in urls_catalogue else "moi", "etat": etat_par_url[f.url],
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

    tous_mes_flux = list(db.scalars(select(RssFeed).where(RssFeed.user_id == uuid.UUID(user_id))))
    if _flux_a_reverifier(tous_mes_flux):
        _verifier_utilisateur_en_arriere_plan(user_id)

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
