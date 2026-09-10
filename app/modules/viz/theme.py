"""Design system des visualisations — un seul objet `config` Vega-Lite,
partagé par l'app et le PDF. Une couleur pleine pour le point clé, tout le
reste désaturé ; Helvetica (polices standard du PDF) ; grille discrète ;
jamais de bordure de vue.
"""
ACCENT = "#7976F7"
CONTEXTE = "#C9C7E8"
ALERTE = "#E5484D"
TEXTE = "#222222"
GRIS = "#555555"
GRILLE = "#E4E2F0"
CATEGORIES = ["#7976F7", "#A5A3F2", "#C9C7E8", "#5E5BD1", "#8E8CF4", "#DCDBF4"]

CONFIG = {
    "background": "white",
    "font": "Helvetica",
    "view": {"stroke": None},
    "axis": {
        "labelFont": "Helvetica", "labelFontSize": 9.5, "labelColor": GRIS,
        "titleFont": "Helvetica", "titleFontSize": 9.5, "titleFontWeight": "normal", "titleColor": GRIS,
        "domain": False, "tickColor": GRILLE, "gridColor": GRILLE, "gridDash": [2, 2],
    },
    "axisX": {"grid": False},
    "title": {
        "font": "Helvetica", "fontSize": 13, "fontWeight": "bold", "color": TEXTE, "anchor": "start",
        "subtitleFont": "Helvetica", "subtitleFontSize": 10.5, "subtitleColor": GRIS, "subtitlePadding": 4,
        "offset": 10,
    },
    "legend": {"labelFont": "Helvetica", "labelFontSize": 9.5, "labelColor": GRIS, "symbolType": "circle",
               "titleFontSize": 9.5},
    "range": {"category": CATEGORIES},
}

LARGEUR = 520  # points PDF = largeur A4 moins marges ; l'app adapte via viewBox
