/* markdown.js — parseur markdown maison, pur (sans React, sans `window`).
   Consommé par `MarkdownView` (App.jsx) et par les tests Node
   (`frontend/tests/markdown.test.mjs`). Pas de dépendance externe : c'est
   tout l'objet de ce module (spec §7).

   `parserMarkdown(texte) → blocs[]`

   Formes de bloc :
   - { type:'heading', level, inline }
   - { type:'paragraph', inline }
   - { type:'list', ordered, items:[{ inline, children? }] }   (1 niveau d'imbrication)
   - { type:'code', lang, code }
   - { type:'quote', blocks }                                   (récursif)
   - { type:'hr' }
   - { type:'table', header:[inline], rows:[[inline]] }
   - { type:'viz', raw, closed }                                 bloc ```viz … ``` conservé brut

   Forme inline (tableau de nœuds) :
   - { type:'text', text }
   - { type:'strong', children:[inline] }
   - { type:'em', children:[inline] }
   - { type:'code', text }
   - { type:'link', href, children:[inline] }
   - { type:'cite', n }                                          citation [N]
*/

/* ---------- inline ---------- */

// Découpe une ligne en nœuds inline. Ordre de priorité des marqueurs :
// code inline `…` (rien à l'intérieur n'est réinterprété), lien [texte](url),
// citation [N], gras **…**, italique *…*/_..._, puis texte brut.
function parserInline(texte) {
  const nodes = [];
  const s = String(texte == null ? '' : texte);
  const re = /`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)|\[(\d+)\]|\*\*([^*]+)\*\*|__([^_]+)__|\*([^*]+)\*|_([^_]+)_/g;
  let last = 0, m;
  while ((m = re.exec(s)) !== null) {
    if (m.index > last) nodes.push({ type: 'text', text: s.slice(last, m.index) });
    if (m[1] !== undefined) {
      nodes.push({ type: 'code', text: m[1] });
    } else if (m[2] !== undefined) {
      nodes.push({ type: 'link', href: m[3], children: parserInline(m[2]) });
    } else if (m[4] !== undefined) {
      nodes.push({ type: 'cite', n: parseInt(m[4], 10) });
    } else if (m[5] !== undefined || m[6] !== undefined) {
      nodes.push({ type: 'strong', children: parserInline(m[5] !== undefined ? m[5] : m[6]) });
    } else if (m[7] !== undefined || m[8] !== undefined) {
      nodes.push({ type: 'em', children: parserInline(m[7] !== undefined ? m[7] : m[8]) });
    }
    last = m.index + m[0].length;
  }
  if (last < s.length) nodes.push({ type: 'text', text: s.slice(last) });
  return nodes;
}

/* ---------- helpers bloc ---------- */

const reSep = /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$/;
const isSep = (l) => reSep.test((l || '').trim());
const cellsOf = (l) => {
  let s = l.trim();
  if (s.startsWith('|')) s = s.slice(1);
  if (s.endsWith('|')) s = s.slice(0, -1);
  return s.split('|').map((c) => c.trim());
};
const isBullet = (l) => /^(\s*)[-*]\s+(.*)$/.exec(l);
const isNumbered = (l) => /^(\s*)\d+[.)]\s+(.*)$/.exec(l);

/* ---------- bloc ---------- */

// Analyse une portion de lignes en blocs. Utilisée à la fois pour le document
// entier et pour le corps d'une citation `> ` (récursion).
function parserBlocs(lines) {
  const blocks = [];
  let idx = 0;

  const parseListe = (startIdx, ordered) => {
    // Rassemble les éléments d'une liste au même style (puce ou numérotée),
    // avec un niveau d'imbrication (indentation d'au moins 2 espaces).
    const items = [];
    let i = startIdx;
    const test = ordered ? isNumbered : isBullet;
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) break;
      const top = test(line);
      if (!top || top[1].length > 1) break; // pas de premier niveau ici
      const item = { inline: parserInline(top[2]) };
      i += 1;
      // Enfants indentés (>=2 espaces), puces ou numérotés, un seul niveau.
      const children = [];
      while (i < lines.length) {
        const cl = lines[i];
        const cb = isBullet(cl);
        const cn = isNumbered(cl);
        const sub = cb || cn;
        if (sub && sub[1].length >= 2) {
          children.push({ inline: parserInline(sub[2]), ordered: !!cn });
          i += 1;
        } else break;
      }
      if (children.length) item.children = children;
      items.push(item);
    }
    return { items, next: i };
  };

  while (idx < lines.length) {
    const raw = lines[idx];
    const line = raw.replace(/\s+$/, '');

    if (!line.trim()) { idx += 1; continue; }

    // Bloc ```viz … ``` : conservé brut, rendu côté React (VizFigure).
    if (line.trim().startsWith('```viz')) {
      let j = idx + 1; const corps = [];
      while (j < lines.length && !lines[j].trim().startsWith('```')) { corps.push(lines[j]); j += 1; }
      const closed = j < lines.length;
      blocks.push({ type: 'viz', raw: corps.join('\n'), closed });
      idx = closed ? j + 1 : j;
      continue;
    }

    // Bloc de code ``` lang … ```
    if (line.trim().startsWith('```')) {
      const lang = line.trim().slice(3).trim();
      let j = idx + 1; const corps = [];
      while (j < lines.length && !lines[j].trim().startsWith('```')) { corps.push(lines[j]); j += 1; }
      blocks.push({ type: 'code', lang: lang || '', code: corps.join('\n') });
      idx = j < lines.length ? j + 1 : j;
      continue;
    }

    // Tableau : ligne « | … | » suivie d'une ligne de séparation « |---|---| ».
    if (line.trim().startsWith('|') && isSep(lines[idx + 1])) {
      const header = cellsOf(line).map((c) => parserInline(c));
      const rows = [];
      idx += 2;
      while (idx < lines.length && lines[idx].trim().startsWith('|')) {
        rows.push(cellsOf(lines[idx]).map((c) => parserInline(c)));
        idx += 1;
      }
      blocks.push({ type: 'table', header, rows });
      continue;
    }

    // Titres
    const hMatch = /^(#{1,3})\s+(.*)$/.exec(line);
    if (hMatch) {
      blocks.push({ type: 'heading', level: hMatch[1].length, inline: parserInline(hMatch[2]) });
      idx += 1;
      continue;
    }

    // Séparateur
    if (line.trim() === '---' || line.trim() === '***') {
      blocks.push({ type: 'hr' });
      idx += 1;
      continue;
    }

    // Citation `> …` : les lignes contiguës commençant par `>` forment un bloc,
    // analysé récursivement (peut contenir titres, listes, etc.).
    if (/^>\s?/.test(line)) {
      const inner = [];
      while (idx < lines.length && /^>\s?/.test(lines[idx])) {
        inner.push(lines[idx].replace(/^>\s?/, ''));
        idx += 1;
      }
      blocks.push({ type: 'quote', blocks: parserBlocs(inner) });
      continue;
    }

    // Listes numérotées / à puces (racine)
    if (isNumbered(line) && isNumbered(line)[1].length <= 1) {
      const { items, next } = parseListe(idx, true);
      blocks.push({ type: 'list', ordered: true, items });
      idx = next;
      continue;
    }
    if (isBullet(line) && isBullet(line)[1].length <= 1) {
      const { items, next } = parseListe(idx, false);
      blocks.push({ type: 'list', ordered: false, items });
      idx = next;
      continue;
    }

    // Paragraphe : la ligne courante, sans agrégation multi-ligne (comportement
    // historique conservé — chaque ligne non vide est son propre paragraphe).
    // `raw` est conservé pour la détection de l'ancienne marque
    // « Graphique : titre » (repli d'un ```viz mal formé), gérée côté React.
    blocks.push({ type: 'paragraph', inline: parserInline(line), raw: line });
    idx += 1;
  }

  return blocks;
}

export function parserMarkdown(texte) {
  const lines = String(texte == null ? '' : texte).split('\n');
  return parserBlocs(lines);
}
