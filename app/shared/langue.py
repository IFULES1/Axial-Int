"""Langue de production des contenus.

**Règle retenue (décision Miradie, 22/08) : la langue de la question commande la
langue de la réponse.** C'est le comportement qu'attend quelqu'un qui écrit en
anglais dans une interface française — il n'a pas à aller changer un réglage.

Une consigne de miroir vaut mieux qu'une détection automatique : un détecteur se
trompe sur les messages courts, les questions truffées de noms propres anglais ou
les phrases mêlant deux langues, alors que le modèle qui lit la question sait
parfaitement dans quelle langue elle est posée.

La préférence stockée sur le profil ne sert qu'aux **emails** (récap hebdo,
digests de veille) : là, il n'y a aucune question à refléter.
"""
from __future__ import annotations

LANGUES = {"fr", "en"}
DEFAUT = "fr"


def normaliser(valeur: str | None) -> str:
    v = (valeur or "").strip().lower()[:2]
    return v if v in LANGUES else DEFAUT


def de_utilisateur(db, user_id: str) -> str:
    """Préférence de langue du profil — pour les envois sans question associée."""
    try:
        from app.modules.memory import service as memory

        profil = memory.get_profile(db, user_id)
        return normaliser(getattr(profil, "language", None) if profil else None)
    except Exception:  # noqa: BLE001 — la langue ne bloque jamais une génération
        return DEFAUT


def consigne_miroir() -> str:
    """Instruction de miroir linguistique, à ajouter au prompt système.

    Formulée comme une règle de sortie ferme : un modèle nourri de sources
    anglaises et interrogé en français a tendance à recopier des tournures
    anglaises s'il n'a pas d'instruction explicite.
    """
    return (
        "\n\nLANGUE DE RÉDACTION : rédige dans la LANGUE DE LA QUESTION posée par "
        "l'utilisateur — question en français, réponse entièrement en français ; "
        "question en anglais, réponse entièrement en anglais. Cela vaut pour tout : "
        "titres, corps, listes, section des sources et recommandations. Les sources "
        "fournies peuvent être dans une autre langue : traduis ce que tu en reprends "
        "plutôt que de recopier leurs phrases. AUCUN mot d'une autre langue ne doit "
        "subsister dans le corps du texte — relis-toi sur ce point avant de conclure. "
        "Seules exceptions : les noms propres, raisons sociales et intitulés officiels, "
        "qui se conservent tels quels."
    )


def consigne_langue(langue: str) -> str:
    """Consigne explicite, pour les contenus sans question à refléter (emails)."""
    cible = "anglais" if normaliser(langue) == "en" else "français"
    return (
        f"\n\nLANGUE DE RÉDACTION : rédige intégralement en {cible}. Les sources "
        "peuvent être dans une autre langue : traduis ce que tu en reprends. "
        "Conserve tels quels les noms propres et raisons sociales."
    )
