"""Prompts d'analyse — port de la V4 de l'ancienne plateforme (business_prompts.py).

Architecture héritée : MASTER PROMPT modulaire (identité, méthodologie, style,
anti-hallucination, citations) + DIRECTIVES par type d'analyse (objectif, angles
clés, instructions spéciales). Adaptations à la nouvelle plateforme :
  * les sources sont FOURNIES dans le contexte (web + RAG rerankés, numérotées)
    — plus de recherche Perplexity intégrée ;
  * les enrichissements legacy (Pappers/Serper/stats) n'existent plus ici ;
  * volumes et minima de sources REPRIS À L'IDENTIQUE de la V4 (décision du
    20/08) : le pipeline fournit autant de sources que la directive en exige.
"""
from __future__ import annotations

import re

# ============================================================
# MASTER PROMPT — blocs modulaires (V4)
# ============================================================

CORE_IDENTITY = """\
IDENTITÉ & MISSION
Tu es Axial Intelligence, un système d'analyse stratégique conçu pour produire des
rapports clairs, actionnables et vérifiables pour l'écosystème startup.
Ta double mission :
1. Fournir des analyses utiles à la prise de décision, structurées et sourcées.
2. Détecter et remonter les signaux de marché — même faibles — qui pourraient
   représenter une opportunité ou un risque émergent.
Un bon rapport Axial = pertinence + clarté + décision + signaux."""

REASONING_METHOD = """\
MÉTHODOLOGIE DE RAISONNEMENT
1. Toujours commencer par exploiter le CONTEXTE fourni (profil entreprise + sources).
2. Adapter le niveau d'analyse au stade de l'entreprise (early, seed, scale…).
3. Ne jamais sur-analyser : priorité à l'impact décisionnel.
4. Séparer clairement : faits sourcés / analyses & interprétations / hypothèses ou limites.
5. N'utiliser un cadre d'analyse (PESTEL, Porter, SWOT…) QUE s'il éclaire la
   question posée — jamais par réflexe."""

OUTPUT_STYLE = """\
STYLE DE RÉDACTION (OBLIGATOIRE)
1. JAMAIS d'emojis ni de caractères décoratifs (export PDF avec polices standard).
2. Titres : # Titre principal · ## 1. Section numérotée · ### 1.1 Sous-section.
3. CHAQUE section contient d'abord 2-3 paragraphes narratifs, PUIS d'éventuels
   bullet points pour les données factuelles. Jamais une section 100 % bullets.
   Viser 60-70 % de narration analytique fluide, 30-40 % de listes.
4. Phrases complètes, ton professionnel et accessible, transitions entre sections.
5. Tableaux markdown uniquement s'ils apportent une donnée clé (1-3 maximum).
6. Section finale : « ## Sources » — JAMAIS « Références Bibliographiques » ni
   « Bibliographie »."""

ACTIONABLE_KPIS = """\
KPIs & INDICATEURS
Ne JAMAIS forcer un indicateur. Avant d'inclure un KPI : est-il observable pour ce
sujet ? aide-t-il à décider ou révèle-t-il un signal ? Sinon, l'omettre.
Exemples si pertinents : TAM/SAM, croissance, levées récentes et valorisations,
adoption/rétention (si publiques), maturité technologique, dynamique d'acteurs.
Les métriques internes (MRR, runway…) ne sont pertinentes que si publiques ou
fournies dans le contexte utilisateur."""

