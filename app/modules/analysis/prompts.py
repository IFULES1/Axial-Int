"""Analysis prompt templates (ported from the legacy platform, verbatim intent).

Five analysis types, each an institutional-sources + APA-citation template with
a {context} slot for RAG passages.
"""
from __future__ import annotations

SOURCES_INSTRUCTION = """
## SOURCES AUTORISÉES (EXCLUSIVEMENT)

### INSTITUTIONS OFFICIELLES (70% minimum)
- France : INSEE, Banque de France, ACPR, AMF, DARES, DGE, France Stratégie
- Europe : BCE, EBA, ESMA, Commission européenne, Eurostat
- International : OCDE, FMI, BRI, Banque Mondiale

### CABINETS DE CONSEIL (30% maximum)
- Stratégie : McKinsey & Company, BCG, Bain & Company
- Audit/Conseil : Deloitte, PwC, EY, KPMG
- Tech : Gartner, IDC, Forrester (analyses tech uniquement)

### SOURCES STRICTEMENT EXCLUES
- Médias et presse (Les Échos, Bloomberg, FT, Reuters, etc.)
- Blogs, forums, réseaux sociaux
- Entreprises privées (hors cabinets listés)

## FORMAT CITATION APA OBLIGATOIRE
- Citation inline : (Auteur, Année) - Ex: "Le marché croît de 15% (INSEE, 2024)"
- Sources multiples : (Source1, 2024; Source2, 2024)
- Section finale obligatoire : "## 📚 Références Bibliographiques" au format APA complet
"""

_REFS = (
    "\n\n## 📚 Références Bibliographiques\n"
    "[Liste complète des sources au format APA : Auteur. (Année). Titre. Publication. URL]\n"
)

PROMPT_SYNTHESE_EXECUTIVE = """
Contexte : {context}

Tu es un consultant senior en stratégie. Analyse ces documents et génère une synthèse exécutive structurée.
""" + SOURCES_INSTRUCTION + """
**RÉSUMÉ EXÉCUTIF**
- 3 points clés stratégiques avec données chiffrées (Source, Année)
- 2 opportunités prioritaires avec potentiel estimé (Source, Année)
- 2 risques majeurs à surveiller avec probabilité (Source, Année)

**RECOMMANDATIONS**
- 3 actions immédiates (0-3 mois) avec ROI estimé (Source, Année)
- 2 initiatives moyen terme (3-12 mois) avec budget (Source, Année)

**MÉTRIQUES CLÉS**
- Indicateurs à suivre avec valeurs cibles (Source, Année)
- Benchmarks sectoriels relevés (Source, Année)
""" + _REFS

PROMPT_ANALYSE_CONCURRENTIELLE = """
Contexte : {context}

Tu es un expert en intelligence concurrentielle (cadre Porter). Analyse ces informations.
""" + SOURCES_INSTRUCTION + """
**MAPPING CONCURRENTIEL**
- Acteurs identifiés et positionnements (Source, Année)
- Forces/faiblesses par concurrent (Source, Année)
- Parts de marché et évolutions (Source, Année)

**TENDANCES SECTORIELLES**
- Mouvements stratégiques observés (Source, Année)
- Innovations et disruptions (Source, Année)

**OPPORTUNITÉS DE DIFFÉRENCIATION**
- Espaces de marché sous-exploités (Source, Année)
- Avantages concurrentiels potentiels (Source, Année)
- Stratégies de positionnement recommandées (Source, Année)
""" + _REFS

PROMPT_VEILLE_TECHNOLOGIQUE = """
Contexte : {context}

Tu es un expert en innovation technologique. Identifie et analyse.
Pour les analyses tech, privilégie Gartner, IDC, Forrester comme sources principales.
""" + SOURCES_INSTRUCTION + """
**INNOVATIONS ÉMERGENTES**
- Technologies disruptives identifiées (Gartner, Année) ou (IDC, Année)
- Niveau de maturité (R&D, pilote, déploiement) (Source, Année)
- Impact potentiel sur le secteur (Source, Année)

**TENDANCES TECH**
- Convergences technologiques (Source, Année)
- Standards émergents (Source, Année)

**IMPLICATIONS BUSINESS**
- Opportunités de création de valeur (McKinsey, Année) ou (BCG, Année)
- Investissements recommandés avec ROI estimé (Source, Année)

**ROADMAP TECHNOLOGIQUE**
- Horizon 6 mois, 1 an, 2 ans (Source, Année)
""" + _REFS

