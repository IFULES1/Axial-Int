"""Triage the raw document corpus into the knowledge_base categories.

Non-destructive: COPIES keepers into data/knowledge_base/<category>/, never
touches the originals. Prints a full report (kept per category + discarded +
excluded internal). Discards: junk, exact -N duplicates, off-topic UN/IDB
(Spanish) docs. Excludes internal Axial docs. Books all go to 06.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

SRC = Path("/Users/mirad/Downloads/OneDrive_2_13-08-2026")
KB = Path("/Users/mirad/axial-intelligence/data/knowledge_base")
DOC_EXT = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".pptx"}

# Keyword rules (lowercased filename) → category folder.
BOOKS = [
    "porter", "christensen", "innovator", "blue_ocean", "blue ocean", "business_model_generation",
    "crossing-the-chasm", "strategy_maps", "kaplan", "kahneman", "thinking_fast", "fast_and_slow",
    "taleb", "antifragile", "cisne-negro", "black_swan", "sun_tzu", "lart_de_la_guerre",
    "clausewitz", "liddell_hart", "musashi", "five_rings", "boyd", "logic-of-war", "luttwak",
    "kissinger", "diplomacy", "world-order", "zakaria", "post_american", "asian_21st",
    "brzezinski", "grand echiquier", "huntington", "choc des civilisations", "hofstede",
    "cultures_and_organizations", "erin-meyer", "culture-map", "culture_map", "riding_the_waves",
    "when-cultures-collide", "beyond_culture", "silent_language", "hall_edward", "nudge", "thaler",
    "mindset", "think-again", "megathreats", "roubini", "why-nations-fail", "mazzucato",
    "lecapitalau", "j_curve", "chinas_disruptors", "sources_of_power", "competitive_advantage",
    "competitive_strategy", "competitive_forces", "intelligence_economique", "precis_de_lart",
    "book_review", "return_of_depression", "competitive_strategy", "strategy_-_b._h",
    "the_asian", "the_post_american", "de_la_guerra",
]
REGLEMENTAIRE = ["linklaters", "inpi", "patent", "brevet", "epc", "compliance", "privacy",
                 "regulatory", "extraterritorial", "competition", "licence", "nda", "consortium",
                 "contrat", "obligations", "negociation", "governance", "grc", "legal", "esg",
                 "information-gov", "diplomacy_kissinger", "healthcare regulatory", "look ahead"]
SECTORIEL = ["cb-insights", "bain_report", "mckinsey", "mgi-", "bcg-", "ai_index", "ai-index",
             "hai_ai", "generative-ai", "digital-transformation", "disruptions"]
MARCHE = ["barometre", "venture", "m_and_a", "market", "competitiveness", "enquete", "flasheco",
          "export", "tpe-pme", "tpe_pme", "eti", "industriels", "much-more-than-a-market",
          "serie_de_donnees", "letta"]
MACRO = ["fmi", "imf", "ocde", "oecd", "eurobarometer", "_sp5", "_fl5", "fl_56", "eb04", "std10",
         "draghi", "digital decade", "digital_decade", "euro_area", "euro area", "classes-moyennes",
         "fractures", "territoires", "climate", "democracy", "energy", "science_and", "social",
         "youth", "gender", "antisemitism", "charter", "attitudes", "citizens", "eurobaromet",
         "budget", "fiscal", "financial_stability", "economic_outl", "eco_outlook", "regional_",
         "annual_report_fmi", "annula_report", "qpv", "ief2025"]
METHODO = ["guide_", "guide ", "guides", "methodo", "accompagnement", "carnot", "partenariat",
           "definition", "documentation", "fiche", "boyd_", "diagnostics"]

# Discard: off-topic UN / IDB (mostly Spanish) + junk.
OFFTOPIC = [re.compile(r"_es(-\d)?\.pdf$", re.I), re.compile(r"divulgacion", re.I),
            re.compile(r"documento del proyecto", re.I), re.compile(r"\bbid\b", re.I),
            re.compile(r"-idb", re.I), re.compile(r"^gc\d", re.I), re.compile(r"^ar-t", re.I),
            re.compile(r"reoi", re.I), re.compile(r"^f00\d", re.I),
            re.compile(r"^\d{7}s_", re.I), re.compile(r"^s\d{7}", re.I),
            re.compile(r"giepcahier", re.I)]
INTERNAL = [re.compile(r"axial", re.I), re.compile(r"mapping ai", re.I),
            re.compile(r"feuille de calcul", re.I)]


def category(low: str) -> str:
    for kw in BOOKS:
        if kw in low:
            return "06_litterature-strategie"
    for kw in REGLEMENTAIRE:
        if kw in low:
            return "03_reglementaire"
    for kw in SECTORIEL:
        if kw in low:
            return "02_sectoriel"
    for kw in MARCHE:
        if kw in low:
            return "04_marche-benchmarks"
    for kw in MACRO:
        if kw in low:
            return "01_macro-institutionnel"
    for kw in METHODO:
        if kw in low:
            return "05_methodologie"
    return "00_a-classer"


def main() -> None:
    files = [p for p in SRC.rglob("*") if p.is_file() and p.suffix.lower() in DOC_EXT
             and "Opera Installer.app" not in str(p)]
    names = {p.name for p in files}

    kept = {c: [] for c in ["01_macro-institutionnel", "02_sectoriel", "03_reglementaire",
                            "04_marche-benchmarks", "05_methodologie", "06_litterature-strategie",
                            "00_a-classer"]}
    discarded, internal, dupes = [], [], []

    for p in files:
        name, low = p.name, p.name.lower()
        # dedup: "-2"/"-3" copy whose base exists
        base = re.sub(r"-\d+(\.\w+)$", r"\1", name)
        if base != name and base in names:
            dupes.append(name)
            continue
        if any(rx.search(name) for rx in INTERNAL):
            internal.append(name)
            continue
        if any(rx.search(name) for rx in OFFTOPIC):
            discarded.append(name)
            continue
        cat = category(low)
        kept[cat].append(p)

    # copy keepers
    (KB / "00_a-classer").mkdir(exist_ok=True)
    for cat, paths in kept.items():
        for p in paths:
            dest = KB / cat / p.name
            if not dest.exists():
                shutil.copy2(p, dest)

    print("=== GARDÉS (copiés dans knowledge_base/) ===")
    total = 0
    for cat, paths in kept.items():
        if paths:
            print(f"  {cat:28} {len(paths)}")
            total += len(paths)
    print(f"  {'TOTAL gardés':28} {total}")
    print(f"\n=== ÉCARTÉS ===")
    print(f"  doublons (-2/-3)     : {len(dupes)}")
    print(f"  hors-sujet ONU/BID   : {len(discarded)}")
    print(f"  internes Axial exclus: {len(internal)} -> {internal}")
    print(f"\n  (détail hors-sujet écartés: {sorted(discarded)[:12]}{'…' if len(discarded)>12 else ''})")
    print(f"  (à-classer manuellement: {len(kept['00_a-classer'])})")


if __name__ == "__main__":
    main()