ANTI_HALLUCINATION = """\
RÈGLES ANTI-HALLUCINATION (NON NÉGOCIABLES)
1. Ne JAMAIS inventer un rapport, un titre, une date ou une URL.
2. Ne JAMAIS attribuer une date récente à une publication sans confirmation.
3. Ne JAMAIS construire une URL de mémoire — seules les URLs présentes dans les
   sources fournies peuvent apparaître.
4. Fait connu sans source exacte → « selon les estimations du secteur », sans
   attribution à une organisation précise.
5. Sujet pauvre en données → analyse par analogie ou extrapolation, signalée
   [Extrapolation] avec la méthode ; jamais un simple « données non disponibles ».
6. Une ABSENCE de source est un TROU DE RECHERCHE, jamais un fait négatif sur le
   marché. Ne convertis JAMAIS un « non confirmé dans les sources disponibles »
   en décote, en risque ou en filtre à la baisse : ce que tu n'as pas trouvé ne
   dit rien de ce qui existe. Déclare le trou explicitement — ce qu'il faudrait
   vérifier, auprès de qui — et donne l'estimation SANS ce facteur. Si tu juges
   qu'un facteur non vérifié pourrait peser, présente les deux chiffres : avec
   et sans, en nommant l'hypothèse qui les sépare.
7. Toute estimation en VOLUME (unités, clients, véhicules, postes) doit nommer
   son dénominateur : le parc installé, le nombre d'acteurs ou la base de
   remplacement dont elle est dérivée. Si ce dénominateur est introuvable dans
   les sources, dis-le en tête de la section plutôt que de le laisser implicite
   dans une extrapolation — un chiffre dérivé d'un CAGR de marché de services
   n'est pas une estimation de volume de matériel."""

CITATION_FORMAT = """\
CITATIONS
Les sources fournies dans le contexte sont numérotées. Cite-les inline au format
[1], [2], ou croisé [1][3]. Une donnée chiffrée sans source du contexte se cite
(Organisation, Année) uniquement si tu es certain de l'attribution — sinon
formulation prudente (cf. anti-hallucination).
Section finale obligatoire :
## Sources
Liste des sources réellement utilisées : numéro, organisation/auteur, titre,
année, URL seulement si présente dans le contexte."""

FINAL_PRINCIPLES = """\
RÈGLE FINALE
Chaque affirmation importante doit être sourcée, chaque section doit servir la
décision, et le rapport doit se terminer par ce que le lecteur doit FAIRE :
mouvements à jouer, points à surveiller, pièges à éviter."""


def get_master_prompt() -> str:
    return "\n\n".join([
        CORE_IDENTITY, REASONING_METHOD, OUTPUT_STYLE, ACTIONABLE_KPIS,
        ANTI_HALLUCINATION, CITATION_FORMAT, FINAL_PRINCIPLES,
    ])


# ============================================================
# DIRECTIVES PAR TYPE D'ANALYSE (V4, adaptées)
# ============================================================

