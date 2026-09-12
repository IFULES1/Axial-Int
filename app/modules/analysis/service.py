"""Analysis service — the single entry point to "run the algo".

`run_analysis()` is the one function that produces a report. It is deliberately
**resilient**: every external dependency (RAG, web-search, enrichment) is
best-effort. If the primary web-search engine is down (e.g. Perplexity quota),
the call does NOT crash — it returns a clear `degraded` result with a readable
status note, instead of the cryptic fallback the legacy system produced.

Depuis Rapports v2 (12/09), la production d'un rapport passe TOUJOURS par le
moteur suivi par identifiant : `lancer_rapport()` crée la ligne `reports` en
`en_cours` et `_executer_rapport()` la mène à son terme sur sa propre session,
en écrivant son avancement en base. `stream_analysis()` ne produit plus rien —
il REGARDE cette ligne et la relaie en Server-Sent Events, `POST /analysis/run`
attend son terme, et `POST /reports/{id}/annuler` pose un drapeau que la tâche
relit. Une seule implémentation, une seule propriété de survie à tester.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import threading
from dataclasses import dataclass, field

from app.modules.analysis.prompts import (
    SYSTEM_PROMPT,
    get_prompt_template,
    is_valid_type,
    angles_de_recherche,
    sources_for,
)
from app.errors import AppError
from app.shared import llm_client

logger = logging.getLogger("axial.analysis")

# Cadence de relecture de la ligne de rapport par le flux SSE (secondes). Le
# battement fictif à +3 % a disparu : ce que le flux émet vient de la base.
INTERVALLE_SUIVI_SECONDES = 2

# Amorce conservée quand l'utilisateur clique sur Stop : de quoi montrer que la
# rédaction avait commencé, pas de quoi lire le rapport sans l'avoir payé.
LIMITE_CONTENU_PARTIEL = 2000

# Correspondance étape → ancien `step` du flux, conservée jusqu'à Task 4 : le
# front en production lit encore `step` et `progress`.
_STEP_HERITE = {
    "recherche": "retrieve",
    "selection": "retrieve",
    "couverture": "retrieve",
    "redaction": "generate",
    "finalisation": "finalize",
}

# Type d'analyse adossé à la base investisseurs plutôt qu'à la recherche web.
INVESTOR_MAPPING = "cartographie_investisseurs"


def _canonical_type(analysis_type: str) -> str:
    from app.modules.analysis.prompts import _canonical

    return _canonical(analysis_type)


@dataclass
class AnalysisResult:
    analysis_type: str
    title: str
    content: str
    sources: list[dict] = field(default_factory=list)
    degraded: bool = False
    status_note: str | None = None
    metadata: dict = field(default_factory=dict)


def _retrieve_context(query: str, user_id: str, top_k: int):
    """RAG retrieval — best-effort. Returns (context_str, passages)."""
    if top_k <= 0:
        return "", []
    try:
        from app.modules.rag import service as rag

        passages = rag.retrieve(query, user_id=user_id, top_k=top_k)
        return rag.format_context(passages), passages
    except Exception as e:  # embeddings/qdrant unavailable → continue without RAG
        logger.warning("RAG retrieval skipped: %s", e)
        return "", []


# --- Suivi de progression et Stop (spec §1) --------------------------------

class ArretGeneration(Exception):
    """Interruption qui doit traverser les `except Exception` du pipeline.

    Une base commune aux deux motifs d'arrêt (Stop de l'utilisateur, échéance
    dépassée) : chaque `try/except Exception` large de `run_analysis` la réémet
    par un seul `except ArretGeneration: raise`, sans avoir à connaître la liste.
    """


class AnnulationDemandee(ArretGeneration):
    """Stop demandé par l'utilisateur — remonte jusqu'au moteur, qui range le
    rapport en `annule` sans rien débiter. Une exception plutôt qu'un code de
    retour : elle traverse les cinq étapes sans que chacune ait à la relayer."""


class DelaiDepasse(ArretGeneration):
    """Échéance globale atteinte — le rapport part en `echec`, rien n'est débité.

    Distincte de l'annulation : personne ne l'a demandée, et le statut doit le
    dire (`echec` + `detail.raison = "delai_depasse"`, et non `annule`).
    """


class Suivi:
    """Écrit l'avancement du rapport en base et relit le drapeau de Stop.

    Un objet et pas un `callable` : les deux gestes vont ensemble (on écrit
    l'étape, on relit l'annulation) et partagent la même session — celle du
    thread d'exécution, jamais celle de la requête HTTP.

    Chaque écriture commit : la ligne doit être lisible par la requête
    `GET /reports/{id}` d'un AUTRE processus pendant que la tâche tourne.
    C'est tout l'intérêt du suivi par identifiant.
    """

    # Toutes les N portions de texte, on relit le drapeau d'annulation. 20 :
    # assez pour ne pas faire une requête par mot, assez peu pour que « Stop »
    # réponde en moins d'une seconde.
    CHUNKS_PAR_VERIFICATION = 20

    def __init__(self, db, rapport):
        import time as _time

        self.db = db
        self.rapport = rapport
        self._chunks = 0
        # Échéance globale : les délais des fournisseurs sont des délais par
        # lecture, aucun ne borne la durée totale d'un rapport (jusqu'à quatre
        # appels de 32 000 tokens avec les reprises). Relue à chaque
        # `verifier()`, donc entre les étapes et toutes les 20 portions.
        self._depart = _time.monotonic()
        # Ce que la rédaction avait produit au moment du Stop. Rempli par
        # `_rediger`, relu par `_ranger_annule` : le texte est dans une variable
        # locale du générateur de flux, il faut le faire remonter avant que
        # l'exception ne déroule la pile.
        self.contenu_partiel = ""

    def etape(self, nom: str, progression: int, **detail) -> None:
        from app.modules.reports import models as rm

        if nom not in rm.ETAPES:  # garde-fou : une étape inconnue ne passe pas
            raise ValueError(f"Étape inconnue : {nom}")
        self.rapport.etape = nom
        self.rapport.progression = max(0, min(100, int(progression)))
        fusion = dict(self.rapport.detail or {})
        fusion.update({k: v for k, v in detail.items() if v is not None})
        self.rapport.detail = fusion
        self.db.commit()

    def depasse_le_delai(self) -> bool:
        """Vrai si l'échéance globale du rapport est atteinte.

        Lue sur le module de configuration à chaque appel (et non capturée à
        l'import) pour rester réglable sans redémarrage — et bouchonnable.
        """
        import time as _time

        from app import config as app_config

        return (_time.monotonic() - self._depart) > app_config.DELAI_MAX_RAPPORT_SECONDES

    def verifier(self) -> None:
        """Relit le drapeau depuis la BASE (et non l'objet en mémoire) : il est
        posé par une autre requête, sur une autre session. Vérifie du même
        geste l'échéance globale — les deux motifs d'arrêt sont relus aux mêmes
        instants (entre les étapes, toutes les 20 portions)."""
        self.db.refresh(self.rapport)
        if self.rapport.annulation_demandee:
            raise AnnulationDemandee()
        if self.depasse_le_delai():
            raise DelaiDepasse()

    def chunk(self, texte: str) -> None:
        """Appelé à chaque portion reçue du modèle pendant la rédaction."""
        self._chunks += 1
        if self._chunks % self.CHUNKS_PAR_VERIFICATION:
            return
        self.verifier()


# --- Aperçu des sources avant débit (spec §2) ------------------------------

# En deçà, le rapport n'aurait rien de solide à citer : la génération serait
# une extrapolation facturée. Le seuil est celui de la spec §2.
#
# « Pertinentes » se lit ici comme un NOMBRE de citations survivantes, pas
# comme un score : le seuil compte les entrées qui restent après le rerank et
# la déduplication — exactement ce que le modèle de rédaction verra — sans lire
# le score du reranker. Lecture plus permissive que la spec §2 (« dont le score
# dépasse le seuil du reranker »), assumée : l'orchestrateur ne remonte aucun
# score aujourd'hui, et le brief laissait `orchestrator.py` optionnel. Le jour
# où un score remonte, c'est ici que le filtre se resserre.
MIN_SOURCES_PERTINENTES = 5

# Jugement de couverture. NOUVEAU prompt court, tier `chat` : il ne touche à
# aucune directive de rapport (arbitrage §0 — les prompts système des rapports
# restent inchangés dans ce chantier). Isolé dans une constante pour relecture.
PROMPT_COUVERTURE = (
    "Voici une question et la liste des sources trouvées pour y répondre "
    "(titre et extrait).\n\n"
    "Question : {question}\n\n"
    "Sources :\n{sources}\n\n"
    "Ces sources permettent-elles de traiter la question de façon documentée ?\n"
    "Réponds par UN SEUL mot, sans ponctuation ni explication :\n"
    "- oui — les sources couvrent l'essentiel de la question ;\n"
    "- partiel — elles couvrent une partie seulement, le rapport devra signaler "
    "ses angles morts ;\n"
    "- non — elles sont hors sujet ou trop maigres pour produire quoi que ce soit."
)

_SYSTEME_COUVERTURE = ("Tu évalues la couverture documentaire d'une question. "
                       "Tu réponds par un seul mot : oui, partiel ou non.")


def apercu_sources(citations: list[dict], limite: int = 20) -> list[dict]:
    """Titre / URL / domaine des sources — ce que le front affiche quand la
    couverture est jugée insuffisante. Pas les extraits : l'aperçu est stocké
    en JSON sur la ligne du rapport, il doit rester léger."""
    apercu = []
    for c in (citations or [])[:limite]:
        if not isinstance(c, dict):
            continue
        apercu.append({"titre": c.get("title"), "url": c.get("url"),
                       "domaine": c.get("domain") or c.get("source")})
    return apercu


def _evaluer_couverture(question: str, citations: list[dict]) -> str:
    """« oui » | « partiel » | « non ». Un échec du juge ne bloque jamais.

    Le juge est un garde-fou, pas une autorité : s'il tombe (quota, panne,
    réponse illisible), le rapport part quand même. Refuser de générer parce
    qu'un modèle à 200 tokens n'a pas répondu serait pire que le problème.
    """
    if not citations:
        return "non"
    lignes = []
    for i, c in enumerate(citations[:25], 1):
        if not isinstance(c, dict):
            continue
        titre = (c.get("title") or "").strip()[:150]
        extrait = (c.get("excerpt") or "").strip().replace("\n", " ")[:200]
        lignes.append(f"[{i}] {titre} — {extrait}")
    try:
        res = llm_client.generate(
            system=_SYSTEME_COUVERTURE,
            prompt=PROMPT_COUVERTURE.format(question=question[:500],
                                            sources="\n".join(lignes)),
            tier="chat", max_tokens=200)
        mot = (res.text or "").strip().lower()
    except Exception as e:  # noqa: BLE001
        logger.warning("Jugement de couverture indisponible (%s) — on génère", e)
        return "oui"
    for verdict in ("partiel", "non", "oui"):  # « partiel » avant « non » : il
        if verdict in mot:                     # contient parfois les deux mots
            return verdict
    logger.info("Verdict de couverture illisible (%r) — on génère", mot[:60])
    return "oui"


def _angles_elargis(analysis_type: str, query: str, profile: dict | None) -> list[str]:
    """Angles supplémentaires pour « Recherche élargie » (spec §2).

    Produits une seule fois, par le moteur de relance : la route `relancer`
    crée un NOUVEAU rapport avec `elargir=True`, et ce rapport-là ne relance
    rien à son tour. Un échec rend une liste vide — la recherche standard
    tourne quand même.
    """
    contexte = ", ".join(str(v) for v in (
        (profile or {}).get("company_name"), (profile or {}).get("sector"),
        (profile or {}).get("target_market")) if v)
    try:
        res = llm_client.generate(
            system="Tu proposes des requêtes de recherche web, une par ligne, "
                   "sans numérotation ni commentaire.",
            prompt=("Question : " + query[:500]
                    + (f"\nContexte de l'entreprise : {contexte}" if contexte else "")
                    + "\n\nLa recherche standard n'a pas ramené assez de sources. "
                      "Propose 4 requêtes supplémentaires qui attaquent le sujet "
                      "par des angles différents (acteurs, synonymes du marché, "
                      "sources institutionnelles, langue anglaise)."),
            tier="chat", max_tokens=300)
        lignes = [ligne.strip(" -•\t") for ligne in (res.text or "").splitlines()]
    except Exception as e:  # noqa: BLE001
        logger.warning("Angles élargis indisponibles : %s", e)
        return []
    return [ligne for ligne in lignes if 8 <= len(ligne) <= 200][:4]


# --- Rédaction en flux : sections détectées au fil du texte (spec §1) ------

# Reprises après troncature, comme `claude.generate` sur le chemin bloquant :
# un rapport de 10 000 mots atteint la limite de sortie avant sa conclusion.
REPRISES_REDACTION_MAX = 3
_TITRE_SECTION = re.compile(r"^##\s+\S", re.MULTILINE)


def _sections_attendues(analysis_type: str) -> int:
    """Nombre de titres `##` attendus — le dénominateur de « section 3/8 ».

    Les directives ne portent pas de plan fixe (arbitrage §0 : on ne touche pas
    aux prompts). On l'estime depuis les axes de la directive, plus la synthèse
    exécutive d'ouverture, la conclusion et la section « Sources » qu'impose le
    style. C'est une estimation assumée : le numérateur, lui, est réel, et
    l'affichage est borné pour ne jamais annoncer « section 9/8 ».
    """
    from app.modules.analysis.prompts import ANALYSIS_DIRECTIVES, _canonical

    directive = ANALYSIS_DIRECTIVES.get(_canonical(analysis_type)) or {}
    return max(4, len(directive.get("key_angles") or []) + 3)


def _rediger(*, system: str, prompt: str, tier: str, max_tokens: int,
             suivi: "Suivi | None", analysis_type: str):
    """Génère le rapport. En flux si un suivi est branché, sinon en bloquant.

    Le flux n'est pas un confort : c'est le seul moyen de savoir où en est la
    rédaction (les titres `##` arrivent au fil du texte) et de répondre à un
    Stop pendant les minutes d'écriture. Sans suivi — appels directs au
    pipeline, tests unitaires — on garde l'appel bloquant, plus simple.
    """
    from app.shared.llm_client.base import resultat_de_mesure

    if suivi is None:
        return llm_client.generate(system=system, prompt=prompt, tier=tier,
                                   max_tokens=max_tokens)

    from app.shared.llm_client.claude import SUITE_CONSIGNE

    total = _sections_attendues(analysis_type)
    mesure: dict = {}
    morceaux: list[str] = []
    sections_vues = 0
    raison = None
    prompt_courant, historique = prompt, None

    # Fournisseur épinglé dès la première passe : `stream_text` rejoue sa
    # chaîne de repli à chaque appel, et si Claude devenait indisponible entre
    # deux reprises, la suite du rapport serait écrite par Gemini — deux styles
    # recollés dans un même document. Mieux vaut un rapport tronqué (statut
    # `truncated_generation`, rien débité) qu'un rapport épissé.
    fournisseur: str | None = None

    for reprise in range(REPRISES_REDACTION_MAX + 1):
        flux = llm_client.stream_text(system=system, prompt=prompt_courant,
                                      tier=tier, history=historique,
                                      max_tokens=max_tokens, mesure=mesure,
                                      fournisseur=fournisseur)
        try:
            while True:
                try:
                    chunk = next(flux)
                except StopIteration as fin:
                    raison = fin.value
                    break
                morceaux.append(chunk)
                suivi.chunk(chunk)  # relit le Stop toutes les N portions
                # Les titres sont comptés sur le texte RECOLLÉ, jamais sur la
                # portion : « ## Titre » arrive régulièrement à cheval sur
                # deux portions. Le re-balayage est espacé — un `findall` sur
                # tout le texte à chaque portion serait quadratique.
                if len(morceaux) % Suivi.CHUNKS_PAR_VERIFICATION:
                    continue
                vues = len(_TITRE_SECTION.findall("".join(morceaux)))
                if vues == sections_vues:
                    continue
                sections_vues = vues
                suivi.etape("redaction",
                            min(85, 50 + int(35 * min(vues, total) / total)),
                            section=f"{min(max(vues, 1), total)}/{total}",
                            message="Rédaction du rapport…")
        except ArretGeneration:
            # Faire remonter l'amorce AVANT que l'exception ne déroule la pile :
            # `morceaux` est local à cette fonction.
            suivi.contenu_partiel = "".join(morceaux)
            raise
        finally:
            flux.close()
        if raison != "max_tokens":
            break
        partiel = "".join(morceaux)
        if not partiel.strip():
            break
        logger.info("Rapport tronqué, reprise %d/%d", reprise + 1,
                    REPRISES_REDACTION_MAX)
        # `mesure["provider"]` est rempli par le fournisseur qui a répondu :
        # c'est le seul moyen de savoir qui a commencé, donc qui doit finir.
        fournisseur = mesure.get("provider") or fournisseur
        historique = [{"role": "user", "content": prompt},
                      {"role": "assistant", "content": partiel}]
        prompt_courant = SUITE_CONSIGNE

    texte = "".join(morceaux)
    res = resultat_de_mesure(mesure)
    if res is None:  # fournisseur muet : mieux vaut aucun coût qu'un coût faux
        from app.shared.llm_client.base import LLMResult

        res = LLMResult(text="", model="", provider="")
    res.text = texte
    res.stop_reason = raison
    return res


def run_analysis(*, query: str, analysis_type: str, user_id: str,
                 title: str | None = None, top_k: int | None = None,
                 company_context: str = "", tier: str = "report",
                 profile: dict | None = None,
                 db_pour_notion=None, suivi: "Suivi | None" = None,
                 elargir: bool = False, forcer: bool = False) -> AnalysisResult:
    """Produit un rapport. `suivi` (facultatif) reçoit l'avancement réel.

    `suivi` est le seul lien avec la ligne `reports` : sans lui le moteur se
    comporte exactement comme avant (c'est ce que font les tests unitaires du
    pipeline). Avec lui, chaque étape écrit `etape`/`progression`/`detail` en
    base et le drapeau de Stop est relu entre deux étapes et pendant le flux.

    `elargir` — une seconde passe de recherche sur des angles supplémentaires
    produits par le modèle (spec §2, « Recherche élargie »), une seule fois.
    `forcer` — génère malgré un verdict de couverture `non` (« Générer quand
    même »), le rapport porte alors `detail.raison = couverture_partielle`.
    """
    import time as _time

    _depart = _time.monotonic()
    # Rempli par l'orchestrateur : le coût de recherche n'apparaît sur aucune
    # facture ventilée par rapport, il faut le compter à la source.
    appels_recherche: dict[str, int] = {}
    if not is_valid_type(analysis_type):
        raise AppError(f"Type d'analyse inconnu : {analysis_type}", 400,
                       code="unknown_analysis_type")

    # Le type d'analyse commande le volume de sources (40 pour une synthèse
    # exécutive, 25 pour une veille) — la directive et le pipeline restent alignés.
    top_k = top_k or sources_for(analysis_type)

    label_title = title or analysis_type.replace("_", " ").title()

    # Disponibilité du moteur de génération vérifiée AVANT la recherche : c'est
    # instantané, et sans modèle ni le jugement de couverture ni la rédaction ne
    # peuvent aboutir — inutile de payer des appels de recherche pour rien.
    if not llm_client.generation_available():
        return AnalysisResult(
            analysis_type=analysis_type, title=label_title,
            content=("⚠️ Aucun moteur de génération n'est disponible pour le moment. "
                     "Réessayez une fois le service rétabli."),
            degraded=True, status_note="llm_unavailable",
            metadata={"passages": 0, "web_sources": 0},
        )

    # 1. External grounding: multi-provider web search (Exa+Tavily+Linkup) + rerank.
    from app.shared import search as web_search

    if suivi:
        suivi.verifier()
        suivi.etape("recherche", 10, message="Recherche des sources…")
    try:
        # Recherche multi-angles : la question de l'utilisateur, plus un angle
        # par axe de la directive. Une requête unique ne ramenait qu'une facette
        # du sujet, et ce que la recherche ne trouvait pas finissait comblé par
        # extrapolation dans le rapport.
        angles = angles_de_recherche(analysis_type, query)
        if elargir:
            angles = angles + _angles_elargis(analysis_type, query, profile)
        web_results = web_search.search_multi(angles, top_k=top_k,
                                              requete_de_rang=query,
                                              compteur=appels_recherche)
    except ArretGeneration:
        raise
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        angles, web_results = [query], []
    if suivi:
        suivi.etape("recherche", 20, angles=len(angles),
                    sources_trouvees=len(web_results),
                    message=f"{len(web_results)} source(s) trouvée(s) sur "
                            f"{len(angles)} angle(s).")

    # 2. Internal grounding: RAG over the user's documents. No arbitrary cap —
    # retrieval hands over everything it finds and the reranker below arbitrates,
    # so a user with rich documents gets all of their relevant material.
    _, passages = _retrieve_context(query, user_id, top_k)

    # 3. ONE ranked, numbered pool: web and internal compete on relevance and the
    # [N] markers map 1:1 to the citations the reader sees (they used to be two
    # separate numberings colliding in the same prompt).
    from app.shared import grounding

    # Investor mapping is grounded FIRST on Axial's own investor database — that
    # verified data is the subject of the report; web results only add timing
    # context, and are numbered after so every [N] still maps to one citation.
    investor_context, investor_citations = "", []
    if _canonical_type(analysis_type) == INVESTOR_MAPPING:
        from app.modules.investors import service as investors

        mapping = None
        try:
            mapping = investors.map_for_profile(profile or {})
            investor_context = investors.format_context(mapping)
            investor_citations = investors.citations(mapping)
        except Exception as e:
            logger.warning("Investor mapping unavailable: %s", e)
        # Ce rapport N'EXISTE que par la base investisseurs : sans elle, mieux
        # vaut le dire et ne rien facturer qu'un texte adossé au web seul.
        if not investor_citations:
            reason = (mapping or {}).get("note") if mapping else None
            return AnalysisResult(
                analysis_type=analysis_type, title=label_title,
                content=("⚠️ La cartographie des investisseurs n'a pas pu être "
                         "produite. " + (reason or "La base investisseurs est "
                         "momentanément indisponible.") + " Aucun crédit n'a été "
                         "débité."),
                degraded=True, status_note="investors_unavailable",
                metadata={"passages": len(passages), "web_sources": len(web_results)},
            )

    # Espace Notion de l'utilisateur : ses pages rejoignent le pool de sources.
    try:
        from app.modules.integrations import notion_context

        passages = list(passages) + notion_context.passages_pour(db_pour_notion, user_id, query) \
            if db_pour_notion is not None else list(passages)
    except Exception as e:  # noqa: BLE001
        logger.warning("Espace Notion indisponible : %s", e)

    if suivi:
        suivi.verifier()
        suivi.etape("selection", 30, message="Sélection des sources les plus pertinentes…")

    context, citations = grounding.assemble(
        query, web_results, passages, top_k, start_at=len(investor_citations) + 1
    )
    if investor_context:
        context = investor_context + ("\n\n" + context if context else "")
        citations = investor_citations + citations

    if suivi:
        suivi.etape("selection", 35, sources_retenues=len(citations),
                    sources=apercu_sources(citations),
                    message=f"{len(citations)} source(s) retenue(s).")

    # --- Aperçu des sources avant débit (spec §2) --------------------------
    # Le jugement tourne APRÈS le rerank et AVANT le modèle de rédaction :
    # c'est le seul instant où l'on sait ce qu'on a réellement sous la main et
    # où l'on n'a encore rien facturé. « Pertinentes » = ce qui reste après le
    # rerank et la déduplication, c'est-à-dire exactement ce que le modèle
    # verra.
    if suivi:
        suivi.verifier()
        suivi.etape("couverture", 40, message="Vérification de la couverture…")
    verdict = _evaluer_couverture(query, citations) if not forcer else "forcee"
    if not forcer and (verdict == "non" or len(citations) < MIN_SOURCES_PERTINENTES):
        return AnalysisResult(
            analysis_type=analysis_type, title=label_title,
            content=("Les sources trouvées ne permettent pas de traiter cette "
                     "question de façon fiable. Aucun crédit n'a été débité. "
                     "Vous pouvez reformuler la question, élargir la recherche "
                     "ou lancer la génération malgré tout."),
            sources=citations, degraded=True,
            status_note="sources_insuffisantes",
            metadata={"passages": len(passages), "web_sources": len(web_results),
                      "couverture": verdict, "sources_pertinentes": len(citations)},
        )
    # `partiel` (et « générer quand même ») n'arrêtent rien : le rapport est
    # produit, mais il porte la raison en clair — le lecteur doit savoir sur
    # quoi il s'appuie.
    raison_couverture = ("couverture_partielle"
                         if verdict in ("partiel", "forcee") else None)
    if suivi:
        suivi.etape("couverture", 45, couverture=verdict,
                    raison=raison_couverture,
                    message="Couverture suffisante." if verdict == "oui"
                            else "Couverture partielle — génération poursuivie.")

    prompt = get_prompt_template(analysis_type).format(context=context or "Aucun.")
    if company_context:
        prompt = f"{company_context}\n\n{prompt}"
    prompt = f"{prompt}\n\nQuestion de l'utilisateur : {query}"

    # PII guard: redact outbound payload per configured mode before it leaves.
    from app.modules.pii.client import guard_outbound

    prompt = guard_outbound(prompt)

    # 4. Two-tier synthesis (Gemini for chat/draft, Claude for final reports).
    if suivi:
        suivi.verifier()
        suivi.etape("redaction", 50, section="1/%d" % _sections_attendues(analysis_type),
                    message="Rédaction du rapport…")
    try:
        # Sonnet 5 : le thinking adaptatif se décompte de max_tokens — un budget
        # trop court peut être entièrement consommé en réflexion (texte vide).
        from app.shared import langue as lg

        result = _rediger(system=SYSTEM_PROMPT + lg.consigne_miroir(),
                          prompt=prompt, tier=tier, max_tokens=32000,
                          suivi=suivi, analysis_type=analysis_type)
    except ArretGeneration:
        raise
    except Exception as e:
        logger.warning("Generation failed: %s", e)
        return AnalysisResult(
            analysis_type=analysis_type, title=label_title,
            content=f"⚠️ La génération a échoué ({type(e).__name__}). Réessayez dans un instant.",
            degraded=True, status_note="generation_failed",
            metadata={"passages": len(passages), "web_sources": len(web_results)},
        )

    if not (result.text or "").strip():
        logger.warning("Génération vide (thinking a consommé le budget ?) — modèle %s",
                       result.model)
        return AnalysisResult(
            analysis_type=analysis_type, title=label_title,
            content=("⚠️ La génération n'a pas abouti. Réessayez dans un instant — "
                     "aucun crédit n'a été débité."),
            degraded=True, status_note="empty_generation",
            metadata={"passages": len(passages), "web_sources": len(web_results)},
        )

    # Dernier filet : si le texte reste tronqué après les reprises automatiques,
    # on ne livre pas un document coupé en plein mot comme s'il était terminé.
    # Le crédit n'est pas débité — l'utilisateur n'a pas reçu ce qu'il a demandé.
    if result.stop_reason == "max_tokens":
        logger.warning("Rapport encore tronqué après reprises — type %s, modèle %s, "
                       "%d caractères produits", analysis_type, result.model,
                       len(result.text or ""))
        return AnalysisResult(
            analysis_type=analysis_type, title=label_title,
            content=(result.text or "") + (
                "\n\n---\n\n⚠️ **Ce rapport est incomplet.** La rédaction a atteint "
                "la limite de sortie du modèle avant sa conclusion. Aucun crédit "
                "n'a été débité — relancez la génération."),
            sources=citations, degraded=True, status_note="truncated_generation",
            metadata={"passages": len(passages), "web_sources": len(web_results),
                      "stop_reason": result.stop_reason},
        )

    from app.modules.billing.couts import cout_micro_eur, cout_recherche_micro_eur

    mesure = {
        "appels_recherche": sum(appels_recherche.values()) or None,
        "cout_recherche_micro_eur": cout_recherche_micro_eur(appels_recherche) or None,
        "tokens_entree": result.input_tokens or None,
        "tokens_sortie": result.output_tokens or None,
        "modele": result.model,
        "cout_micro_eur": cout_micro_eur(result.model, result.input_tokens or 0,
                                         result.output_tokens or 0) or None,
        "duree_secondes": int(_time.monotonic() - _depart),
    }

    sources = citations
    return AnalysisResult(
        analysis_type=analysis_type,
        title=label_title,
        content=result.text,
        sources=sources,
        degraded=False,
        status_note=None,
        metadata={
            "passages": len(passages),
            "web_sources": len(web_results),
            "model": result.model,
            "provider": result.provider,
            "tier": tier,
            "tokens": result.tokens,
            "cout": mesure,
            "couverture": verdict,
            "raison": raison_couverture,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )


# --- Billing / persistence orchestration -----------------------------------

def precheck_credits(db, user_id: str, analysis_type: str, *, is_admin: bool) -> None:
    """Verify affordability BEFORE spending an API call. Admins bypass."""
    if is_admin:
        return
    from app.modules.billing import service as billing

    chk = billing.check_credits(db, user_id, analysis_type)
    if not chk["affordable"]:
        raise AppError(
            f"Crédits insuffisants ({chk['available']}/{chk['cost']}).",
            402, code="insufficient_credits",
        )


def finalize(db, user_id: str, analysis_type: str, result: AnalysisResult,
             *, is_admin: bool, rapport=None) -> dict:
    """Terme d'une analyse : débit + contenu + viz, **en une transaction**.

    Jusqu'au 12/09, `consume_credits` committait le débit puis `create_report`
    committait l'archive : entre les deux, une panne laissait 40 crédits
    débités sans rapport. Les deux écritures partagent désormais la session et
    un seul `commit` — si l'archivage échoue, le débit tombe avec lui.

    `rapport` — la ligne `en_cours` créée au lancement (spec §1). Absent, une
    ligne est créée ici : c'est le chemin des appelants qui ne suivent pas la
    génération par identifiant.

    Un résultat dégradé n'est jamais facturé. Il est en revanche CONSERVÉ
    quand une ligne existe déjà (statut `degrade` / `sources_insuffisantes`,
    `detail.raison`) : la spec §3 veut que l'utilisateur retrouve son rapport
    raté avec la raison en clair, plutôt qu'un écran vide.
    """
    from app.modules.reports import models as rm

    if result.degraded:
        if rapport is None:
            return {"report_id": None, "charged": 0}
        statut = (rm.SOURCES_INSUFFISANTES
                  if result.status_note == "sources_insuffisantes" else rm.DEGRADE)
        _cloturer(db, rapport, result, statut=statut, charged=0,
                  viz=_viz_hors_transaction(db, result.content or ""))
        return {"report_id": str(rapport.id), "charged": 0, "statut": statut}

    from app.modules.analytics import client as analytics
    from app.modules.billing import service as billing

    if rapport is None:
        rapport = _nouvelle_ligne(db, user_id, analysis_type=analysis_type,
                                  title=result.title, question=None,
                                  statut=rm.EN_COURS)
    # Visualisations préparées AVANT la transaction de clôture, sur leur propre
    # commit : elles insèrent des `VizRendu` partagés par empreinte, et deux
    # rapports concurrents qui produisent la même viz se collisionnent. Dans la
    # transaction de clôture, cette collision laissait la session en
    # `PendingRollbackError` et faisait partir en `echec` un rapport de 32 000
    # tokens entièrement produit. Ici, elle ne coûte au pire que les viz.
    viz = _viz_hors_transaction(db, result.content or "")
    # Débit SANS commit : il rejoint la transaction de l'archivage ci-dessous.
    billing_res = billing.consume_credits(db, user_id, analysis_type,
                                          is_admin=is_admin, commit=False)
    charged = billing_res.get("charged", 0)
    try:
        _cloturer(db, rapport, result, statut=rm.TERMINE, charged=charged,
                  viz=viz)
    except Exception:
        # Un seul rollback pour les deux : le débit n'a jamais été committé.
        db.rollback()
        raise

    analytics.increment_usage(user_id, analyses=1, credits=charged, reports=1)
    result.metadata["report_id"] = str(rapport.id)
    result.metadata["charged"] = charged
    result.metadata["viz"] = rapport.viz or []
    return {"report_id": str(rapport.id), "charged": charged, "statut": rm.TERMINE}


def _nouvelle_ligne(db, user_id: str, *, analysis_type: str, title: str | None,
                    question: str | None, statut: str):
    """La ligne `reports` créée AU LANCEMENT (spec §1) — contenu vide."""
    import uuid as _uuid

    from app.modules.reports.models import Report

    rapport = Report(
        id=_uuid.uuid4(), user_id=_uuid.UUID(user_id), analysis_type=analysis_type,
        title=title or _titre_provisoire(analysis_type), content="",
        statut=statut, progression=0, etape=None, question=question,
    )
    db.add(rapport)
    db.commit()
    db.refresh(rapport)
    return rapport


def _titre_provisoire(analysis_type: str) -> str:
    from app.modules.analysis.prompts import ANALYSIS_LABELS, _canonical

    return ANALYSIS_LABELS.get(_canonical(analysis_type)) or \
        analysis_type.replace("_", " ").title()


def _viz_hors_transaction(db, contenu: str) -> list[dict] | None:
    """Prépare et enregistre les visualisations sur leur PROPRE transaction.

    Hors de la transaction de clôture, délibérément (spec §5.1 revue) : les
    rendus sont partagés par empreinte entre rapports, donc leur insertion peut
    entrer en collision, et une collision à l'intérieur de la clôture faisait
    tomber le débit ET le contenu d'un rapport abouti. Un échec ici ne coûte
    que les viz : le rapport est archivé `termine` sans elles.
    """
    from app.modules.viz import service as viz_service

    # `preparer_sans_faute` garde son `try/except` (il avale déjà les erreurs
    # de compilation) ; ce qu'il ne fait pas, c'est ranger la session après une
    # erreur de BASE. C'est le rôle du rollback ci-dessous.
    viz = viz_service.preparer_sans_faute(db, contenu)
    try:
        db.commit()
    except Exception:  # noqa: BLE001 — course sur une empreinte, par exemple
        logger.exception("Enregistrement des visualisations échoué — rapport "
                         "archivé sans elles")
        db.rollback()
        return None
    return viz


def _cloturer(db, rapport, result: AnalysisResult, *, statut: str,
              charged: int, viz: list[dict] | None = None) -> None:
    """Écrit le terme du rapport dans la session courante, SANS committer le
    débit séparément : `db.commit()` ici clôt les deux d'un coup.

    `viz` est passé tout prêt par `_viz_hors_transaction` : rien de ce qui peut
    échouer sur une course entre rapports n'entre dans cette transaction.
    """
    cout = (result.metadata or {}).get("cout") or {}
    rapport.title = result.title or rapport.title
    rapport.content = result.content or ""
    rapport.sources = result.sources or None
    rapport.tokens_entree = cout.get("tokens_entree")
    rapport.tokens_sortie = cout.get("tokens_sortie")
    rapport.cout_micro_eur = cout.get("cout_micro_eur")
    rapport.modele = cout.get("modele")
    rapport.duree_secondes = cout.get("duree_secondes")
    rapport.cout_recherche_micro_eur = cout.get("cout_recherche_micro_eur")
    rapport.appels_recherche = cout.get("appels_recherche")
    # Visualisations : préparées une fois, en amont (`_viz_hors_transaction`),
    # réutilisées par l'app et le PDF. Un échec ne remet en cause ni la
    # facturation ni l'archive — la ligne porte simplement `viz = None`.
    rapport.viz = viz
    rapport.statut = statut
    rapport.etape = "finalisation"
    rapport.progression = 100
    rapport.termine_at = dt.datetime.now(dt.timezone.utc)
    detail = dict(rapport.detail or {})
    detail["credits"] = charged
    raison = result.status_note or (result.metadata or {}).get("raison")
    if raison:
        detail["raison"] = raison
    if result.sources:
        detail["sources"] = apercu_sources(result.sources)
    rapport.detail = detail
    db.commit()


# --- Moteur suivi par identifiant (spec §1) --------------------------------

def lancer_rapport(db, user_id: str, *, query: str, analysis_type: str,
                   title: str | None = None, top_k: int | None = None,
                   is_admin: bool = False, elargir: bool = False,
                   forcer: bool = False, attendre: bool = False):
    """Crée la ligne `en_cours` et lance le moteur. Retourne le `Report`.

    `attendre=False` (flux) : la tâche part dans un thread démon et survit à la
    requête HTTP — c'est ce qui permet de fermer l'onglet sans perdre le
    rapport. `attendre=True` (`POST /analysis/run`) : la même tâche tourne dans
    le thread de la requête, mais **sur sa propre session** — la propriété de
    survie appartient au moteur, pas à la route, et il n'existe qu'une
    implémentation à tester (arbitrage §0).
    """
    from app.modules.reports import models as rm

    # Type et solde vérifiés AVANT de créer la ligne : une question mal formée
    # doit rendre un 400, pas un rapport en échec dans la liste.
    if not is_valid_type(analysis_type):
        raise AppError(f"Type d'analyse inconnu : {analysis_type}", 400,
                       code="unknown_analysis_type")
    precheck_credits(db, user_id, analysis_type, is_admin=is_admin)
    rapport = _nouvelle_ligne(db, user_id, analysis_type=analysis_type,
                              title=title, question=query, statut=rm.EN_COURS)
    # Le contexte d'entreprise et le profil sont lus ICI, sur la session de la
    # requête : la tâche ne doit dépendre d'aucun objet de cette session.
    from app.modules.memory import service as memory

    contexte = dict(
        query=query, analysis_type=analysis_type, title=title, top_k=top_k,
        is_admin=is_admin, elargir=elargir, forcer=forcer, user_id=user_id,
        company_context=memory.build_context(db, user_id),
        profile=_profile_dict(db, user_id),
    )
    rapport_id = str(rapport.id)
    if attendre:
        _executer_rapport(rapport_id, **contexte)
        # `rollback()` et pas `expire_all()` : le second vide le cache
        # d'identité mais LAISSE la transaction de lecture ouverte — plusieurs
        # minutes d'« idle in transaction » par appel, et sous une isolation
        # plus stricte que READ COMMITTED la relecture rendrait la ligne encore
        # `en_cours` (donc `offrir` concluant « non abouti » sur un rapport
        # réussi). Un rollback clôt la transaction ET expire les objets.
        db.rollback()
        return db.get(rm.Report, rapport.id)

    threading.Thread(target=_executer_rapport, args=(rapport_id,),
                     kwargs=contexte, daemon=True,
                     name=f"rapport-{rapport_id[:8]}").start()
    return rapport


def _executer_rapport(rapport_id: str, *, user_id: str, query: str,
                      analysis_type: str, title: str | None, top_k: int | None,
                      is_admin: bool, elargir: bool, forcer: bool,
                      company_context: str, profile: dict) -> None:
    """Le moteur. Tourne sur SA session, quoi qu'il arrive au client.

    La session de la requête HTTP meurt avec la réponse : ouvrir la sienne est
    la condition pour que la tâche puisse encore écrire quand le navigateur est
    parti. Cette fonction ne lève jamais — tout se termine par un statut, y
    compris quand c'est l'OUVERTURE de la session qui échoue (pool saturé, base
    injoignable) : le thread mourait alors avant d'avoir pu écrire quoi que ce
    soit et la ligne restait `en_cours` pour toujours.

    C'est aussi le seul endroit qui prévient par email : `offrir` et
    `POST /analysis/run` passent par ici, une notification par rapport abouti.
    """
    import uuid as _uuid

    from app.modules.reports import models as rm

    try:
        from app.db import SessionLocal

        with SessionLocal() as db:
            rapport = db.get(rm.Report, _uuid.UUID(rapport_id))
            if rapport is None:  # supprimé entre-temps : rien à écrire
                logger.info("Rapport %s disparu avant exécution", rapport_id)
                return
            suivi = Suivi(db, rapport)
            try:
                resultat = run_analysis(
                    query=query, analysis_type=analysis_type, user_id=user_id,
                    title=title, top_k=top_k, company_context=company_context,
                    profile=profile, db_pour_notion=db, suivi=suivi,
                    elargir=elargir, forcer=forcer,
                )
            except AnnulationDemandee:
                _ranger_annule(db, rapport, suivi.contenu_partiel)
                return
            except DelaiDepasse as e:
                logger.warning("Rapport %s abandonné : échéance de %ds dépassée",
                               rapport_id, _delai_max())
                _ranger_echec(db, rapport, e, raison="delai_depasse")
                return
            except Exception as e:  # noqa: BLE001 — aucune panne ne laisse `en_cours`
                logger.warning("Rapport %s en échec : %s", rapport_id, e, exc_info=True)
                _ranger_echec(db, rapport, e)
                return

            try:
                # Dernière lecture du Stop et de l'échéance : l'utilisateur a pu
                # cliquer pendant la finalisation. Après le débit, il serait trop tard.
                suivi.verifier()
                suivi.etape("finalisation", 90, message="Finalisation…")
                finalize(db, user_id, analysis_type, resultat, is_admin=is_admin,
                         rapport=rapport)
            except AnnulationDemandee:
                _ranger_annule(db, rapport, suivi.contenu_partiel)
                return
            except DelaiDepasse as e:
                logger.warning("Rapport %s abandonné à la finalisation : échéance "
                               "de %ds dépassée", rapport_id, _delai_max())
                _ranger_echec(db, rapport, e, raison="delai_depasse")
                return
            except Exception as e:  # noqa: BLE001
                logger.warning("Archivage du rapport %s en échec : %s", rapport_id, e,
                               exc_info=True)
                _ranger_echec(db, rapport, e)
                return

            if resultat.degraded:
                return  # `finalize` a déjà rangé le rapport en degrade/sources_insuffisantes
            # Prévenir depuis la tâche : c'est le seul endroit qui s'exécute que le
            # navigateur soit encore là ou non. UNE seule notification par rapport
            # — les appelants (`offrir`, `/run`) n'en envoient pas de leur côté.
            try:
                from app.modules.reports import notification

                notification.prevenir(db, user_id, titre=resultat.title,
                                      contenu=resultat.content,
                                      sources=resultat.sources)
            except Exception as e:  # noqa: BLE001 — un email raté n'annule pas un rapport
                logger.warning("Notification du rapport %s échouée : %s", rapport_id, e)
    except Exception as e:  # noqa: BLE001 — y compris l'ouverture de la session
        logger.warning("Rapport %s : le moteur n'a pas pu tourner (%s)",
                       rapport_id, e, exc_info=True)
        _ranger_echec_session_courte(rapport_id, e)


def _delai_max() -> int:
    from app import config as app_config

    return app_config.DELAI_MAX_RAPPORT_SECONDES


def _ranger_echec_session_courte(rapport_id: str, erreur: BaseException) -> None:
    """Range la ligne en `echec` depuis une SECONDE session, très courte.

    Dernier recours quand la session du moteur n'a pas pu s'ouvrir ou qu'elle
    est morte en route : sans cela la ligne reste `en_cours` indéfiniment et
    rien côté flux ne s'en aperçoit. Si même cette session échoue, on le
    journalise — c'est tout ce qui reste, et le balayage des orphelins
    (Task 3) prendra la suite.
    """
    import uuid as _uuid

    from app.modules.reports import models as rm

    try:
        from app.db import SessionLocal

        with SessionLocal() as db:
            rapport = db.get(rm.Report, _uuid.UUID(rapport_id))
            if rapport is None:
                return
            _ranger_echec(db, rapport, erreur)
    except Exception as e:  # noqa: BLE001
        logger.error("Rapport %s laissé en_cours : impossible d'écrire l'échec "
                     "(%s)", rapport_id, e)


def _ranger_annule(db, rapport, partiel: str = "") -> None:
    """Stop : aucun débit, `content` vide, l'amorce rangée dans `detail`.

    `content` reste vide DÉLIBÉRÉMENT : un rapport annulé n'a pas été payé, il
    ne doit pas se lire comme un rapport. L'amorce tronquée à 2 000 caractères
    dit seulement que la rédaction avait commencé.
    """
    from app.modules.reports import models as rm

    db.rollback()  # rien de ce qui était en attente ne doit passer
    rapport = db.get(rm.Report, rapport.id)
    if rapport is None:
        return
    detail = dict(rapport.detail or {})
    detail["raison"] = "annule_par_utilisateur"
    detail["message"] = "Génération arrêtée. Aucun crédit n'a été débité."
    if partiel:
        detail["contenu_partiel"] = partiel[:LIMITE_CONTENU_PARTIEL]
    rapport.detail = detail
    rapport.statut = rm.ANNULE
    rapport.content = ""
    rapport.progression = 100
    rapport.termine_at = dt.datetime.now(dt.timezone.utc)
    db.commit()


def _ranger_echec(db, rapport, erreur: BaseException, *,
                  raison: str = "echec_generation") -> None:
    """`echec` : rien débité, la raison en clair dans `detail`.

    `raison` — « delai_depasse » quand l'échéance globale a coupé la tâche :
    le front (Task 4) doit pouvoir distinguer « ça a planté » de « ça a duré
    trop longtemps », les deux ne se relancent pas dans le même état d'esprit.
    """
    from app.modules.reports import models as rm

    db.rollback()
    rapport = db.get(rm.Report, rapport.id)
    if rapport is None:
        return
    detail = dict(rapport.detail or {})
    detail["raison"] = raison
    # Une `AppError` porte un message déjà écrit pour l'utilisateur (« Crédits
    # insuffisants », par exemple, quand le solde a fondu ailleurs pendant les
    # minutes de rédaction) : le masquer derrière un message générique
    # laisserait la personne sans explication actionnable.
    message = getattr(erreur, "message", None) if isinstance(erreur, AppError) else None
    if raison == "delai_depasse":
        message = message or ("La génération a dépassé le délai maximal et a été "
                              "arrêtée. Aucun crédit n'a été débité — vous pouvez "
                              "la relancer.")
    detail["message"] = message or ("La génération a échoué. Aucun crédit n'a été "
                                    "débité — vous pouvez la relancer.")
    detail["erreur"] = type(erreur).__name__
    rapport.detail = detail
    rapport.statut = rm.ECHEC
    rapport.progression = 100
    rapport.termine_at = dt.datetime.now(dt.timezone.utc)
    db.commit()


# --- SSE streaming ---------------------------------------------------------

def _sse(event: dict) -> str:
    # `default=str` : l'événement `done` porte désormais un `ReportDetail`
    # complet, dates comprises. Sans lui, `created_at` faisait échouer la
    # sérialisation du DERNIER événement — celui qui porte le rapport.
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


def stream_analysis(*, db, user_id: str, is_admin: bool, query: str,
                    analysis_type: str, title: str | None = None,
                    top_k: int | None = None, elargir: bool = False,
                    forcer: bool = False):
    """Générateur SSE : suit la ligne de rapport, puis émet `done`.

    Le flux ne produit plus rien lui-même — il REGARDE. La tâche tourne dans
    son thread, écrit sa progression en base, et ce générateur relit la ligne
    toutes les 2 s. Conséquence directe : fermer l'onglet ne coupe rien, et
    deux onglets branchés sur le même rapport voient la même chose.

    Le contrat d'événement de Task 1 est conservé (`step`, `progress`) pour que
    le front actuel continue de fonctionner jusqu'à Task 4, augmenté de
    `etape`, `detail` et `report_id`.
    """
    import time as _time

    from app.modules.reports import models as rm

    try:
        rapport = lancer_rapport(db, user_id, query=query,
                                 analysis_type=analysis_type, title=title,
                                 top_k=top_k, is_admin=is_admin,
                                 elargir=elargir, forcer=forcer)
    except AppError as e:
        yield _sse({"step": "error", "done": True, "detail": {},
                    "error": e.message, "code": e.code})
        return

    rapport_id = str(rapport.id)
    # `detail` sur `start` comme sur les événements intermédiaires (vide ici :
    # rien n'a encore été écrit) — Task 4 lit la même clé partout, elle n'a pas
    # à traiter deux formes d'événement.
    yield _sse({"progress": 5, "step": "start", "etape": None,
                "report_id": rapport_id, "detail": {},
                "message": "Démarrage de l'analyse…"})

    depart = _time.monotonic()
    dernier: tuple | None = None
    while True:
        _time.sleep(INTERVALLE_SUIVI_SECONDES)
        # La boucle est BORNÉE par la même échéance que le moteur : sans elle,
        # une tâche morte sans avoir pu écrire son statut (pool saturé) faisait
        # tourner ce générateur indéfiniment en tenant une connexion — donc en
        # aggravant la saturation qui l'avait causée.
        if (_time.monotonic() - depart) > _delai_max():
            yield _sse({"progress": 100, "step": "done", "done": True,
                        "etape": None, "report_id": rapport_id,
                        "code": "delai_depasse", "detail": {},
                        "error": "Le suivi de la génération a dépassé le délai "
                                 "maximal. Retrouvez l'état du rapport dans "
                                 "votre liste de rapports."})
            return
        # Clore la transaction de lecture PUIS vider le cache d'identité : la
        # ligne est écrite par une AUTRE session, et sans ces deux gestes le
        # flux relirait indéfiniment son propre instantané — la progression
        # semblait figée à 0.
        db.rollback()
        db.expire_all()
        ligne = db.get(rm.Report, rapport.id)
        if ligne is None:
            yield _sse({"step": "error", "done": True, "detail": {},
                        "error": "Le rapport a été supprimé pendant sa génération."})
            return
        if ligne.statut != rm.EN_COURS:
            break
        empreinte = (ligne.etape, ligne.progression)
        if empreinte == dernier:
            continue
        dernier = empreinte
        yield _sse({"progress": ligne.progression, "step": _STEP_HERITE.get(
                        ligne.etape or "", "generate"),
                    "etape": ligne.etape, "report_id": rapport_id,
                    "detail": ligne.detail or {},
                    "message": (ligne.detail or {}).get("message") or ""})

    from app.modules.reports import service as reports

    detail = reports.detail_dict(ligne, is_admin=is_admin)
    evenement = {
        "progress": 100, "step": "done", "done": True, "etape": ligne.etape,
        "report_id": rapport_id, "statut": ligne.statut,
        # `detail` aussi sur `done` : la clé est présente sur TOUS les
        # événements, éventuellement vide.
        "detail": ligne.detail or {},
        "data": dict(detail, balance=_solde(db, user_id)),
    }
    if ligne.statut != rm.TERMINE:
        evenement["degraded"] = True
        evenement["message"] = (ligne.detail or {}).get("message") or ""
    yield _sse(evenement)


def _solde(db, user_id: str) -> int | None:
    """Solde après débit — le front le rafraîchit depuis le payload final."""
    try:
        from app.modules.billing import service as billing

        return billing.available_credits(billing.get_or_create_balance(db, user_id))
    except Exception as e:  # noqa: BLE001 — un solde illisible ne casse pas un rapport
        logger.warning("Solde indisponible après rapport : %s", e)
        return None


def _profile_dict(db, user_id: str) -> dict:
    """Company profile as a plain dict — what the investor mapping matches on."""
    from app.modules.memory import service as memory

    p = memory.get_profile(db, user_id)
    if p is None:
        return {}
    return {
        "sector": p.sector, "funding_stage": p.funding_stage,
        "target_market": p.target_market, "country": getattr(p, "country", None),
        "company_name": p.company_name,
    }
