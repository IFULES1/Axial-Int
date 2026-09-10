"""Registre backend : l'app vouvoie l'utilisateur, les emails tutoient.

Couvre :
  * les messages d'erreur HTTP (`AppError(...)`) — dans tout `app/` SAUF les
    fichiers/fonctions qui composent le corps d'un email (sequences.py,
    notification.py, l'intégralité de password_reset.py — vérifié à part par
    un test ciblé — et watches/email.py) ;
  * les 7 réponses dégradées (messages "⚠️ ... Réessai...") renvoyées à la
    place d'une génération manquée ;
  * le registre imposé au contenu généré par le modèle (prompts).

Les emails (sequences.py, notification.py, password_reset.py, la signature de
watches/email.py) tutoient — c'est la voix personnelle de Miradie, une règle
distincte, non couverte ici.
"""
from __future__ import annotations

import ast
import glob
import re

from app.modules.analysis import prompts
from app.modules.intelligence import personas

# Fichiers qui composent (en tout ou partie) le corps d'un email : hors
# périmètre du vouvoiement — ils gardent le tutoiement de la voix de Miradie.
EMAIL_FILES = {
    "app/modules/emailing/sequences.py",
    "app/modules/reports/notification.py",
    "app/modules/watches/email.py",
}

# password_reset.py mélange des corps d'email (tutoiement, à garder) et des
# messages d'erreur HTTP (AppError, à vouvoyer) : on l'exclut du scan
# générique et on vérifie ses AppError avec un test ciblé plus bas.
PASSWORD_RESET_FILE = "app/modules/auth/password_reset.py"

# Registre à bannir dans un message adressé à l'utilisateur de l'app.
TUTOIEMENT = re.compile(
    r"\b(tu|te|toi|ton|ta|tes)\b|-toi\b|\bréessaie\b|\breconnecte-toi\b"
    r"|\bremplis\b|\bvérifie\b|\bredemande\b",
    re.IGNORECASE,
)


def _string_value(node: ast.AST) -> str | None:
    """Texte porté par un `Constant` str ou les parties littérales d'un f-string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            v.value for v in node.values
            if isinstance(v, ast.Constant) and isinstance(v.value, str)
        )
    return None


def _docstring_ids(tree: ast.AST) -> set[int]:
    """id() des noeuds `Constant` qui sont des docstrings (doc technique, hors
    scope : ne sont jamais montrés à l'utilisateur)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr):
                value = body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    ids.add(id(value))
    return ids


def _appError_and_degraded_strings(path: str) -> list[tuple[int, str]]:
    """Chaînes littérales des appels `AppError(...)` et des réponses dégradées
    (contenant "⚠️" ou "Réessai"/"réessai") du fichier, hors docstrings."""
    with open(path, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, filename=path)
    skip = _docstring_ids(tree)
    found: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name == "AppError":
                for arg in list(node.args) + [kw.value for kw in node.keywords]:
                    if id(arg) in skip:
                        continue
                    text = _string_value(arg)
                    if text:
                        found.append((node.lineno, text))
        if isinstance(node, (ast.Constant, ast.JoinedStr)) and id(node) not in skip:
            text = _string_value(node)
            if text and ("⚠️" in text or "réessai" in text.lower()):
                found.append((node.lineno, text))

    return found


def _app_python_files() -> list[str]:
    return sorted(glob.glob("app/**/*.py", recursive=True))


def test_app_error_and_degraded_messages_vouvoient():
    violations: list[str] = []
    for path in _app_python_files():
        if path in EMAIL_FILES or path == PASSWORD_RESET_FILE:
            continue
        for lineno, text in _appError_and_degraded_strings(path):
            if TUTOIEMENT.search(text):
                violations.append(f"{path}:{lineno}: {text!r}")

    assert not violations, (
        "Message(s) d'erreur ou réponse(s) dégradée(s) au tutoiement — l'app "
        "vouvoie l'utilisateur :\n" + "\n".join(violations)
    )


def test_password_reset_app_errors_vouvoient():
    """password_reset.py mélange emails (tutoiement, hors scope) et erreurs
    HTTP (AppError, vouvoiement) — vérifié ici à part de son corps d'email."""
    violations: list[str] = []
    for lineno, text in _appError_and_degraded_strings(PASSWORD_RESET_FILE):
        if TUTOIEMENT.search(text):
            violations.append(f"{PASSWORD_RESET_FILE}:{lineno}: {text!r}")

    assert not violations, (
        "AppError de password_reset.py au tutoiement :\n" + "\n".join(violations)
    )


def test_registre_impose_au_contenu_genere():
    # "vouvoyant"/"vouvoie" : mêmes formes de "vouvoyer", pas la même
    # conjugaison selon le texte (règle 8 du prompt vs REGISTRE_INSTRUCTION).
    assert "vouvoy" in prompts.OUTPUT_STYLE.lower()
    assert "vouvoie" in personas.REGISTRE_INSTRUCTION
    assert personas.REGISTRE_INSTRUCTION in personas.MARKET_SCANNER.full_system_prompt()