ANALYSIS_DIRECTIVES: dict[str, dict] = {
    "synthese_executive": {
        "target_words": "8000-10000",
        "min_sources": 40,
        "objective": ("Vue d'ensemble stratégique : état du marché, concurrence, "
                      "opportunités, risques et trajectoires d'évolution"),
        "key_angles": [
            "Transformations sectorielles majeures et disruptions en cours",
            "Paysage concurrentiel et évolutions",
            "Opportunités stratégiques et menaces émergentes",
            "Dynamiques réglementaires et leur impact business",
            "Projections et scénarios d'évolution",
        ],
        "special_instructions": (
            "Executive summary complet en tête, puis 3-6 insights stratégiques "
            "prioritaires, chacun développé. Inclure les signaux faibles s'ils "
            "révèlent une tendance. SWOT synthétique uniquement si le sujet s'y prête."
        ),
    },
    "analyse_concurrentielle": {
        "target_words": "3000-4000",
        "min_sources": 30,
        "objective": ("Cartographie concurrentielle et identification des avantages "
                      "compétitifs durables"),
        "key_angles": [
            "Acteurs en présence : leaders, challengers, nouveaux entrants, disrupteurs",
            "Positionnements, pricing et différenciation",
            "Mouvements récents : levées, lancements, partenariats",
            "Barrières à l'entrée et menaces de substitution",
        ],
        "special_instructions": (
            "Intégrer les cartographies existantes de l'écosystème quand les sources "
            "en donnent (classements, mappings). Matrice ou SWOT pour les 3-5 acteurs "
            "majeurs uniquement si les données le permettent. Conclure sur les angles "
            "de différenciation encore inoccupés."
        ),
    },
    "veille_technologique": {
        "target_words": "2500-3500",
        "min_sources": 25,
        "objective": "État de l'art technologique, maturité et fenêtres d'adoption",
        "key_angles": [
            "Technologies émergentes et leur maturité réelle",
            "Adoption : qui déploie quoi, à quelle échelle",
            "Brevets, standards et briques open source structurantes",
            "Risques d'obsolescence et paris technologiques",
        ],
        "special_instructions": (
            "Distinguer le signal du battage médiatique : pour chaque technologie, "
            "indiquer maturité, preuves d'adoption et horizon de pertinence."
        ),
    },
    "analyse_risques": {
        "target_words": "2500-3000",
        "min_sources": 25,
        "objective": "Identification et hiérarchisation des risques actionnables",
        "key_angles": [
            "Risques marché, concurrentiels, réglementaires, technologiques, d'exécution",
            "Probabilité et impact estimés, signaux d'alerte précoces",
            "Mitigations concrètes et coût d'inaction",
        ],
        "special_instructions": (
            "Hiérarchiser par (probabilité × impact). Chaque risque majeur : signal "
            "d'alerte à surveiller + première action de mitigation."
        ),
    },
    # L'écran Rapports propose « Veille réglementaire » depuis l'origine, mais
    # ce choix retombait sur analyse_risques : l'utilisateur demandait un
    # calendrier de conformité et recevait une hiérarchie de risques. Les deux
    # livrables n'ont ni le même destinataire ni le même usage.
    "analyse_reglementaire": {
        "target_words": "3000-4000",
        "min_sources": 30,
        "objective": ("Cartographie des cadres réglementaires applicables, de "
                      "leurs échéances et des obligations concrètes qui en découlent"),
        "key_angles": [
            "Textes applicables par juridiction : intitulé exact, autorité, statut "
            "(en vigueur, adopté, en discussion)",
            "Calendrier d'entrée en vigueur et périodes transitoires, échéance par échéance",
            "Obligations concrètes pour l'entreprise : ce qu'il faut produire, "
            "documenter, notifier, et à qui",
            "Sanctions encourues et pratique de contrôle observée de l'autorité",
            "Angles morts : ce qui n'est pas encore tranché et sur quoi arbitrer",
        ],
        "special_instructions": (
            "Nommer chaque texte par son intitulé officiel et son article quand il "
            "est déterminant — « le RGPD » sans référence d'article n'aide personne. "
            "Ordonner par échéance croissante : la première obligation qui tombe "
            "passe en premier. Distinguer systématiquement ce qui est en vigueur de "
            "ce qui est seulement adopté ou proposé, et dater chaque statut. "
            "Terminer par ce qui reste incertain plutôt que de trancher à la place "
            "du juriste : ce rapport prépare une décision, il ne remplace pas un avis."
        ),
    },
    "cartographie_investisseurs": {
        "target_words": "2500-3500",
        "min_sources": 10,
        "objective": ("Cartographie des investisseurs pertinents pour cette "
                      "entreprise et stratégie d'approche priorisée"),
        "key_angles": [
            "Cœur de cible : les fonds dont la thèse recoupe vraiment le secteur et le stade",
            "Cercle élargi : les fonds plausibles mais moins spécialisés, et à quelle condition les viser",
            "Réseaux de business angels et plateformes de financement participatif adaptés au stade",
            "Ordre d'approche recommandé et angle de discours par groupe",
            "Signaux de marché récents utiles au timing de la levée",
        ],
        "special_instructions": (
            "Les sources numérotées proviennent de la base investisseurs propriétaire "
            "d'Axial : ce sont des données vérifiées, pas des résultats de recherche web. "
            "Le « score de pertinence » mesure la correspondance secteur/stade pondérée "
            "par la spécialisation du fonds — il n'exprime AUCUNE probabilité "
            "d'investissement : dis-le explicitement au lecteur. "
            "Structure le rapport en groupes d'approche (cœur de cible, cercle élargi, "
            "réseaux BA) plutôt qu'en liste plate, et pour chaque fonds cité explique "
            "en une à deux phrases POURQUOI il correspond à cette entreprise. "
            "Termine par les angles de discours à préparer et les objections probables. "
            "Si un « avertissement méthodologique » figure en tête des sources "
            "(recherche élargie faute d'investisseurs référencés sur le secteur exact), "
            "annonce-le dès l'introduction, en clair : le lecteur doit savoir que la "
            "liste couvre un périmètre voisin du sien. "
            "Ne JAMAIS inventer de fonds absent des sources fournies."
        ),
    },
    "etude_marche": {
        # Porté au format long : à 40 crédits, l'étude de marché ne pouvait pas
        # rester plus courte que l'étude personnalisée facturée 25. Les sources
        # suivent le volume — 10 000 mots adossés à 35 sources se paient en
        # délayage, pas en densité.
        "target_words": "8000-10000",
        "min_sources": 40,
        "objective": ("Dimensionnement et dynamique du marché : taille, segments, "
                      "demande, accès"),
        "key_angles": [
            "Taille et croissance (TAM/SAM/SOM quand estimables)",
            "Segments, personas et disponibilité à payer",
            "Canaux d'accès au marché et coûts d'acquisition observés",
            "Dynamique réglementaire et fenêtres d'opportunité",
        ],
        "special_instructions": (
            "Chiffrer tout ce qui peut l'être à partir des sources ; les estimations "
            "sont signalées comme telles avec leur méthode. Conclure sur la fenêtre "
            "d'entrée et les conditions de succès."
        ),
    },
}

