"""Rendu Vega-Lite côté serveur, sans navigateur (vl-convert).

Le SVG sert l'app, le PNG sert le PDF et l'email. Le cache est adressé par
l'empreinte du spec compilé : un même graphique n'est jamais rendu deux fois,
et cette empreinte est aussi l'identifiant public des images.
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging

logger = logging.getLogger("axial.viz.render")


def empreinte(vl: dict) -> str:
    return hashlib.sha256(json.dumps(vl, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@functools.lru_cache(maxsize=256)
def _svg(cle: str, vl_json: str) -> str:
    import vl_convert as vlc

    return vlc.vegalite_to_svg(vl_json)


def vers_svg(vl: dict) -> str:
    return _svg(empreinte(vl), json.dumps(vl, ensure_ascii=False))


def vers_png(vl: dict, scale: float = 2.0) -> bytes:
    import vl_convert as vlc

    return vlc.vegalite_to_png(json.dumps(vl, ensure_ascii=False), scale=scale)


def compile_ou_none(vl: dict) -> str | None:
    """Une spec qui ne compile pas = pas de graphique (repli tableau), jamais
    une exception vers l'utilisateur. La cause est journalisée."""
    try:
        return vers_svg(vl)
    except Exception as e:  # noqa: BLE001 — vl-convert lève des types variés
        logger.warning("Spec Vega-Lite refusée : %s", str(e)[:200])
        return None