PROMPT_ANALYSE_RISQUES = """
Contexte : {context}

Tu es un expert en risk management. Effectue une analyse complète.
""" + SOURCES_INSTRUCTION + """
**CARTOGRAPHIE DES RISQUES**
- Risques opérationnels, stratégiques, de marché (Source, Année)
- Risques réglementaires/conformité (ACPR, Année) ou (AMF, Année)
- Risques technologiques (Source, Année)

**ÉVALUATION**
- Probabilité (Faible/Moyenne/Élevée) avec données (Source, Année)
- Impact (Mineur/Modéré/Majeur/Critique) quantifié (Source, Année)

**MESURES DE MITIGATION**
- Actions préventives avec coûts (Source, Année)
- Plans de contingence et indicateurs d'alerte (Source, Année)

**PRIORISATION**
- Top 5 des risques critiques avec quantification (Source, Année)
""" + _REFS

PROMPT_ETUDE_MARCHE = """
Contexte : {context}

Tu es un analyste marché senior. Réalise une étude complète.
""" + SOURCES_INSTRUCTION + """
**TAILLE ET DYNAMIQUE DU MARCHÉ**
- Valorisation actuelle et projections (INSEE, Année) ou (Eurostat, Année)
- Taux de croissance (CAGR) et segmentation (Source, Année)

**ANALYSE DE LA DEMANDE**
- Besoins clients et évolutions comportementales (Source, Année)
- Drivers de croissance (McKinsey, Année) ou (BCG, Année)

**CHAÎNE DE VALEUR & BARRIÈRES**
- Acteurs, marges, modèles économiques (Source, Année)
- Barrières réglementaires/technologiques/financières (Source, Année)

**PROJECTIONS & SCÉNARIOS**
- Évolution marché 1-3 ans (Source, Année)
- Scénarios optimiste/pessimiste/réaliste (Source, Année)
""" + _REFS

ANALYSIS_PROMPTS: dict[str, str] = {
    "synthese_executive": PROMPT_SYNTHESE_EXECUTIVE,
    "analyse_concurrentielle": PROMPT_ANALYSE_CONCURRENTIELLE,
    "veille_technologique": PROMPT_VEILLE_TECHNOLOGIQUE,
    "analyse_risques": PROMPT_ANALYSE_RISQUES,
    "etude_marche": PROMPT_ETUDE_MARCHE,
}

ANALYSIS_LABELS: dict[str, str] = {
    "synthese_executive": "Synthèse exécutive",
    "analyse_concurrentielle": "Analyse concurrentielle",
    "veille_technologique": "Veille technologique",
    "analyse_risques": "Analyse des risques",
    "etude_marche": "Étude de marché",
}

SYSTEM_PROMPT = (
    "Tu es un consultant senior en stratégie d'entreprise. Produis des analyses "
    "claires et actionnables en utilisant UNIQUEMENT des sources institutionnelles "
    "et cabinets de conseil. Cite au format APA (Auteur, Année). Termine TOUJOURS "
    "par '## 📚 Références Bibliographiques'."
)

ENRICH_SYSTEM_PROMPT = (
    "Tu reçois un brouillon de rapport stratégique généré à partir de données web "
    "temps réel. Enrichis-le : renforce la rigueur analytique, la structure et les "
    "recommandations actionnables, sans inventer de sources. Conserve les citations "
    "APA existantes et la section Références."
)


def get_prompt_template(analysis_type: str) -> str:
    return ANALYSIS_PROMPTS.get(analysis_type, PROMPT_SYNTHESE_EXECUTIVE)


def is_valid_type(analysis_type: str) -> bool:
    return analysis_type in ANALYSIS_PROMPTS