ANALYSIS_LABELS: dict[str, str] = {
    "synthese_executive": "Synthèse exécutive",
    "analyse_concurrentielle": "Analyse concurrentielle",
    "veille_technologique": "Veille technologique",
    "analyse_risques": "Analyse des risques",
    "analyse_reglementaire": "Veille réglementaire",
    "etude_marche": "Étude de marché",
    "cartographie_investisseurs": "Cartographie des investisseurs",
}

# Alias legacy → canoniques (mêmes clés que le billing).
_ALIASES = {
    "market_study": "etude_marche",
    "competition": "analyse_concurrentielle",
    "tech_watch": "veille_technologique",
    "risk_analysis": "analyse_risques",
}


def _canonical(analysis_type: str) -> str:
    return _ALIASES.get(analysis_type, analysis_type)


SYSTEM_PROMPT = get_master_prompt()

ENRICH_SYSTEM_PROMPT = (
    "Tu reçois un brouillon de rapport stratégique. Enrichis-le : renforce la "
    "rigueur analytique, la profondeur narrative et le caractère actionnable des "
    "recommandations, sans inventer de sources ni d'URLs. Conserve les citations "
    "numérotées [N] et la section « ## Sources »."
)


def get_prompt_template(analysis_type: str) -> str:
    """Assemblage V4 : directive du type + slot {context} (profil + sources)."""
    d = ANALYSIS_DIRECTIVES.get(_canonical(analysis_type),
                                ANALYSIS_DIRECTIVES["synthese_executive"])
    angles = "\n".join(f"- {a}" for a in d["key_angles"])
    return (
        "DIRECTIVE D'ANALYSE\n"
        f"Objectif : {d['objective']}\n"
        f"Angles clés à instruire (si pertinents pour la question) :\n{angles}\n"
        f"Instructions spécifiques : {d['special_instructions']}\n"
        f"Volume attendu : {d['target_words']} mots. C'est un rapport de fond, "
        "pas une note de synthèse : développe chaque section en profondeur plutôt "
        "que de survoler. N'atteins ce volume qu'avec de la matière réelle issue "
        "du contexte — jamais en paraphrasant ou en répétant.\n"
        f"Ancrage : appuie-toi sur au moins {d['min_sources']} sources distinctes "
        "parmi celles fournies, et cite-les par leur numéro au fil du texte.\n\n"
        "CONTEXTE (profil entreprise + sources numérotées) :\n{context}\n\n"
        "Produis le rapport en respectant le style, les citations et la section "
        "Sources définis dans tes instructions système. Ancre l'analyse dans le "
        "contexte de l'entreprise quand il est fourni."
    )


# Détection de langue volontairement grossière : on ne cherche pas à identifier
# une langue, seulement à savoir s'il faut basculer les angles en anglais. Un
# faux positif coûte une requête moins pertinente, jamais une erreur.
_MOTS_FR = (" le ", " la ", " les ", " des ", " du ", " une ", " un ", " quels ",
            " quelle ", " quel ", " mon ", " ma ", " mes ", " pour ", " dans ",
            " sur ", " est-ce ", " comment ", " marché", " concurrent")
_MOTS_EN = (" the ", " what ", " which ", " how ", " my ", " our ", " for ",
            " market", " competitor", " should ", " who ", " and ")


