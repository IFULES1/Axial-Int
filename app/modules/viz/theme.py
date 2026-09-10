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

# Liste de repli, pas un nom unique : sur le VPS le rasteriseur PNG ne trouve
# pas « Helvetica » et, sans repli, il n'écrit AUCUN texte (constaté le 11/09 :
# titres, libellés et valeurs absents). Liberation Sans a les métriques
# d'Helvetica ; DejaVu est présent partout.
POLICE = "Helvetica, Liberation Sans, DejaVu Sans, sans-serif"

CONFIG = {
    "background": "white",
    "font": POLICE,
    "view": {"stroke": None},
    "axis": {
        "labelFont": POLICE, "labelFontSize": 9.5, "labelColor": GRIS,
        "titleFont": POLICE, "titleFontSize": 9.5, "titleFontWeight": "normal", "titleColor": GRIS,
        "domain": False, "tickColor": GRILLE, "gridColor": GRILLE, "gridDash": [2, 2],
    },
    "axisX": {"grid": False},
    "title": {
        "font": POLICE, "fontSize": 13, "fontWeight": "bold", "color": TEXTE, "anchor": "start",
        "subtitleFont": POLICE, "subtitleFontSize": 10.5, "subtitleColor": GRIS, "subtitlePadding": 4,
        "offset": 10,
    },
    "legend": {"labelFont": POLICE, "labelFontSize": 9.5, "labelColor": GRIS, "symbolType": "circle",
               "titleFontSize": 9.5},
    "range": {"category": CATEGORIES},
}

LARGEUR = 520  # points PDF = largeur A4 moins marges ; l'app adapte via viewBox