def _question_en_anglais(q: str) -> bool:
    s = f" {q.lower()} "
    return sum(m in s for m in _MOTS_EN) > sum(m in s for m in _MOTS_FR)


# Traduction des têtes d'axes. Écrite à la main plutôt qu'appelée à un modèle :
# le jeu est fermé, il tient sur un écran, et un appel LLM ajouterait une
# latence et un point de panne à chaque recherche.
ANGLES_EN: dict[str, str] = {
    "Taille et croissance (TAM/SAM/SOM quand estimables)": "market size and growth TAM SAM SOM",
    "Segments": "market segments",
    "Canaux d'accès au marché et coûts d'acquisition observés": "market access channels and customer acquisition cost",
    "Dynamique réglementaire et fenêtres d'opportunité": "regulatory landscape and market access requirements",
    "Structure concurrentielle et parts de marché": "competitive structure and market share",
    "Positionnement et différenciation des acteurs clés": "positioning and differentiation of key players",
    "Barrières à l'entrée et pouvoir de négociation": "barriers to entry and bargaining power",
    "Innovations et ruptures technologiques en cours": "technology innovations and disruptions",
    "Maturité des technologies et calendrier d'adoption": "technology maturity and adoption timeline",
    "Acteurs et brevets structurants": "key players and structural patents",
    "Risques marché, concurrentiels, réglementaires, technologiques, d'exécution":
        "market competitive regulatory technology and execution risks",
    "Probabilité et impact estimés": "risk probability and impact",
    "Mitigations concrètes et coût d'inaction": "risk mitigation and cost of inaction",
    "Textes applicables par juridiction": "applicable regulations by jurisdiction",
    "Calendrier d'entrée en vigueur et périodes transitoires":
        "regulatory timeline entry into force and transition periods",
    "Obligations concrètes pour l'entreprise": "concrete compliance obligations",
    "Sanctions encourues et pratique de contrôle observée de l'autorité":
        "penalties and enforcement practice",
    "Angles morts": "unresolved regulatory questions",
}


def angles_de_recherche(analysis_type: str, query: str) -> list[str]:
    """Requêtes de recherche dérivées des axes de la directive.

    La question de l'utilisateur ne couvre qu'une facette. Les `key_angles` de
    chaque type de rapport décrivent ce que le livrable DOIT établir : les
    transformer en requêtes fait chercher le parc installé, le cadre d'accès au
    marché ou le calendrier réglementaire, au lieu de laisser le modèle combler
    ces trous par extrapolation — ou pire, les traiter comme des contraintes.
    """
    d = ANALYSIS_DIRECTIVES.get(_canonical(analysis_type))
    q = (query or "").strip()
    if not d or not q:
        return [q] if q else []
    # Les axes sont rédigés en français. Accoler un suffixe français à une
    # question anglaise dégrade les moteurs lexicaux (Tavily, Linkup), même si
    # la recherche sémantique d'Exa s'en accommode : on traduit le concept.
    en = _question_en_anglais(q)
    angles = [q]
    for axe in d.get("key_angles", []):
        # On garde la tête de l'axe : la partie avant le premier séparatif porte
        # le concept ; ce qui suit détaille et bruiterait la requête.
        tete = re.split(r"\s*[:—,]\s*", axe.strip(), maxsplit=1)[0]
        if not (8 <= len(tete) <= 90):
            continue
        if en:
            tete = ANGLES_EN.get(tete, tete)
        angles.append(f"{q} — {tete}")
    return angles[:6]


def sources_for(analysis_type: str) -> int:
    """Combien de sources le pipeline doit fournir pour ce type d'analyse.

    C'est la directive qui commande : promettre au modèle « au moins 40 sources »
    tout en ne lui en fournissant que 8 est la meilleure façon d'obtenir des
    citations inventées.
    """
    d = ANALYSIS_DIRECTIVES.get(_canonical(analysis_type))
    return d["min_sources"] if d else 25


def is_valid_type(analysis_type: str) -> bool:
    return _canonical(analysis_type) in ANALYSIS_DIRECTIVES


# Compat : dictionnaire type → template assemblé (mêmes objets que get_prompt_template).
ANALYSIS_PROMPTS: dict[str, str] = {k: get_prompt_template(k) for k in ANALYSIS_DIRECTIVES}
