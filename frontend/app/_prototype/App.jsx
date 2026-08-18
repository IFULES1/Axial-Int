"use client";
/* eslint-disable */
// Auto-assembled from the exact prototype (frontend/prototype/axial-source.html).
// Compiled by Next (no Babel-in-browser). Mock data still inline — wired to the
// backend screen by screen.
import React from "react";
import { axRegister, axLogin, axMe, axSaveProfile, axGetProfile, axBalance, axPlans, axCheckout, axSubscribe, axPrefill, axSubscription, axCreditHistory, axInvoices, axPortal, axGetNotifPrefs, axSetNotifPrefs, axChat, axChatIn, axCreateConversation, axListConversations, axMessages, axNewConversation, axClearToken, axWatchSkills, axListWatches, axCreateWatch, axWatchRuns, axWatchActivity, axRunWatch, axPauseWatch, axResumeWatch, axListFeeds, axAddFeed, axDeleteFeed, axRunAnalysis, axCreateReport, axDownloadReportPdf, axListDocuments, axUploadDocument, axDeleteDocument } from "./bridge";
const ReactDOM = { createRoot: () => ({ render: () => {} }) };


/* data.js */
/* data.js — mock state for the prototype */

const SUGGESTED_PROMPTS = [
  "Mes 3 concurrents directs sur le SaaS RH en France",
  "Combien lever en Série A pour un SaaS Seed à 1,2M ARR",
  "Risques d'un go-to-market Allemagne avant France",
  "Comment positionner un produit IA face à un incumbent",
];

window.AXIAL_DATA = { SUGGESTED_PROMPTS };




/* surfaces-data.js */
/* surfaces-data.js — mock data for new surfaces (FR-first w/ EN strings nested) */

const REPORT_TYPES = [
  { id: 'market', icon: 'trending', estCredits: 320, estMin: 8 },
  { id: 'competitive', icon: 'users', estCredits: 280, estMin: 7 },
  { id: 'regulatory', icon: 'shield', estCredits: 240, estMin: 6 },
  { id: 'risk', icon: 'alert', estCredits: 360, estMin: 9 },
  { id: 'custom', icon: 'sparkle', estCredits: 400, estMin: 10 },
];

const REPORT_TEMPLATES = {
  fr: [
    'Marché des CSRD-tech en France',
    'Concurrents directs sur le segment B2B SaaS RH',
    'Veille IA Act — secteur santé',
    'Risques opérationnels d\'expansion en LATAM',
  ],
  en: [
    'CSRD-tech market in France',
    'Direct competitors — B2B HR SaaS',
    'EU AI Act watch — healthcare',
    'Operational risks of LATAM expansion',
  ],
};

const REPORT_OUTLINE = {
  fr: [
    { num: '1', title: 'Synthèse exécutive' },
    { num: '2', title: 'Cadrage de la question' },
    { num: '3', title: 'Marché — taille & dynamique' },
    { num: '4', title: 'Acteurs en présence' },
    { num: '5', title: 'Risques structurels' },
    { num: '6', title: 'Recommandations' },
    { num: 'A', title: 'Sources' },
  ],
  en: [
    { num: '1', title: 'Executive summary' },
    { num: '2', title: 'Framing the question' },
    { num: '3', title: 'Market — size & dynamics' },
    { num: '4', title: 'Players' },
    { num: '5', title: 'Structural risks' },
    { num: '6', title: 'Recommendations' },
    { num: 'A', title: 'Sources' },
  ],
};

const REPORT_SOURCES = [
  { num: 1, title: 'Étude de marché B2B SaaS RH France 2025', src: 'XERFI · 2025' },
  { num: 2, title: 'Rapport sectoriel — Logiciels RH Europe', src: 'IDC · Q1 2026' },
  { num: 3, title: 'Baromètre des DRH — édition 2026', src: 'Cegos · 2026' },
  { num: 4, title: 'Communication financière H1', src: 'Lucca · 2025' },
  { num: 5, title: 'Étude de cadrage CSRD-RH', src: 'AFNOR Group · 2025' },
  { num: 6, title: 'EU AI Act — Article 6', src: 'Journal officiel UE · 2024' },
  { num: 7, title: 'Decision Velocity Report', src: 'McKinsey · 2024' },
];

const REPORT_ACTIVITY = {
  fr: [
    { time: 'il y a 2 min', text: 'Question reformulée pour précision sur le périmètre RH-tech.' },
    { time: 'il y a 5 min', text: 'Recoupement des chiffres XERFI et IDC : écart de 8 % détecté.' },
    { time: 'il y a 8 min', text: '23 sources retenues sur 47 examinées.' },
    { time: 'il y a 12 min', text: 'Hypothèse posée : marché adressable = SIRH + paie + talent.' },
  ],
  en: [
    { time: '2 min ago', text: 'Question reframed to clarify HR-tech scope.' },
    { time: '5 min ago', text: 'Cross-checked XERFI vs IDC figures: 8% delta found.' },
    { time: '8 min ago', text: '23 sources kept of 47 reviewed.' },
    { time: '12 min ago', text: 'Assumption set: addressable market = HRIS + payroll + talent.' },
  ],
};

const AGENTS = {
  fr: [
    {
      id: 'a1', name: 'Veille concurrentielle — Lucca, Payfit, Cegid',
      desc: 'Surveille les communiqués, levées, recrutements et changements de pricing des trois acteurs clés.',
      status: 'running', sources: 12,
      lastFinding: 'Payfit a annoncé l\'acquisition de SmartFlow (4 nov). Impact estimé : +18 % de couverture sur la paie internationale.',
      lastFindingTime: 'il y a 1 h', nextRun: 'dans 22 h', icon: 'users',
    },
    {
      id: 'a2', name: 'Réglementation IA Act — secteur santé',
      desc: 'Suit les actes délégués, lignes directrices et jurisprudence appliquée à l\'IA en santé.',
      status: 'running', sources: 8,
      lastFinding: 'Nouvelle ligne directrice CNIL sur le profilage clinique. À instruire avant le 15 décembre.',
      lastFindingTime: 'il y a 4 h', nextRun: 'dans 20 h', icon: 'shield',
    },
    {
      id: 'a3', name: 'Mouvements RH — talents IA seniors',
      desc: 'Détecte les départs et arrivées de profils IA seniors dans 14 entreprises ciblées.',
      status: 'paused', sources: 14,
      lastFinding: 'Mise en pause manuelle — données en cours de validation.',
      lastFindingTime: 'il y a 2 j', nextRun: '—', icon: 'briefcase',
    },
    {
      id: 'a4', name: 'Signaux faibles — clients churn-risk',
      desc: 'Croise activité produit, sentiment et événements externes pour signaler les comptes à risque.',
      status: 'idle', sources: 6,
      lastFinding: 'Aucune trouvaille depuis la dernière exécution. Score de bruit faible.',
      lastFindingTime: 'il y a 6 j', nextRun: 'lundi', icon: 'trending',
    },
  ],
  en: [
    {
      id: 'a1', name: 'Competitive watch — Lucca, Payfit, Cegid',
      desc: 'Tracks releases, fundraising, hiring and pricing shifts for the three key players.',
      status: 'running', sources: 12,
      lastFinding: 'Payfit announced acquisition of SmartFlow (Nov 4). Estimated impact: +18% coverage on international payroll.',
      lastFindingTime: '1 h ago', nextRun: 'in 22 h', icon: 'users',
    },
    {
      id: 'a2', name: 'EU AI Act — healthcare sector',
      desc: 'Watches delegated acts, guidance and case law applied to AI in healthcare.',
      status: 'running', sources: 8,
      lastFinding: 'New CNIL guidance on clinical profiling. To be reviewed before Dec 15.',
      lastFindingTime: '4 h ago', nextRun: 'in 20 h', icon: 'shield',
    },
    {
      id: 'a3', name: 'Talent moves — senior AI profiles',
      desc: 'Detects departures and arrivals of senior AI profiles across 14 target companies.',
      status: 'paused', sources: 14,
      lastFinding: 'Manually paused — data being validated.',
      lastFindingTime: '2 d ago', nextRun: '—', icon: 'briefcase',
    },
    {
      id: 'a4', name: 'Weak signals — churn-risk accounts',
      desc: 'Crosses product activity, sentiment and external events to flag at-risk accounts.',
      status: 'idle', sources: 6,
      lastFinding: 'No findings since last run. Noise score low.',
      lastFindingTime: '6 d ago', nextRun: 'Monday', icon: 'trending',
    },
  ],
};

const AGENT_TIMELINE = {
  fr: [
    { time: 'il y a 1 h', title: 'Trouvaille publiée', body: 'Acquisition Payfit / SmartFlow détectée via communiqué de presse + confirmation par 3 sources indépendantes.' },
    { time: 'il y a 1 h', title: 'Recoupement', body: 'Croisement TechCrunch, Les Échos, communiqué officiel. Confiance : haute.' },
    { time: 'il y a 1 h', title: 'Source identifiée', body: 'Communiqué de presse Payfit, 4 novembre 2026, 09:12 CET.' },
    { time: 'il y a 1 j', title: 'Cycle quotidien démarré', body: '47 sources scannées. 2 signaux faibles écartés (insuffisance de recoupement).' },
    { time: 'il y a 2 j', title: 'Trouvaille publiée', body: 'Cegid recrute un Head of Product (LinkedIn). Profil ex-Workday.', muted: true },
  ],
  en: [
    { time: '1 h ago', title: 'Finding published', body: 'Payfit / SmartFlow acquisition detected via press release + confirmation from 3 independent sources.' },
    { time: '1 h ago', title: 'Cross-check', body: 'Crossed TechCrunch, Les Échos, official PR. Confidence: high.' },
    { time: '1 h ago', title: 'Source identified', body: 'Payfit press release, November 4 2026, 09:12 CET.' },
    { time: '1 d ago', title: 'Daily run started', body: '47 sources scanned. 2 weak signals discarded (insufficient cross-checking).' },
    { time: '2 d ago', title: 'Finding published', body: 'Cegid hired a Head of Product (LinkedIn). Ex-Workday profile.', muted: true },
  ],
};

const AGENT_FINDINGS = {
  fr: [
    { title: 'Payfit acquiert SmartFlow', body: 'Couverture paie internationale étendue à 14 nouveaux pays. Risque pour Lucca sur les comptes mid-market exposés à l\'international.', conf: 'high' },
    { title: 'Cegid — recrutement Head of Product', body: 'Profil ex-Workday. Signal d\'inflexion produit possible.', conf: 'med' },
    { title: 'Lucca — ralentissement de la cadence release', body: '3 releases en Q4 vs 6 en Q3. À surveiller.', conf: 'low' },
  ],
  en: [
    { title: 'Payfit acquires SmartFlow', body: 'International payroll coverage extended to 14 new countries. Risk for Lucca on mid-market accounts with international exposure.', conf: 'high' },
    { title: 'Cegid — Head of Product hire', body: 'Ex-Workday profile. Possible product inflection signal.', conf: 'med' },
    { title: 'Lucca — release cadence slowdown', body: '3 releases in Q4 vs 6 in Q3. Worth watching.', conf: 'low' },
  ],
};

const MEMORY_FACTS = {
  fr: {
    you: [
      { id: 'm1', text: 'Camille Verdun, fondatrice, 38 ans', src: 'direct', date: '12 mars 2026' },
      { id: 'm2', text: 'Basée à Paris, équipe distribuée Europe', src: 'direct', date: '12 mars 2026' },
      { id: 'm3', text: 'Préfère les réponses chiffrées et sourcées au verbiage', src: 'inferred', date: '4 avril 2026' },
    ],
    preferences: [
      { id: 'm4', text: 'Jamais de tableaux à plus de 3 colonnes — illisibles à l\'export', src: 'conv', date: '21 mai 2026' },
      { id: 'm5', text: 'Style direct, FR/EN selon contexte client', src: 'direct', date: '12 mars 2026' },
      { id: 'm6', text: 'Citations préférées : sources institutionnelles + études sectorielles', src: 'inferred', date: '8 juin 2026' },
    ],
    work: [
      { id: 'm7', text: 'Entreprise : Axial — SaaS d\'analyse stratégique pour fondateurs', src: 'direct', date: '12 mars 2026' },
      { id: 'm8', text: 'ICP : fondateurs B2B SaaS, 10–80 personnes, post-Série A', src: 'direct', date: '12 mars 2026' },
      { id: 'm9', text: 'Concurrents instruits : Perplexity Pro, ChatGPT Team, Glean', src: 'conv', date: '18 juin 2026' },
      { id: 'm10', text: 'Marchés prioritaires : France, Allemagne, Pays-Bas', src: 'conv', date: '2 juillet 2026' },
    ],
    history: [
      { id: 'm11', text: 'Hypothèse validée : « Mes prospects ne lisent pas les rapports de plus de 8 pages »', src: 'conv', date: '15 juillet 2026' },
      { id: 'm12', text: 'Hypothèse validée : « La preuve par citation pèse plus que la preuve par chiffre »', src: 'conv', date: '23 août 2026' },
    ],
  },
  en: {
    you: [
      { id: 'm1', text: 'Camille Verdun, founder, 38', src: 'direct', date: 'Mar 12, 2026' },
      { id: 'm2', text: 'Based in Paris, distributed team across Europe', src: 'direct', date: 'Mar 12, 2026' },
      { id: 'm3', text: 'Prefers numeric, sourced answers over prose', src: 'inferred', date: 'Apr 4, 2026' },
    ],
    preferences: [
      { id: 'm4', text: 'Never tables with more than 3 columns — illegible on export', src: 'conv', date: 'May 21, 2026' },
      { id: 'm5', text: 'Direct style, FR/EN per client context', src: 'direct', date: 'Mar 12, 2026' },
      { id: 'm6', text: 'Preferred citations: institutional sources + sector studies', src: 'inferred', date: 'Jun 8, 2026' },
    ],
    work: [
      { id: 'm7', text: 'Company: Axial — strategic analysis SaaS for founders', src: 'direct', date: 'Mar 12, 2026' },
      { id: 'm8', text: 'ICP: B2B SaaS founders, 10–80 employees, post-Series A', src: 'direct', date: 'Mar 12, 2026' },
      { id: 'm9', text: 'Competitors learned: Perplexity Pro, ChatGPT Team, Glean', src: 'conv', date: 'Jun 18, 2026' },
      { id: 'm10', text: 'Priority markets: France, Germany, Netherlands', src: 'conv', date: 'Jul 2, 2026' },
    ],
    history: [
      { id: 'm11', text: 'Validated: "My prospects don\'t read reports over 8 pages"', src: 'conv', date: 'Jul 15, 2026' },
      { id: 'm12', text: 'Validated: "Citation proof beats numeric proof"', src: 'conv', date: 'Aug 23, 2026' },
    ],
  },
};

const CREDITS_DAYS = (() => {
  // 14 days, in credit units, with reports/conv/agents split
  const labels = ['12','13','14','15','16','17','18','19','20','21','22','23','24','25'];
  const data = [
    [80, 30, 12], [0, 18, 8], [120, 22, 10], [0, 12, 8],
    [200, 45, 14], [80, 28, 10], [0, 12, 8], [160, 38, 12],
    [40, 30, 14], [240, 52, 16], [80, 22, 12], [120, 32, 14],
    [320, 64, 18], [180, 48, 16],
  ];
  return labels.map((d, i) => ({ d, reports: data[i][0], conv: data[i][1], agents: data[i][2] }));
})();

const SHARE_RECIPIENTS = [
  { name: 'Marc Lefèvre', email: 'marc@axial.intelligence', role: 'editor', avatar: 'ML' },
  { name: 'Sophie Renaud', email: 'sophie@axial.intelligence', role: 'commenter', avatar: 'SR' },
  { name: 'jean.duval@boardpartner.fr', email: 'jean.duval@boardpartner.fr', role: 'viewer', avatar: 'JD', external: true },
];

const SHARE_COMMENTS = {
  fr: [
    { author: 'Marc Lefèvre', avatar: 'ML', time: 'il y a 12 min', text: 'Le chiffre de 47 % me paraît optimiste. Vous avez la source primaire ?' },
    { author: 'Axial', avatar: '', axial: true, time: 'il y a 11 min', text: 'Source primaire : XERFI 2025, panel 240 entreprises. Le chiffre de 47 % concerne le segment SIRH > 50 employés. Hors petit segment, on retombe à 38 %.' },
    { author: 'Marc Lefèvre', avatar: 'ML', time: 'il y a 8 min', text: 'OK, alors clarifions le segment dans la phrase. Sinon Jean va sauter dessus.' },
    { author: 'Camille Verdun', avatar: 'CV', time: 'il y a 6 min', text: 'Je passe la phrase à : « 47 % chez les SIRH > 50 employés (XERFI 2025) ».' },
    { author: 'Sophie Renaud', avatar: 'SR', time: 'il y a 3 min', text: 'Beaucoup mieux. Je valide la section 3.' },
  ],
  en: [
    { author: 'Marc Lefèvre', avatar: 'ML', time: '12 min ago', text: 'The 47% figure feels optimistic. Do you have the primary source?' },
    { author: 'Axial', avatar: '', axial: true, time: '11 min ago', text: 'Primary source: XERFI 2025, panel of 240 companies. The 47% figure is for the HRIS > 50 employees segment. Excluding the SMB segment, it drops to 38%.' },
    { author: 'Marc Lefèvre', avatar: 'ML', time: '8 min ago', text: 'OK, then let\'s clarify the segment in the sentence. Otherwise Jean will jump on it.' },
    { author: 'Camille Verdun', avatar: 'CV', time: '6 min ago', text: 'I\'m moving the sentence to: "47% in HRIS > 50 employees (XERFI 2025)".' },
    { author: 'Sophie Renaud', avatar: 'SR', time: '3 min ago', text: 'Much better. Section 3 approved.' },
  ],
};

const SETTINGS_MEMBERS = [
  { name: 'Camille Verdun', email: 'camille@axial.intelligence', role: 'owner', avatar: 'CV' },
  { name: 'Marc Lefèvre', email: 'marc@axial.intelligence', role: 'admin', avatar: 'ML' },
  { name: 'Sophie Renaud', email: 'sophie@axial.intelligence', role: 'editor', avatar: 'SR' },
  { name: 'Léa Bouvier', email: 'lea@axial.intelligence', role: 'editor', avatar: 'LB' },
  { name: 'Tarik Hassan', email: 'tarik@axial.intelligence', role: 'viewer', avatar: 'TH' },
];

const SETTINGS_CONNECTIONS = [
  { id: 'gdrive', name: 'Google Drive', meta: 'Connecté · 1 248 documents indexés', icon: 'G', connected: true },
  { id: 'notion', name: 'Notion', meta: 'Connecté · 3 espaces', icon: 'N', connected: true },
  { id: 'slack', name: 'Slack', meta: 'Non connecté', icon: 'S', connected: false },
  { id: 'github', name: 'GitHub', meta: 'Non connecté', icon: 'GH', connected: false },
  { id: 'linear', name: 'Linear', meta: 'Connecté · workspace Axial', icon: 'L', connected: true },
];

window.AXIAL_SURFACES = {
  REPORT_TYPES, REPORT_TEMPLATES, REPORT_OUTLINE, REPORT_SOURCES, REPORT_ACTIVITY,
  AGENTS, AGENT_TIMELINE, AGENT_FINDINGS,
  MEMORY_FACTS,
  CREDITS_DAYS,
  SHARE_RECIPIENTS, SHARE_COMMENTS,
  SETTINGS_MEMBERS, SETTINGS_CONNECTIONS,
};




/* theme.js */
/* theme.js — light/dark switch with persistence */

window.setAxialTheme = function (theme) {
  if (theme !== 'light' && theme !== 'dark') return;
  document.documentElement.setAttribute('data-theme', theme);
  window.AXIAL_THEME = theme;
  try { localStorage.setItem('axial:theme', theme); } catch (_) {}
  window.dispatchEvent(new Event('axial:theme'));
};

window.useTheme = function useTheme() {
  const [theme, setTheme] = React.useState(() => window.AXIAL_THEME || 'dark');
  React.useEffect(() => {
    const onChange = () => setTheme(window.AXIAL_THEME || 'dark');
    window.addEventListener('axial:theme', onChange);
    return () => window.removeEventListener('axial:theme', onChange);
  }, []);
  return [theme, window.setAxialTheme];
};

(function init() {
  let saved = 'dark';
  try { saved = localStorage.getItem('axial:theme') || 'dark'; } catch (_) {}
  window.AXIAL_THEME = (saved === 'light') ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', window.AXIAL_THEME);
})();




/* i18n.js */
/* i18n.js — bilingual EN/FR strings + global toggle helper.
   Strings are organized by surface. To add a key, add both EN and FR. */

const STRINGS = {
  fr: {
    // common
    'common.continue': 'Continuer',
    'common.back': 'Retour',
    'common.cancel': 'Annuler',
    'common.save': 'Enregistrer',
    'common.send': 'Envoyer',
    'common.close': 'Fermer',
    'common.search': 'Rechercher',
    'common.new': 'Nouveau',
    'common.delete': 'Supprimer',
    'common.edit': 'Modifier',
    'common.share': 'Partager',
    'common.copy': 'Copier',
    'common.upgrade': 'Améliorer',
    'common.invite': 'Inviter',
    'common.done': 'Terminé',
    'common.loading': 'Chargement…',

    // sidebar / nav
    'nav.conversations': 'Conversations',
    'nav.reports': 'Rapports',
    'nav.agents': 'Agents',
    'nav.memory': 'Mémoire',
    'nav.memory_sub': 'Clé d\'Axial',
    'nav.credits': 'Crédits',
    'nav.settings': 'Paramètres',
    'nav.recent': 'RÉCENTES',
    'nav.tools': 'OUTILS',
    'nav.docs': 'Documentation',
    'nav.new_analysis': 'Nouvelle analyse',
    'nav.new_report': 'Nouveau rapport',
    'nav.new_agent': 'Nouvel agent',

    // topbar
    'topbar.credits': 'crédits',
    'topbar.settings': 'Paramètres',

    // reports
    'reports.title': 'Rapports',
    'reports.empty.h1': 'Un rapport, pas un résumé.',
    'reports.empty.lede': 'Choisissez un type d\'étude. Axial cadre la question, recueille les sources, raisonne, et livre un document structuré.',
    'reports.types.market': 'Étude de marché',
    'reports.types.market_desc': 'TAM/SAM/SOM, segments, dynamiques de croissance.',
    'reports.types.competitive': 'Cartographie concurrentielle',
    'reports.types.competitive_desc': 'Positionnement, parts, forces structurelles.',
    'reports.types.regulatory': 'Veille réglementaire',
    'reports.types.regulatory_desc': 'Cadres légaux applicables, calendriers d\'entrée en vigueur.',
    'reports.types.risk': 'Analyse de risques',
    'reports.types.risk_desc': 'Risques opérationnels, marché, réglementaires.',
    'reports.types.custom': 'Étude personnalisée',
    'reports.types.custom_desc': 'Question stratégique ouverte. Axial cadre.',
    'reports.template_strip': 'Modèles récents',
    'reports.start': 'Lancer le rapport',
    'reports.estimate': 'Estimation',
    'reports.depth': 'Profondeur',
    'reports.depth.scan': 'Scan',
    'reports.depth.standard': 'Standard',
    'reports.depth.deep': 'Approfondi',
    'reports.cost': 'crédits',
    'reports.duration': 'min',

    'reports.gen.title': 'Génération en cours',
    'reports.gen.tasks.parsed': 'Question cadrée',
    'reports.gen.tasks.gathered': 'Sources recueillies',
    'reports.gen.tasks.cross': 'Recoupement',
    'reports.gen.tasks.drafting': 'Rédaction',
    'reports.gen.tasks.charts': 'Graphiques',
    'reports.gen.tasks.review': 'Vérification',
    'reports.gen.sources_found': 'sources trouvées',
    'reports.gen.elapsed': 'Temps écoulé',

    'reports.editor.outline': 'Plan',
    'reports.editor.sources': 'Sources',
    'reports.editor.activity': 'Activité',
    'reports.editor.suggest': 'Suggestion d\'Axial',

    'reports.gap.title': 'Donnée insuffisante',
    'reports.gap.body': 'Ce paragraphe manque de signal vérifiable. Vous pouvez fournir un chiffre interne, autoriser une recherche profonde, ou laisser la lacune visible.',
    'reports.gap.add': 'Fournir une donnée',
    'reports.gap.deepen': 'Recherche profonde',
    'reports.gap.confidence': 'Confiance par section',

    'reports.conflict.title': 'Sources en désaccord',
    'reports.conflict.body': 'Deux sources crédibles donnent des chiffres incompatibles sur ce point. Axial s\'arrête et vous laisse trancher.',
    'reports.conflict.recommendation': 'Recommandation d\'Axial',
    'reports.conflict.use_a': 'Utiliser source A',
    'reports.conflict.use_b': 'Utiliser source B',
    'reports.conflict.cite_both': 'Citer les deux',

    'reports.quota.title': 'Crédits insuffisants',
    'reports.quota.body': 'Ce rapport demande plus de crédits que ce qu\'il vous reste ce mois-ci. Deux options.',
    'reports.quota.upgrade': 'Passer à Pro',
    'reports.quota.topup': 'Recharger ponctuellement',
    'reports.quota.usage': 'Consommation du mois',

    // agents
    'agents.title': 'Agents',
    'agents.subtitle': 'Travailleurs persistants. Vous définissez la mission, ils ramènent des trouvailles.',
    'agents.status.running': 'En cours',
    'agents.status.paused': 'En pause',
    'agents.status.idle': 'Au repos',
    'agents.last_finding': 'Dernière trouvaille',
    'agents.next_run': 'Prochaine exécution',
    'agents.sources': 'sources',
    'agents.create': 'Créer un agent',
    'agents.wizard.trigger': 'Déclencheur',
    'agents.wizard.sources': 'Sources',
    'agents.wizard.output': 'Livrable',
    'agents.wizard.schedule': 'Cadence',
    'agents.session.timeline': 'Chronologie de la session',
    'agents.session.findings': 'Trouvailles',
    'agents.confidence': 'Confiance',

    // memory
    'memory.title': 'Mémoire — la clé d\'Axial',
    'memory.subtitle': 'Voici ce qu\'Axial sait de vous. Chaque fait est révocable.',
    'memory.privacy': 'Privé. Stocké chiffré. Jamais utilisé pour entraîner un modèle externe.',
    'memory.cat.you': 'Vous',
    'memory.cat.preferences': 'Préférences',
    'memory.cat.work': 'Contexte professionnel',
    'memory.cat.history': 'Hypothèses validées',
    'memory.source_conv': 'd\'une conversation',
    'memory.source_direct': 'vous me l\'avez dit',
    'memory.source_inferred': 'déduit',
    'memory.freeze': 'Geler',
    'memory.unfreeze': 'Dégeler',

    // credits
    'credits.title': 'Crédits',
    'credits.month': 'Ce mois-ci',
    'credits.used': 'utilisés',
    'credits.remaining': 'restants',
    'credits.breakdown': 'Répartition',
    'credits.plan': 'Plan',
    'credits.plan.beta': 'Beta · Gratuit',
    'credits.plan.next': 'Pro — 50 €/mois',

    // settings
    'settings.title': 'Paramètres',
    'settings.personal': 'Personnel',
    'settings.workspace': 'Espace de travail',
    'settings.account': 'Compte',
    'settings.notifications': 'Notifications',
    'settings.appearance': 'Apparence',
    'settings.members': 'Membres',
    'settings.models': 'Modèles',
    'settings.connections': 'Connexions',
    'settings.billing': 'Facturation',

    // sharing
    'share.title': 'Partager',
    'share.tab.people': 'Personnes',
    'share.tab.link': 'Lien',
    'share.tab.embed': 'Intégrer',
    'share.role.viewer': 'Lecture',
    'share.role.commenter': 'Commentaire',
    'share.role.editor': 'Édition',
    'share.link.private': 'Privé',
    'share.link.workspace': 'Espace de travail',
    'share.link.anyone': 'Toute personne avec le lien',
    'share.recipient.read_only': 'Lecture seule',
    'share.thread.reply': 'Répondre',
    'share.thread.axial_replied': 'Axial a répondu',

    // landing (public)
    'landing.nav.product': 'Produit',
    'landing.nav.how': 'Comment ça marche',
    'landing.nav.trust': 'Confiance',
    'landing.nav.pricing': 'Tarifs',
    'landing.nav.signin': 'Se connecter',
    'landing.nav.start': 'Commencer',
    'landing.hero.eyebrow': 'L’intelligence stratégique sur demande',
    'landing.hero.h1.line1': 'Le copilote stratégique',
    'landing.hero.h1.line2': 'des décisions de fondateur.',
    'landing.hero.lede': 'Générez des études de marché, des cartographies concurrentielles et des analyses de risque, puis posez à AXIAL les questions qui guident votre prochaine levée, votre GTM ou votre entrée sur un nouveau marché.',
    'landing.hero.cta.start': 'Démarrer une analyse',
    'landing.hero.cta.signin': 'J’ai déjà un compte',
    'landing.hero.meta': 'UTILISÉ PAR DES FONDATEURS DE  ·  HAPSTER  ·  NORTHERN  ·  MODULR  ·  LINÉAIRE  ·  POLARIS',
    'landing.feat.conv.t': 'Conversation libre',
    'landing.feat.conv.b': 'Posez n’importe quelle question stratégique. Réponses structurées, citées, exportables.',
    'landing.feat.agents.t': 'Agents spécialisés',
    'landing.feat.agents.b': 'PESTEL, Porter, GTM, due diligence — invoquez un agent, recevez un livrable.',
    'landing.feat.mem.t': 'Mémoire contextuelle',
    'landing.feat.mem.b': 'Axial retient votre marché, votre stade, vos hypothèses. Chaque fait est révocable.',
    'landing.feat.src.t': 'Sources vérifiables',
    'landing.feat.src.b': 'Chaque assertion renvoie à un rapport, un cadre légal, une donnée terrain.',
    'landing.how.eyebrow': 'COMMENT ÇA MARCHE',
    'landing.how.h2.line1': 'De la question floue',
    'landing.how.h2.line2': 'à la décision instruite, en quatre temps.',
    'landing.how.s1.t': 'Vous posez la question',
    'landing.how.s1.b': 'En langage naturel. Axial reformule, désambiguïse, confirme le périmètre avant d’investir des crédits de raisonnement.',
    'landing.how.s2.t': 'Axial cherche et raisonne',
    'landing.how.s2.b': 'Sources publiques, rapports sectoriels, votre mémoire privée. Le raisonnement est tracé, pas dissimulé.',
    'landing.how.s3.t': 'Vous recevez une réponse',
    'landing.how.s3.b': 'Synthèse, friction, recommandations. Chaque chiffre, chaque assertion est citée et cliquable.',
    'landing.how.s4.t': 'Axial apprend votre contexte',
    'landing.how.s4.b': 'La mémoire conserve vos hypothèses validées. La conversation suivante part du bon endroit.',
    'landing.cta.h2': 'Posez votre première question stratégique.',
    'landing.cta.body': 'Trois minutes pour configurer votre contexte. Aucune carte de crédit pour explorer.',
    'landing.cta.btn': 'Démarrer maintenant',
    'landing.footer.note': '© 2026 AXIAL · PARIS · CONÇU POUR LES FONDATEURS FRANCOPHONES',
  },
  en: {
    'common.continue': 'Continue',
    'common.back': 'Back',
    'common.cancel': 'Cancel',
    'common.save': 'Save',
    'common.send': 'Send',
    'common.close': 'Close',
    'common.search': 'Search',
    'common.new': 'New',
    'common.delete': 'Delete',
    'common.edit': 'Edit',
    'common.share': 'Share',
    'common.copy': 'Copy',
    'common.upgrade': 'Upgrade',
    'common.invite': 'Invite',
    'common.done': 'Done',
    'common.loading': 'Loading…',

    'nav.conversations': 'Conversations',
    'nav.reports': 'Reports',
    'nav.agents': 'Agents',
    'nav.memory': 'Memory',
    'nav.memory_sub': 'Axial\'s Key',
    'nav.credits': 'Credits',
    'nav.settings': 'Settings',
    'nav.recent': 'RECENT',
    'nav.tools': 'TOOLS',
    'nav.docs': 'Documentation',
    'nav.new_analysis': 'New analysis',
    'nav.new_report': 'New report',
    'nav.new_agent': 'New agent',

    'topbar.credits': 'credits',
    'topbar.settings': 'Settings',

    'reports.title': 'Reports',
    'reports.empty.h1': 'A report, not a summary.',
    'reports.empty.lede': 'Pick a study type. Axial frames the question, gathers sources, reasons, and ships a structured document.',
    'reports.types.market': 'Market study',
    'reports.types.market_desc': 'TAM/SAM/SOM, segments, growth dynamics.',
    'reports.types.competitive': 'Competitive map',
    'reports.types.competitive_desc': 'Positioning, share, structural forces.',
    'reports.types.regulatory': 'Regulatory scan',
    'reports.types.regulatory_desc': 'Applicable legal frames and timelines.',
    'reports.types.risk': 'Risk analysis',
    'reports.types.risk_desc': 'Operational, market, regulatory risks.',
    'reports.types.custom': 'Custom study',
    'reports.types.custom_desc': 'Open strategic question. Axial frames it.',
    'reports.template_strip': 'Recent templates',
    'reports.start': 'Run report',
    'reports.estimate': 'Estimate',
    'reports.depth': 'Depth',
    'reports.depth.scan': 'Scan',
    'reports.depth.standard': 'Standard',
    'reports.depth.deep': 'Deep',
    'reports.cost': 'credits',
    'reports.duration': 'min',

    'reports.gen.title': 'Generating',
    'reports.gen.tasks.parsed': 'Question framed',
    'reports.gen.tasks.gathered': 'Sources gathered',
    'reports.gen.tasks.cross': 'Cross-checked',
    'reports.gen.tasks.drafting': 'Drafting',
    'reports.gen.tasks.charts': 'Charts',
    'reports.gen.tasks.review': 'Review',
    'reports.gen.sources_found': 'sources found',
    'reports.gen.elapsed': 'Elapsed',

    'reports.editor.outline': 'Outline',
    'reports.editor.sources': 'Sources',
    'reports.editor.activity': 'Activity',
    'reports.editor.suggest': 'Axial\'s suggestion',

    'reports.gap.title': 'Insufficient data',
    'reports.gap.body': 'This passage lacks verifiable signal. Provide an internal figure, authorize a deeper search, or leave the gap visible.',
    'reports.gap.add': 'Provide a figure',
    'reports.gap.deepen': 'Deeper search',
    'reports.gap.confidence': 'Section confidence',

    'reports.conflict.title': 'Sources disagree',
    'reports.conflict.body': 'Two credible sources give incompatible figures here. Axial pauses and lets you decide.',
    'reports.conflict.recommendation': 'Axial\'s recommendation',
    'reports.conflict.use_a': 'Use source A',
    'reports.conflict.use_b': 'Use source B',
    'reports.conflict.cite_both': 'Cite both',

    'reports.quota.title': 'Out of credits',
    'reports.quota.body': 'This report needs more credits than you have left this month. Two paths.',
    'reports.quota.upgrade': 'Move to Pro',
    'reports.quota.topup': 'One-time top-up',
    'reports.quota.usage': 'This month',

    'agents.title': 'Agents',
    'agents.subtitle': 'Persistent workers. You set the mission, they bring back findings.',
    'agents.status.running': 'Running',
    'agents.status.paused': 'Paused',
    'agents.status.idle': 'Idle',
    'agents.last_finding': 'Last finding',
    'agents.next_run': 'Next run',
    'agents.sources': 'sources',
    'agents.create': 'Create agent',
    'agents.wizard.trigger': 'Trigger',
    'agents.wizard.sources': 'Sources',
    'agents.wizard.output': 'Output',
    'agents.wizard.schedule': 'Schedule',
    'agents.session.timeline': 'Session timeline',
    'agents.session.findings': 'Findings',
    'agents.confidence': 'Confidence',

    'memory.title': 'Memory — Axial\'s Key',
    'memory.subtitle': 'Here\'s what Axial knows about you. Every fact is revocable.',
    'memory.privacy': 'Private. Stored encrypted. Never used to train an external model.',
    'memory.cat.you': 'You',
    'memory.cat.preferences': 'Preferences',
    'memory.cat.work': 'Work context',
    'memory.cat.history': 'Validated assumptions',
    'memory.source_conv': 'from a conversation',
    'memory.source_direct': 'you told me directly',
    'memory.source_inferred': 'inferred',
    'memory.freeze': 'Freeze',
    'memory.unfreeze': 'Unfreeze',

    'credits.title': 'Credits',
    'credits.month': 'This month',
    'credits.used': 'used',
    'credits.remaining': 'left',
    'credits.breakdown': 'Breakdown',
    'credits.plan': 'Plan',
    'credits.plan.beta': 'Beta · Free',
    'credits.plan.next': 'Pro — €50/mo',

    'settings.title': 'Settings',
    'settings.personal': 'Personal',
    'settings.workspace': 'Workspace',
    'settings.account': 'Account',
    'settings.notifications': 'Notifications',
    'settings.appearance': 'Appearance',
    'settings.members': 'Members',
    'settings.models': 'Models',
    'settings.connections': 'Connections',
    'settings.billing': 'Billing',

    'share.title': 'Share',
    'share.tab.people': 'People',
    'share.tab.link': 'Link',
    'share.tab.embed': 'Embed',
    'share.role.viewer': 'Viewer',
    'share.role.commenter': 'Commenter',
    'share.role.editor': 'Editor',
    'share.link.private': 'Private',
    'share.link.workspace': 'Workspace',
    'share.link.anyone': 'Anyone with the link',
    'share.recipient.read_only': 'Read-only',
    'share.thread.reply': 'Reply',
    'share.thread.axial_replied': 'Axial replied',

    // landing (public)
    'landing.nav.product': 'Product',
    'landing.nav.how': 'How it works',
    'landing.nav.trust': 'Trust',
    'landing.nav.pricing': 'Pricing',
    'landing.nav.signin': 'Sign in',
    'landing.nav.start': 'Get started',
    'landing.hero.eyebrow': 'Strategic intelligence, on demand',
    'landing.hero.h1.line1': 'The strategic copilot',
    'landing.hero.h1.line2': 'for founder decisions.',
    'landing.hero.lede': 'Generate market studies, competitive mappings, and risk analyses, then ask AXIAL the questions behind your next fundraising, GTM, or market-entry decision.',
    'landing.hero.cta.start': 'Start an analysis',
    'landing.hero.cta.signin': 'I already have an account',
    'landing.hero.meta': 'USED BY FOUNDERS AT  ·  HAPSTER  ·  NORTHERN  ·  MODULR  ·  LINÉAIRE  ·  POLARIS',
    'landing.feat.conv.t': 'Open conversation',
    'landing.feat.conv.b': 'Ask any strategic question. Structured answers, cited, exportable.',
    'landing.feat.agents.t': 'Specialized agents',
    'landing.feat.agents.b': 'PESTEL, Porter, GTM, due diligence — invoke an agent, get a deliverable.',
    'landing.feat.mem.t': 'Contextual memory',
    'landing.feat.mem.b': 'Axial remembers your market, stage, and assumptions. Every fact is revocable.',
    'landing.feat.src.t': 'Verifiable sources',
    'landing.feat.src.b': 'Every claim links back to a report, a legal framework, or a field data point.',
    'landing.how.eyebrow': 'HOW IT WORKS',
    'landing.how.h2.line1': 'From a fuzzy question',
    'landing.how.h2.line2': 'to an informed decision, in four steps.',
    'landing.how.s1.t': 'You ask the question',
    'landing.how.s1.b': 'In plain language. Axial rephrases, disambiguates, and confirms the scope before spending reasoning credits.',
    'landing.how.s2.t': 'Axial searches and reasons',
    'landing.how.s2.b': 'Public sources, sector reports, your private memory. The reasoning is traced, not hidden.',
    'landing.how.s3.t': 'You get an answer',
    'landing.how.s3.b': 'Synthesis, frictions, recommendations. Every number and claim is cited and clickable.',
    'landing.how.s4.t': 'Axial learns your context',
    'landing.how.s4.b': 'Memory keeps your validated assumptions. The next conversation starts in the right place.',
    'landing.cta.h2': 'Ask your first strategic question.',
    'landing.cta.body': 'Three minutes to configure your context. No credit card to explore.',
    'landing.cta.btn': 'Start now',
    'landing.footer.note': '© 2026 AXIAL · PARIS · BUILT FOR FOUNDERS',
  },
};

window.AXIAL_I18N = STRINGS;

window.useT = function useT() {
  const [, force] = React.useReducer((x) => x + 1, 0);
  React.useEffect(() => {
    const onChange = () => force();
    window.addEventListener('axial:lang', onChange);
    return () => window.removeEventListener('axial:lang', onChange);
  }, []);
  const lang = window.AXIAL_LANG || 'fr';
  return (key) => (STRINGS[lang] && STRINGS[lang][key]) || STRINGS.fr[key] || key;
};

window.setAxialLang = function (lang) {
  if (lang !== 'fr' && lang !== 'en') return;
  window.AXIAL_LANG = lang;
  try { localStorage.setItem('axial:lang', lang); } catch (_) {}
  document.documentElement.setAttribute('lang', lang);
  window.dispatchEvent(new Event('axial:lang'));
};

(function init() {
  let saved = 'fr';
  try { saved = localStorage.getItem('axial:lang') || 'fr'; } catch (_) {}
  window.AXIAL_LANG = (saved === 'en') ? 'en' : 'fr';
  document.documentElement.setAttribute('lang', window.AXIAL_LANG);
})();




/* atoms.jsx */
/* atoms.jsx — shared primitives (icons, lockup) */

/* ---- Inline SVG icon set (lucide-style, 1.5px stroke) ---- */
function Icon({ name, size = 18, stroke = 1.6, ...rest }) {
  const common = {
    width: size, height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: stroke,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    ...rest,
  };
  switch (name) {
    case 'plus': return (
      <svg {...common}><path d="M12 5v14M5 12h14" /></svg>
    );
    case 'arrow-right': return (
      <svg {...common}><path d="M5 12h14M13 5l7 7-7 7" /></svg>
    );
    case 'arrow-up': return (
      <svg {...common}><path d="M12 19V5M5 12l7-7 7 7" /></svg>
    );
    case 'arrow-left': return (
      <svg {...common}><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
    );
    case 'search': return (
      <svg {...common}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
    );
    case 'message': return (
      <svg {...common}><path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5z" /></svg>
    );
    case 'cpu': return (
      <svg {...common}><rect x="4" y="4" width="16" height="16" rx="2" /><rect x="9" y="9" width="6" height="6" /><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3" /></svg>
    );
    case 'database': return (
      <svg {...common}><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14a9 3 0 0 0 18 0V5" /><path d="M3 12a9 3 0 0 0 18 0" /></svg>
    );
    case 'zap': return (
      <svg {...common}><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" /></svg>
    );
    case 'settings': return (
      <svg {...common}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
    );
    case 'check': return (
      <svg {...common}><path d="M20 6 9 17l-5-5" /></svg>
    );
    case 'x': return (
      <svg {...common}><path d="M18 6 6 18M6 6l12 12" /></svg>
    );
    case 'thumb-up': return (
      <svg {...common}><path d="M7 22V11M2 13v7a2 2 0 0 0 2 2h13.66a2 2 0 0 0 2-1.7l1.26-8a2 2 0 0 0-2-2.3H15V5a3 3 0 0 0-3-3l-3 8v12" /></svg>
    );
    case 'thumb-down': return (
      <svg {...common} style={{ transform: 'rotate(180deg)', ...(rest.style||{}) }}><path d="M7 22V11M2 13v7a2 2 0 0 0 2 2h13.66a2 2 0 0 0 2-1.7l1.26-8a2 2 0 0 0-2-2.3H15V5a3 3 0 0 0-3-3l-3 8v12" /></svg>
    );
    case 'flag': return (
      <svg {...common}><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" /><line x1="4" y1="22" x2="4" y2="15" /></svg>
    );
    case 'download': return (
      <svg {...common}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" /></svg>
    );
    case 'sparkle': return (
      <svg {...common}><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" /></svg>
    );
    case 'logout': return (
      <svg {...common}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" /></svg>
    );
    case 'mark': return (
      // Axial concentric mark
      <svg {...common} viewBox="0 0 32 32" stroke="currentColor" strokeWidth="1.4" fill="none">
        <circle cx="16" cy="16" r="13" opacity=".25" />
        <circle cx="16" cy="16" r="9" opacity=".5" />
        <circle cx="16" cy="16" r="5" opacity=".8" />
        <path d="M3 16h26M16 3v26" opacity=".35" />
        <circle cx="16" cy="16" r="2" fill="currentColor" stroke="none" />
      </svg>
    );
    case 'google': return (
      <svg width={size} height={size} viewBox="0 0 24 24" {...rest}>
        <path fill="#FFC107" d="M21.8 10H12v4h5.6c-.6 2.7-2.9 4-5.6 4a6 6 0 1 1 0-12c1.5 0 2.9.6 4 1.5l3-3A10 10 0 1 0 12 22c5.7 0 10-4 10-10 0-.7-.1-1.3-.2-2z"/>
        <path fill="#FF3D00" d="M3.2 7 6.5 9.5C7.4 7.5 9.5 6 12 6c1.5 0 2.9.6 4 1.5l3-3A10 10 0 0 0 3.2 7z"/>
        <path fill="#4CAF50" d="M12 22c2.5 0 4.8-1 6.5-2.5L15.4 17c-1 .7-2.2 1-3.4 1-2.7 0-5-1.7-5.8-4.1L3 16.4A10 10 0 0 0 12 22z"/>
        <path fill="#1976D2" d="M21.8 10H12v4h5.6c-.3 1.4-1.2 2.6-2.4 3.4l3.1 2.5c1.8-1.7 2.9-4.2 2.9-7.4 0-.7-.1-1.3-.2-2z"/>
      </svg>
    );
    case 'chevron-right': return (
      <svg {...common}><path d="m9 18 6-6-6-6" /></svg>
    );
    case 'chevron-down': return (
      <svg {...common}><path d="m6 9 6 6 6-6" /></svg>
    );
    case 'chevron-up': return (
      <svg {...common}><path d="m6 15 6-6 6 6" /></svg>
    );
    case 'file': return (
      <svg {...common}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></svg>
    );
    case 'document': return (
      <svg {...common}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M9 13h6M9 17h6M9 9h2" /></svg>
    );
    case 'bot': return (
      <svg {...common}><rect x="3" y="8" width="18" height="12" rx="2" /><path d="M12 4v4M9 14h.01M15 14h.01M9 17h6" /></svg>
    );
    case 'key': return (
      <svg {...common}><circle cx="8" cy="15" r="4" /><path d="m10.85 12.15 9.15-9.15M16 4l3 3M14 6l3 3" /></svg>
    );
    case 'lock': return (
      <svg {...common}><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
    );
    case 'eye': return (
      <svg {...common}><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>
    );
    case 'globe': return (
      <svg {...common}><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20z" /></svg>
    );
    case 'users': return (
      <svg {...common}><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></svg>
    );
    case 'user': return (
      <svg {...common}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
    );
    case 'bell': return (
      <svg {...common}><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0" /></svg>
    );
    case 'palette': return (
      <svg {...common}><circle cx="13.5" cy="6.5" r="1" fill="currentColor" /><circle cx="17.5" cy="10.5" r="1" fill="currentColor" /><circle cx="8.5" cy="7.5" r="1" fill="currentColor" /><circle cx="6.5" cy="12.5" r="1" fill="currentColor" /><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.93 0 1.5-.7 1.5-1.5 0-.4-.16-.77-.42-1.04-.27-.27-.42-.63-.42-1.04 0-.83.67-1.5 1.5-1.5H16a6 6 0 0 0 6-6c0-5.5-4.5-10-10-10z" /></svg>
    );
    case 'play': return (
      <svg {...common}><polygon points="6 4 20 12 6 20 6 4" fill="currentColor" stroke="currentColor" /></svg>
    );
    case 'pause': return (
      <svg {...common}><rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" /></svg>
    );
    case 'refresh': return (
      <svg {...common}><path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5" /></svg>
    );
    case 'edit': return (
      <svg {...common}><path d="M12 20h9M16.5 3.5a2.12 2.12 0 1 1 3 3L7 19l-4 1 1-4z" /></svg>
    );
    case 'trash': return (
      <svg {...common}><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /></svg>
    );
    case 'snowflake': return (
      <svg {...common}><path d="M12 2v20M2 12h20M5 5l14 14M19 5 5 19" /></svg>
    );
    case 'link': return (
      <svg {...common}><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /></svg>
    );
    case 'copy': return (
      <svg {...common}><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
    );
    case 'send': return (
      <svg {...common}><path d="m22 2-7 20-4-9-9-4 20-7z" /></svg>
    );
    case 'sun': return (
      <svg {...common}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" /></svg>
    );
    case 'moon': return (
      <svg {...common}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg>
    );
    case 'alert': return (
      <svg {...common}><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01" /></svg>
    );
    case 'plug': return (
      <svg {...common}><path d="M9 2v6M15 2v6M6 8h12v4a6 6 0 0 1-12 0V8zM12 18v4" /></svg>
    );
    case 'briefcase': return (
      <svg {...common}><rect x="2" y="7" width="20" height="14" rx="2" /><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" /></svg>
    );
    case 'trending': return (
      <svg {...common}><polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" /></svg>
    );
    case 'shield': return (
      <svg {...common}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
    );
    case 'clock': return (
      <svg {...common}><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
    );
    case 'message-square': return (
      <svg {...common}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
    );
    case 'book': return (
      <svg {...common}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14zM4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5" /></svg>
    );
    case 'sparkles': return (
      <svg {...common}><path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z" /></svg>
    );
    default: return <svg {...common} />;
  }
}

/* ---- Logo lockup ---- */
function Lockup({ sub = 'Intelligence' }) {
  return (
    <span className="lockup">
      <span className="lockup-mark">
        <img src="data:image/png;base64,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" alt="" className="lockup-flame" />
      </span>
      <span className="lockup-word">Axial</span>
      {sub && <span className="lockup-sub">{sub}</span>}
    </span>
  );
}

window.Icon = Icon;
window.Lockup = Lockup;




/* landing.jsx */
/* landing.jsx — public landing page (logged-out) */

var { useEffect, useRef } = React;

function LandingLangPill() {
  const [, force] = React.useReducer((x) => x + 1, 0);
  React.useEffect(() => {
    const onChange = () => force();
    window.addEventListener('axial:lang', onChange);
    return () => window.removeEventListener('axial:lang', onChange);
  }, []);
  const lang = window.AXIAL_LANG || 'fr';
  return (
    <div className="lang-pill" role="group" aria-label="Language">
      <button className={lang === 'fr' ? 'active' : ''} onClick={() => window.setAxialLang('fr')}>FR</button>
      <button className={lang === 'en' ? 'active' : ''} onClick={() => window.setAxialLang('en')}>EN</button>
    </div>
  );
}

function LandingPage({ onCTAStart, onCTASignIn }) {
  const t = window.useT();
  const isFR = (window.AXIAL_LANG || 'fr') === 'fr';
  const pricingPlans = [
    { name: 'Free Beta', price: '0 €', per: isFR ? '/mois' : '/mo',
      credits: isFR ? '20 crédits / mois' : '20 credits / mo',
      features: isFR ? ['Découverte', 'Export PDF', '1 siège'] : ['Discovery', 'PDF export', '1 seat'],
      tag: null, cta: 'start' },
    { name: 'Pro', price: '50 €', per: isFR ? '/mois' : '/mo',
      credits: isFR ? '120 crédits / mois' : '120 credits / mo',
      features: isFR ? ['Workspace', '2 agents de veille', 'Templates (fundraising, ICP, GTM)'] : ['Workspace', '2 monitoring agents', 'Templates (fundraising, ICP, GTM)'],
      tag: isFR ? 'POPULAIRE' : 'POPULAR', cta: 'start' },
    { name: 'Premium', price: '90 €', per: isFR ? '/mois' : '/mo',
      credits: isFR ? '250 crédits / mois · 2 sièges' : '250 credits / mo · 2 seats',
      features: isFR ? ['Tout Pro', "Jusqu'à 10 agents", 'Mémoire avancée'] : ['Everything in Pro', 'Up to 10 agents', 'Advanced memory'],
      tag: null, cta: 'start' },
    { name: 'Enterprise', price: isFR ? 'Sur devis' : 'Custom', per: '',
      credits: isFR ? 'Multi-startups, équipe' : 'Multi-startup, team',
      features: isFR ? ['Signaux portefeuille', 'Accès équipe', 'Support dédié'] : ['Portfolio signals', 'Team access', 'Dedicated support'],
      tag: null, cta: 'contact' },
  ];
  return (
    <div className="page">
      <div className="bg-radial" />

      <header className="landing-nav">
        <Lockup sub="Intelligence" />
        <nav className="landing-nav-links">
          <a href="#product">{t('landing.nav.product')}</a>
          <a href="#how">{t('landing.nav.how')}</a>
          <a href="#trust">{t('landing.nav.trust')}</a>
          <a href="#pricing">{t('landing.nav.pricing')}</a>
        </nav>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <LandingLangPill />
          <button className="btn btn-ghost" onClick={onCTASignIn}>{t('landing.nav.signin')}</button>
          <button className="btn btn-primary" onClick={onCTAStart}>
            {t('landing.nav.start')} <Icon name="arrow-right" size={14} />
          </button>
        </div>
      </header>

      <section className="hero">
        <div className="hero-eyebrow-pill">
          <span className="hero-eyebrow-dot" />
          <span className="hero-eyebrow-text">{t('landing.hero.eyebrow')}</span>
        </div>

        <h1>
          {t('landing.hero.h1.line1')}<br />
          <span style={{
            background: 'linear-gradient(90deg, var(--v-soft), var(--v-bright))',
            WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
          }}>{t('landing.hero.h1.line2')}</span>
        </h1>

        <p className="lede" style={{ fontSize: 17, color: 'var(--fg-2)', maxWidth: 720, margin: '0 auto 32px', lineHeight: 1.55 }}>
          {t('landing.hero.lede')}
        </p>

        <div className="hero-cta-row">
          <button className="btn btn-primary btn-lg" onClick={onCTAStart}>
            {t('landing.hero.cta.start')} <Icon name="arrow-right" size={15} />
          </button>
          <button className="btn btn-secondary btn-lg" onClick={onCTASignIn}>
            {t('landing.hero.cta.signin')}
          </button>
        </div>

        <div className="hero-meta" style={{ marginTop: 28 }}>
          {t('landing.hero.meta')}
        </div>
      </section>

      <section id="product" className="feature-row">
        <FeatureCard icon="message" title={t('landing.feat.conv.t')}   body={t('landing.feat.conv.b')} />
        <FeatureCard icon="cpu"     title={t('landing.feat.agents.t')} body={t('landing.feat.agents.b')} />
        <FeatureCard icon="database" title={t('landing.feat.mem.t')}    body={t('landing.feat.mem.b')} />
        <FeatureCard icon="zap"     title={t('landing.feat.src.t')}    body={t('landing.feat.src.b')} />
      </section>

      <section id="how" style={{ maxWidth: 1180, margin: '120px auto 80px', padding: '0 32px' }}>
        <div style={{ textAlign: 'center', marginBottom: 56 }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>{t('landing.how.eyebrow')}</div>
          <h2 style={{ fontSize: 38, margin: 0, letterSpacing: '-0.02em', fontWeight: 700, lineHeight: 1.15 }}>
            {t('landing.how.h2.line1')}<br />{t('landing.how.h2.line2')}
          </h2>
        </div>
        <ol style={{
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20,
          listStyle: 'none', padding: 0, margin: 0,
        }}>
          {[
            ['01', t('landing.how.s1.t'), t('landing.how.s1.b')],
            ['02', t('landing.how.s2.t'), t('landing.how.s2.b')],
            ['03', t('landing.how.s3.t'), t('landing.how.s3.b')],
            ['04', t('landing.how.s4.t'), t('landing.how.s4.b')],
          ].map(([n, ti, bo]) => (
            <li key={n} className="card" style={{ padding: 24 }}>
              <div className="mono" style={{ color: 'var(--v-soft)', fontSize: 11, marginBottom: 14, letterSpacing: '0.16em' }}>{n}</div>
              <h3 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 8px' }}>{ti}</h3>
              <p style={{ margin: 0, fontSize: 13.5, color: 'var(--fg-2)', lineHeight: 1.55 }}>{bo}</p>
            </li>
          ))}
        </ol>
      </section>

      <section id="trust" style={{ maxWidth: 1180, margin: '80px auto 40px', padding: '0 32px' }}>
        <div style={{ textAlign: 'center', marginBottom: 48 }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>{isFR ? 'CONFIANCE' : 'TRUST'}</div>
          <h2 style={{ fontSize: 38, margin: 0, letterSpacing: '-0.02em', fontWeight: 700, lineHeight: 1.15 }}>
            {isFR ? 'Vos données restent les vôtres.' : 'Your data stays yours.'}
          </h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 18 }}>
          {[
            { icon: 'key', t: isFR ? 'Cloisonnement par compte' : 'Scoped to your account',
              b: isFR ? 'Votre mémoire et vos documents ne sont jamais partagés ni indexés pour d’autres utilisateurs.' : 'Your memory and documents are never shared or indexed for other users.' },
            { icon: 'database', t: isFR ? 'Jamais d’entraînement' : 'Never used for training',
              b: isFR ? 'Vos données ne servent jamais à entraîner un modèle, ni pour Axial ni pour un tiers.' : 'Your data is never used to train a model, for Axial or any third party.' },
            { icon: 'cpu', t: isFR ? 'Hébergement européen' : 'European hosting',
              b: isFR ? 'Base et authentification Supabase en région UE, sur infrastructure dédiée.' : 'Supabase database and auth in an EU region, on dedicated infrastructure.' },
            { icon: 'zap', t: isFR ? 'Sources traçables' : 'Traceable sources',
              b: isFR ? 'Chaque analyse cite ses sources : rien n’est affirmé sans référence vérifiable.' : 'Every analysis cites its sources — nothing is asserted without a verifiable reference.' },
          ].map((c) => (
            <article key={c.t} className="card" style={{ padding: 24 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(121,118,247,0.10)', border: '1px solid var(--border)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: 'var(--v-soft)', marginBottom: 14 }}>
                <Icon name={c.icon} size={18} />
              </div>
              <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 6px' }}>{c.t}</h3>
              <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)', lineHeight: 1.55 }}>{c.b}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="pricing" style={{ maxWidth: 1180, margin: '40px auto 40px', padding: '0 32px' }}>
        <div style={{ textAlign: 'center', marginBottom: 48 }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>{isFR ? 'TARIFS' : 'PRICING'}</div>
          <h2 style={{ fontSize: 38, margin: 0, letterSpacing: '-0.02em', fontWeight: 700, lineHeight: 1.15 }}>
            {isFR ? 'Abonnement mensuel, ou crédits à la carte.' : 'Monthly plans, or pay-as-you-go credits.'}
          </h2>
          <p style={{ color: 'var(--fg-2)', fontSize: 15, maxWidth: 560, margin: '14px auto 0', lineHeight: 1.55 }}>
            {isFR
              ? 'Les crédits du plan se renouvellent chaque mois. Besoin ponctuel ? Packs de 50, 100 ou 200 crédits (20/40/80 €) qui ne périment pas.'
              : 'Plan credits renew every month. Need a top-up? One-off packs of 50, 100 or 200 credits (€20/40/80) that never expire.'}
          </p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 18 }}>
          {pricingPlans.map((p) => (
            <article key={p.name} className="card" style={{ padding: 24, position: 'relative', display: 'flex', flexDirection: 'column', ...(p.tag ? { borderColor: 'var(--v-soft)' } : {}) }}>
              {p.tag && <div className="mono" style={{ position: 'absolute', top: 16, right: 16, fontSize: 9.5, color: 'var(--v-soft)', letterSpacing: '0.12em', fontWeight: 700 }}>{p.tag}</div>}
              <h3 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 10px' }}>{p.name}</h3>
              <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 2 }}>
                {p.price}<span style={{ fontSize: 13, color: 'var(--fg-3)', fontWeight: 500 }}>{p.per}</span>
              </div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--v-soft)', marginBottom: 14 }}>{p.credits}</div>
              <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 18px', fontSize: 12.5, color: 'var(--fg-2)', lineHeight: 1.7, flex: 1 }}>
                {p.features.map((f, j) => <li key={j}><Icon name="check" size={12} /> {f}</li>)}
              </ul>
              {p.cta === 'contact'
                ? <a className="btn btn-secondary btn-block" style={{ textAlign: 'center' }} href="mailto:sales@axial-ia.fr">{isFR ? 'Nous contacter' : 'Contact us'}</a>
                : <button className={p.tag ? 'btn btn-primary btn-block' : 'btn btn-secondary btn-block'} onClick={onCTAStart}>{isFR ? 'Commencer' : 'Get started'}</button>}
            </article>
          ))}
        </div>
      </section>

      <section style={{ textAlign: 'center', padding: '80px 32px 100px', maxWidth: 720, margin: '0 auto' }}>
        <h2 style={{ fontSize: 36, margin: '0 0 14px', letterSpacing: '-0.02em', fontWeight: 700 }}>
          {t('landing.cta.h2')}
        </h2>
        <p style={{ color: 'var(--fg-2)', fontSize: 16, margin: '0 0 28px' }}>
          {t('landing.cta.body')}
        </p>
        <button className="btn btn-primary btn-lg" onClick={onCTAStart}>
          {t('landing.cta.btn')} <Icon name="arrow-right" size={15} />
        </button>
      </section>

      <footer style={{
        borderTop: '1px solid var(--border)',
        padding: '24px 32px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        maxWidth: 1180, margin: '0 auto',
      }}>
        <Lockup sub="Intelligence" />
        <span className="mono" style={{ color: 'var(--fg-3)', fontSize: 11 }}>
          {t('landing.footer.note')}
        </span>
        <span style={{ display: 'inline-flex', gap: 14, fontSize: 11 }}>
          <a href="/legal/cgu" style={{ color: 'var(--fg-3)' }}>CGU</a>
          <a href="/legal/confidentialite" style={{ color: 'var(--fg-3)' }}>Confidentialité</a>
          <a href="/legal/mentions" style={{ color: 'var(--fg-3)' }}>Mentions légales</a>
        </span>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, body }) {
  return (
    <article className="feature-card">
      <div style={{
        width: 36, height: 36, borderRadius: 10,
        background: 'rgba(121,118,247,0.10)',
        border: '1px solid var(--border)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--v-soft)', marginBottom: 16,
      }}>
        <Icon name={icon} size={18} />
      </div>
      <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 6px', letterSpacing: '-0.005em' }}>{title}</h3>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--fg-2)', lineHeight: 1.55 }}>{body}</p>
    </article>
  );
}

window.LandingPage = LandingPage;




/* auth.jsx */
/* auth.jsx — Sign up / Log in tabbed screen */

var { useState: useAuthState } = React;

function AuthPage({ initialMode = 'signup', onSubmit, onBack }) {
  const [mode, setMode] = useAuthState(initialMode); // 'signup' | 'login'
  const [email, setEmail] = useAuthState('');
  const [pwd, setPwd] = useAuthState('');
  const [busy, setBusy] = useAuthState(null); // null | 'email' | 'google'
  const [authErr, setAuthErr] = useAuthState(null);

  const finish = async (kind) => {
    if (busy) return;
    if (kind === 'google') {
      setAuthErr("Connexion Google bientôt disponible — utilise ton email professionnel.");
      return;
    }
    setAuthErr(null);
    setBusy(kind);
    try {
      await (onSubmit && onSubmit({ mode, email, pwd }));
    } catch (err) {
      setBusy(null);
      setAuthErr((err && err.message) ? err.message : "Une erreur est survenue.");
    }
  };

  const submit = (e) => {
    e.preventDefault();
    if (busy) return;
    finish('email');
  };

  return (
    <div className="page auth-shell">
      <div className="bg-radial" />

      <button onClick={onBack} className="btn btn-ghost"
        style={{ position: 'absolute', top: 22, left: 22 }}>
        <Icon name="arrow-left" size={14} /> Retour
      </button>

      <div className="auth-card">
        <Lockup sub="Intelligence" />

        <h1 className="auth-hook">
          {mode === 'signup'
            ? "Créez votre espace stratégique."
            : "Bon retour parmi nous."}
        </h1>
        <p className="caption" style={{ marginTop: -16, marginBottom: 22 }}>
          {mode === 'signup'
            ? "Trois minutes pour configurer votre contexte. Pas de carte bancaire."
            : "Reprenez vos analyses là où vous les avez laissées."}
        </p>

        <div className="auth-tabs" role="tablist">
          <button role="tab" aria-selected={mode === 'signup'}
            className={`auth-tab ${mode === 'signup' ? 'active' : ''}`}
            onClick={() => setMode('signup')}>Créer un compte</button>
          <button role="tab" aria-selected={mode === 'login'}
            className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
            onClick={() => setMode('login')}>Se connecter</button>
        </div>

        <button className="btn btn-secondary btn-block" type="button"
          style={{ marginBottom: 4 }}
          disabled={!!busy}
          onClick={() => finish('google')}>
          {busy === 'google'
            ? <><span className="spinner" /> Connexion en cours…</>
            : <><Icon name="google" size={18} />
                {mode === 'signup' ? "Continuer avec Google" : "Se connecter avec Google"}</>}
        </button>

        <div className="auth-divider">
          <span style={{ flex: 1, height: 1, background: 'var(--border)' }} />
          <span className="mono" style={{ color: 'var(--fg-3)', fontSize: 10, letterSpacing: '0.12em' }}>OU PAR EMAIL</span>
          <span style={{ flex: 1, height: 1, background: 'var(--border)' }} />
        </div>

        <form onSubmit={submit} className="auth-fields">
          <div>
            <label className="label">EMAIL PROFESSIONNEL</label>
            <input className="input" type="email" required
              placeholder="vous@votre-entreprise.com"
              value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <label className="label">MOT DE PASSE</label>
            <input className="input" type="password" required minLength={8}
              placeholder={mode === 'signup' ? "8 caractères minimum" : "Votre mot de passe"}
              value={pwd} onChange={(e) => setPwd(e.target.value)} />
          </div>
          {mode === 'login' && (
            <a href="#" style={{ fontSize: 12, color: 'var(--v-soft)', alignSelf: 'flex-end', marginTop: -6 }}>
              Mot de passe oublié ?
            </a>
          )}
          {authErr && (
            <p className="caption" style={{ color: 'var(--error, #f87171)', margin: '2px 0 0' }}>{authErr}</p>
          )}
          <button className="btn btn-primary btn-lg btn-block" type="submit"
            style={{ marginTop: 6 }} disabled={!!busy}>
            {busy === 'email'
              ? <><span className="spinner" /> {mode === 'signup' ? "Création du compte…" : "Connexion en cours…"}</>
              : <>{mode === 'signup' ? "Créer mon compte" : "Se connecter"}
                  <Icon name="arrow-right" size={14} /></>}
          </button>
        </form>

        <p className="auth-foot">
          {mode === 'signup' ? (
            <>En créant un compte, vous acceptez nos <a href="/legal/cgu" target="_blank" rel="noopener" style={{ color: 'var(--v-soft)' }}>Conditions</a> et notre <a href="/legal/confidentialite" target="_blank" rel="noopener" style={{ color: 'var(--v-soft)' }}>Politique de confidentialité</a>.</>
          ) : (
            <>Pas encore de compte ? <a href="#" style={{ color: 'var(--v-soft)' }}
              onClick={(e) => { e.preventDefault(); setMode('signup'); }}>Créer un compte</a></>
          )}
        </p>
      </div>
    </div>
  );
}

window.AuthPage = AuthPage;




/* onboarding.jsx */
/* onboarding.jsx — 3-step onboarding */

var { useState: useOnbState, useEffect: useOnbEffect, useMemo: useOnbMemo } = React;

const SECTORS = ['SaaS B2B', 'SaaS B2C', 'Marketplace', 'Fintech', 'Deeptech / IA', 'Industrie / Hardware', 'Services pro', 'E-commerce'];
const STAGES = ['Idéation', 'Pre-seed', 'Seed', 'Série A', 'Série B+', 'Profitable'];
const CHALLENGES = [
  'Comprendre mon marché et mes concurrents',
  'Définir ma stratégie GTM',
  'Préparer une levée de fonds',
  'Anticiper les risques réglementaires',
  'Recruter et structurer mon équipe',
];
const GEOS = ['France', 'Europe', 'États-Unis', 'Monde'];

/* ----- Step 1 ----- */
function OnbStep1({ value, onChange, onNext }) {
  const v = value || {};
  const ready = v.companyName && v.sector && v.stage && v.challenge && v.geo;
  const [prefilling, setPrefilling] = React.useState(false);
  const [prefillMsg, setPrefillMsg] = React.useState('');

  const doPrefill = async () => {
    if (!v.website || prefilling) return;
    setPrefilling(true); setPrefillMsg('');
    try {
      const d = await axPrefill(v.website);
      onChange({
        ...v,
        companyName: d.company_name || v.companyName,
        positioning: d.positioning || v.positioning,
        website: d.website || v.website,
        // Le secteur extrait est libre (ex. "SaaS RH") — on le garde tel quel
        // s'il n'y a pas déjà un chip sélectionné.
        sector: v.sector || d.sector || '',
      });
      setPrefillMsg('Pré-rempli depuis votre site — vérifiez et corrigez si besoin.');
    } catch (e) {
      setPrefillMsg((e && e.message) || 'Site injoignable — remplissez à la main.');
    }
    setPrefilling(false);
  };

  return (
    <OnbShell step={1}
      title="Parlez-nous de votre startup."
      sub="Axial calibre ses réponses sur votre entreprise — pas seulement votre secteur."
      onNext={onNext} canNext={!!ready}>
      <div className="onb-form">
        <Field label="VOTRE ENTREPRISE">
          <div style={{ display: 'grid', gap: 10 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input className="input" style={{ flex: '2 1 180px' }} value={v.companyName || ''}
                placeholder="Nom de l'entreprise *"
                onChange={(e) => onChange({ ...v, companyName: e.target.value })} />
              <input className="input" style={{ flex: '2 1 180px' }} value={v.website || ''}
                placeholder="Site web (ex. axial-ia.fr)"
                onChange={(e) => onChange({ ...v, website: e.target.value })}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); doPrefill(); } }} />
              <button type="button" className="btn btn-secondary" onClick={doPrefill}
                disabled={!v.website || prefilling} style={{ flex: '0 0 auto' }}>
                {prefilling ? 'Lecture du site…' : 'Pré-remplir depuis mon site'}
              </button>
            </div>
            <input className="input" value={v.positioning || ''}
              placeholder="Positionnement en une phrase — ex. « QKD pour sécuriser les communications de drones »"
              onChange={(e) => onChange({ ...v, positioning: e.target.value })} />
            {prefillMsg && <p className="caption" style={{ margin: 0, color: 'var(--v-soft)' }}>{prefillMsg}</p>}
          </div>
        </Field>
        <Field label="VOTRE SECTEUR">
          <ChipsRow value={v.sector} options={SECTORS} onChange={(o) => onChange({ ...v, sector: o })} />
        </Field>
        <Field label="VOTRE STADE">
          <ChipsRow value={v.stage} options={STAGES} onChange={(o) => onChange({ ...v, stage: o })} />
        </Field>
        <Field label="VOTRE PRINCIPAL DÉFI">
          <ChipsRow value={v.challenge} options={CHALLENGES} onChange={(o) => onChange({ ...v, challenge: o })} />
        </Field>
        <Field label="VOTRE MARCHÉ">
          <ChipsRow value={v.geo} options={GEOS} onChange={(o) => onChange({ ...v, geo: o })} />
        </Field>
        <Field label="PRÉCISIONS (OPTIONNEL — enrichissent la mémoire d'Axial)">
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input className="input" style={{ flex: '1 1 130px' }} value={v.foundingYear || ''}
              placeholder="Année de création" inputMode="numeric"
              onChange={(e) => onChange({ ...v, foundingYear: e.target.value.replace(/[^0-9]/g, '').slice(0, 4) })} />
            <input className="input" style={{ flex: '1 1 130px' }} value={v.teamSize || ''}
              placeholder="Taille d'équipe (ex. 4)"
              onChange={(e) => onChange({ ...v, teamSize: e.target.value })} />
            <input className="input" style={{ flex: '1 1 130px' }} value={v.country || ''}
              placeholder="Pays"
              onChange={(e) => onChange({ ...v, country: e.target.value })} />
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
            <input className="input" style={{ flex: '1 1 200px' }} value={v.clientSegment || ''}
              placeholder="Segment client (ex. DRH de PME 50-500)"
              onChange={(e) => onChange({ ...v, clientSegment: e.target.value })} />
            <input className="input" style={{ flex: '1 1 200px' }} value={v.competitors || ''}
              placeholder="Concurrents connus (séparés par des virgules)"
              onChange={(e) => onChange({ ...v, competitors: e.target.value })} />
          </div>
        </Field>
        <Field label="VOS DOCUMENTS (OPTIONNEL — pitch deck, étude, business plan)">
          <OnbDocUpload />
        </Field>
      </div>

      <div className="onb-preview-card">
        <div className="label" style={{ marginBottom: 10 }}>CE QU'AXIAL RETIENDRA</div>
        <div className="onb-preview-row">
          <span className="onb-preview-tag"><span className="dim">entreprise:</span> {v.companyName || '—'}</span>
          <span className="onb-preview-tag"><span className="dim">positionnement:</span> {(v.positioning || '—').slice(0, 60)}</span>
          <span className="onb-preview-tag"><span className="dim">sector:</span> {v.sector || '—'}</span>
          <span className="onb-preview-tag"><span className="dim">stage:</span> {v.stage || '—'}</span>
          <span className="onb-preview-tag"><span className="dim">challenge:</span> {v.challenge || '—'}</span>
          <span className="onb-preview-tag"><span className="dim">geography:</span> {v.geo || '—'}</span>
        </div>
        <p className="caption" style={{ marginTop: 14, marginBottom: 0 }}>
          Vous pourrez modifier, supprimer ou ajouter des faits depuis votre mémoire.
        </p>
      </div>
    </OnbShell>
  );
}

function OnbDocUpload() {
  const fileRef = React.useRef(null);
  const [docs, setDocs] = React.useState([]);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState('');
  const onFile = async (e) => {
    const f = e.target.files && e.target.files[0];
    e.target.value = '';
    if (!f || busy) return;
    setBusy(true); setErr('');
    try {
      const d = await axUploadDocument(f);
      setDocs((ds) => [...ds, d.filename]);
    } catch (ex) { setErr((ex && ex.message) || 'Échec de l\'import.'); }
    setBusy(false);
  };
  return (
    <div>
      <input ref={fileRef} type="file" accept=".pdf,.docx,.xlsx,.csv,.txt,.md" style={{ display: 'none' }} onChange={onFile} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <button type="button" className="btn btn-secondary" disabled={busy}
          onClick={() => fileRef.current && fileRef.current.click()}>
          <Icon name="plus" size={13} /> {busy ? 'Import…' : 'Ajouter un document'}
        </button>
        {docs.map((n) => (
          <span key={n} className="chip" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <Icon name="check" size={11} /> {n}
          </span>
        ))}
      </div>
      {err && <p className="caption" style={{ color: 'var(--error, #e5484d)', margin: '6px 0 0' }}>{err}</p>}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div style={{ marginTop: 8 }}>{children}</div>
    </div>
  );
}

function ChipsRow({ options, value, onChange }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {options.map((o) => (
        <button key={o} type="button"
          className="chip"
          onClick={() => onChange(o)}
          style={value === o ? {
            background: 'rgba(121,118,247,0.18)',
            borderColor: 'var(--border-active)',
            color: 'var(--fg)',
          } : undefined}>
          {o}
        </button>
      ))}
    </div>
  );
}

/* ----- Step 2 — Value demo ----- */
function OnbStep2({ ctx, onNext, onBack }) {
  return (
    <OnbShell step={2}
      title={`Voici à quoi ressemblera une analyse pour ${ctx.companyName || ctx.sector || 'votre startup'}.`}
      sub="Deux questions instruites en moins de trente secondes. Vous pourrez les rejouer après l'onboarding."
      onNext={onNext} onBack={onBack} canNext>
      <div className="value-cards">
        <DemoCard
          q={demo1(ctx).q}
          bullets={demo1(ctx).bullets}
          srcs={3} time="~12 s" />
        <DemoCard
          q="Quels risques réglementaires si j'intègre des modèles GenAI ?"
          bullets={[
            "EU AI Act — obligations transparence août 2025 → août 2026",
            "Doctrine CNIL durcie sur l'entraînement avec données personnelles",
            "Garanties contractuelles enterprise sur hallucinations en 2026",
          ]}
          srcs={3} time="~14 s" />
      </div>

      <div className="proof-strip">
        <span><Icon name="database" size={12} /> Sources publiques + votre contexte privé</span>
        <span style={{ opacity: 0.4 }}>·</span>
        <span><Icon name="zap" size={12} /> Réponses traçables, exportables</span>
        <span style={{ opacity: 0.4 }}>·</span>
        <span><Icon name="cpu" size={12} /> Mémoire qui apprend</span>
      </div>
    </OnbShell>
  );
}

/* Carte 1 de la démo : personnalisée avec le NOM de l'entreprise + le DÉFI choisi,
   pour montrer dès l'onboarding qu'Axial parle de VOTRE startup (pas d'un secteur). */
function demo1(ctx) {
  const who = ctx.companyName || `votre ${ctx.sector || 'startup'}`;
  const stage = ctx.stage || 'Seed';
  const c = ctx.challenge || '';
  if (c.includes('levée')) {
    return {
      q: `Comment ${who} devrait-elle préparer sa prochaine levée en ${stage} ?`,
      bullets: [
        'Métriques attendues par les fonds à ce stade — benchmarks 2026',
        'Fenêtre de tir et fonds actifs sur votre segment',
        'Narratif : positionner la traction avant le produit',
      ],
    };
  }
  if (c.includes('marché')) {
    return {
      q: `Quels concurrents directs ${who} doit-elle surveiller en ${ctx.geo || 'France'} ?`,
      bullets: [
        'Cartographie des acteurs établis vs entrants récents',
        'Levées et lancements des 12 derniers mois sur le segment',
        'Angles de différenciation encore inoccupés',
      ],
    };
  }
  if (c.includes('régle')) {
    return {
      q: `Quels risques réglementaires ${who} doit-elle anticiper en 2026 ?`,
      bullets: [
        'Cadres applicables à votre activité — échéances 2026',
        'Obligations déjà en vigueur vs à venir',
        'Coût de mise en conformité vs risque de sanction',
      ],
    };
  }
  return {
    q: `Quels sont les leviers GTM les plus pertinents pour ${who} en ${stage} ?`,
    bullets: [
      'Inbound technique sur niches verticales — payback médian 9 mois',
      'Founder-led outbound LinkedIn — taux de réponse ×3,4 sur le DACH',
      'Partenariats canal — ACV 1,8× supérieur, cycle plus long',
    ],
  };
}

function DemoCard({ q, bullets, srcs, time }) {
  return (
    <article className="value-card">
      <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--fg)' }}>
        <Icon name="message" size={14} /> {q}
      </h3>
      <ul style={{ listStyle: 'none', padding: 0, margin: '8px 0 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {bullets.map((b, i) => (
          <li key={i} style={{ display: 'flex', gap: 10, fontSize: 13.5, color: 'var(--fg-2)', lineHeight: 1.5 }}>
            <span className="mono" style={{
              color: 'var(--v-bright)',
              minWidth: 18, fontWeight: 600,
            }}>{i + 1}.</span>
            <span>{b}</span>
          </li>
        ))}
      </ul>
      <div className="mono" style={{
        display: 'flex', justifyContent: 'space-between',
        fontSize: 11, color: 'var(--fg-3)', letterSpacing: '0.06em',
        paddingTop: 12, borderTop: '1px solid var(--border)',
      }}>
        <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
          <Icon name="database" size={11} /> {srcs} SOURCES CITÉES
        </span>
        <span>{time}</span>
      </div>
    </article>
  );
}

/* ----- Step 3 — First action ----- */
function OnbStep3({ ctx, onLaunch, onBack }) {
  const seedQ = useOnbMemo(() => {
    // Question construite avec le NOM + le DÉFI + le contexte — jamais générique.
    const who = ctx.companyName || `ma startup ${ctx.sector || ''}`.trim();
    const pos = ctx.positioning ? ` (${ctx.positioning})` : '';
    const c = ctx.challenge || '';
    if (c.includes('marché')) return `Quels sont les concurrents directs de ${who}${pos} en ${ctx.geo || 'France'}, et comment se différencier ?`;
    if (c.includes('GTM')) return `Quel levier GTM ${who}${pos} devrait-elle prioriser en ${ctx.stage || 'Seed'} ?`;
    if (c.includes('levée')) return `Comment ${who}${pos} doit-elle préparer sa prochaine levée en ${ctx.stage || 'Seed'} : montant, timing, fonds à cibler ?`;
    if (c.includes('régle')) return `Quels risques réglementaires ${who}${pos} doit-elle anticiper en 2026 ?`;
    return `Quel est le risque #1 que ${who}${pos} doit instruire ce trimestre ?`;
  }, [ctx]);

  return (
    <OnbShell step={4}
      title="Prêt. Voici votre première analyse."
      sub="Lancez votre première analyse maintenant.">
      <article className="first-action-card">
        <div className="first-action-head">
          <span className="chip" style={{ background: 'rgba(121,118,247,0.10)' }}>
            <Icon name="sparkle" size={12} /> QUESTION SUGGÉRÉE
          </span>
        </div>
        <p className="first-action-q">{seedQ}</p>
        <div className="mono" style={{ display: 'flex', flexWrap: 'wrap', gap: 18, color: 'var(--fg-3)', fontSize: 11, letterSpacing: '0.06em', marginBottom: 22 }}>
          <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Icon name="cpu" size={11} /> AGENT STRATÉGIQUE</span>
          <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Icon name="database" size={11} /> SOURCES + CONTEXTE</span>
          <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Icon name="zap" size={11} /> ~30 S</span>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-primary btn-lg" onClick={() => onLaunch(seedQ)}>
            Lancer cette analyse <Icon name="arrow-right" size={14} />
          </button>
          <button className="btn btn-ghost" onClick={() => onLaunch(null)}>
            Je préfère poser ma propre question
          </button>
        </div>
      </article>

      <div className="checklist-strip">
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--success)' }}>
          <Icon name="check" size={12} /> Contexte configuré
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--v-soft)' }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--v-bright)', boxShadow: '0 0 calc(8px * var(--glow-amount)) var(--v-bright)' }} />
          Première analyse
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, opacity: 0.5 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', border: '1px solid var(--border-strong)' }} />
          Inviter un co-fondateur
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, opacity: 0.5 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', border: '1px solid var(--border-strong)' }} />
          Connecter une source privée
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, opacity: 0.5 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', border: '1px solid var(--border-strong)' }} />
          Activer un agent
        </span>
      </div>
    </OnbShell>
  );
}

/* ----- Shared shell ----- */
function OnbShell({ step, title, sub, children, onNext, onBack, canNext = true }) {
  const labels = ['Contexte', 'Démo', 'Activation', 'Première analyse'];
  return (
    <div className="page onb-shell">
      <div className="bg-radial" />

      <div className="onb-progress-bar">
        <Lockup sub="Intelligence" />
        <div className="onb-progress-track">
          <div className="onb-progress-fill" style={{ width: `${(step / 4) * 100}%` }} />
        </div>
        <span className="onb-progress-label">ÉTAPE {step} / 4 · {labels[step - 1]}</span>
      </div>

      <main className="onb-stage">
        <h1>{title}</h1>
        {sub && <p className="sub">{sub}</p>}
        {children}

        <div className="onb-foot">
          {onBack && (
            <button className="btn btn-ghost" onClick={onBack}>
              <Icon name="arrow-left" size={14} /> Retour
            </button>
          )}
          {onNext && (
            <button className="btn btn-primary btn-lg" onClick={onNext} disabled={!canNext}>
              Continuer <Icon name="arrow-right" size={14} />
            </button>
          )}
        </div>
      </main>
    </div>
  );
}

/* ----- Step 4 — Activation (carte via Stripe, essai 14 jours) ----- */
function OnbStep4({ onBack }) {
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState('');

  const start = async () => {
    if (busy) return;
    setBusy(true); setErr('');
    try {
      try { localStorage.setItem('axial_onb_card_pending', '1'); } catch (e) {}
      const r = await axSubscribe('pro', true);
      if (r && r.checkout_url) { window.location.href = r.checkout_url; return; }
      throw new Error('no url');
    } catch (e) {
      setErr("Paiement momentanément indisponible. Réessayez dans un instant.");
      setBusy(false);
    }
  };

  return (
    <OnbShell step={3} onBack={onBack}
      title="Activez votre essai."
      sub="20 crédits offerts pendant 14 jours — aucun débit aujourd'hui.">
      <article className="first-action-card">
        <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[
            ['check', "20 crédits offerts, utilisables dès maintenant"],
            ['check', "0 € débité aujourd'hui — votre carte sert uniquement à activer l'essai"],
            ['check', "Au bout de 14 jours, l'abonnement Pro démarre : 50 €/mois, 120 crédits"],
            ['check', "Email de rappel avant le premier débit · annulation en 1 clic, à tout moment"],
          ].map(([ic, txt], i) => (
            <li key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 14, color: 'var(--fg-2)', lineHeight: 1.5 }}>
              <span style={{ color: 'var(--success)', marginTop: 2 }}><Icon name={ic} size={14} /></span>
              <span>{txt}</span>
            </li>
          ))}
        </ul>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-primary btn-lg" onClick={start} disabled={busy}>
            {busy ? 'Redirection vers Stripe…' : 'Ajouter ma carte et commencer'} <Icon name="arrow-right" size={14} />
          </button>
          <span className="mono" style={{ fontSize: 11, color: 'var(--fg-3)', display: 'inline-flex', gap: 6, alignItems: 'center' }}>
            <Icon name="key" size={12} /> Paiement sécurisé par Stripe — Axial ne voit jamais votre carte.
          </span>
        </div>
        {err && <p style={{ color: 'var(--error, #e5484d)', fontSize: 13, marginTop: 14, marginBottom: 0 }}>{err}</p>}
      </article>
    </OnbShell>
  );
}

window.OnbStep1 = OnbStep1;
window.OnbStep2 = OnbStep2;
window.OnbStep3 = OnbStep3;
window.OnbStep4 = OnbStep4;




/* shell.jsx */
/* shell.jsx — sidebar (240) + topbar (56) chrome.
   Sidebar sub-routes: 'conversations' | 'reports' | 'agents' | 'memory' | 'credits' | 'settings'
*/

function AppShell({ user, conversations, activeId, onPickConv, onNewChat, onLogout, children, topbar, subRoute, onSubRoute }) {
  const t = window.useT();
  const lang = window.AXIAL_LANG || 'fr';

  const ToolBtn = ({ id, icon, label }) => (
    <li>
      <button
        className={`nav-item nav-tool ${subRoute === id ? 'active' : ''}`}
        style={{ width: '100%', textAlign: 'left' }}
        onClick={() => onSubRoute(id)}>
        <Icon name={icon} size={14} /> {label}
      </button>
    </li>
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Lockup sub="Intelligence" />

        <button className="sidebar-newconv" onClick={onNewChat}>
          <Icon name="plus" size={14} /> {t('nav.new_analysis')}
        </button>

        {/* TOOLS (first) */}
        <div>
          <div className="sidebar-section-label">{t('nav.tools')}</div>
          <ul className="nav-list" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            <ToolBtn id="conversations" icon="message-square" label={t('nav.conversations')} />
            <ToolBtn id="reports" icon="document" label={t('nav.reports')} />
            <ToolBtn id="agents" icon="cpu" label={t('nav.agents')} />
            <ToolBtn id="memory" icon="key" label={t('nav.memory')} />
            <ToolBtn id="credits" icon="zap" label={t('nav.credits')} />
            <ToolBtn id="docs" icon="book" label={t('nav.docs')} />
            <ToolBtn id="settings" icon="settings" label={t('nav.settings')} />
          </ul>
        </div>

        {/* RECENT CONVERSATIONS (below tools, only on conversations route) */}
        {subRoute === 'conversations' && (
          <div className="sidebar-recents" style={{ marginTop: 16 }}>
            <div className="sidebar-section-label">{t('nav.recent')}</div>
            <ul className="nav-list" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {conversations.map((c) => (
                <li key={c.id}>
                  <button
                    className={`nav-item conv-item ${c.id === activeId ? 'active' : ''}`}
                    onClick={() => onPickConv(c.id)}
                    style={{ width: '100%', textAlign: 'left' }}>
                    <span className="conv-item-title">{c.title}</span>
                    <span className="conv-item-meta">{lang === 'fr' ? 'IL Y A ' : ''}{c.lastUpdated.toUpperCase()}{lang === 'en' ? ' AGO' : ''}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="sidebar-foot">
          <div className="user-row" onClick={onLogout} style={{ cursor: 'pointer' }}>
            <div className="user-avatar">{user.initials}</div>
            <div className="user-meta">
              <span className="user-name">{user.name}</span>
              <span className="user-email">{user.email}</span>
            </div>
            <Icon name="logout" size={14} style={{ marginLeft: 'auto', color: 'var(--fg-3)' }} />
          </div>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          {topbar}
        </header>
        <div className={`app-body ${subRoute !== 'conversations' ? 'app-body-single' : ''}`}>
          {children}
        </div>
      </div>
    </div>
  );
}

window.AppShell = AppShell;





/* conversations.jsx */
/* conversations.jsx — empty state, thread, citations side panel, composer */

var { useState: useConvState, useEffect: useConvEffect, useRef: useConvRef, useMemo: useConvMemo } = React;

/* ============================================================
   Conversations region — combines list-panel, thread, composer
   ============================================================ */
function ConversationsRegion({
  conversations, activeId, setActiveId, onSendInActive, onSendNew, onNewChat,
  suggestedPrompts, streamingSpeed, showCitePanelFor, setShowCitePanelFor,
}) {
  const active = conversations.find((c) => c.id === activeId);

  return (
    <>
      <ConvListPanel
        conversations={conversations}
        activeId={activeId}
        onPick={setActiveId}
        onNew={onNewChat}
      />
      {active ? (
        <ConvThread
          conversation={active}
          onSend={onSendInActive}
          streamingSpeed={streamingSpeed}
          openCite={(srcId) => setShowCitePanelFor({ convId: active.id, sourceId: srcId })}
        />
      ) : (
        <EmptyConvState onSend={onSendNew} suggestedPrompts={suggestedPrompts} />
      )}
      {showCitePanelFor && (
        <CitationPanel
          conv={conversations.find((c) => c.id === showCitePanelFor.convId)}
          sourceId={showCitePanelFor.sourceId}
          onClose={() => setShowCitePanelFor(null)}
        />
      )}
    </>
  );
}

/* ============================================================
   Conversation list panel (middle column)
   ============================================================ */
function ConvListPanel({ conversations, activeId, onPick, onNew }) {
  const [q, setQ] = useConvState('');
  const filtered = conversations.filter((c) => c.title.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="conv-list-panel">
      <div className="conv-search">
        <Icon name="search" size={14} className="conv-search-icon" />
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Rechercher une analyse…" />
      </div>

      <button className="sidebar-newconv" onClick={onNew} style={{ marginBottom: 12 }}>
        <Icon name="plus" size={14} /> Nouvelle analyse
      </button>

      <div className="sidebar-section-label">RÉCENTES</div>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {filtered.map((c) => (
          <li key={c.id}>
            <button
              className={`conv-item ${c.id === activeId ? 'active' : ''}`}
              onClick={() => onPick(c.id)}
              style={{ width: '100%', textAlign: 'left', border: 'none' }}>
              <span className="conv-item-title">{c.title}</span>
              <span className="conv-item-meta">IL Y A {c.lastUpdated.toUpperCase()}</span>
            </button>
          </li>
        ))}
        {filtered.length === 0 && (
          <li className="caption" style={{ padding: '12px', color: 'var(--fg-3)' }}>
            Aucun résultat.
          </li>
        )}
      </ul>
    </div>
  );
}

/* ============================================================
   Empty state — no conversation selected
   ============================================================ */
function EmptyConvState({ onSend, suggestedPrompts }) {
  // La question suggérée de l'onboarding pré-remplit le composer (jamais
  // envoyée automatiquement — l'utilisateur garde la main).
  const [draft, setDraft] = useConvState(() => {
    try {
      const seed = localStorage.getItem('axial_seed_q');
      if (seed) { localStorage.removeItem('axial_seed_q'); return seed; }
    } catch (e) {}
    return '';
  });

  return (
    <div className="thread-region">
      <div className="empty-state">
        <div style={{
          width: 80, height: 80, borderRadius: 16,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 24,
        }}>
          <img src="data:image/png;base64,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" alt="" style={{
            width: '100%', height: '100%', objectFit: 'contain',
            filter: 'drop-shadow(0 0 calc(40px * var(--glow-amount)) var(--v-glow))',
          }} />
        </div>
        <h2 style={{ fontSize: 26, margin: '0 0 12px', letterSpacing: '-0.015em' }}>
          Quelle question stratégique aujourd'hui ?
        </h2>
        <p>
          Posez votre question en langage naturel. Axial reformule, cherche, raisonne, et cite chaque source.
        </p>

        <div className="empty-prompt-chips">
          {suggestedPrompts.map((p) => (
            <button key={p} className="prompt-chip" onClick={() => onSend(p)}>{p}</button>
          ))}
        </div>
      </div>

      <Composer value={draft} onChange={setDraft} onSend={() => {
        if (draft.trim()) { onSend(draft); setDraft(''); }
      }} />
    </div>
  );
}

/* ============================================================
   Conversation thread
   ============================================================ */
function ConvThread({ conversation, onSend, streamingSpeed, openCite }) {
  const [draft, setDraft] = useConvState('');
  const scrollRef = useConvRef(null);

  useConvEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [conversation.messages.length, conversation.id]);

  return (
    <div className="thread-region">
      <div className="thread-scroll" ref={scrollRef}>
        <div className="thread-inner">
          {conversation.messages.map((m, i) => (
            m.role === 'user'
              ? <UserMsg key={i} text={m.content} />
              : <AiMsg key={i} content={m.content} sources={m.sources || []} agent={m.agent}
                  streamingSpeed={streamingSpeed} openCite={openCite}
                  isLast={i === conversation.messages.length - 1} />
          ))}
        </div>
      </div>

      <Composer value={draft} onChange={setDraft} onSend={() => {
        if (draft.trim()) { onSend(draft); setDraft(''); }
      }} />
    </div>
  );
}

function UserMsg({ text }) {
  return (
    <div className="msg-user-wrap">
      <div className="msg-user">{text}</div>
    </div>
  );
}

// Badge affiché seulement pour les agents spécialisés — la conversation libre
// (clé "conseiller") reste une discussion simple, sans badge.
const AGENT_LABELS = { market_scanner: 'Market Scanner · PESTEL', competitor_radar: 'Competitor Radar · Porter' };

function AiMsg({ content, sources, agent, streamingSpeed, openCite, isLast }) {
  // Pending state: a real backend answer is on its way (search + RAG + LLM can
  // take 20-40s). Show a clear "thinking" indicator instead of a mute placeholder.
  if (content === '__PENDING__') {
    return (
      <div className="msg-ai-wrap">
        <div className="msg-ai-mark" />
        <div className="msg-ai">
          <span className="ax-thinking">
            <span className="dots"><i /><i /><i /></span>
            AXIAL analyse — recherche web + base de connaissance…
          </span>
        </div>
      </div>
    );
  }
  // Le backend renvoie un texte markdown avec citations [N].
  const fullText = useConvMemo(() => (content == null ? '' : String(content)), [content]);
  const [shown, setShown] = useConvState(isLast ? 0 : fullText.length);

  useConvEffect(() => {
    if (!isLast) { setShown(fullText.length); return; }
    if (streamingSpeed === 0) { setShown(fullText.length); return; }
    let cancelled = false;
    let i = 0;
    const tick = () => {
      if (cancelled) return;
      i = Math.min(fullText.length, i + Math.max(2, Math.round(streamingSpeed)));
      setShown(i);
      if (i < fullText.length) setTimeout(tick, 18);
    };
    tick();
    return () => { cancelled = true; };
  }, [fullText, isLast, streamingSpeed]);

  const shownText = fullText.slice(0, shown);
  const stillStreaming = isLast && shown < fullText.length && streamingSpeed > 0;

  return (
    <div className="msg-ai-wrap">
      <div className="msg-ai-mark"><img src="data:image/png;base64,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" alt="" style={{ width: 18, height: 18, objectFit: 'contain' }} /></div>
      <div className="msg-ai">
        {agent && AGENT_LABELS[agent] && (
          <div className="mono" style={{ fontSize: 10, letterSpacing: '0.10em', textTransform: 'uppercase', color: 'var(--v-soft)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'normal' }}>
            <Icon name="cpu" size={10} /> {AGENT_LABELS[agent]}
          </div>
        )}
        <MarkdownView text={shownText} onCite={openCite} />
        {stillStreaming && <span className="typing-cursor" />}
        {!stillStreaming && (
          <div className="msg-ai-actions">
            <button className="icon-btn" title="Utile"><Icon name="thumb-up" size={14} /></button>
            <button className="icon-btn" title="À améliorer"><Icon name="thumb-down" size={14} /></button>
            <button className="icon-btn" title="Exporter"><Icon name="download" size={14} /></button>
            <button className="icon-btn report" title="Signaler">
              <Icon name="flag" size={11} /> Signaler
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Composer
   ============================================================ */
/* Sélecteur de mode du Workspace (modèle Perplexity) : Conversation libre
   (routing par intention) ou un agent spécialisé explicite. Persisté pour que
   bridge.axChat l'envoie avec chaque message. */
const AGENT_MODES = [
  { key: 'auto', label: 'Conversation', icon: 'message' },
  { key: 'market_scanner', label: 'Market Scanner', icon: 'trending' },
  { key: 'competitor_radar', label: 'Competitor Radar', icon: 'users' },
];

function Composer({ value, onChange, onSend }) {
  const ref = useConvRef(null);
  const fileRef = useConvRef(null);
  const [uploading, setUploading] = React.useState(false);
  const [uploadMsg, setUploadMsg] = React.useState(null); // { ok, text }
  const [mode, setMode] = React.useState(() => {
    try { return localStorage.getItem('axial_agent_mode') || 'auto'; } catch (e) { return 'auto'; }
  });
  const pickMode = (k) => {
    setMode(k);
    try { localStorage.setItem('axial_agent_mode', k); } catch (e) {}
  };
  const [pendingDocs, setPendingDocs] = React.useState(() => (window.AXIAL_PENDING_DOCS || []));
  React.useEffect(() => {
    const sync = () => setPendingDocs([...(window.AXIAL_PENDING_DOCS || [])]);
    window.addEventListener('axial-pending-docs', sync);
    return () => window.removeEventListener('axial-pending-docs', sync);
  }, []);
  const onPickFile = async (e) => {
    const f = e.target.files && e.target.files[0];
    e.target.value = '';
    if (!f || uploading) return;
    setUploading(true); setUploadMsg(null);
    try {
      const d = await axUploadDocument(f);
      // Joint au PROCHAIN message envoyé (comme une pièce jointe), en plus de
      // rester durablement dans la mémoire documentaire.
      window.AXIAL_PENDING_DOCS = [...(window.AXIAL_PENDING_DOCS || []), { id: d.id, filename: d.filename }];
      window.dispatchEvent(new Event('axial-pending-docs'));
    } catch (ex) {
      setUploadMsg({ ok: false, text: (ex && ex.message) || 'Échec de l’import.' });
    }
    setUploading(false);
  };
  const removePending = (id) => {
    window.AXIAL_PENDING_DOCS = (window.AXIAL_PENDING_DOCS || []).filter((d) => d.id !== id);
    window.dispatchEvent(new Event('axial-pending-docs'));
  };
  useConvEffect(() => {
    const el = ref.current; if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(180, el.scrollHeight) + 'px';
  }, [value]);

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); }
  };

  return (
    <div className="composer-shell">
      <div className="composer">
        <input ref={fileRef} type="file" accept=".pdf,.docx,.xlsx,.csv,.txt,.md"
          style={{ display: 'none' }} onChange={onPickFile} />
        <button className="icon-btn" onClick={() => fileRef.current && fileRef.current.click()}
          disabled={uploading} aria-label="Importer un document"
          title="Importer un document (PDF, DOCX, XLSX, CSV, TXT — utilisé dans les analyses)"
          style={{ alignSelf: 'flex-end', marginBottom: 6, flexShrink: 0 }}>
          <Icon name={uploading ? 'clock' : 'plus'} size={15} />
        </button>
        <textarea
          ref={ref}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKey}
          placeholder="Posez votre question stratégique… (Maj+Entrée pour aller à la ligne)"
        />
        <button className="composer-send" onClick={onSend} disabled={!value.trim()}
          aria-label="Envoyer">
          <Icon name="arrow-up" size={16} />
        </button>
      </div>
      {pendingDocs.length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
          {pendingDocs.map((d) => (
            <span key={d.id} className="chip" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'rgba(121,118,247,0.10)', fontSize: 12 }}>
              <Icon name="database" size={11} /> {d.filename}
              <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>· joint au prochain message</span>
              <button onClick={() => removePending(d.id)} aria-label="Retirer"
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--fg-3)', padding: 0, display: 'inline-flex' }}>
                <Icon name="x" size={11} />
              </button>
            </span>
          ))}
        </div>
      )}
      {uploadMsg && !uploadMsg.ok && (
        <div style={{ fontSize: 12.5, marginTop: 6, color: 'var(--error, #e5484d)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon name="alert" size={12} /> {uploadMsg.text}
        </div>
      )}
      <div className="composer-tip" style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ display: 'inline-flex', gap: 4, padding: 3, borderRadius: 999, border: '1px solid var(--border)', background: 'var(--bg-2, rgba(255,255,255,0.03))' }}>
          {AGENT_MODES.map((m) => (
            <button key={m.key} type="button" onClick={() => pickMode(m.key)}
              title={m.key === 'auto' ? 'Discussion libre avec Axial, sans cadre imposé' : `Utiliser l'agent ${m.label}`}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 5,
                padding: '4px 10px', borderRadius: 999, border: 'none', cursor: 'pointer',
                fontSize: 11.5, fontFamily: 'var(--font-mono)', letterSpacing: '0.02em',
                background: mode === m.key ? 'rgba(121,118,247,0.18)' : 'transparent',
                color: mode === m.key ? 'var(--fg)' : 'var(--fg-3)',
              }}>
              <Icon name={m.icon} size={11} /> {m.label}
            </button>
          ))}
        </div>
        <span style={{ color: 'var(--fg-3)', fontSize: 11.5 }}>
          {mode === 'auto'
            ? 'Discussion libre — réponse rapide ou approfondie selon votre question.'
            : 'Cet agent spécialisé répondra à toutes vos questions.'}
        </span>
      </div>
    </div>
  );
}

/* ============================================================
   Citation side panel
   ============================================================ */
function CitationPanel({ conv, sourceId, onClose }) {
  // find the source across messages
  let src = null;
  for (const m of conv.messages) {
    if (m.sources) {
      const found = m.sources.find((s) => s.id === sourceId);
      if (found) { src = found; break; }
    }
  }
  if (!src) return null;

  return (
    <>
      <div className="cite-panel-backdrop" onClick={onClose} />
      <aside className="cite-panel" role="dialog">
        <div className="cite-panel-head">
          <h3>SOURCE [{src.id}]</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Fermer">
            <Icon name="x" size={16} />
          </button>
        </div>
        <div className="cite-panel-body">
          <h2>{src.title}</h2>
          <div className="cite-panel-meta">{src.source}</div>
          <div className="cite-panel-quote">{src.excerpt}</div>
          {src.link && (
            <a className="cite-panel-link" href={src.link} target="_blank" rel="noreferrer">
              <Icon name="arrow-right" size={12} /> {src.link}
            </a>
          )}
        </div>
      </aside>
    </>
  );
}

window.ConversationsRegion = ConversationsRegion;




/* surface-reports.jsx */
/* surfaces.jsx — Reports, Agents, Memory, Credits, Settings, Sharing
   All routes below /app. Uses window.useT() for i18n.
*/

var { useState: useStateS, useEffect: useEffectS, useMemo: useMemoS, useRef: useRefS } = React;

/* =================================================================
   GLOBAL TOP CONTROLS (lang + theme) — shows on every surface
   ================================================================= */
function TopControls() {
  const t = window.useT();
  const [theme, setTheme] = window.useTheme();
  const [, force] = useStateS(0);
  useEffectS(() => {
    const h = () => force((x) => x + 1);
    window.addEventListener('axial:lang', h);
    return () => window.removeEventListener('axial:lang', h);
  }, []);
  const lang = window.AXIAL_LANG || 'fr';
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <div className="lang-pill" role="group" aria-label="Language">
        <button className={lang === 'fr' ? 'active' : ''} onClick={() => window.setAxialLang('fr')}>FR</button>
        <button className={lang === 'en' ? 'active' : ''} onClick={() => window.setAxialLang('en')}>EN</button>
      </div>
      <button
        className="theme-toggle"
        onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
      >
        <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={15} />
      </button>
    </div>
  );
}

/* =================================================================
   REPORTS — Empty state composer (state 1)
   ================================================================= */
function ReportsEmpty({ onStart }) {
  const t = window.useT();
  const lang = window.AXIAL_LANG || 'fr';
  const [type, setType] = useStateS('market');
  const [depth, setDepth] = useStateS('standard');
  const [prompt, setPrompt] = useStateS(
    lang === 'fr'
      ? 'Cartographie concurrentielle du marché SIRH français : Lucca, Payfit, Cegid. Positionnement, parts, forces structurelles.'
      : 'Competitive map of the French HRIS market: Lucca, Payfit, Cegid. Positioning, share, structural forces.'
  );
  const types = window.AXIAL_SURFACES.REPORT_TYPES;
  const tpl = window.AXIAL_SURFACES.REPORT_TEMPLATES[lang];
  const sel = types.find((x) => x.id === type);
  const depthMul = { scan: 0.4, standard: 1, deep: 2 }[depth];
  const credits = Math.round(sel.estCredits * depthMul);
  const minutes = Math.round(sel.estMin * depthMul);

  return (
    <div className="surface">
      <div className="surface-head">
        <div>
          <h1>{t('reports.empty.h1')}</h1>
          <p>{t('reports.empty.lede')}</p>
        </div>
        <TopControls />
      </div>

      <div className="rep-types">
        {types.map((tp) => (
          <button
            key={tp.id}
            className={'rep-type-tile' + (type === tp.id ? ' active' : '')}
            onClick={() => setType(tp.id)}
          >
            <span className="icon-tile"><Icon name={tp.icon} size={16} /></span>
            <h4>{t(`reports.types.${tp.id}`)}</h4>
            <p>{t(`reports.types.${tp.id}_desc`)}</p>
          </button>
        ))}
      </div>

      <div className="rep-prompt-card">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={lang === 'fr'
            ? 'Décrivez la question stratégique. Plus elle est précise, plus le rapport est utile.'
            : 'Describe the strategic question. The sharper, the more useful the report.'}
        />
        <div className="rep-prompt-foot">
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>{t('reports.depth')}</span>
              <div className="rep-depth-seg">
                <button className={depth === 'scan' ? 'active' : ''} onClick={() => setDepth('scan')}>{t('reports.depth.scan')}</button>
                <button className={depth === 'standard' ? 'active' : ''} onClick={() => setDepth('standard')}>{t('reports.depth.standard')}</button>
                <button className={depth === 'deep' ? 'active' : ''} onClick={() => setDepth('deep')}>{t('reports.depth.deep')}</button>
              </div>
            </div>
            <div className="rep-estimate">
              {t('reports.estimate')} : <strong>{credits}</strong> {t('reports.cost')} · <strong>~{minutes}</strong> {t('reports.duration')}
            </div>
          </div>
          <button className="btn btn-primary" onClick={() => onStart({ type, depth, prompt })}>
            <Icon name="sparkle" size={15} /> {t('reports.start')}
          </button>
        </div>
      </div>

      <div style={{ marginTop: 22 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', letterSpacing: '0.10em', textTransform: 'uppercase', marginBottom: 10 }}>
          {t('reports.template_strip')}
        </div>
        <div className="rep-templates">
          {tpl.map((s, i) => (
            <button key={i} className="rep-template-chip" onClick={() => setPrompt(s)}>{s}</button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* =================================================================
   REPORTS — Generating (state 2)
   ================================================================= */
function ReportsGenerating({ onDone }) {
  const t = window.useT();
  const lang = window.AXIAL_LANG || 'fr';
  const [progress, setProgress] = useStateS(0);
  const [sourceCount, setSourceCount] = useStateS(0);
  const [elapsed, setElapsed] = useStateS(0);

  useEffectS(() => {
    const id = setInterval(() => {
      setProgress((p) => Math.min(p + 1.4, 100));
      setElapsed((e) => e + 1);
      setSourceCount((c) => Math.min(c + (Math.random() < 0.4 ? 1 : 0), 47));
    }, 220);
    return () => clearInterval(id);
  }, []);

  const tasks = [
    { key: 'parsed', threshold: 8 },
    { key: 'gathered', threshold: 32 },
    { key: 'cross', threshold: 50 },
    { key: 'drafting', threshold: 72 },
    { key: 'charts', threshold: 86 },
    { key: 'review', threshold: 96 },
  ];

  const head = lang === 'fr'
    ? 'Cartographie concurrentielle — SIRH France'
    : 'Competitive map — French HRIS';
  const meta = lang === 'fr'
    ? 'Brouillon · Profondeur Standard · 47 sources scannées'
    : 'Draft · Standard depth · 47 sources scanned';

  return (
    <div className="surface" style={{ paddingBottom: 32 }}>
      <div className="surface-head">
        <div>
          <h1>{t('reports.gen.title')}</h1>
          <p>{lang === 'fr' ? 'Vous pouvez quitter cette page — Axial vous notifie quand le rapport est prêt.' : 'You can leave this page — Axial will notify you when the report is ready.'}</p>
        </div>
        <TopControls />
      </div>

      <div className="rep-gen">
        <div className="rep-gen-doc">
          <h1>{head}</h1>
          <div className="doc-meta">{meta}</div>

          <h2>{lang === 'fr' ? '1. Synthèse exécutive' : '1. Executive summary'}</h2>
          <p>
            {lang === 'fr'
              ? 'Le marché français du SIRH atteint 1,8 Md€ en 2025, en croissance de 11 % vs 2024. Trois acteurs concentrent 62 % du segment > 50 employés : Lucca (24 %), Payfit (22 %), Cegid (16 %).'
              : 'The French HRIS market reaches €1.8B in 2025, up 11% vs 2024. Three players hold 62% of the >50-employee segment: Lucca (24%), Payfit (22%), Cegid (16%).'}
            <span className="gen-cursor"></span>
          </p>
          <div className="skeleton med"></div>
          <div className="skeleton"></div>
          <div className="skeleton short"></div>

          <h2>{lang === 'fr' ? '2. Cadrage de la question' : '2. Framing the question'}</h2>
          <div className="skeleton"></div>
          <div className="skeleton med"></div>
          <div className="skeleton short"></div>
          <div className="skeleton"></div>
        </div>

        <div className="rep-gen-side">
          <div className="rep-gen-progress">
            <div className="rep-gen-progress-label">
              <span>{Math.round(progress)}%</span>
              <span>{t('reports.gen.elapsed')} {Math.floor(elapsed / 5)}m {(elapsed * 12) % 60}s</span>
            </div>
            <div className="rep-gen-progress-track">
              <div className="rep-gen-progress-fill" style={{ width: progress + '%' }}></div>
            </div>
          </div>

          <div className="task-list">
            {tasks.map((tk) => {
              const done = progress >= tk.threshold;
              const active = !done && progress >= (tk.threshold - 14);
              return (
                <div key={tk.key} className={'task' + (done ? ' done' : '') + (active ? ' active' : '')}>
                  <span className="task-dot">
                    {done ? <Icon name="check" size={11} stroke={2.4} /> : (active ? <span className="spinner" style={{ width: 10, height: 10, margin: 0, borderWidth: 1.5 }} /> : null)}
                  </span>
                  <div className="task-body">
                    <div className="task-title">{t(`reports.gen.tasks.${tk.key}`)}</div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="rep-source-counter">
            <span className="num">{sourceCount}</span>
            <span className="lbl">{t('reports.gen.sources_found')}</span>
          </div>

          <button className="btn btn-secondary" onClick={onDone} style={{ marginTop: 'auto' }}>
            {lang === 'fr' ? 'Voir le brouillon' : 'View draft'} <Icon name="arrow-right" size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

/* =================================================================
   REPORTS — Editor (state 3) — three-column
   ================================================================= */
function renderInline(text, kp, onCite) {
  const nodes = [];
  const re = /\*\*(.+?)\*\*|\[(\d+(?:\]\[\d+)*)\]/g;
  let last = 0, m, i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[1] !== undefined) nodes.push(<strong key={kp + 'b' + i++}>{m[1]}</strong>);
    else {
      const firstId = parseInt(m[2], 10);
      nodes.push(
        <sup key={kp + 'c' + i++}
          onClick={onCite ? () => onCite(firstId) : undefined}
          style={{ color: 'var(--v-bright)', fontWeight: 600, marginLeft: 1,
                   cursor: onCite ? 'pointer' : 'inherit' }}>[{m[2]}]</sup>
      );
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function MarkdownView({ text, onCite }) {
  const lines = (text || '').split('\n');
  const blocks = [];
  let bullets = [];
  const flush = (k) => {
    if (bullets.length) {
      blocks.push(
        <ul key={'ul' + k} style={{ margin: '6px 0 6px 20px', display: 'flex', flexDirection: 'column', gap: 5 }}>
          {bullets.map((b, i) => <li key={i} style={{ lineHeight: 1.55 }}>{renderInline(b, 'l' + k + i, onCite)}</li>)}
        </ul>,
      );
      bullets = [];
    }
  };
  lines.forEach((raw, idx) => {
    const line = raw.replace(/\s+$/, '');
    if (!line.trim()) { flush(idx); return; }
    if (line.startsWith('### ')) { flush(idx); blocks.push(<h3 key={idx} style={{ fontSize: 15, fontWeight: 700, margin: '14px 0 6px' }}>{renderInline(line.slice(4), 'h' + idx, onCite)}</h3>); }
    else if (line.startsWith('## ')) { flush(idx); blocks.push(<h2 key={idx} style={{ fontSize: 17, fontWeight: 700, margin: '18px 0 8px' }}>{renderInline(line.slice(3), 'h' + idx, onCite)}</h2>); }
    else if (line.startsWith('# ')) { flush(idx); blocks.push(<h1 key={idx} style={{ fontSize: 20, fontWeight: 800, margin: '8px 0 10px' }}>{renderInline(line.slice(2), 'h' + idx, onCite)}</h1>); }
    else if (line.trim() === '---' || line.trim() === '***') { flush(idx); blocks.push(<hr key={idx} style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '16px 0' }} />); }
    else if (/^\s*[-*]\s+/.test(line)) { bullets.push(line.replace(/^\s*[-*]\s+/, '')); }
    else { flush(idx); blocks.push(<p key={idx} style={{ margin: '6px 0', lineHeight: 1.6 }}>{renderInline(line, 'p' + idx, onCite)}</p>); }
  });
  flush('end');
  return <div>{blocks}</div>;
}

function ReportsEditor({ data, onBack, openShare }) {
  const lang = window.AXIAL_LANG || 'fr';
  const t = window.useT();
  const [saving, setSaving] = React.useState(false);
  const [savedId, setSavedId] = React.useState(null);
  const title = (data && data.title) || (lang === 'fr' ? 'Rapport' : 'Report');
  const content = (data && data.content) || '';
  const sources = (data && data.sources) || [];

  const exportPdf = async () => {
    setSaving(true);
    try {
      let id = savedId;
      if (!id) {
        const r = await axCreateReport({ title, content, analysis_type: (data && data.analysis_type) || 'synthese_executive', sources });
        id = r.id; setSavedId(id);
      }
      await axDownloadReportPdf(id, title.slice(0, 60) + '.pdf');
    } catch (e) { /* noop */ }
    setSaving(false);
  };

  return (
    <div className="surface" style={{ paddingTop: 16, paddingBottom: 16, maxWidth: 1000 }}>
      <div className="surface-head" style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button className="btn btn-ghost btn-sm" onClick={onBack}><Icon name="arrow-left" size={14} /></button>
          <div>
            <h1 style={{ fontSize: 22 }}>{title}</h1>
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              {sources.length} sources · {lang === 'fr' ? 'Rapport Axial' : 'Axial report'}
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="btn btn-secondary btn-sm" onClick={openShare}><Icon name="share" size={14} />{t('common.share')}</button>
          <button className="btn btn-primary btn-sm" onClick={exportPdf} disabled={saving}>
            <Icon name="download" size={14} />{saving ? (lang === 'fr' ? 'Export…' : 'Exporting…') : 'PDF'}
          </button>
          <TopControls />
        </div>
      </div>

      <div className="rep-doc" style={{ fontSize: 14, maxWidth: 820 }}>
        {content ? <MarkdownView text={content} /> : (lang === 'fr' ? 'Aucun contenu.' : 'No content.')}
      </div>

      {sources.length > 0 && (
        <div style={{ marginTop: 28 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', letterSpacing: '0.10em', textTransform: 'uppercase', marginBottom: 12 }}>
            Sources
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {sources.map((s, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'baseline', fontSize: 13 }}>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--v-bright)' }}>[{i + 1}]</span>
                {s.url
                  ? <a href={s.url} target="_blank" rel="noreferrer" style={{ color: 'var(--fg)', textDecoration: 'none' }}>{s.title || s.url}</a>
                  : <span>{s.title || s.reference || ''}</span>}
                {s.domain && <span style={{ color: 'var(--fg-3)' }}>· {s.domain}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* =================================================================
   REPORTS — Quota Exceeded (state 6)
   ================================================================= */
function ReportsQuota({ onClose }) {
  const t = window.useT();
  const lang = window.AXIAL_LANG || 'fr';
  return (
    <div className="surface">
      <div className="surface-head">
        <div>
          <h1>{t('reports.quota.title')}</h1>
          <p>{t('reports.quota.body')}</p>
        </div>
        <TopControls />
      </div>
      <div className="quota-card">
        <div className="quota-usage">
          <h3>{t('reports.quota.title')}</h3>
          <p style={{ fontSize: 13.5, color: 'var(--fg-2)', lineHeight: 1.6, margin: '6px 0 0' }}>
            {t('reports.quota.body')}
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="quota-option featured">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <h3>Pro</h3>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--v-soft)', letterSpacing: '0.10em', textTransform: 'uppercase', fontWeight: 700 }}>{lang === 'fr' ? 'Recommandé' : 'Recommended'}</span>
            </div>
            <div className="price">50 €<small>/{lang === 'fr' ? 'mois' : 'mo'}</small></div>
            <ul>
              <li><Icon name="check" size={13} className="check" />120 {lang === 'fr' ? 'crédits' : 'credits'} / {lang === 'fr' ? 'mois' : 'mo'}</li>
              <li><Icon name="check" size={13} className="check" />{lang === 'fr' ? '2 agents de veille' : '2 monitoring agents'}</li>
              <li><Icon name="check" size={13} className="check" />{lang === 'fr' ? 'Templates (fundraising, ICP, GTM)' : 'Templates (fundraising, ICP, GTM)'}</li>
              <li><Icon name="check" size={13} className="check" />{lang === 'fr' ? 'Export PDF' : 'PDF export'}</li>
            </ul>
            <button className="btn btn-primary" style={{ marginTop: 4 }}>{t('reports.quota.upgrade')}</button>
          </div>

          <div className="quota-option">
            <h3>{lang === 'fr' ? 'Recharge ponctuelle' : 'One-time top-up'}</h3>
            <div className="price">20 €<small>{lang === 'fr' ? ' · 50 crédits' : ' · 50 credits'}</small></div>
            <p style={{ fontSize: 12.5, color: 'var(--fg-2)', margin: 0, lineHeight: 1.5 }}>
              {lang === 'fr' ? 'Packs ponctuels (50, 100 ou 200 crédits) qui ne périment pas.' : 'One-off packs (50, 100 or 200 credits) that never expire.'}
            </p>
            <button className="btn btn-secondary" style={{ marginTop: 4 }}>{t('reports.quota.topup')}</button>
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 18 }}>
        <button className="btn btn-ghost" onClick={onClose}>{t('common.back')}</button>
      </div>
    </div>
  );
}

window.ReportsEmpty = ReportsEmpty;
window.ReportsGenerating = ReportsGenerating;
window.ReportsEditor = ReportsEditor;
function SourceConflictModal({ onClose }) {
  const lang = window.AXIAL_LANG || 'fr';
  return (
    <div className="wizard-modal" onClick={onClose}>
      <div className="wizard-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 560 }}>
        <div className="wizard-head">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: 18, margin: 0 }}>{lang === 'fr' ? 'Conflit de sources' : 'Source conflict'}</h2>
            <button className="icon-btn" onClick={onClose}><Icon name="x" size={16} /></button>
          </div>
        </div>
        <div className="wizard-body">
          <p style={{ color: 'var(--fg-2)', fontSize: 13.5, lineHeight: 1.6 }}>
            {lang === 'fr'
              ? "Deux sources citées présentent des chiffres divergents sur ce point. Axial retient la source primaire la plus récente et signale l'écart pour que vous puissiez trancher."
              : 'Two cited sources report diverging figures here. Axial keeps the most recent primary source and flags the gap so you can decide.'}
          </p>
        </div>
        <div className="wizard-foot">
          <button className="btn btn-primary" onClick={onClose}>{lang === 'fr' ? 'Compris' : 'Got it'}</button>
        </div>
      </div>
    </div>
  );
}

window.SourceConflictModal = SourceConflictModal;
window.ReportsQuota = ReportsQuota;
window.TopControls = TopControls;




/* surface-agents.jsx */
/* surface-agents.jsx — Agents library, wizard, active session */

var { useState: useStateA, useEffect: useEffectA } = React;

const SKILL_META = {
  concurrentielle: { icon: 'users', label: 'Veille concurrentielle' },
  reglementaire: { icon: 'shield', label: 'Veille réglementaire' },
  financement: { icon: 'trending', label: 'Veille financement' },
  produit_tech: { icon: 'sparkle', label: 'Veille produit & tech' },
  marche: { icon: 'database', label: 'Veille marché' },
};
const skillMeta = (k) => SKILL_META[k] || { icon: 'search', label: k };
const watchStatusClass = (s) => (s === 'paused' ? 'paused' : s === 'active' ? 'running' : 'idle');
const fmtWhen = (iso, lang) => (iso
  ? new Date(iso).toLocaleDateString(lang === 'en' ? 'en-US' : 'fr-FR', { day: '2-digit', month: 'short' })
  : '—');

const FEED_CATEGORIES = ['concurrence', 'startup', 'financement', 'vc', 'reglementaire', 'juridique', 'produit', 'tech', 'marche', 'general'];

function FeedsManager({ onClose }) {
  const lang = window.AXIAL_LANG || 'fr';
  const [feeds, setFeeds] = React.useState(null);
  const [url, setUrl] = React.useState('');
  const [category, setCategory] = React.useState('startup');
  const [busy, setBusy] = React.useState(false);
  const load = () => axListFeeds().then(setFeeds).catch(() => setFeeds([]));
  React.useEffect(() => { load(); }, []);
  const add = async () => {
    if (!url.trim()) return;
    setBusy(true);
    try { await axAddFeed({ url: url.trim(), category }); setUrl(''); } catch (e) { /* noop */ }
    setBusy(false); load();
  };
  const del = async (id) => { try { await axDeleteFeed(id); } catch (e) { /* noop */ } load(); };

  return (
    <div className="wizard-modal" onClick={onClose}>
      <div className="wizard-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 620 }}>
        <div className="wizard-head">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: 18, margin: 0 }}>{lang === 'fr' ? 'Sources RSS' : 'RSS sources'}</h2>
            <button className="icon-btn" onClick={onClose}><Icon name="x" size={16} /></button>
          </div>
          <p style={{ color: 'var(--fg-2)', fontSize: 13, margin: '6px 0 0' }}>
            {lang === 'fr'
              ? 'Les agents combinent ces flux avec la recherche web selon leur skill (catégorie).'
              : 'Agents combine these feeds with web search by skill (category).'}
          </p>
        </div>
        <div className="wizard-body">
          <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…/feed"
              style={{ flex: 1, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--fg)', fontSize: 13, padding: '9px 11px', outline: 'none' }} />
            <select value={category} onChange={(e) => setCategory(e.target.value)}
              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--fg)', fontSize: 13, padding: '9px 8px' }}>
              {FEED_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <button className="btn btn-primary btn-sm" onClick={add} disabled={busy || !url.trim()}>
              <Icon name="plus" size={13} />{lang === 'fr' ? 'Ajouter' : 'Add'}
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 340, overflowY: 'auto' }}>
            {feeds === null && <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>…</p>}
            {feeds !== null && feeds.length === 0 && (
              <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>{lang === 'fr' ? 'Aucun flux. Ajoutez-en un.' : 'No feed yet.'}</p>
            )}
            {(feeds || []).map((f) => (
              <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 11px', background: 'var(--surface-2)', borderRadius: 8 }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--v-bright)', textTransform: 'uppercase', minWidth: 82 }}>{f.category}</span>
                <span style={{ flex: 1, minWidth: 0, fontSize: 12.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.title || f.url}</span>
                <button className="icon-btn" onClick={() => del(f.id)} title={lang === 'fr' ? 'Supprimer' : 'Delete'}><Icon name="x" size={13} /></button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ActivityHistory({ onClose }) {
  const lang = window.AXIAL_LANG || 'fr';
  const [runs, setRuns] = React.useState(null);
  React.useEffect(() => { axWatchActivity().then(setRuns).catch(() => setRuns([])); }, []);
  return (
    <div className="wizard-modal" onClick={onClose}>
      <div className="wizard-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 680 }}>
        <div className="wizard-head">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: 18, margin: 0 }}>{lang === 'fr' ? 'Historique des veilles' : 'Veille history'}</h2>
            <button className="icon-btn" onClick={onClose}><Icon name="x" size={16} /></button>
          </div>
          <p style={{ color: 'var(--fg-2)', fontSize: 13, margin: '6px 0 0' }}>
            {lang === 'fr' ? "Tous les runs de tes agents (skill + résultat), du plus récent au plus ancien." : "All your agents' runs, newest first."}
          </p>
        </div>
        <div className="wizard-body">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 440, overflowY: 'auto' }}>
            {runs === null && <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>…</p>}
            {runs !== null && runs.length === 0 && (
              <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>{lang === 'fr' ? "Aucun run pour l'instant." : 'No run yet.'}</p>
            )}
            {(runs || []).map((r) => {
              const meta = skillMeta(r.skill);
              return (
                <div key={r.id} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '10px 12px', background: 'var(--surface-2)', borderRadius: 8 }}>
                  <div className="agent-card-mark" style={{ width: 30, height: 30, flexShrink: 0 }}><Icon name={meta.icon} size={14} /></div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                      <strong style={{ fontSize: 13 }}>{r.watch_name}</strong>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--v-bright)', textTransform: 'uppercase' }}>{meta.label}</span>
                      <span style={{ fontSize: 11, color: r.had_changes ? 'var(--v-bright)' : 'var(--fg-3)' }}>
                        {r.had_changes ? '🆕' : (lang === 'fr' ? 'rien de neuf' : 'nothing new')}
                      </span>
                      <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--fg-3)' }}>
                        {new Date(r.created_at).toLocaleString(lang === 'en' ? 'en-US' : 'fr-FR')}
                      </span>
                    </div>
                    <p style={{ fontSize: 12, color: 'var(--fg-2)', margin: '4px 0 0', lineHeight: 1.5 }}>
                      {(r.delta_preview || '').replace(/[#*>`]/g, '').slice(0, 130)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function AgentsLibrary({ onCreate, onOpenSession }) {
  const t = window.useT();
  const lang = window.AXIAL_LANG || 'fr';
  const [agents, setAgents] = React.useState(null); // null = loading
  const [showFeeds, setShowFeeds] = React.useState(false);
  const [showHistory, setShowHistory] = React.useState(false);
  React.useEffect(() => {
    axListWatches().then(setAgents).catch(() => setAgents([]));
  }, []);

  return (
    <div className="surface">
      <div className="surface-head">
        <div>
          <h1>{t('agents.title')}</h1>
          <p>{t('agents.subtitle')}</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="btn btn-secondary" onClick={() => setShowHistory(true)}>
            <Icon name="clock" size={14} />{lang === 'fr' ? 'Historique' : 'History'}
          </button>
          <button className="btn btn-secondary" onClick={() => setShowFeeds(true)}>
            <Icon name="database" size={14} />{lang === 'fr' ? 'Sources RSS' : 'RSS sources'}
          </button>
          <button className="btn btn-primary" onClick={onCreate}>
            <Icon name="plus" size={14} />{t('agents.create')}
          </button>
          <TopControls />
        </div>
      </div>

      {showFeeds && <FeedsManager onClose={() => setShowFeeds(false)} />}
      {showHistory && <ActivityHistory onClose={() => setShowHistory(false)} />}

      <div className="agent-grid">
        <button className="agent-create-card" onClick={onCreate}>
          <span className="icon-tile"><Icon name="plus" size={22} /></span>
          <div style={{ fontSize: 14.5, fontWeight: 700 }}>{t('agents.create')}</div>
          <div style={{ fontSize: 12.5, color: 'var(--fg-2)', maxWidth: 220 }}>
            {lang === 'fr' ? '4 étapes : déclencheur, sources, livrable, cadence.' : '4 steps: trigger, sources, output, schedule.'}
          </div>
        </button>

        {(agents || []).map((a) => {
          const meta = skillMeta(a.skill);
          const status = watchStatusClass(a.status);
          return (
          <div key={a.id} className="agent-card" onClick={() => onOpenSession(a)}>
            <div className="agent-card-head">
              <div style={{ display: 'flex', gap: 12, flex: 1, minWidth: 0 }}>
                <div className="agent-card-mark"><Icon name={meta.icon} size={18} /></div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h3>{a.name}</h3>
                </div>
              </div>
              <span className={'agent-status ' + status}>
                {status === 'running' && <span className="dot"></span>}
                {t('agents.status.' + status)}
              </span>
            </div>
            <p className="desc">{a.query}</p>
            <div className="agent-meta">
              <span className="item"><Icon name="search" size={11} />{meta.label}</span>
              <span className="item"><Icon name="clock" size={11} />{a.cadence}</span>
              <span className="item"><Icon name="check" size={11} />{lang === 'fr' ? 'Dernier' : 'Last'}: {fmtWhen(a.last_run_at, lang)}</span>
            </div>
          </div>
          );
        })}
        {agents !== null && agents.length === 0 && (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', color: 'var(--fg-3)', padding: 20, fontSize: 13.5 }}>
            {lang === 'fr' ? 'Aucun agent de veille pour l\'instant.' : 'No veille agent yet.'}
          </div>
        )}
      </div>
    </div>
  );
}

function AgentWizard({ onClose, onCreate }) {
  const t = window.useT();
  const lang = window.AXIAL_LANG || 'fr';
  const [step, setStep] = useStateA(0);
  const [skill, setSkill] = useStateA('concurrentielle');
  const [subject, setSubject] = useStateA('');
  const [output, setOutput] = useStateA('digest');
  const [email, setEmail] = useStateA('');
  const [name, setName] = useStateA(lang === 'fr' ? 'Veille concurrentielle' : 'Competitive watch');
  const [cadence, setCadence] = useStateA('daily');
  const [busy, setBusy] = useStateA(false);

  // Wizard cadence → backend cadence (daily | weekly | manual).
  const cadenceMap = { hourly: 'daily', daily: 'daily', weekly: 'weekly', realtime: 'daily', manual: 'manual' };

  const steps = [
    { key: 'skill', label: lang === 'fr' ? 'Sujet & skill' : 'Subject & skill' },
    { key: 'sources', label: t('agents.wizard.sources') },
    { key: 'output', label: t('agents.wizard.output') },
    { key: 'schedule', label: t('agents.wizard.schedule') },
  ];

  return (
    <div className="wizard-modal" onClick={onClose}>
      <div className="wizard-card" onClick={(e) => e.stopPropagation()}>
        <div className="wizard-head">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: 18, margin: 0 }}>{t('agents.create')}</h2>
            <button className="icon-btn" onClick={onClose}><Icon name="x" size={16} /></button>
          </div>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ width: '100%', background: 'transparent', border: 0, color: 'var(--fg)', fontSize: 15, fontWeight: 600, padding: '8px 0', outline: 'none' }}
            placeholder={lang === 'fr' ? 'Nom de l\'agent' : 'Agent name'}
          />
          <div className="wizard-steps">
            {steps.map((s, i) => (
              <div key={s.key} className={'wizard-step ' + (i === step ? 'active' : i < step ? 'done' : '')}></div>
            ))}
          </div>
        </div>

        <div className="wizard-body">
          <div className="wizard-step-label">{lang === 'fr' ? 'Étape' : 'Step'} {step + 1} / 4 — {steps[step].label}</div>

          {step === 0 && (
            <>
              <p style={{ color: 'var(--fg-2)', fontSize: 13.5, margin: '0 0 8px' }}>
                {lang === 'fr' ? 'Quel sujet surveiller ?' : 'What subject to monitor?'}
              </p>
              <textarea
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder={lang === 'fr'
                  ? 'Ex : marché SIRH France (Payfit, Lucca, Cegid) — positionnement, levées, pricing'
                  : 'e.g. French HRIS market (Payfit, Lucca, Cegid) — positioning, funding, pricing'}
                style={{ width: '100%', minHeight: 68, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--fg)', fontSize: 13.5, padding: 12, outline: 'none', resize: 'vertical', marginBottom: 16 }}
              />
              <p style={{ color: 'var(--fg-2)', fontSize: 13.5, margin: '0 0 8px' }}>
                {lang === 'fr' ? 'Quel type de veille (skill) ?' : 'Which veille skill?'}
              </p>
              <div className="choice-grid">
                {[
                  { id: 'concurrentielle', t: lang === 'fr' ? 'Concurrentielle' : 'Competitive', d: lang === 'fr' ? 'Levées, lancements, pricing, recrutements.' : 'Funding, launches, pricing, hiring.' },
                  { id: 'reglementaire', t: lang === 'fr' ? 'Réglementaire' : 'Regulatory', d: lang === 'fr' ? 'Lois, normes, conformité du secteur.' : 'Laws, standards, compliance.' },
                  { id: 'financement', t: lang === 'fr' ? 'Financement' : 'Funding', d: lang === 'fr' ? 'Levées, valorisations, investisseurs.' : 'Rounds, valuations, investors.' },
                  { id: 'produit_tech', t: lang === 'fr' ? 'Produit & tech' : 'Product & tech', d: lang === 'fr' ? 'Innovations, tendances, signaux d\'usage.' : 'Innovations, trends, usage signals.' },
                  { id: 'marche', t: lang === 'fr' ? 'Marché' : 'Market', d: lang === 'fr' ? 'Taille, dynamique, macro, demande.' : 'Size, dynamics, macro, demand.' },
                ].map((c) => (
                  <button key={c.id} className={'choice-tile' + (skill === c.id ? ' selected' : '')} onClick={() => setSkill(c.id)}>
                    <h4>{c.t}</h4><p>{c.d}</p>
                  </button>
                ))}
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <p style={{ color: 'var(--fg-2)', fontSize: 13.5, margin: '0 0 8px' }}>
                {lang === 'fr' ? 'Quelles sources l\'agent doit-il surveiller ?' : 'Which sources should the agent watch?'}
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[
                  { id: 'web', n: lang === 'fr' ? 'Web public' : 'Public web', m: lang === 'fr' ? '142 sources sectorielles, 28 régulateurs' : '142 sector sources, 28 regulators' },
                  { id: 'pr', n: lang === 'fr' ? 'Communiqués de presse' : 'Press releases', m: lang === 'fr' ? 'Wires : Reuters, PR Newswire, AFP' : 'Wires: Reuters, PR Newswire, AFP' },
                  { id: 'linkedin', n: 'LinkedIn', m: lang === 'fr' ? 'Publications + mouvements' : 'Posts + people moves' },
                  { id: 'gdrive', n: 'Google Drive', m: lang === 'fr' ? 'Connecté · 1 248 documents' : 'Connected · 1,248 documents' },
                ].map((s, i) => (
                  <label key={s.id} className="choice-tile" style={{ flexDirection: 'row', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
                    <input type="checkbox" defaultChecked={i < 2} style={{ accentColor: 'var(--v-bright)' }} />
                    <div>
                      <h4 style={{ marginBottom: 2 }}>{s.n}</h4>
                      <p>{s.m}</p>
                    </div>
                  </label>
                ))}
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <p style={{ color: 'var(--fg-2)', fontSize: 13.5, margin: '0 0 8px' }}>
                {lang === 'fr' ? 'Quel livrable Axial doit-il produire ?' : 'What should Axial deliver?'}
              </p>
              <div className="choice-grid">
                {[
                  { id: 'digest', t: lang === 'fr' ? 'Digest quotidien' : 'Daily digest', d: lang === 'fr' ? 'Email résumé + lien rapport.' : 'Email summary + report link.' },
                  { id: 'alert', t: lang === 'fr' ? 'Alerte signalée' : 'Triggered alert', d: lang === 'fr' ? 'Notification immédiate + carte trouvaille.' : 'Immediate notification + finding card.' },
                  { id: 'report', t: lang === 'fr' ? 'Mini-rapport' : 'Mini-report', d: lang === 'fr' ? 'Document structuré récurrent.' : 'Recurring structured document.' },
                  { id: 'feed', t: lang === 'fr' ? 'Flux continu' : 'Continuous stream', d: lang === 'fr' ? 'Trouvailles dans le panneau Agent.' : 'Findings inside the Agent pane.' },
                ].map((c) => (
                  <button key={c.id} className={'choice-tile' + (output === c.id ? ' selected' : '')} onClick={() => setOutput(c.id)}>
                    <h4>{c.t}</h4><p>{c.d}</p>
                  </button>
                ))}
              </div>
              <p style={{ color: 'var(--fg-2)', fontSize: 13.5, margin: '16px 0 8px' }}>
                {lang === 'fr' ? 'Recevoir la veille par email (optionnel)' : 'Receive the digest by email (optional)'}
              </p>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={lang === 'fr' ? 'vous@entreprise.com' : 'you@company.com'}
                style={{ width: '100%', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--fg)', fontSize: 13.5, padding: '10px 12px', outline: 'none' }}
              />
            </>
          )}

          {step === 3 && (
            <>
              <p style={{ color: 'var(--fg-2)', fontSize: 13.5, margin: '0 0 8px' }}>
                {lang === 'fr' ? 'À quelle fréquence ?' : 'At what frequency?'}
              </p>
              <div className="choice-grid">
                {[
                  { id: 'hourly', t: lang === 'fr' ? 'Toutes les heures' : 'Every hour', d: lang === 'fr' ? 'Coût : élevé.' : 'Cost: high.' },
                  { id: 'daily', t: lang === 'fr' ? 'Quotidien' : 'Daily', d: lang === 'fr' ? 'Compromis recommandé.' : 'Recommended trade-off.' },
                  { id: 'weekly', t: lang === 'fr' ? 'Hebdomadaire' : 'Weekly', d: lang === 'fr' ? 'Coût bas, latence haute.' : 'Low cost, high latency.' },
                  { id: 'realtime', t: lang === 'fr' ? 'Temps réel' : 'Real-time', d: lang === 'fr' ? 'Pour signaux critiques uniquement.' : 'For critical signals only.' },
                ].map((c) => (
                  <button key={c.id} className={'choice-tile' + (cadence === c.id ? ' selected' : '')} onClick={() => setCadence(c.id)}>
                    <h4>{c.t}</h4><p>{c.d}</p>
                  </button>
                ))}
              </div>
              <div style={{ marginTop: 16, padding: 14, background: 'var(--surface-2)', borderRadius: 10, fontSize: 12.5, color: 'var(--fg-2)', lineHeight: 1.55 }}>
                {lang === 'fr' ? <>Estimation : <strong style={{ color: 'var(--fg)' }}>~210 crédits / mois</strong> à cette cadence.</> : <>Estimate: <strong style={{ color: 'var(--fg)' }}>~210 credits / month</strong> at this cadence.</>}
              </div>
            </>
          )}
        </div>

        <div className="wizard-foot">
          <button className="btn btn-ghost" onClick={() => step === 0 ? onClose() : setStep(step - 1)}>
            {step === 0 ? t('common.cancel') : t('common.back')}
          </button>
          <button className="btn btn-primary" disabled={busy || (step === 0 && !subject.trim())}
            onClick={() => {
              if (step !== 3) { setStep(step + 1); return; }
              setBusy(true);
              onCreate({ name, query: subject, skill, cadence: cadenceMap[cadence] || 'weekly',
                         email_recipients: email.trim() ? [email.trim()] : null });
            }}>
            {step === 3 ? (busy ? (lang === 'fr' ? 'Création…' : 'Creating…') : t('agents.create')) : t('common.continue')} <Icon name="arrow-right" size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

function AgentSession({ agent, onBack }) {
  const t = window.useT();
  const lang = window.AXIAL_LANG || 'fr';
  const meta = skillMeta(agent.skill);
  const [status, setStatus] = React.useState(agent.status);
  const [runs, setRuns] = React.useState(null); // null = loading
  const [busy, setBusy] = React.useState(false);
  const [openRunId, setOpenRunId] = React.useState(null);

  const loadRuns = React.useCallback(() => {
    axWatchRuns(agent.id).then(setRuns).catch(() => setRuns([]));
  }, [agent.id]);
  React.useEffect(() => { loadRuns(); }, [loadRuns]);

  const runNow = async () => {
    setBusy(true);
    try { await axRunWatch(agent.id); } catch (e) { /* noop */ }
    setBusy(false);
    loadRuns();
  };
  const toggle = async () => {
    try {
      const w = status === 'active' ? await axPauseWatch(agent.id) : await axResumeWatch(agent.id);
      setStatus(w.status);
    } catch (e) { /* noop */ }
  };

  const statusCls = watchStatusClass(status);
  const latest = runs && runs.length ? runs[0] : null;
  const shown = (openRunId && runs) ? runs.find((r) => r.id === openRunId) : latest;

  return (
    <div className="surface" style={{ paddingTop: 20, paddingBottom: 16, maxWidth: 1480 }}>
      <div className="surface-head" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
          <button className="btn btn-ghost btn-sm" onClick={onBack}><Icon name="arrow-left" size={14} /></button>
          <div className="agent-card-mark"><Icon name={meta.icon} size={20} /></div>
          <div>
            <h1 style={{ fontSize: 22, marginBottom: 4 }}>{agent.name}</h1>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <span className={'agent-status ' + statusCls}>
                {statusCls === 'running' && <span className="dot"></span>}
                {t('agents.status.' + statusCls)}
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', letterSpacing: '0.04em' }}>
                {meta.label} · {agent.cadence} · {t('agents.next_run')}: {fmtWhen(agent.next_run_at, lang)}
              </span>
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button className="btn btn-primary btn-sm" onClick={runNow} disabled={busy}>
            <Icon name="play" size={13} />
            {busy ? (lang === 'fr' ? 'Analyse…' : 'Running…') : (lang === 'fr' ? 'Lancer maintenant' : 'Run now')}
          </button>
          <button className="btn btn-secondary btn-sm" onClick={toggle}>
            <Icon name={status === 'active' ? 'pause' : 'play'} size={13} />
            {status === 'active' ? 'Pause' : (lang === 'fr' ? 'Reprendre' : 'Resume')}
          </button>
          <TopControls />
        </div>
      </div>

      <div className="agent-session">
        <div className="agent-timeline">
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', letterSpacing: '0.10em', textTransform: 'uppercase', marginBottom: 18 }}>
            {t('agents.session.timeline')}
          </div>
          {runs === null && <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>{lang === 'fr' ? 'Chargement…' : 'Loading…'}</p>}
          {runs !== null && runs.length === 0 && (
            <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>
              {lang === 'fr' ? 'Aucun run pour l\'instant. Lancez l\'agent.' : 'No run yet. Launch the agent.'}
            </p>
          )}
          {(runs || []).map((r) => (
            <div key={r.id} className={'timeline-event' + (r.had_changes ? '' : ' muted')}
                 style={{ cursor: 'pointer', outline: r.id === (shown && shown.id) ? '1px solid var(--v-bright)' : 'none' }}
                 onClick={() => setOpenRunId(r.id)}>
              <span className="timeline-event-dot"></span>
              <div className="timeline-event-time">{new Date(r.created_at).toLocaleString(lang === 'en' ? 'en-US' : 'fr-FR')}</div>
              <h4>{r.had_changes ? (lang === 'fr' ? '🆕 Nouveautés' : '🆕 New signals') : (lang === 'fr' ? 'Rien de neuf' : 'Nothing new')}</h4>
              <p>{(r.delta_content || '').replace(/[#*>`]/g, '').slice(0, 140)}</p>
            </div>
          ))}
        </div>

        <div className="findings-stream">
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', letterSpacing: '0.10em', textTransform: 'uppercase' }}>
            {shown ? (lang === 'fr' ? 'Détail du run' : 'Run detail') : t('agents.session.findings')}
          </div>
          {shown ? (
            <>
              <div className="finding-card">
                <div className="finding-card-head">
                  <h4>{lang === 'fr' ? '🆕 Nouveautés (delta)' : '🆕 New signals (delta)'}</h4>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)' }}>
                    {new Date(shown.created_at).toLocaleDateString(lang === 'en' ? 'en-US' : 'fr-FR')}
                  </span>
                </div>
                <div style={{ fontSize: 13.5 }}>{shown.delta_content ? <MarkdownView text={shown.delta_content} /> : '—'}</div>
              </div>
              <div className="finding-card">
                <div className="finding-card-head"><h4>{lang === 'fr' ? '📊 Rapport complet' : '📊 Full report'}</h4></div>
                <div style={{ fontSize: 13.5 }}>{shown.full_content ? <MarkdownView text={shown.full_content} /> : '—'}</div>
              </div>
            </>
          ) : (
            <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>
              {lang === 'fr' ? 'Lancez l\'agent pour voir sa première veille.' : 'Run the agent to see its first digest.'}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

window.AgentsLibrary = AgentsLibrary;
window.AgentWizard = AgentWizard;
window.AgentSession = AgentSession;




/* surface-misc.jsx */
/* surface-misc.jsx — Memory, Credits, Settings, Sharing */

var { useState: useStateM } = React;

/* =================================================================
   MEMORY — Axial's Key
   ================================================================= */
function DocumentsPanel() {
  const lang = window.AXIAL_LANG || 'fr';
  const [docs, setDocs] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState('');
  const fileRef = React.useRef(null);
  const load = () => axListDocuments().then(setDocs).catch(() => setDocs([]));
  React.useEffect(() => { load(); }, []);
  const onFile = async (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    setBusy(true); setErr('');
    try { await axUploadDocument(f); } catch (ex) { setErr((ex && ex.message) || 'Échec upload'); }
    setBusy(false);
    if (fileRef.current) fileRef.current.value = '';
    load();
  };
  const del = async (id) => { try { await axDeleteDocument(id); } catch (e) { /* noop */ } load(); };
  const fmtSize = (b) => (b > 1e6 ? (b / 1e6).toFixed(1) + ' Mo' : Math.max(1, Math.round(b / 1024)) + ' Ko');
  return (
    <div style={{ maxWidth: 720, marginTop: 34 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, gap: 12 }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', letterSpacing: '0.10em', textTransform: 'uppercase' }}>
          {lang === 'fr' ? 'Tes documents (utilisés dans les analyses)' : 'Your documents (used in analyses)'}
        </div>
        <button className="btn btn-secondary btn-sm" onClick={() => fileRef.current && fileRef.current.click()} disabled={busy}>
          <Icon name="plus" size={13} />{busy ? (lang === 'fr' ? 'Envoi…' : 'Uploading…') : (lang === 'fr' ? 'Ajouter' : 'Add')}
        </button>
        <input ref={fileRef} type="file" accept=".pdf,.docx,.xlsx,.csv,.txt,.md" style={{ display: 'none' }} onChange={onFile} />
      </div>
      {err && <p style={{ color: 'var(--error, #e5484d)', fontSize: 12.5, marginBottom: 10 }}>{err}</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {docs === null && <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>…</p>}
        {docs !== null && docs.length === 0 && (
          <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>{lang === 'fr' ? 'Ajoutez vos documents pour enrichir le contexte d’Axial et obtenir des analyses plus personnalisées. Pitch deck, étude de marché, business plan… (PDF, DOCX, XLSX, CSV, TXT — 20 Mo max, PDF scannés lus par OCR)' : 'Add documents to enrich Axial’s context and get more personalized analyses. Pitch deck, market study, business plan… (PDF, DOCX, XLSX, CSV, TXT — 20 MB max, scanned PDFs read via OCR)'}</p>
        )}
        {(docs || []).map((d) => (
          <div key={d.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', background: 'var(--surface-2)', borderRadius: 8 }}>
            <Icon name="database" size={14} style={{ color: 'var(--v-bright)', flexShrink: 0 }} />
            <span style={{ flex: 1, minWidth: 0, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.filename}</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--fg-3)', flexShrink: 0 }}>{d.chunk_count} chunks · {fmtSize(d.size_bytes)}</span>
            <button className="icon-btn" onClick={() => del(d.id)} title={lang === 'fr' ? 'Supprimer' : 'Delete'}><Icon name="x" size={13} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}

function MemorySurface() {
  const t = window.useT();
  const lang = window.AXIAL_LANG || 'fr';
  const FIELDS = [
    { k: 'company_name', l: lang === 'fr' ? 'Entreprise' : 'Company' },
    { k: 'website', l: lang === 'fr' ? 'Site web' : 'Website' },
    { k: 'sector', l: lang === 'fr' ? 'Secteur' : 'Sector' },
    { k: 'positioning', l: lang === 'fr' ? 'Positionnement' : 'Positioning' },
    { k: 'founding_year', l: lang === 'fr' ? 'Année de création' : 'Founding year', num: true },
    { k: 'funding_stage', l: lang === 'fr' ? 'Stade de financement' : 'Funding stage' },
    { k: 'team_size', l: lang === 'fr' ? "Taille d'équipe" : 'Team size' },
    { k: 'country', l: lang === 'fr' ? 'Pays' : 'Country' },
    { k: 'target_market', l: lang === 'fr' ? 'Marché cible' : 'Target market' },
    { k: 'client_segment', l: lang === 'fr' ? 'Segment client' : 'Client segment' },
    { k: 'known_competitors', l: lang === 'fr' ? 'Concurrents connus' : 'Known competitors' },
    { k: 'main_challenge', l: lang === 'fr' ? 'Défi principal' : 'Main challenge' },
  ];
  const [profile, setProfile] = React.useState(null);
  const [saving, setSaving] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  React.useEffect(() => { axGetProfile().then((p) => setProfile(p || {})).catch(() => setProfile({})); }, []);
  const set = (k, v) => { setProfile((p) => ({ ...p, [k]: v })); setSaved(false); };
  const save = async () => {
    setSaving(true);
    try {
      const body = {};
      FIELDS.forEach(({ k, num }) => {
        let v = profile[k];
        if (v === '' || v === undefined) v = null;
        if (num && v != null) v = parseInt(v, 10) || null;
        body[k] = v;
      });
      await axSaveProfile(body);
      setSaved(true);
    } catch (e) { /* noop */ }
    setSaving(false);
  };
  return (
    <div className="surface">
      <div className="surface-head">
        <div>
          <h1>{t('memory.title')}</h1>
          <p>{lang === 'fr' ? "Ce qu'Axial sait de ton entreprise — injecté dans chaque analyse." : 'What Axial knows about your company — injected into every analysis.'}</p>
        </div>
        <TopControls />
      </div>
      <div className="memory-hero">
        <div className="memory-hero-icon"><Icon name="key" size={20} /></div>
        <p><strong>{lang === 'fr' ? 'Privé.' : 'Private.'}</strong> {t('memory.privacy')}</p>
      </div>
      {profile === null ? (
        <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>…</p>
      ) : (
        <div style={{ maxWidth: 720 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            {FIELDS.map(({ k, l, num }) => (
              <div key={k} style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <label style={{ fontSize: 11, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--fg-3)' }}>{l}</label>
                <input value={profile[k] == null ? '' : profile[k]} onChange={(e) => set(k, e.target.value)} type={num ? 'number' : 'text'}
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--fg)', fontSize: 13.5, padding: '9px 11px', outline: 'none' }} />
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 18 }}>
            <button className="btn btn-primary" onClick={save} disabled={saving}>
              <Icon name="check" size={14} />{saving ? (lang === 'fr' ? 'Enregistrement…' : 'Saving…') : (lang === 'fr' ? 'Enregistrer' : 'Save')}
            </button>
            {saved && <span style={{ color: 'var(--v-bright)', fontSize: 13 }}>✓ {lang === 'fr' ? 'Enregistré' : 'Saved'}</span>}
          </div>
        </div>
      )}
      <DocumentsPanel />
    </div>
  );
}

/* =================================================================
   CREDITS
   ================================================================= */
function CreditsSurface() {
  const t = window.useT();
  const lang = window.AXIAL_LANG || 'fr';
  const [bal, setBal] = React.useState(null);
  const [packs, setPacks] = React.useState([]);
  const [plans, setPlans] = React.useState([]);
  const [busy, setBusy] = React.useState('');
  const [err, setErr] = React.useState('');
  const [sub, setSub] = React.useState(null);
  React.useEffect(() => {
    axBalance().then(setBal).catch(() => {});
    axSubscription().then(setSub).catch(() => {});
    axPlans().then((d) => {
      setPacks(Object.entries(d.packs || {}).map(([k, p]) => ({ key: k, ...p })));
      setPlans(d.plans || []);
    }).catch(() => {});
  }, []);
  const openPortal = async () => {
    try { const r = await axPortal(); if (r.portal_url) window.location.href = r.portal_url; }
    catch (e) { setErr((e && e.message) || 'Portail indisponible.'); }
  };
  const SUB_STATUS = {
    trialing: lang === 'fr' ? 'Essai en cours' : 'Trial',
    active: lang === 'fr' ? 'Actif' : 'Active',
    past_due: lang === 'fr' ? 'Paiement en retard' : 'Past due',
    canceled: lang === 'fr' ? 'Annulé' : 'Canceled',
  };
  const fmtDate = (iso) => iso ? new Date(iso).toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB', { day: 'numeric', month: 'long', year: 'numeric' }) : null;
  const go = async (fn, id) => {
    setBusy(id); setErr('');
    try {
      const r = await fn();
      if (r && r.checkout_url) window.location.href = r.checkout_url;
      else throw new Error('no url');
    } catch (e) {
      setErr(lang === 'fr' ? 'Paiement indisponible (vérifie la config Stripe).' : 'Payment unavailable (check Stripe config).');
    }
    setBusy('');
  };
  const buy = (key) => go(() => axCheckout(key), 'pack-' + key);
  const subscribe = (key) => go(() => axSubscribe(key), 'plan-' + key);
  const paidPlans = plans.filter((p) => p.key !== 'free_beta');
  return (
    <div className="surface">
      <div className="surface-head">
        <div>
          <h1>{t('credits.title')}</h1>
          <p>{lang === 'fr' ? "Ton solde, ton abonnement et l'achat de crédits." : 'Your balance, subscription and credit purchases.'}</p>
        </div>
        <TopControls />
      </div>

      <div className="credits-summary" style={{ marginBottom: 26 }}>
        <div className="credits-stat"><div className="lbl">{lang === 'fr' ? 'Disponible' : 'Available'}</div><div className="val">{bal ? bal.available.toLocaleString(lang) : '—'}</div></div>
        <div className="credits-stat"><div className="lbl">{lang === 'fr' ? 'Achetés' : 'Purchased'}</div><div className="val">{bal ? (bal.purchased_credits || 0).toLocaleString(lang) : '—'}</div></div>
        <div className="credits-stat"><div className="lbl">{lang === 'fr' ? 'Essai' : 'Trial'}</div><div className="val">{bal ? (bal.trial_credits || 0).toLocaleString(lang) : '—'}</div></div>
      </div>

      {sub && sub.active && (
        <div className="plan-card" style={{ maxWidth: 760, marginBottom: 26, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--v-soft)', letterSpacing: '0.10em', textTransform: 'uppercase', marginBottom: 6 }}>
              {lang === 'fr' ? 'Mon abonnement' : 'My subscription'}
            </div>
            <div style={{ fontSize: 17, fontWeight: 700 }}>
              {sub.plan_name || sub.plan} · {sub.price_eur} €/{lang === 'fr' ? 'mois' : 'mo'}
              <span style={{ marginLeft: 10, fontSize: 11.5, fontFamily: 'var(--font-mono)', color: sub.status === 'past_due' ? 'var(--error, #e5484d)' : 'var(--success)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {SUB_STATUS[sub.status] || sub.status}
              </span>
            </div>
            <p style={{ fontSize: 12.5, color: 'var(--fg-2)', margin: '6px 0 0' }}>
              {sub.monthly_credits} {lang === 'fr' ? 'crédits/mois' : 'credits/mo'}
              {sub.current_period_end && (sub.cancel_at_period_end
                ? (lang === 'fr' ? ` · prend fin le ${fmtDate(sub.current_period_end)}` : ` · ends on ${fmtDate(sub.current_period_end)}`)
                : (lang === 'fr' ? ` · prochain prélèvement le ${fmtDate(sub.current_period_end)}` : ` · next debit on ${fmtDate(sub.current_period_end)}`))}
            </p>
          </div>
          <button className="btn btn-secondary" onClick={openPortal}>
            {lang === 'fr' ? "Gérer l'abonnement" : 'Manage subscription'}
          </button>
        </div>
      )}

      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', letterSpacing: '0.10em', textTransform: 'uppercase', marginBottom: 12 }}>
        {lang === 'fr' ? 'Abonnements (mensuel)' : 'Subscriptions (monthly)'}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))', gap: 14, maxWidth: 760, marginBottom: 30 }}>
        {paidPlans.map((p) => (
          <div key={p.key} className="plan-card">
            <span className="plan-tag">{p.name}</span>
            {p.price_eur != null
              ? <div className="price">{p.price_eur} €<small>/{lang === 'fr' ? 'mois' : 'mo'}</small></div>
              : <div className="price">{lang === 'fr' ? 'Sur devis' : 'Custom'}</div>}
            <p style={{ fontSize: 12.5, color: 'var(--fg-2)', margin: '8px 0 4px', lineHeight: 1.5 }}>
              {p.monthly_credits ? `${p.monthly_credits} ${lang === 'fr' ? 'crédits/mois' : 'credits/mo'} · ${p.seats} ${lang === 'fr' ? 'siège(s)' : 'seat(s)'}` : (lang === 'fr' ? 'Multi-startups, équipe' : 'Multi-startup, team')}
            </p>
            <ul style={{ margin: '6px 0 12px 16px', padding: 0, fontSize: 12, color: 'var(--fg-2)', lineHeight: 1.5 }}>
              {(p.features || []).slice(0, 3).map((f, i) => <li key={i}>{f}</li>)}
            </ul>
            {p.price_eur != null
              ? <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => subscribe(p.key)} disabled={busy === 'plan-' + p.key}>
                  {busy === 'plan-' + p.key ? '…' : (lang === 'fr' ? "S'abonner" : 'Subscribe')}
                </button>
              : <a className="btn btn-secondary" style={{ width: '100%', textAlign: 'center' }} href="mailto:sales@axial-ia.fr">{lang === 'fr' ? 'Nous contacter' : 'Contact us'}</a>}
          </div>
        ))}
      </div>

      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', letterSpacing: '0.10em', textTransform: 'uppercase', marginBottom: 12 }}>
        {lang === 'fr' ? 'Recharge ponctuelle (pay-as-you-go)' : 'One-off top-up (pay-as-you-go)'}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: 14, maxWidth: 760 }}>
        {packs.map((p) => (
          <div key={p.key} className="plan-card">
            <h3 style={{ marginBottom: 6 }}>{p.label}</h3>
            <div className="price">{(p.amount_cents / 100).toFixed(0)} €<small> · {p.credits} {lang === 'fr' ? 'crédits' : 'credits'}</small></div>
            <button className="btn btn-primary" style={{ width: '100%', marginTop: 14 }} onClick={() => buy(p.key)} disabled={busy === 'pack-' + p.key}>
              <Icon name="sparkle" size={13} />{busy === 'pack-' + p.key ? '…' : (lang === 'fr' ? 'Acheter' : 'Buy')}
            </button>
          </div>
        ))}
      </div>
      {err && <p style={{ color: 'var(--error, #e5484d)', fontSize: 13, marginTop: 16 }}>{err}</p>}
    </div>
  );
}

/* =================================================================
   SETTINGS
   ================================================================= */
function SettingsSurface() {
  const t = window.useT();
  const lang = window.AXIAL_LANG || 'fr';
  const [theme, setTheme] = window.useTheme();
  const [tab, setTab] = useStateM('account');
  const [notif, setNotifState] = useStateM({ findings: true, weekly: true, marketing: false });
  React.useEffect(() => { axGetNotifPrefs().then(setNotifState).catch(() => {}); }, []);
  const setNotif = (next) => {
    setNotifState(next);
    axSetNotifPrefs(next).catch(() => {});  // persistance silencieuse
  };

  const tabs = [
    { group: t('settings.personal'), items: [
      { id: 'account', label: t('settings.account'), icon: 'user' },
      { id: 'notifications', label: t('settings.notifications'), icon: 'bell' },
      { id: 'appearance', label: t('settings.appearance'), icon: 'palette' },
    ]},
    { group: t('settings.workspace'), items: [
      { id: 'models', label: t('settings.models'), icon: 'cpu' },
      { id: 'connections', label: t('settings.connections'), icon: 'plug' },
      { id: 'billing', label: t('settings.billing'), icon: 'zap' },
    ]},
  ];

  return (
    <div className="surface">
      <div className="surface-head">
        <div>
          <h1>{t('settings.title')}</h1>
          <p>{lang === 'fr' ? 'Préférences personnelles et de l\'espace de travail.' : 'Personal and workspace preferences.'}</p>
        </div>
        <TopControls />
      </div>

      <div className="settings-shell">
        <aside className="settings-tabs">
          {tabs.map((g) => (
            <React.Fragment key={g.group}>
              <div className="group-label">{g.group}</div>
              {g.items.map((i) => (
                <button key={i.id} className={tab === i.id ? 'active' : ''} onClick={() => setTab(i.id)}>
                  {i.label}
                </button>
              ))}
            </React.Fragment>
          ))}
        </aside>

        <div className="settings-pane">
          {tab === 'account' && (
            <>
              <h2>{t('settings.account')}</h2>
              <p>{lang === 'fr' ? 'Vos informations de compte.' : 'Your account information.'}</p>
              <div className="settings-row">
                <div><h3>{lang === 'fr' ? 'Nom' : 'Name'}</h3><p>{lang === 'fr' ? 'Votre nom affiché sur les rapports partagés.' : 'Your name shown on shared reports.'}</p></div>
                <div className="control"><input type="text" defaultValue="Camille Verdun" style={inputStyle} /></div>
              </div>
              <div className="settings-row">
                <div><h3>Email</h3><p>{lang === 'fr' ? 'Adresse principale.' : 'Primary address.'}</p></div>
                <div className="control"><input type="email" defaultValue="camille@axial.intelligence" style={inputStyle} /></div>
              </div>
              <div className="settings-row">
                <div><h3>{lang === 'fr' ? 'Langue' : 'Language'}</h3><p>{lang === 'fr' ? 'Affichage de l\'interface.' : 'Interface language.'}</p></div>
                <div className="control">
                  <select className="role-select" value={lang} onChange={(e) => window.setAxialLang(e.target.value)}>
                    <option value="fr">Français</option>
                    <option value="en">English</option>
                  </select>
                </div>
              </div>
              <div className="settings-row">
                <div><h3>{lang === 'fr' ? 'Supprimer le compte' : 'Delete account'}</h3><p>{lang === 'fr' ? 'Action irréversible. Toutes les données sont supprimées sous 30 jours.' : 'Irreversible. All data is deleted within 30 days.'}</p></div>
                <div className="control"><button className="btn btn-secondary" style={{ color: 'var(--error)' }}>{lang === 'fr' ? 'Supprimer' : 'Delete'}</button></div>
              </div>
            </>
          )}

          {tab === 'notifications' && (
            <>
              <h2>{t('settings.notifications')}</h2>
              <p>{lang === 'fr' ? 'Choisissez ce qui mérite une notification.' : 'Pick what is worth a notification.'}</p>
              {[
                ['findings', lang === 'fr' ? 'Trouvailles d\'agents' : 'Agent findings', lang === 'fr' ? 'Email immédiat dès qu\'un agent publie une trouvaille à confiance haute.' : 'Immediate email when an agent publishes a high-confidence finding.'],
                ['weekly', lang === 'fr' ? 'Récap hebdomadaire' : 'Weekly recap', lang === 'fr' ? 'Lundi matin. Résumé des conversations, rapports et trouvailles.' : 'Monday morning. Summary of conversations, reports, findings.'],
                ['marketing', lang === 'fr' ? 'Nouvelles fonctionnalités' : 'New features', lang === 'fr' ? 'Annonces produit Axial. Une fois par mois maximum.' : 'Axial product announcements. Once a month max.'],
              ].map(([k, label, desc]) => (
                <div key={k} className="settings-row">
                  <div><h3>{label}</h3><p>{desc}</p></div>
                  <div className="control" style={{ alignItems: 'flex-end' }}>
                    <div className={'toggle' + (notif[k] ? ' on' : '')} onClick={() => setNotif({ ...notif, [k]: !notif[k] })}></div>
                  </div>
                </div>
              ))}
            </>
          )}

          {tab === 'appearance' && (
            <>
              <h2>{t('settings.appearance')}</h2>
              <p>{lang === 'fr' ? 'Apparence de l\'application.' : 'Application look and feel.'}</p>
              <div className="settings-row">
                <div><h3>{lang === 'fr' ? 'Thème' : 'Theme'}</h3><p>{lang === 'fr' ? 'Sombre par défaut. Le clair est conçu pour la lecture longue.' : 'Dark by default. Light is designed for long-form reading.'}</p></div>
                <div className="control" style={{ flexDirection: 'row', justifyContent: 'flex-end' }}>
                  <div className="rep-depth-seg">
                    <button className={theme === 'dark' ? 'active' : ''} onClick={() => setTheme('dark')}><Icon name="moon" size={13} /> {lang === 'fr' ? 'Sombre' : 'Dark'}</button>
                    <button className={theme === 'light' ? 'active' : ''} onClick={() => setTheme('light')}><Icon name="sun" size={13} /> {lang === 'fr' ? 'Clair' : 'Light'}</button>
                  </div>
                </div>
              </div>
              <div className="settings-row">
                <div><h3>{lang === 'fr' ? 'Densité' : 'Density'}</h3><p>{lang === 'fr' ? 'Compactage de l\'interface.' : 'Interface compactness.'}</p></div>
                <div className="control" style={{ flexDirection: 'row', justifyContent: 'flex-end' }}>
                  <select className="role-select"><option>{lang === 'fr' ? 'Confortable' : 'Comfortable'}</option><option>{lang === 'fr' ? 'Compacte' : 'Compact'}</option></select>
                </div>
              </div>
            </>
          )}


          {tab === 'models' && (
            <>
              <h2>{t('settings.models')}</h2>
              <p>{lang === 'fr' ? 'Modèles de raisonnement pilotés par Axial.' : 'Reasoning models driven by Axial.'}</p>
              <div className="settings-row">
                <div><h3>{lang === 'fr' ? 'Modèle par défaut' : 'Default model'}</h3><p>{lang === 'fr' ? 'Pour les conversations et les rapports standards.' : 'For conversations and standard reports.'}</p></div>
                <div className="control"><select className="role-select"><option>Axial Reason 2.1 (équilibré)</option><option>Axial Reason 2.1 Pro (qualité)</option><option>Axial Speed 1.4 (rapide)</option></select></div>
              </div>
              <div className="settings-row">
                <div><h3>{lang === 'fr' ? 'Modèle profondeur' : 'Deep model'}</h3><p>{lang === 'fr' ? 'Activé pour les rapports en mode Approfondi.' : 'Used for reports in Deep mode.'}</p></div>
                <div className="control"><select className="role-select"><option>Axial Reason 2.1 Pro</option><option>Axial Reason 2.0 Long-context</option></select></div>
              </div>
              <div className="settings-row">
                <div><h3>{lang === 'fr' ? 'Citations strictes' : 'Strict citations'}</h3><p>{lang === 'fr' ? 'Refuse de produire une affirmation chiffrée sans source primaire.' : 'Refuse to assert a numeric claim without a primary source.'}</p></div>
                <div className="control" style={{ alignItems: 'flex-end' }}><div className="toggle on"></div></div>
              </div>
            </>
          )}

          {tab === 'connections' && (
            <>
              <h2>{t('settings.connections')}</h2>
              <p>{lang === 'fr' ? 'Sources internes connectées à Axial.' : 'Internal sources connected to Axial.'}</p>
              {window.AXIAL_SURFACES.SETTINGS_CONNECTIONS.map((c) => (
                <div key={c.id} className="connection-row">
                  <div className="connection-icon">{c.icon}</div>
                  <div className="connection-body">
                    <div className="name">{c.name}</div>
                    <div className="meta">{c.meta}</div>
                  </div>
                  <button className={c.connected ? 'btn btn-ghost btn-sm' : 'btn btn-secondary btn-sm'}>
                    {c.connected ? (lang === 'fr' ? 'Configurer' : 'Configure') : (lang === 'fr' ? 'Connecter' : 'Connect')}
                  </button>
                </div>
              ))}
            </>
          )}

          {tab === 'billing' && <BillingSettings lang={lang} t={t} />}
        </div>
      </div>
    </div>
  );
}

function BillingSettings({ lang, t }) {
  const [sub, setSub] = React.useState(null);
  const [invoices, setInvoices] = React.useState(null);
  const [events, setEvents] = React.useState(null);
  React.useEffect(() => {
    axSubscription().then(setSub).catch(() => setSub({ active: false }));
    axInvoices().then(setInvoices).catch(() => setInvoices([]));
    axCreditHistory().then(setEvents).catch(() => setEvents([]));
  }, []);
  const fmtD = (iso) => new Date(iso).toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  const ACTION_LABELS = {
    essai_bienvenue: lang === 'fr' ? 'Crédits de bienvenue' : 'Welcome credits',
    pack_credits: lang === 'fr' ? 'Achat de pack' : 'Pack purchase',
    abonnement_mensuel: lang === 'fr' ? 'Renouvellement du plan' : 'Plan renewal',
    agent_message: lang === 'fr' ? 'Message agent' : 'Agent message',
    run_agent_veille: lang === 'fr' ? 'Run de veille' : 'Monitoring run',
    etude_marche: lang === 'fr' ? 'Étude de marché' : 'Market study',
    synthese_executive: lang === 'fr' ? 'Synthèse exécutive' : 'Executive summary',
    analyse_concurrentielle: lang === 'fr' ? 'Analyse concurrentielle' : 'Competitive analysis',
    veille_technologique: lang === 'fr' ? 'Veille technologique' : 'Tech watch',
    analyse_risques: lang === 'fr' ? 'Analyse de risques' : 'Risk analysis',
  };
  return (
    <>
      <h2>{t('settings.billing')}</h2>
      <p>{lang === 'fr' ? 'Abonnement, factures et consommation de crédits.' : 'Subscription, invoices and credit usage.'}</p>

      <div className="settings-row">
        <div>
          <h3>{lang === 'fr' ? 'Plan actuel' : 'Current plan'}</h3>
          <p>{sub === null ? '…'
            : sub.active
              ? `${sub.plan_name || sub.plan} · ${sub.price_eur} €/${lang === 'fr' ? 'mois' : 'mo'}${sub.current_period_end ? (lang === 'fr' ? ` · prochain prélèvement le ${fmtD(sub.current_period_end)}` : ` · next debit ${fmtD(sub.current_period_end)}`) : ''}`
              : (lang === 'fr' ? 'Aucun abonnement actif.' : 'No active subscription.')}</p>
        </div>
        {sub && sub.active && (
          <div className="control">
            <button className="btn btn-secondary" onClick={async () => {
              try { const r = await axPortal(); if (r.portal_url) window.location.href = r.portal_url; } catch (e) {}
            }}>{lang === 'fr' ? 'Gérer' : 'Manage'}</button>
          </div>
        )}
      </div>

      <div className="settings-row" style={{ display: 'block' }}>
        <h3 style={{ marginBottom: 8 }}>{lang === 'fr' ? 'Factures' : 'Invoices'}</h3>
        {invoices === null && <p>…</p>}
        {invoices && invoices.length === 0 && <p>{lang === 'fr' ? 'Aucune facture pour le moment.' : 'No invoice yet.'}</p>}
        {invoices && invoices.filter((i) => i.amount_eur > 0 || i.status === 'paid').map((inv) => (
          <div key={inv.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
            <span>{fmtD(inv.date)} · {inv.amount_eur.toFixed(2)} € · <span style={{ color: inv.status === 'paid' ? 'var(--success)' : 'var(--fg-3)' }}>{inv.status === 'paid' ? (lang === 'fr' ? 'payée' : 'paid') : inv.status}</span></span>
            {(inv.pdf || inv.url) && (
              <a className="btn btn-ghost" href={inv.pdf || inv.url} target="_blank" rel="noopener" style={{ fontSize: 12 }}>
                <Icon name="download" size={12} /> PDF
              </a>
            )}
          </div>
        ))}
      </div>

      <div className="settings-row" style={{ display: 'block' }}>
        <h3 style={{ marginBottom: 8 }}>{lang === 'fr' ? 'Consommation de crédits' : 'Credit usage'}</h3>
        {events === null && <p>…</p>}
        {events && events.length === 0 && <p>{lang === 'fr' ? 'Aucun mouvement pour le moment.' : 'No movement yet.'}</p>}
        {events && events.slice(0, 30).map((e, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
            <span style={{ color: 'var(--fg-2)' }}>{ACTION_LABELS[e.action] || e.action}</span>
            <span style={{ display: 'inline-flex', gap: 14 }}>
              <span className="mono" style={{ color: e.delta >= 0 ? 'var(--success)' : 'var(--fg)', fontWeight: 600 }}>{e.delta >= 0 ? '+' : ''}{e.delta}</span>
              <span className="mono" style={{ color: 'var(--fg-3)', fontSize: 11.5 }}>{fmtD(e.created_at)}</span>
            </span>
          </div>
        ))}
      </div>
    </>
  );
}

const inputStyle = {
  background: 'var(--surface-2)',
  border: '1px solid var(--border)',
  color: 'var(--fg)',
  padding: '9px 12px',
  borderRadius: 8,
  fontFamily: 'var(--font-sans)',
  fontSize: 13.5,
  outline: 'none',
};

/* =================================================================
   SHARING — modal
   ================================================================= */
function ShareModal({ onClose, onOpenRecipient }) {
  const t = window.useT();
  const lang = window.AXIAL_LANG || 'fr';
  const [tab, setTab] = useStateM('people');
  const [vis, setVis] = useStateM('workspace');
  const recipients = window.AXIAL_SURFACES.SHARE_RECIPIENTS;

  return (
    <div className="share-modal" onClick={onClose}>
      <div className="share-card" onClick={(e) => e.stopPropagation()}>
        <div className="share-head">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>{t('share.title')}</h2>
            <button className="icon-btn" onClick={onClose}><Icon name="x" size={16} /></button>
          </div>
          <div className="share-tabs">
            <button className={tab === 'people' ? 'active' : ''} onClick={() => setTab('people')}>{t('share.tab.people')}</button>
            <button className={tab === 'link' ? 'active' : ''} onClick={() => setTab('link')}>{t('share.tab.link')}</button>
            <button className={tab === 'embed' ? 'active' : ''} onClick={() => setTab('embed')}>{t('share.tab.embed')}</button>
          </div>
        </div>

        <div className="share-body">
          {tab === 'people' && (
            <>
              <div className="share-input-row">
                <input type="email" placeholder={lang === 'fr' ? 'Ajouter par email…' : 'Add by email…'} />
                <select className="role-select">
                  <option>{t('share.role.editor')}</option>
                  <option>{t('share.role.commenter')}</option>
                  <option>{t('share.role.viewer')}</option>
                </select>
              </div>
              <div>
                {recipients.map((r) => (
                  <div key={r.email} className="share-recipient">
                    <div className="member-avatar">{r.avatar}</div>
                    <div style={{ flex: 1 }}>
                      <div className="member-name">{r.name}</div>
                      <div className="member-email">{r.email} {r.external && <span style={{ color: 'var(--v-soft)' }}>· {lang === 'fr' ? 'externe' : 'external'}</span>}</div>
                    </div>
                    <select className="role-select" defaultValue={r.role}>
                      <option value="editor">{t('share.role.editor')}</option>
                      <option value="commenter">{t('share.role.commenter')}</option>
                      <option value="viewer">{t('share.role.viewer')}</option>
                    </select>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <button className="btn btn-ghost btn-sm" onClick={onOpenRecipient}>
                  <Icon name="eye" size={13} />{lang === 'fr' ? 'Aperçu côté destinataire' : 'Preview as recipient'}
                </button>
                <button className="btn btn-primary" onClick={onClose}>{t('common.done')}</button>
              </div>
            </>
          )}

          {tab === 'link' && (
            <>
              <div style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 13, color: 'var(--fg-2)', marginBottom: 8 }}>{lang === 'fr' ? 'Visibilité' : 'Visibility'}</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {[
                    ['private', 'lock', t('share.link.private'), lang === 'fr' ? 'Vous seul.' : 'Only you.'],
                    ['workspace', 'users', t('share.link.workspace'), lang === 'fr' ? 'Membres de l\'espace.' : 'Workspace members.'],
                    ['anyone', 'globe', t('share.link.anyone'), lang === 'fr' ? 'Toute personne disposant du lien (lecture seule).' : 'Anyone with the link (view only).'],
                  ].map(([id, ic, lbl, desc]) => (
                    <button key={id} className={'choice-tile' + (vis === id ? ' selected' : '')} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, textAlign: 'left' }} onClick={() => setVis(id)}>
                      <Icon name={ic} size={16} style={{ color: vis === id ? 'var(--v-bright)' : 'var(--fg-2)' }} />
                      <div style={{ flex: 1 }}>
                        <h4>{lbl}</h4>
                        <p>{desc}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="share-link-row">
                <Icon name="link" size={14} style={{ color: 'var(--fg-3)' }} />
                <input className="share-link-input" readOnly value="https://axial.intelligence/r/9f2e-csrd-hris-france" />
                <button className="btn btn-secondary btn-sm"><Icon name="copy" size={13} />{t('common.copy')}</button>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 6 }}>
                <span className="share-vis-pill"><Icon name="lock" size={11} />{lang === 'fr' ? 'Expire' : 'Expires'} 31 / 12 / 2026</span>
                <button className="btn btn-ghost btn-sm">{lang === 'fr' ? 'Modifier' : 'Edit'}</button>
              </div>
            </>
          )}

          {tab === 'embed' && (
            <>
              <p style={{ color: 'var(--fg-2)', fontSize: 13.5, margin: '0 0 12px' }}>
                {lang === 'fr' ? 'Code à coller dans Notion, Confluence ou un site interne.' : 'Code to paste into Notion, Confluence or an internal site.'}
              </p>
              <pre style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 10, padding: 14, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg)', overflowX: 'auto', margin: 0 }}>
{`<iframe src="https://axial.intelligence/r/9f2e-csrd-hris-france/embed"
        width="100%" height="640" frameborder="0">
</iframe>`}
              </pre>
              <button className="btn btn-secondary btn-sm" style={{ marginTop: 12 }}><Icon name="copy" size={13} />{t('common.copy')}</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* =================================================================
   SHARING — recipient view (read-only with comment thread)
   ================================================================= */
function RecipientView({ onBack }) {
  const t = window.useT();
  const lang = window.AXIAL_LANG || 'fr';
  const comments = window.AXIAL_SURFACES.SHARE_COMMENTS[lang];
  const [reply, setReply] = useStateM('');

  return (
    <div className="recipient-shell">
      <div className="recipient-doc">
        <div className="recipient-banner">
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <Icon name="eye" size={14} />
            <span>{lang === 'fr' ? 'Vous consultez ce rapport en' : 'You are viewing this report in'} <strong>{t('share.recipient.read_only')}</strong> · {lang === 'fr' ? 'partagé par Camille Verdun' : 'shared by Camille Verdun'}</span>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button className="btn btn-ghost btn-sm" onClick={onBack}><Icon name="arrow-left" size={13} />{t('common.back')}</button>
            <TopControls />
          </div>
        </div>

        <div style={{ marginBottom: 4, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          {lang === 'fr' ? 'Rapport · Cartographie concurrentielle' : 'Report · Competitive map'}
        </div>
        <h1 style={{ fontSize: 32, fontWeight: 700, letterSpacing: '-0.02em', margin: '4px 0 18px' }}>
          {lang === 'fr' ? 'Cartographie concurrentielle — SIRH France' : 'Competitive map — French HRIS'}
        </h1>
        <div style={{ fontSize: 13, color: 'var(--fg-2)', borderBottom: '1px solid var(--border)', paddingBottom: 18, marginBottom: 24 }}>
          {lang === 'fr' ? 'Brouillon partagé · 23 sources · Profondeur Standard · 4 nov 2026' : 'Shared draft · 23 sources · Standard depth · Nov 4, 2026'}
        </div>

        <h2 style={{ fontSize: 19, margin: '20px 0 10px', letterSpacing: '-0.01em' }}>1. {lang === 'fr' ? 'Synthèse exécutive' : 'Executive summary'}</h2>
        <p style={{ fontSize: 14.5, lineHeight: 1.65 }}>
          {lang === 'fr'
            ? <>Le marché français du SIRH atteint <strong>1,8 Md€</strong> en 2025, en croissance de 11 % vs 2024. Trois acteurs concentrent <strong>62 %</strong> du segment supérieur à 50 employés.</>
            : <>The French HRIS market reaches <strong>€1.8B</strong> in 2025, up 11% vs 2024. Three players hold <strong>62%</strong> of the &gt;50-employee segment.</>}
        </p>

        <h2 style={{ fontSize: 19, margin: '24px 0 10px', letterSpacing: '-0.01em' }}>3. {lang === 'fr' ? 'Marché — taille & dynamique' : 'Market — size & dynamics'}</h2>
        <p style={{ fontSize: 14.5, lineHeight: 1.65, background: 'rgba(245,193,108,0.06)', padding: '8px 12px', borderRadius: 8, borderLeft: '2px solid rgba(245,193,108,0.5)' }}>
          {lang === 'fr'
            ? <><strong>47 % des SIRH &gt; 50 employés</strong> intègrent désormais un module CSRD natif (XERFI 2025).</>
            : <><strong>47% of HRIS &gt; 50 employees</strong> now integrate a native CSRD module (XERFI 2025).</>}
        </p>
        <p style={{ fontSize: 14.5, lineHeight: 1.65 }}>
          {lang === 'fr'
            ? 'La progression annuelle moyenne est de 11 %, tirée à 70 % par les renouvellements et 30 % par les nouveaux clients.'
            : 'Annual growth averages 11%, 70% from renewals and 30% from new logos.'}
        </p>
      </div>

      <aside className="recipient-comments">
        <div className="recipient-comments-head">
          {lang === 'fr' ? 'Fil de commentaires · Section 3' : 'Comment thread · Section 3'}
        </div>
        <div className="comment-thread">
          {comments.map((c, i) => (
            <div key={i} className={'comment' + (c.axial ? ' axial' : '')}>
              <div className="comment-avatar">{c.axial ? <Icon name="sparkle" size={13} /> : c.avatar}</div>
              <div className="comment-body">
                <div className="comment-head">
                  <span className="comment-author">{c.author}</span>
                  {c.axial && <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: 'var(--v-soft)', letterSpacing: '0.08em', textTransform: 'uppercase', fontWeight: 700 }}>· {t('share.thread.axial_replied').split(' ')[0]}</span>}
                  <span className="comment-time">{c.time}</span>
                </div>
                <p className="comment-text">{c.text}</p>
              </div>
            </div>
          ))}
        </div>
        <div style={{ padding: 14, borderTop: '1px solid var(--border)' }}>
          <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
            <textarea
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              placeholder={lang === 'fr' ? 'Répondre… (mention @axial pour une réponse instantanée)' : 'Reply… (mention @axial for an instant answer)'}
              style={{ width: '100%', background: 'transparent', border: 0, color: 'var(--fg)', resize: 'none', minHeight: 48, fontSize: 13, fontFamily: 'var(--font-sans)', outline: 'none' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-3)', letterSpacing: '0.06em' }}>JEAN DUVAL · {lang === 'fr' ? 'commentaire' : 'commenter'}</span>
              <button className="btn btn-primary btn-sm"><Icon name="send" size={12} />{t('share.thread.reply')}</button>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}

window.MemorySurface = MemorySurface;
window.CreditsSurface = CreditsSurface;
window.SettingsSurface = SettingsSurface;
window.ShareModal = ShareModal;
window.RecipientView = RecipientView;




/* surface-docs.jsx */
/* surface-docs.jsx — Documentation hub
   Sub-pages: use-cases, prompts, agents, memory, credits */

var { useState: useDocsState } = React;

const DOCS_TOPICS = [
  { id: 'use-cases', icon: 'sparkles', fr: 'Cas d\u2019usage', en: 'Use cases' },
  { id: 'prompts',   icon: 'document', fr: 'Mod\u00e8les de prompts', en: 'Prompt templates' },
  { id: 'agents',    icon: 'cpu',      fr: 'Agents', en: 'Agents' },
  { id: 'memory',    icon: 'key',      fr: 'M\u00e9moire', en: 'Memory' },
  { id: 'credits',   icon: 'zap',      fr: 'Cr\u00e9dits & plans', en: 'Credits & plans' },
];

function DocsSurface() {
  const lang = window.AXIAL_LANG || 'fr';
  const [topic, setTopic] = useDocsState('use-cases');
  const isFR = lang === 'fr';

  return (
    <div className="docs-surface">
      <aside className="docs-toc">
        <div className="docs-toc-label">
          {isFR ? 'DOCUMENTATION' : 'DOCUMENTATION'}
        </div>
        <ul className="docs-toc-list">
          {DOCS_TOPICS.map((tp) => (
            <li key={tp.id}>
              <button
                className={`docs-toc-item ${topic === tp.id ? 'active' : ''}`}
                onClick={() => setTopic(tp.id)}>
                <span className="docs-toc-icon"><Icon name={tp.icon} size={14} /></span>
                <span>{isFR ? tp.fr : tp.en}</span>
              </button>
            </li>
          ))}
        </ul>

        <div className="docs-toc-foot">
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-3)', letterSpacing: '0.10em', marginBottom: 8 }}>
            {isFR ? 'BESOIN D\u2019AIDE ?' : 'NEED HELP?'}
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--fg-2)', lineHeight: 1.5 }}>
            {isFR
              ? <>\u00c9crivez \u00e0 <a href="#" style={{ color: 'var(--v-bright)' }}>support@axial.intelligence</a>. R\u00e9ponse sous 24h ouvr\u00e9es.</>
              : <>Reach <a href="#" style={{ color: 'var(--v-bright)' }}>support@axial.intelligence</a>. Reply within 24 business hours.</>}
          </div>
        </div>
      </aside>

      <main className="docs-main">
        {topic === 'use-cases' && <DocsUseCases isFR={isFR} />}
        {topic === 'prompts'   && <DocsPrompts isFR={isFR} />}
        {topic === 'agents'    && <DocsAgents isFR={isFR} />}
        {topic === 'memory'    && <DocsMemory isFR={isFR} />}
        {topic === 'credits'   && <DocsCredits isFR={isFR} />}
      </main>
    </div>
  );
}

/* ============================================================
   USE CASES
   ============================================================ */
function DocsUseCases({ isFR }) {
  const cases = isFR ? [
    {
      tag: 'GTM',
      title: 'Cadrer une mise sur le march\u00e9',
      body: 'Vous lancez un nouveau produit ou un nouveau march\u00e9 g\u00e9ographique. Axial vous aide \u00e0 d\u00e9finir la s\u00e9quence de canaux, le persona prioritaire, et les hypoth\u00e8ses \u00e0 valider en premier.',
      ex: '\u00ab Quels sont les 3 leviers GTM les plus efficaces pour un SaaS B2B Seed lan\u00e7ant en France et au DACH ? \u00bb',
    },
    {
      tag: 'CONCURRENCE',
      title: 'Cartographier vos concurrents',
      body: 'Identifiez les acteurs structurants de votre march\u00e9, leurs angles, leurs forces. Axial cite ses sources et signale les zones de vide concurrentiel.',
      ex: '\u00ab Mes 5 concurrents directs sur le SaaS RH en France et leurs positionnements respectifs \u00bb',
    },
    {
      tag: 'FINANCEMENT',
      title: 'Pr\u00e9parer une lev\u00e9e',
      body: 'Calibrez le montant, le timing et les benchmarks. Axial confronte vos m\u00e9triques aux benchmarks publics et propose une fourchette d\u00e9fendable.',
      ex: '\u00ab Combien lever en S\u00e9rie A pour un SaaS B2B \u00e0 1,2 M\u20ac d\u2019ARR avec 8 % de croissance mensuelle ? \u00bb',
    },
    {
      tag: 'R\u00c9GLEMENTAIRE',
      title: 'Anticiper un cadre l\u00e9gal',
      body: 'AI Act, RGPD, CNIL\u00a0: Axial liste les obligations applicables, leurs calendriers, et les risques contractuels c\u00f4t\u00e9 client.',
      ex: '\u00ab Quels risques r\u00e9glementaires majeurs pour un SaaS qui int\u00e8gre des mod\u00e8les GenAI sur le march\u00e9 fran\u00e7ais ? \u00bb',
    },
    {
      tag: 'ORG',
      title: 'Structurer votre \u00e9quipe',
      body: 'Quelle premi\u00e8re embauche apr\u00e8s un Seed ? Quelles fonctions externaliser, lesquelles internaliser ? Axial benchmark les choix d\u2019\u00e9quipes comparables.',
      ex: '\u00ab Profil id\u00e9al pour un premier Head of Product post-Seed dans un SaaS B2B \u00bb',
    },
    {
      tag: 'STRAT\u00c9GIE',
      title: 'D\u00e9cider sous incertitude',
      body: 'Quand les donn\u00e9es manquent, Axial expose les hypoth\u00e8ses cl\u00e9s, leur sensibilit\u00e9, et propose des sc\u00e9narios.',
      ex: '\u00ab Faut-il prioriser l\u2019Allemagne avant la France pour notre go-to-market ? \u00bb',
    },
  ] : [
    {
      tag: 'GTM',
      title: 'Frame a market launch',
      body: 'You\u2019re launching a new product or geo. Axial helps define the channel sequence, priority persona, and the hypotheses to validate first.',
      ex: '\u201cWhat are the 3 most effective GTM levers for a B2B SaaS Seed launching in France and DACH?\u201d',
    },
    {
      tag: 'COMPETITION',
      title: 'Map your competitors',
      body: 'Identify the structural players, their angles, their strengths. Axial cites sources and flags whitespace.',
      ex: '\u201cMy 5 direct competitors in HR SaaS in France and their respective positioning.\u201d',
    },
    {
      tag: 'FUNDING',
      title: 'Prepare a fundraise',
      body: 'Calibrate amount, timing, and benchmarks. Axial confronts your metrics with public benchmarks and proposes a defensible range.',
      ex: '\u201cHow much to raise for a Series A on a B2B SaaS at \u20ac1.2M ARR with 8% MoM growth?\u201d',
    },
    {
      tag: 'REGULATORY',
      title: 'Anticipate a legal framework',
      body: 'AI Act, GDPR, CNIL: Axial lists applicable obligations, timelines, and contractual risks on the client side.',
      ex: '\u201cMajor regulatory risks for a SaaS integrating GenAI models in France?\u201d',
    },
    {
      tag: 'ORG',
      title: 'Structure your team',
      body: 'What\u2019s the first hire after Seed? What to outsource, what to bring in-house? Axial benchmarks comparable team choices.',
      ex: '\u201cIdeal profile for a first Head of Product post-Seed in a B2B SaaS.\u201d',
    },
    {
      tag: 'STRATEGY',
      title: 'Decide under uncertainty',
      body: 'When data is missing, Axial exposes key assumptions, sensitivity, and proposes scenarios.',
      ex: '\u201cShould we prioritize Germany before France for our go-to-market?\u201d',
    },
  ];

  return (
    <div className="docs-page">
      <header className="docs-page-head">
        <div className="eyebrow" style={{ marginBottom: 8 }}>{isFR ? 'CAS D\u2019USAGE' : 'USE CASES'}</div>
        <h1>{isFR ? 'Quand mobiliser Axial.' : 'When to reach for Axial.'}</h1>
        <p>
          {isFR
            ? 'Axial est con\u00e7u pour les questions structurantes\u00a0: celles qui orientent une trajectoire, pas celles qui se r\u00e9solvent par une recherche Google. Six familles d\u2019usage o\u00f9 Axial fait gagner du temps et de la pr\u00e9cision.'
            : 'Axial is built for structuring questions \u2014 the ones that orient a trajectory, not those a Google search resolves. Six use case families where Axial saves time and adds precision.'}
        </p>
      </header>

      <div className="docs-cases-grid">
        {cases.map((c, i) => (
          <article key={i} className="docs-case-card">
            <div className="docs-case-tag">{c.tag}</div>
            <h3>{c.title}</h3>
            <p>{c.body}</p>
            <div className="docs-case-ex">
              <span className="docs-case-ex-label">{isFR ? 'EXEMPLE' : 'EXAMPLE'}</span>
              <p>{c.ex}</p>
            </div>
          </article>
        ))}
      </div>

      <div className="docs-rule" />

      <section className="docs-when-not">
        <h2>{isFR ? 'Quand Axial n\u2019est pas le bon outil.' : 'When Axial isn\u2019t the right tool.'}</h2>
        <ul>
          <li>{isFR ? 'Recherches factuelles ponctuelles (\u00ab quel est le PIB du Portugal ? \u00bb).' : 'Quick factual lookups (\u201cwhat is Portugal\u2019s GDP?\u201d).'}</li>
          <li>{isFR ? 'R\u00e9daction marketing ou cr\u00e9ative \u2014 Axial reste t\u00e9moin, pas plume.' : 'Marketing or creative copy \u2014 Axial stays witness, not author.'}</li>
          <li>{isFR ? 'Conseil l\u00e9gal nominatif \u2014 nous fournissons le cadre, pas l\u2019avis sign\u00e9.' : 'Named legal advice \u2014 we provide framework, not signed opinions.'}</li>
          <li>{isFR ? 'Donn\u00e9es internes confidentielles non vers\u00e9es \u00e0 votre m\u00e9moire.' : 'Confidential internal data not committed to your memory.'}</li>
        </ul>
      </section>
    </div>
  );
}

/* ============================================================
   PROMPT TEMPLATES
   ============================================================ */
function DocsPrompts({ isFR }) {
  const groups = isFR ? [
    {
      heading: 'Pour un rapport de march\u00e9',
      templates: [
        {
          name: 'TAM/SAM/SOM',
          template: 'Estime le TAM/SAM/SOM du march\u00e9 [SECTEUR] sur la zone [G\u00c9OGRAPHIE], horizon [ANN\u00c9E]. Pr\u00e9cise les sources, les hypoth\u00e8ses de calcul, et la sensibilit\u00e9 \u00e0 la principale variable.',
        },
        {
          name: 'Segments cl\u00e9s',
          template: 'Identifie les 3 \u00e0 5 segments structurants du march\u00e9 [SECTEUR] en [G\u00c9OGRAPHIE]. Pour chacun\u00a0: taille, dynamique de croissance, principaux acteurs, et angle d\u2019entr\u00e9e recommand\u00e9 pour [STADE].',
        },
        {
          name: 'Dynamiques de croissance',
          template: 'Quels sont les drivers et les freins structurels de croissance du march\u00e9 [SECTEUR] sur [G\u00c9OGRAPHIE] en [ANN\u00c9E] ? Distingue ce qui est conjoncturel de ce qui est structurel.',
        },
      ],
    },
    {
      heading: 'Pour une cartographie concurrentielle',
      templates: [
        {
          name: 'Positionnement',
          template: 'Cartographie les 5\u201310 acteurs structurants de [SECTEUR] en [G\u00c9OGRAPHIE]. Pour chacun\u00a0: taille, segment cible, levier diff\u00e9renciant, m\u00e9triques publiques disponibles.',
        },
        {
          name: 'Forces de Porter',
          template: 'Applique le mod\u00e8le des 5 forces de Porter au march\u00e9 [SECTEUR] [G\u00c9OGRAPHIE]. Pour chaque force, donne une intensit\u00e9 (faible/moyenne/forte) et une justification cit\u00e9e.',
        },
        {
          name: 'Whitespace',
          template: 'Quels sont les angles peu ou pas couverts par les acteurs actuels de [SECTEUR] en [G\u00c9OGRAPHIE] ? Justifie pourquoi ces angles existent (barri\u00e8re technique, march\u00e9 trop \u00e9troit, mod\u00e8le \u00e9conomique difficile).',
        },
      ],
    },
    {
      heading: 'Pour une veille r\u00e9glementaire',
      templates: [
        {
          name: 'Cadre applicable',
          template: 'Quels sont les cadres r\u00e9glementaires applicables \u00e0 [PRODUIT/SERVICE] sur le march\u00e9 [G\u00c9OGRAPHIE] ? Pour chaque cadre\u00a0: source, calendrier d\u2019entr\u00e9e en vigueur, sanctions encourues.',
        },
        {
          name: 'Comparaison juridictions',
          template: 'Compare les obligations r\u00e9glementaires applicables \u00e0 [PRODUIT] entre [PAYS A] et [PAYS B]. Mets en avant les divergences pratiques pour une entreprise qui op\u00e9rerait sur les deux.',
        },
      ],
    },
    {
      heading: 'Pour une analyse de risques',
      templates: [
        {
          name: 'Top risques',
          template: 'Liste les 5 risques les plus structurants pour une entreprise de type [STADE / SECTEUR] op\u00e9rant en [G\u00c9OGRAPHIE]. Pour chaque\u00a0: probabilit\u00e9, impact, mitigation possible, signal pr\u00e9coce \u00e0 surveiller.',
        },
        {
          name: 'Scenario worst-case',
          template: 'Construis un sc\u00e9nario worst-case cr\u00e9dible pour [PROJET/HYPOTH\u00c8SE] \u00e0 horizon [DUR\u00c9E]. Identifie les hypoth\u00e8ses de rupture et le seuil \u00e0 partir duquel le sc\u00e9nario devient probable.',
        },
      ],
    },
  ] : [
    {
      heading: 'For a market study',
      templates: [
        {
          name: 'TAM/SAM/SOM',
          template: 'Estimate TAM/SAM/SOM for [SECTOR] in [GEOGRAPHY], horizon [YEAR]. Cite sources, list calculation assumptions, and show sensitivity to the top variable.',
        },
        {
          name: 'Key segments',
          template: 'Identify 3 to 5 structuring segments of [SECTOR] in [GEOGRAPHY]. For each: size, growth dynamic, main players, and recommended entry angle for [STAGE].',
        },
        {
          name: 'Growth dynamics',
          template: 'What are the structural drivers and headwinds of [SECTOR] in [GEOGRAPHY] for [YEAR]? Separate cyclical from structural.',
        },
      ],
    },
    {
      heading: 'For a competitive map',
      templates: [
        {
          name: 'Positioning',
          template: 'Map the 5\u201310 structural players of [SECTOR] in [GEOGRAPHY]. For each: size, target segment, differentiator, public metrics available.',
        },
        {
          name: 'Porter\u2019s five forces',
          template: 'Apply Porter\u2019s 5-forces to [SECTOR] in [GEOGRAPHY]. For each force, rate intensity (low/med/high) with a cited justification.',
        },
        {
          name: 'Whitespace',
          template: 'Which angles are barely covered by current players of [SECTOR] in [GEOGRAPHY]? Explain why (technical barrier, niche, hard business model).',
        },
      ],
    },
    {
      heading: 'For regulatory monitoring',
      templates: [
        {
          name: 'Applicable framework',
          template: 'Which regulatory frameworks apply to [PRODUCT] in [GEOGRAPHY]? For each: source, timeline, possible sanctions.',
        },
        {
          name: 'Cross-jurisdiction',
          template: 'Compare regulatory obligations on [PRODUCT] between [COUNTRY A] and [COUNTRY B]. Highlight practical divergences for a multi-jurisdiction operator.',
        },
      ],
    },
    {
      heading: 'For risk analysis',
      templates: [
        {
          name: 'Top risks',
          template: 'List the 5 most structural risks for a [STAGE / SECTOR] company operating in [GEOGRAPHY]. For each: probability, impact, mitigation, early signal.',
        },
        {
          name: 'Worst-case scenario',
          template: 'Build a credible worst-case scenario for [PROJECT/HYPOTHESIS] over [TIMEFRAME]. Identify breaking assumptions and the threshold from which the scenario becomes probable.',
        },
      ],
    },
  ];

  return (
    <div className="docs-page">
      <header className="docs-page-head">
        <div className="eyebrow" style={{ marginBottom: 8 }}>{isFR ? 'MOD\u00c8LES DE PROMPTS' : 'PROMPT TEMPLATES'}</div>
        <h1>{isFR ? 'Mod\u00e8les pour vos rapports.' : 'Templates for your reports.'}</h1>
        <p>
          {isFR
            ? 'Bons prompts = bons rapports. Remplacez les variables entre crochets par votre contexte. Plus le cadrage est pr\u00e9cis, moins Axial consomme de cr\u00e9dits \u00e0 d\u00e9sambig\u00fc\u00efser.'
            : 'Good prompts = good reports. Replace the bracketed variables with your context. Tighter framing = fewer disambiguation credits spent.'}
        </p>
      </header>

      {groups.map((g, i) => (
        <section key={i} className="docs-prompt-group">
          <h2>{g.heading}</h2>
          <div className="docs-prompt-list">
            {g.templates.map((t, j) => (
              <div key={j} className="docs-prompt-card">
                <div className="docs-prompt-name">{t.name}</div>
                <pre className="docs-prompt-body">{t.template}</pre>
                <button className="btn btn-secondary btn-sm docs-copy-btn"
                  onClick={(e) => {
                    navigator.clipboard?.writeText(t.template);
                    const el = e.currentTarget;
                    const orig = el.textContent;
                    el.textContent = isFR ? 'Copi\u00e9' : 'Copied';
                    setTimeout(() => { el.textContent = orig; }, 1200);
                  }}>
                  <Icon name="document" size={12} /> {isFR ? 'Copier' : 'Copy'}
                </button>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

/* ============================================================
   AGENTS
   ============================================================ */
function DocsAgents({ isFR }) {
  return (
    <div className="docs-page">
      <header className="docs-page-head">
        <div className="eyebrow" style={{ marginBottom: 8 }}>{isFR ? 'AGENTS' : 'AGENTS'}</div>
        <h1>{isFR ? 'Comment fonctionnent les agents.' : 'How agents work.'}</h1>
        <p>
          {isFR
            ? 'Un agent Axial est une instance sp\u00e9cialis\u00e9e\u00a0: une m\u00e9thode (PESTEL, Porter, due-diligence\u2026), un prompt syst\u00e8me, des sources autoris\u00e9es, et un format de livrable. Vous l\u2019invoquez, il livre.'
            : 'An Axial agent is a specialized instance: a method (PESTEL, Porter, due-diligence\u2026), a system prompt, authorized sources, and a deliverable format. You invoke it, it delivers.'}
        </p>
      </header>

      <div className="docs-three">
        <div className="docs-three-card">
          <div className="docs-three-num">01</div>
          <h3>{isFR ? 'Une m\u00e9thode' : 'A method'}</h3>
          <p>{isFR
            ? 'Chaque agent applique un cadre d\u2019analyse \u00e9prouv\u00e9. PESTEL pour le macro, Porter pour la structure concurrentielle, due-diligence pour l\u2019\u00e9valuation.'
            : 'Each agent applies a battle-tested analytical frame. PESTEL for macro, Porter for competitive structure, due-diligence for evaluation.'}</p>
        </div>
        <div className="docs-three-card">
          <div className="docs-three-num">02</div>
          <h3>{isFR ? 'Une m\u00e9moire d\u00e9di\u00e9e' : 'A dedicated memory'}</h3>
          <p>{isFR
            ? 'L\u2019agent voit votre m\u00e9moire principale (lecture seule) et tient une m\u00e9moire propre li\u00e9e \u00e0 ses sessions, pour ne pas polluer le reste.'
            : 'The agent reads your main memory (read-only) and keeps a private session-bound memory, so it doesn\u2019t pollute the rest.'}</p>
        </div>
        <div className="docs-three-card">
          <div className="docs-three-num">03</div>
          <h3>{isFR ? 'Un livrable structur\u00e9' : 'A structured deliverable'}</h3>
          <p>{isFR
            ? 'Le livrable suit un format pr\u00e9visible\u00a0: synth\u00e8se, hypoth\u00e8ses, sources, recommandations. Compatible export Markdown / PDF.'
            : 'The output follows a predictable format: summary, assumptions, sources, recommendations. Markdown / PDF export.'}</p>
        </div>
      </div>

      <div className="docs-rule" />

      <section>
        <h2>{isFR ? 'Quand utiliser un agent plut\u00f4t qu\u2019une conversation' : 'When to pick an agent over a conversation'}</h2>
        <div className="docs-compare">
          <div className="docs-compare-col">
            <div className="docs-compare-head">{isFR ? 'Conversation' : 'Conversation'}</div>
            <ul>
              <li>{isFR ? 'Question ouverte ou exploratoire' : 'Open or exploratory question'}</li>
              <li>{isFR ? 'Vous cherchez \u00e0 cadrer avant d\u2019instruire' : 'You\u2019re framing before instructing'}</li>
              <li>{isFR ? 'Volume\u00a0: 1 \u00e0 3 \u00e9changes' : 'Volume: 1\u20133 exchanges'}</li>
              <li>{isFR ? 'Cr\u00e9dits\u00a0: l\u00e9ger' : 'Credits: light'}</li>
            </ul>
          </div>
          <div className="docs-compare-col">
            <div className="docs-compare-head">{isFR ? 'Agent' : 'Agent'}</div>
            <ul>
              <li>{isFR ? 'Question structur\u00e9e, p\u00e9rim\u00e8tre clair' : 'Structured question, clear scope'}</li>
              <li>{isFR ? 'Vous voulez un livrable r\u00e9utilisable' : 'You want a reusable deliverable'}</li>
              <li>{isFR ? 'Volume\u00a0: investigation longue' : 'Volume: long-running investigation'}</li>
              <li>{isFR ? 'Cr\u00e9dits\u00a0: forfait par session' : 'Credits: flat per session'}</li>
            </ul>
          </div>
        </div>
      </section>

      <div className="docs-rule" />

      <section>
        <h2>{isFR ? 'Cycle de vie d\u2019une session d\u2019agent' : 'Lifecycle of an agent session'}</h2>
        <ol className="docs-numbered">
          <li><strong>{isFR ? 'Bri\u00e9fing' : 'Briefing'}</strong>{isFR ? ' \u2014 vous d\u00e9crivez le contexte, l\u2019agent reformule jusqu\u2019\u00e0 alignement.' : ' \u2014 you describe the context, the agent rephrases until alignment.'}</li>
          <li><strong>{isFR ? 'Plan' : 'Plan'}</strong>{isFR ? ' \u2014 l\u2019agent propose un plan d\u2019enqu\u00eate. Vous validez ou amendez.' : ' \u2014 the agent proposes an investigation plan. You validate or amend.'}</li>
          <li><strong>{isFR ? 'Investigation' : 'Investigation'}</strong>{isFR ? ' \u2014 ex\u00e9cution. Vous voyez le raisonnement en temps r\u00e9el, vous pouvez interrompre.' : ' \u2014 execution. You see reasoning in real time and can interrupt.'}</li>
          <li><strong>{isFR ? 'Livrable' : 'Deliverable'}</strong>{isFR ? ' \u2014 rapport structur\u00e9, sources cit\u00e9es, prochaines questions sugg\u00e9r\u00e9es.' : ' \u2014 structured report, cited sources, suggested next questions.'}</li>
          <li><strong>{isFR ? 'Archivage' : 'Archive'}</strong>{isFR ? ' \u2014 la session reste consultable et r\u00e9utilisable comme contexte pour la suivante.' : ' \u2014 the session stays readable and reusable as context for the next one.'}</li>
        </ol>
      </section>
    </div>
  );
}

/* ============================================================
   MEMORY
   ============================================================ */
function DocsMemory({ isFR }) {
  return (
    <div className="docs-page">
      <header className="docs-page-head">
        <div className="eyebrow" style={{ marginBottom: 8 }}>{isFR ? 'M\u00c9MOIRE' : 'MEMORY'}</div>
        <h1>{isFR ? 'Une m\u00e9moire qui apprend votre contexte.' : 'A memory that learns your context.'}</h1>
        <p>
          {isFR
            ? 'Axial retient les faits qui orientent vos questions\u00a0: votre secteur, votre stade, vos hypoth\u00e8ses valid\u00e9es. Chaque conversation suivante part du bon endroit, sans re-cadrage.'
            : 'Axial retains the facts that orient your questions: sector, stage, validated assumptions. Each next conversation starts from the right place, no re-framing.'}
        </p>
      </header>

      <div className="docs-three">
        <div className="docs-three-card">
          <div className="docs-three-num">01</div>
          <h3>{isFR ? 'Faits, pas conversations' : 'Facts, not conversations'}</h3>
          <p>{isFR
            ? 'La m\u00e9moire ne stocke pas l\u2019historique entier. Elle extrait des faits structur\u00e9s\u00a0: \u00ab Cible PME 50\u2013250 ETP \u00bb, \u00ab ARR Q1 = 850 k\u20ac \u00bb, \u00ab Marg\u00e9 brute > 75 % \u00bb.'
            : 'Memory doesn\u2019t store the full history. It extracts structured facts: \u201cTarget SMB 50\u2013250 FTE\u201d, \u201cARR Q1 = \u20ac850k\u201d, \u201cGross margin > 75%\u201d.'}</p>
        </div>
        <div className="docs-three-card">
          <div className="docs-three-num">02</div>
          <h3>{isFR ? 'Vous \u00eates le pilote' : 'You\u2019re in control'}</h3>
          <p>{isFR
            ? 'Chaque fait est visible, modifiable, r\u00e9vocable depuis la page M\u00e9moire. Aucun fait n\u2019est ajout\u00e9 sans que vous puissiez le voir.'
            : 'Every fact is visible, editable, revocable from the Memory page. No fact is added without you being able to see it.'}</p>
        </div>
        <div className="docs-three-card">
          <div className="docs-three-num">03</div>
          <h3>{isFR ? 'Sources et cat\u00e9gories' : 'Sources and categories'}</h3>
          <p>{isFR
            ? 'Chaque fait est attach\u00e9 \u00e0 sa conversation d\u2019origine et class\u00e9 (entreprise, march\u00e9, hypoth\u00e8ses, pr\u00e9f\u00e9rences). Vous filtrez, vous nettoyez, vous exportez.'
            : 'Each fact links back to its source conversation and is categorized (company, market, assumptions, preferences). Filter, clean, export.'}</p>
        </div>
      </div>

      <div className="docs-rule" />

      <section>
        <h2>{isFR ? 'Cycle de vie d\u2019un fait' : 'Lifecycle of a fact'}</h2>
        <div className="docs-flow">
          {[
            isFR ? 'Extraction' : 'Extraction',
            isFR ? 'Proposition' : 'Proposal',
            isFR ? 'Validation' : 'Validation',
            isFR ? 'Utilisation' : 'Usage',
            isFR ? 'P\u00e9remption' : 'Expiry',
          ].map((step, i, arr) => (
            <React.Fragment key={i}>
              <div className="docs-flow-step">
                <div className="docs-flow-num">{i+1}</div>
                <div className="docs-flow-label">{step}</div>
              </div>
              {i < arr.length - 1 && <div className="docs-flow-arrow"><Icon name="arrow-right" size={14} /></div>}
            </React.Fragment>
          ))}
        </div>
        <p style={{ color: 'var(--fg-2)', fontSize: 13.5, lineHeight: 1.6, marginTop: 16 }}>
          {isFR
            ? 'Les faits temporels (m\u00e9triques, hypoth\u00e8ses) p\u00e9riment apr\u00e8s 90 jours sans confirmation. Les faits structurels (secteur, march\u00e9 cible) restent jusqu\u2019\u00e0 r\u00e9vocation.'
            : 'Temporal facts (metrics, assumptions) expire after 90 days without confirmation. Structural facts (sector, target market) stay until revoked.'}
        </p>
      </section>

      <div className="docs-rule" />

      <section className="docs-callout">
        <div className="docs-callout-icon"><Icon name="key" size={18} /></div>
        <div>
          <h3>{isFR ? 'Confidentialit\u00e9' : 'Confidentiality'}</h3>
          <p>{isFR
            ? 'Votre m\u00e9moire est cloisonn\u00e9e \u00e0 votre compte. Elle n\u2019est jamais utilis\u00e9e pour entra\u00eener un mod\u00e8le, partag\u00e9e avec un tiers, ou indexe d\u2019autres utilisateurs Axial.'
            : 'Your memory is scoped to your account. It is never used for model training, shared with a third party, or indexed for other Axial users.'}</p>
        </div>
      </section>
    </div>
  );
}

/* ============================================================
   CREDITS & PLANS
   ============================================================ */
function DocsCredits({ isFR }) {
  const plans = isFR ? [
    {
      name: 'Free Beta',
      price: '0\u00a0\u20ac',
      sub: 'pour d\u00e9couvrir',
      credits: '20 / mois',
      features: [
        'D\u00e9couverte',
        'Export PDF',
        '1 si\u00e8ge',
      ],
      tag: null,
    },
    {
      name: 'Pro',
      price: '50\u00a0\u20ac',
      sub: 'par mois',
      credits: '120 / mois',
      features: [
        'Workspace',
        '2 agents',
        'Templates (fundraising, ICP, GTM, mapping)',
        '1 si\u00e8ge',
      ],
      tag: 'POPULAIRE',
    },
    {
      name: 'Premium',
      price: '90\u00a0\u20ac',
      sub: 'par mois',
      credits: '250 / mois',
      features: [
        'Tout Pro',
        "Jusqu'\u00e0 10 agents personnalis\u00e9s",
        'M\u00e9moire avanc\u00e9e',
        '2 si\u00e8ges',
      ],
      tag: null,
    },
    {
      name: 'Enterprise',
      price: 'Sur devis',
      sub: '\u00e9quipe & multi-startups',
      credits: 'Cr\u00e9dits sur mesure',
      features: [
        'Workspace multi-startups',
        'Signaux portefeuille',
        'Acc\u00e8s \u00e9quipe',
      ],
      tag: null,
    },
  ] : [
    {
      name: 'Free Beta',
      price: '\u20ac0',
      sub: 'to explore',
      credits: '20 / month',
      features: [
        'Discovery',
        'PDF export',
        '1 seat',
      ],
      tag: null,
    },
    {
      name: 'Pro',
      price: '\u20ac50',
      sub: 'per month',
      credits: '120 / month',
      features: [
        'Workspace',
        '2 agents',
        'Templates (fundraising, ICP, GTM, mapping)',
        '1 seat',
      ],
      tag: 'POPULAR',
    },
    {
      name: 'Premium',
      price: '\u20ac90',
      sub: 'per month',
      credits: '250 / month',
      features: [
        'Everything in Pro',
        'Up to 10 custom agents',
        'Advanced memory',
        '2 seats',
      ],
      tag: null,
    },
    {
      name: 'Enterprise',
      price: 'Custom',
      sub: 'team & multi-startup',
      credits: 'Custom credits',
      features: [
        'Multi-startup workspace',
        'Portfolio signals',
        'Team access',
      ],
      tag: null,
    },
  ];

  const costs = isFR ? [
    { action: 'Message \u00e0 un agent (conversation)', cost: '2 cr\u00e9dits' },
    { action: 'Run d\u2019un agent de veille (RSS + web + LLM)', cost: '5 cr\u00e9dits' },
    { action: 'Analyse concurrentielle / risques / veille techno', cost: '25 cr\u00e9dits' },
    { action: 'Synth\u00e8se ex\u00e9cutive', cost: '25 cr\u00e9dits' },
    { action: '\u00c9tude de march\u00e9 (rapport complet)', cost: '40 cr\u00e9dits' },
    { action: 'Mise \u00e0 jour de m\u00e9moire', cost: '0 cr\u00e9dit' },
    { action: 'Lecture d\u2019un rapport', cost: '0 cr\u00e9dit' },
  ] : [
    { action: 'Message to an agent (conversation)', cost: '2 credits' },
    { action: 'Monitoring-agent run (RSS + web + LLM)', cost: '5 credits' },
    { action: 'Competitive / risk / tech-watch analysis', cost: '25 credits' },
    { action: 'Executive summary', cost: '25 credits' },
    { action: 'Market study (full report)', cost: '40 credits' },
    { action: 'Memory update', cost: '0 credits' },
    { action: 'Reading a report', cost: '0 credits' },
  ];

  return (
    <div className="docs-page">
      <header className="docs-page-head">
        <div className="eyebrow" style={{ marginBottom: 8 }}>{isFR ? 'CR\u00c9DITS & PLANS' : 'CREDITS & PLANS'}</div>
        <h1>{isFR ? 'Comment fonctionnent les cr\u00e9dits.' : 'How credits work.'}</h1>
        <p>
          {isFR
            ? 'Chaque action consommatrice (raisonnement, recherche, rapport) co\u00fbte un nombre de cr\u00e9dits proportionnel \u00e0 la profondeur d\u2019analyse. Les actions de lecture, organisation, et m\u00e9moire sont gratuites.'
            : 'Every consuming action (reasoning, retrieval, report) costs credits proportional to analysis depth. Read, organize, and memory actions are free.'}
        </p>
      </header>

      <h2 style={{ marginTop: 8 }}>{isFR ? 'Co\u00fbts indicatifs' : 'Indicative costs'}</h2>
      <div className="docs-cost-table">
        {costs.map((c, i) => (
          <div key={i} className="docs-cost-row">
            <span className="docs-cost-action">{c.action}</span>
            <span className="docs-cost-value">{c.cost}</span>
          </div>
        ))}
      </div>

      <div className="docs-rule" />

      <h2>{isFR ? 'Plans disponibles' : 'Available plans'}</h2>
      <div className="docs-plans-grid">
        {plans.map((p, i) => (
          <article key={i} className={`docs-plan-card ${p.tag ? 'featured' : ''}`}>
            {p.tag && <div className="docs-plan-tag">{p.tag}</div>}
            <h3>{p.name}</h3>
            <div className="docs-plan-price">
              <span className="big">{p.price}</span>
              <span className="sub">{p.sub}</span>
            </div>
            <div className="docs-plan-credits">
              <Icon name="zap" size={12} /> {p.credits}
            </div>
            <ul>
              {p.features.map((f, j) => (
                <li key={j}><Icon name="check" size={13} /> {f}</li>
              ))}
            </ul>
            <button className={p.tag ? 'btn btn-primary btn-block' : 'btn btn-secondary btn-block'}>
              {p.price === 'Sur devis' || p.price === 'Custom'
                ? (isFR ? 'Nous contacter' : 'Contact us')
                : (isFR ? `Choisir ${p.name}` : `Choose ${p.name}`)}
            </button>
          </article>
        ))}
      </div>

      <div className="docs-rule" />

      <section className="docs-callout">
        <div className="docs-callout-icon"><Icon name="zap" size={18} /></div>
        <div>
          <h3>{isFR ? 'Cr\u00e9dits non-utilis\u00e9s' : 'Unused credits'}</h3>
          <p>{isFR
            ? 'Les cr\u00e9dits inclus dans votre plan se renouvellent chaque mois et ne s\u2019accumulent pas. Vous pouvez acheter des packs ponctuels qui, eux, ne p\u00e9riment pas.'
            : 'Plan-included credits renew monthly and don\u2019t roll over. You can purchase ad-hoc packs that don\u2019t expire.'}</p>
        </div>
      </section>
    </div>
  );
}

window.DocsSurface = DocsSurface;




/* tweaks-panel.jsx */

// tweaks-panel.jsx
// Reusable Tweaks shell + form-control helpers.
//
// Owns the host protocol (listens for __activate_edit_mode / __deactivate_edit_mode,
// posts __edit_mode_available / __edit_mode_set_keys / __edit_mode_dismissed) so
// individual prototypes don't re-roll it. Ships a consistent set of controls so you
// don't hand-draw <input type="range">, segmented radios, steppers, etc.
//
// Usage (in an HTML file that loads React + Babel):
//
//   const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
//     "primaryColor": "#D97757",
//     "fontSize": 16,
//     "density": "regular",
//     "dark": false
//   }/*EDITMODE-END*/;
//
//   function App() {
//     const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
//     return (
//       <div style={{ fontSize: t.fontSize, color: t.primaryColor }}>
//         Hello
//         <TweaksPanel>
//           <TweakSection label="Typography" />
//           <TweakSlider label="Font size" value={t.fontSize} min={10} max={32} unit="px"
//                        onChange={(v) => setTweak('fontSize', v)} />
//           <TweakRadio  label="Density" value={t.density}
//                        options={['compact', 'regular', 'comfy']}
//                        onChange={(v) => setTweak('density', v)} />
//           <TweakSection label="Theme" />
//           <TweakColor  label="Primary" value={t.primaryColor}
//                        onChange={(v) => setTweak('primaryColor', v)} />
//           <TweakToggle label="Dark mode" value={t.dark}
//                        onChange={(v) => setTweak('dark', v)} />
//         </TweaksPanel>
//       </div>
//     );
//   }
//
// ─────────────────────────────────────────────────────────────────────────────

const __TWEAKS_STYLE = `
  .twk-panel{position:fixed;right:16px;bottom:16px;z-index:2147483646;width:280px;
    max-height:calc(100vh - 32px);display:flex;flex-direction:column;
    background:rgba(250,249,247,.78);color:#29261b;
    -webkit-backdrop-filter:blur(24px) saturate(160%);backdrop-filter:blur(24px) saturate(160%);
    border:.5px solid rgba(255,255,255,.6);border-radius:14px;
    box-shadow:0 1px 0 rgba(255,255,255,.5) inset,0 12px 40px rgba(0,0,0,.18);
    font:11.5px/1.4 ui-sans-serif,system-ui,-apple-system,sans-serif;overflow:hidden}
  .twk-hd{display:flex;align-items:center;justify-content:space-between;
    padding:10px 8px 10px 14px;cursor:move;user-select:none}
  .twk-hd b{font-size:12px;font-weight:600;letter-spacing:.01em}
  .twk-x{appearance:none;border:0;background:transparent;color:rgba(41,38,27,.55);
    width:22px;height:22px;border-radius:6px;cursor:default;font-size:13px;line-height:1}
  .twk-x:hover{background:rgba(0,0,0,.06);color:#29261b}
  .twk-body{padding:2px 14px 14px;display:flex;flex-direction:column;gap:10px;
    overflow-y:auto;overflow-x:hidden;min-height:0;
    scrollbar-width:thin;scrollbar-color:rgba(0,0,0,.15) transparent}
  .twk-body::-webkit-scrollbar{width:8px}
  .twk-body::-webkit-scrollbar-track{background:transparent;margin:2px}
  .twk-body::-webkit-scrollbar-thumb{background:rgba(0,0,0,.15);border-radius:4px;
    border:2px solid transparent;background-clip:content-box}
  .twk-body::-webkit-scrollbar-thumb:hover{background:rgba(0,0,0,.25);
    border:2px solid transparent;background-clip:content-box}
  .twk-row{display:flex;flex-direction:column;gap:5px}
  .twk-row-h{flex-direction:row;align-items:center;justify-content:space-between;gap:10px}
  .twk-lbl{display:flex;justify-content:space-between;align-items:baseline;
    color:rgba(41,38,27,.72)}
  .twk-lbl>span:first-child{font-weight:500}
  .twk-val{color:rgba(41,38,27,.5);font-variant-numeric:tabular-nums}

  .twk-sect{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
    color:rgba(41,38,27,.45);padding:10px 0 0}
  .twk-sect:first-child{padding-top:0}

  .twk-field{appearance:none;width:100%;height:26px;padding:0 8px;
    border:.5px solid rgba(0,0,0,.1);border-radius:7px;
    background:rgba(255,255,255,.6);color:inherit;font:inherit;outline:none}
  .twk-field:focus{border-color:rgba(0,0,0,.25);background:rgba(255,255,255,.85)}
  select.twk-field{padding-right:22px;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='rgba(0,0,0,.5)' d='M0 0h10L5 6z'/></svg>");
    background-repeat:no-repeat;background-position:right 8px center}

  .twk-slider{appearance:none;-webkit-appearance:none;width:100%;height:4px;margin:6px 0;
    border-radius:999px;background:rgba(0,0,0,.12);outline:none}
  .twk-slider::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;
    width:14px;height:14px;border-radius:50%;background:#fff;
    border:.5px solid rgba(0,0,0,.12);box-shadow:0 1px 3px rgba(0,0,0,.2);cursor:default}
  .twk-slider::-moz-range-thumb{width:14px;height:14px;border-radius:50%;
    background:#fff;border:.5px solid rgba(0,0,0,.12);box-shadow:0 1px 3px rgba(0,0,0,.2);cursor:default}

  .twk-seg{position:relative;display:flex;padding:2px;border-radius:8px;
    background:rgba(0,0,0,.06);user-select:none}
  .twk-seg-thumb{position:absolute;top:2px;bottom:2px;border-radius:6px;
    background:rgba(255,255,255,.9);box-shadow:0 1px 2px rgba(0,0,0,.12);
    transition:left .15s cubic-bezier(.3,.7,.4,1),width .15s}
  .twk-seg.dragging .twk-seg-thumb{transition:none}
  .twk-seg button{appearance:none;position:relative;z-index:1;flex:1;border:0;
    background:transparent;color:inherit;font:inherit;font-weight:500;min-height:22px;
    border-radius:6px;cursor:default;padding:4px 6px;line-height:1.2;
    overflow-wrap:anywhere}

  .twk-toggle{position:relative;width:32px;height:18px;border:0;border-radius:999px;
    background:rgba(0,0,0,.15);transition:background .15s;cursor:default;padding:0}
  .twk-toggle[data-on="1"]{background:#34c759}
  .twk-toggle i{position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;
    background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.25);transition:transform .15s}
  .twk-toggle[data-on="1"] i{transform:translateX(14px)}

  .twk-num{display:flex;align-items:center;height:26px;padding:0 0 0 8px;
    border:.5px solid rgba(0,0,0,.1);border-radius:7px;background:rgba(255,255,255,.6)}
  .twk-num-lbl{font-weight:500;color:rgba(41,38,27,.6);cursor:ew-resize;
    user-select:none;padding-right:8px}
  .twk-num input{flex:1;min-width:0;height:100%;border:0;background:transparent;
    font:inherit;font-variant-numeric:tabular-nums;text-align:right;padding:0 8px 0 0;
    outline:none;color:inherit;-moz-appearance:textfield}
  .twk-num input::-webkit-inner-spin-button,.twk-num input::-webkit-outer-spin-button{
    -webkit-appearance:none;margin:0}
  .twk-num-unit{padding-right:8px;color:rgba(41,38,27,.45)}

  .twk-btn{appearance:none;height:26px;padding:0 12px;border:0;border-radius:7px;
    background:rgba(0,0,0,.78);color:#fff;font:inherit;font-weight:500;cursor:default}
  .twk-btn:hover{background:rgba(0,0,0,.88)}
  .twk-btn.secondary{background:rgba(0,0,0,.06);color:inherit}
  .twk-btn.secondary:hover{background:rgba(0,0,0,.1)}

  .twk-swatch{appearance:none;-webkit-appearance:none;width:56px;height:22px;
    border:.5px solid rgba(0,0,0,.1);border-radius:6px;padding:0;cursor:default;
    background:transparent;flex-shrink:0}
  .twk-swatch::-webkit-color-swatch-wrapper{padding:0}
  .twk-swatch::-webkit-color-swatch{border:0;border-radius:5.5px}
  .twk-swatch::-moz-color-swatch{border:0;border-radius:5.5px}
`;

// ── useTweaks ───────────────────────────────────────────────────────────────
// Single source of truth for tweak values. setTweak persists via the host
// (__edit_mode_set_keys → host rewrites the EDITMODE block on disk).
function useTweaks(defaults) {
  const [values, setValues] = React.useState(defaults);
  // Accepts either setTweak('key', value) or setTweak({ key: value, ... }) so a
  // useState-style call doesn't write a "[object Object]" key into the persisted
  // JSON block.
  const setTweak = React.useCallback((keyOrEdits, val) => {
    const edits = typeof keyOrEdits === 'object' && keyOrEdits !== null
      ? keyOrEdits : { [keyOrEdits]: val };
    setValues((prev) => ({ ...prev, ...edits }));
    window.parent.postMessage({ type: '__edit_mode_set_keys', edits }, '*');
  }, []);
  return [values, setTweak];
}

// ── TweaksPanel ─────────────────────────────────────────────────────────────
// Floating shell. Registers the protocol listener BEFORE announcing
// availability — if the announce ran first, the host's activate could land
// before our handler exists and the toolbar toggle would silently no-op.
// The close button posts __edit_mode_dismissed so the host's toolbar toggle
// flips off in lockstep; the host echoes __deactivate_edit_mode back which
// is what actually hides the panel.
function TweaksPanel({ title = 'Tweaks', children }) {
  const [open, setOpen] = React.useState(false);
  const dragRef = React.useRef(null);
  const offsetRef = React.useRef({ x: 16, y: 16 });
  const PAD = 16;

  const clampToViewport = React.useCallback(() => {
    const panel = dragRef.current;
    if (!panel) return;
    const w = panel.offsetWidth, h = panel.offsetHeight;
    const maxRight = Math.max(PAD, window.innerWidth - w - PAD);
    const maxBottom = Math.max(PAD, window.innerHeight - h - PAD);
    offsetRef.current = {
      x: Math.min(maxRight, Math.max(PAD, offsetRef.current.x)),
      y: Math.min(maxBottom, Math.max(PAD, offsetRef.current.y)),
    };
    panel.style.right = offsetRef.current.x + 'px';
    panel.style.bottom = offsetRef.current.y + 'px';
  }, []);

  React.useEffect(() => {
    if (!open) return;
    clampToViewport();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', clampToViewport);
      return () => window.removeEventListener('resize', clampToViewport);
    }
    const ro = new ResizeObserver(clampToViewport);
    ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, [open, clampToViewport]);

  React.useEffect(() => {
    const onMsg = (e) => {
      const t = e?.data?.type;
      if (t === '__activate_edit_mode') setOpen(true);
      else if (t === '__deactivate_edit_mode') setOpen(false);
    };
    window.addEventListener('message', onMsg);
    window.parent.postMessage({ type: '__edit_mode_available' }, '*');
    return () => window.removeEventListener('message', onMsg);
  }, []);

  const dismiss = () => {
    setOpen(false);
    window.parent.postMessage({ type: '__edit_mode_dismissed' }, '*');
  };

  const onDragStart = (e) => {
    const panel = dragRef.current;
    if (!panel) return;
    const r = panel.getBoundingClientRect();
    const sx = e.clientX, sy = e.clientY;
    const startRight = window.innerWidth - r.right;
    const startBottom = window.innerHeight - r.bottom;
    const move = (ev) => {
      offsetRef.current = {
        x: startRight - (ev.clientX - sx),
        y: startBottom - (ev.clientY - sy),
      };
      clampToViewport();
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };

  if (!open) return null;
  return (
    <>
      <style>{__TWEAKS_STYLE}</style>
      <div ref={dragRef} className="twk-panel"
           style={{ right: offsetRef.current.x, bottom: offsetRef.current.y }}>
        <div className="twk-hd" onMouseDown={onDragStart}>
          <b>{title}</b>
          <button className="twk-x" aria-label="Close tweaks"
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={dismiss}>✕</button>
        </div>
        <div className="twk-body">{children}</div>
      </div>
    </>
  );
}

// ── Layout helpers ──────────────────────────────────────────────────────────

function TweakSection({ label, children }) {
  return (
    <>
      <div className="twk-sect">{label}</div>
      {children}
    </>
  );
}

function TweakRow({ label, value, children, inline = false }) {
  return (
    <div className={inline ? 'twk-row twk-row-h' : 'twk-row'}>
      <div className="twk-lbl">
        <span>{label}</span>
        {value != null && <span className="twk-val">{value}</span>}
      </div>
      {children}
    </div>
  );
}

// ── Controls ────────────────────────────────────────────────────────────────

function TweakSlider({ label, value, min = 0, max = 100, step = 1, unit = '', onChange }) {
  return (
    <TweakRow label={label} value={`${value}${unit}`}>
      <input type="range" className="twk-slider" min={min} max={max} step={step}
             value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </TweakRow>
  );
}

function TweakToggle({ label, value, onChange }) {
  return (
    <div className="twk-row twk-row-h">
      <div className="twk-lbl"><span>{label}</span></div>
      <button type="button" className="twk-toggle" data-on={value ? '1' : '0'}
              role="switch" aria-checked={!!value}
              onClick={() => onChange(!value)}><i /></button>
    </div>
  );
}

function TweakRadio({ label, value, options, onChange }) {
  const trackRef = React.useRef(null);
  const [dragging, setDragging] = React.useState(false);
  const opts = options.map((o) => (typeof o === 'object' ? o : { value: o, label: o }));
  const idx = Math.max(0, opts.findIndex((o) => o.value === value));
  const n = opts.length;

  // The active value is read by pointer-move handlers attached for the lifetime
  // of a drag — ref it so a stale closure doesn't fire onChange for every move.
  const valueRef = React.useRef(value);
  valueRef.current = value;

  const segAt = (clientX) => {
    const r = trackRef.current.getBoundingClientRect();
    const inner = r.width - 4;
    const i = Math.floor(((clientX - r.left - 2) / inner) * n);
    return opts[Math.max(0, Math.min(n - 1, i))].value;
  };

  const onPointerDown = (e) => {
    setDragging(true);
    const v0 = segAt(e.clientX);
    if (v0 !== valueRef.current) onChange(v0);
    const move = (ev) => {
      if (!trackRef.current) return;
      const v = segAt(ev.clientX);
      if (v !== valueRef.current) onChange(v);
    };
    const up = () => {
      setDragging(false);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  return (
    <TweakRow label={label}>
      <div ref={trackRef} role="radiogroup" onPointerDown={onPointerDown}
           className={dragging ? 'twk-seg dragging' : 'twk-seg'}>
        <div className="twk-seg-thumb"
             style={{ left: `calc(2px + ${idx} * (100% - 4px) / ${n})`,
                      width: `calc((100% - 4px) / ${n})` }} />
        {opts.map((o) => (
          <button key={o.value} type="button" role="radio" aria-checked={o.value === value}>
            {o.label}
          </button>
        ))}
      </div>
    </TweakRow>
  );
}

function TweakSelect({ label, value, options, onChange }) {
  return (
    <TweakRow label={label}>
      <select className="twk-field" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => {
          const v = typeof o === 'object' ? o.value : o;
          const l = typeof o === 'object' ? o.label : o;
          return <option key={v} value={v}>{l}</option>;
        })}
      </select>
    </TweakRow>
  );
}

function TweakText({ label, value, placeholder, onChange }) {
  return (
    <TweakRow label={label}>
      <input className="twk-field" type="text" value={value} placeholder={placeholder}
             onChange={(e) => onChange(e.target.value)} />
    </TweakRow>
  );
}

function TweakNumber({ label, value, min, max, step = 1, unit = '', onChange }) {
  const clamp = (n) => {
    if (min != null && n < min) return min;
    if (max != null && n > max) return max;
    return n;
  };
  const startRef = React.useRef({ x: 0, val: 0 });
  const onScrubStart = (e) => {
    e.preventDefault();
    startRef.current = { x: e.clientX, val: value };
    const decimals = (String(step).split('.')[1] || '').length;
    const move = (ev) => {
      const dx = ev.clientX - startRef.current.x;
      const raw = startRef.current.val + dx * step;
      const snapped = Math.round(raw / step) * step;
      onChange(clamp(Number(snapped.toFixed(decimals))));
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };
  return (
    <div className="twk-num">
      <span className="twk-num-lbl" onPointerDown={onScrubStart}>{label}</span>
      <input type="number" value={value} min={min} max={max} step={step}
             onChange={(e) => onChange(clamp(Number(e.target.value)))} />
      {unit && <span className="twk-num-unit">{unit}</span>}
    </div>
  );
}

function TweakColor({ label, value, onChange }) {
  return (
    <div className="twk-row twk-row-h">
      <div className="twk-lbl"><span>{label}</span></div>
      <input type="color" className="twk-swatch" value={value}
             onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function TweakButton({ label, onClick, secondary = false }) {
  return (
    <button type="button" className={secondary ? 'twk-btn secondary' : 'twk-btn'}
            onClick={onClick}>{label}</button>
  );
}

Object.assign(window, {
  useTweaks, TweaksPanel, TweakSection, TweakRow,
  TweakSlider, TweakToggle, TweakRadio, TweakSelect,
  TweakText, TweakNumber, TweakColor, TweakButton,
});




/* app.jsx */
/* app.jsx — main router for Axial Intelligence prototype */

var { useState, useEffect, useMemo, useRef } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "glowAmount": 1,
  "streamingSpeed": 40,
  "showChecklistStrip": true,
  "primaryAccent": "#7976F7"
}/*EDITMODE-END*/;

/* Top-level routes:
   'landing' | 'auth' | 'onb1' | 'onb2' | 'onb3' | 'app' | 'recipient'

   App sub-routes (in-app sidebar):
   'conversations' | 'reports' | 'agents' | 'memory' | 'credits' | 'settings'

   Reports flow states (within reports sub-route):
   'empty' | 'generating' | 'editor' | 'quota'
   Plus modals: source-conflict, share

   Agents flow states (within agents sub-route):
   'library' | 'session'
   Plus modal: wizard
*/

const TOP_ROUTES = ['landing','auth','onb1','onb2','onb3','onb4','app','recipient'];

function App() {
  const t = window.useT();

  const [route, setRoute] = useState(() => {
    const h = location.hash.replace('#', '') || 'landing';
    return TOP_ROUTES.includes(h) ? h : 'landing';
  });
  useEffect(() => {
    const onHash = () => {
      const h = location.hash.replace('#', '') || 'landing';
      if (TOP_ROUTES.includes(h)) setRoute(h);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const go = (r) => { location.hash = r; setRoute(r); };

  // onboarding context
  const [onbCtx, setOnbCtx] = useState({});
  const [authMode, setAuthMode] = useState('signup');

  // tweaks
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  useEffect(() => {
    document.documentElement.style.setProperty('--glow-amount', tweaks.glowAmount);
  }, [tweaks.glowAmount]);
  useEffect(() => {
    document.documentElement.style.setProperty('--v-bright', tweaks.primaryAccent);
  }, [tweaks.primaryAccent]);

  // conversations state
  // Start empty — real conversations are created as the user chats (no mock seeds).
  const [conversations, setConversations] = useState(() => []);
  const [activeId, setActiveId] = useState(conversations[0]?.id || null);
  const [showCitePanelFor, setShowCitePanelFor] = useState(null);

  // sub-routes & flow states
  const [subRoute, setSubRoute] = useState('conversations');
  // Real credit balance from the backend (fetched when entering the app).
  const [axBal, setAxBal] = useState(null);
  const [axUser, setAxUser] = useState(null);
  // Session persistence: if a valid token exists on load, resume into the app.
  // Handles the return from the onboarding Stripe checkout (?onb=done|cancel):
  // the card step is MANDATORY — until it's completed, resume lands on onb4.
  useEffect(() => {
    let tok = null;
    try { tok = localStorage.getItem('axial_token'); } catch (e) {}
    if (!tok) return;
    const params = new URLSearchParams(window.location.search);
    const onb = params.get('onb');
    if (onb) {
      // Clean the query string so refreshes don't replay the transition.
      try { window.history.replaceState({}, '', window.location.pathname + window.location.hash); } catch (e) {}
    }
    if (onb === 'done') {
      try { localStorage.removeItem('axial_onb_card_pending'); } catch (e) {}
      go('onb3');  // carte posée → dernière étape : la première analyse
      return;
    }
    let cardPending = false;
    try { cardPending = localStorage.getItem('axial_onb_card_pending') === '1'; } catch (e) {}
    if (cardPending) { go('onb4'); return; }
    // Gate serveur : l'app exige un abonnement (essai ou actif). Un compte au
    // profil complet mais sans abonnement retourne à l'étape carte.
    axMe().then(async (u) => {
      if (!u.onboarding_complete) { go('onb1'); return; }
      try {
        const s = await axSubscription();
        go(s && s.active ? 'app' : 'onb4');
      } catch (e) { go('app'); /* API indisponible : ne pas bloquer l'accès */ }
    }).catch(() => axClearToken());
  }, []);
  const [suggested, setSuggested] = useState(window.AXIAL_DATA.SUGGESTED_PROMPTS);
  useEffect(() => {
    if (route === 'app') {
      // Suggestions construites depuis le VRAI profil (nom, défi, stade) —
      // les génériques ne servent que de repli tant que le profil est vide.
      axGetProfile().then((pr) => {
        if (!pr || !(pr.company_name || pr.sector)) return;
        const who = pr.company_name || `ma startup ${pr.sector || ''}`.trim();
        const stage = pr.funding_stage || 'Seed';
        const qs = [
          `Quels sont les concurrents directs de ${who} et comment se différencier ?`,
          `Quel levier GTM ${who} devrait-elle prioriser en ${stage} ?`,
          `Comment ${who} doit-elle préparer sa prochaine levée : montant, timing, fonds à cibler ?`,
          pr.main_challenge ? `Par où attaquer : « ${pr.main_challenge} » ?` : `Quels risques ${who} doit-elle anticiper cette année ?`,
        ];
        setSuggested(qs);
      }).catch(() => {});
      // Historique persistant : recharger les conversations du compte.
      axListConversations().then((list) => {
        setConversations((cs) => {
          const known = new Set(cs.map((c) => c.id));
          const fetched = list.filter((c) => !known.has(c.id)).map((c) => ({
            id: c.id,
            title: c.title || 'Conversation',
            lastUpdated: c.last_message_at ? new Date(c.last_message_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }) : '',
            loaded: false,
            messages: [],
          }));
          return [...cs, ...fetched];
        });
      }).catch(() => {});
      axBalance().then((b) => setAxBal(b.available)).catch(() => {});
      axMe().then((u) => {
        const nm = u.full_name || u.email;
        const initials = nm.split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((s) => s[0].toUpperCase()).join('');
        setAxUser({ name: nm, email: u.email, initials });
      }).catch(() => {});
    }
  }, [route]);
  const [reportsState, setReportsState] = useState('empty'); // empty | generating | editor | quota
  const [reportData, setReportData] = useState(null);
  const startReport = async ({ type, depth, prompt }) => {
    setReportsState('generating');
    try {
      const r = await axRunAnalysis({ query: prompt, analysis_type: 'synthese_executive' });
      setReportData(r);
    } catch (e) {
      setReportData({ title: 'Erreur', content: '⚠️ ' + ((e && e.message) || 'Échec de génération'), sources: [] });
    }
    setReportsState('editor');
  };
  const [agentsState, setAgentsState] = useState('library'); // library | session
  const [activeAgent, setActiveAgent] = useState(null);

  // modals
  const [showConflict, setShowConflict] = useState(false);
  const [showShare, setShowShare] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [agentsRefresh, setAgentsRefresh] = useState(0);

  const handleNewChat = () => {
    setSubRoute('conversations');
    const id = 'c-' + Date.now();
    const newTitle = (window.AXIAL_LANG === 'en') ? 'New analysis' : 'Nouvelle analyse';
    setConversations((cs) => [{ id, title: newTitle, lastUpdated: (window.AXIAL_LANG === 'en') ? 'now' : 'à l\'instant', messages: [] }, ...cs]);
    setActiveId(id);
  };

  // Citations backend -> format du panneau latéral (URL pour le web,
  // extrait pour les chunks internes/documents).
  const mapCitations = (cits) => (cits || []).map((c, idx) => ({
    id: idx + 1,
    title: c.title || c.domain || 'Source',
    source: c.source === 'web'
      ? ('Web · ' + (c.domain || ''))
      : (c.source === 'document' ? 'Votre document' : ('Base de connaissance Axial' + (c.reference ? ' · ' + c.reference : ''))),
    excerpt: c.excerpt || '',
    link: c.url || null,
  }));
  const mapBackendMsg = (m) => (m.role === 'user'
    ? { role: 'user', content: m.content }
    : { role: 'assistant', content: m.content, agent: m.agent, sources: mapCitations(m.citations) });

  // Historique persistant : sélection d'une conversation -> chargement paresseux
  // de ses messages depuis le backend (une seule fois).
  const openConversation = async (id) => {
    setActiveId(id);
    const conv = conversations.find((c) => c.id === id);
    if (!conv || conv.loaded) return;
    try {
      const msgs = await axMessages(id);
      setConversations((cs) => cs.map((c) => c.id === id
        ? { ...c, loaded: true, messages: msgs.map(mapBackendMsg) } : c));
    } catch (e) { /* la conversation reste vide plutôt que de casser l'UI */ }
  };

  const handleSendInActive = async (text) => {
    if (!activeId) return;
    const cid = activeId;
    const now = (window.AXIAL_LANG === 'en') ? 'now' : 'à l\'instant';
    setConversations((cs) => cs.map((c) => c.id === cid ? {
      ...c,
      messages: [...c.messages, { role: 'user', content: text }, { role: 'assistant', content: '__PENDING__' }],
      lastUpdated: now,
    } : c));
    try {
      const reply = await axChatIn(cid, text);
      setConversations((cs) => cs.map((c) => c.id === cid ? {
        ...c, messages: [...c.messages.slice(0, -1), { role: 'assistant', content: reply.content, agent: reply.agent, sources: mapCitations(reply.citations) }],
      } : c));
    } catch (e) {
      setConversations((cs) => cs.map((c) => c.id === cid ? {
        ...c, messages: [...c.messages.slice(0, -1), { role: 'assistant', content: '⚠️ ' + ((e && e.message) || 'Erreur') }],
      } : c));
    }
  };

  const handleSendNew = async (text) => {
    const title = text.length > 48 ? text.slice(0, 45) + '…' : text;
    const now = (window.AXIAL_LANG === 'en') ? 'now' : 'à l\'instant';
    let id;
    try {
      id = await axCreateConversation();  // id backend réel -> l'historique persiste
    } catch (e) { id = 'c-' + Date.now(); }
    setConversations((cs) => [{
      id, title, lastUpdated: now, loaded: true,
      messages: [{ role: 'user', content: text }, { role: 'assistant', content: '__PENDING__' }],
    }, ...cs]);
    setActiveId(id);
    try {
      const reply = await axChatIn(id, text);
      setConversations((cs) => cs.map((c) => c.id === id ? {
        ...c, messages: [{ role: 'user', content: text }, { role: 'assistant', content: reply.content, agent: reply.agent, sources: mapCitations(reply.citations) }],
      } : c));
    } catch (e) {
      setConversations((cs) => cs.map((c) => c.id === id ? {
        ...c, messages: [{ role: 'user', content: text }, { role: 'assistant', content: '⚠️ ' + ((e && e.message) || 'Erreur') }],
      } : c));
    }
  };

  /* ---- Render top-level routes ---- */
  if (route === 'landing') {
    return <LandingPage
      onCTAStart={() => { setAuthMode('signup'); go('auth'); }}
      onCTASignIn={() => { setAuthMode('login'); go('auth'); }}
    />;
  }

  if (route === 'auth') {
    return <AuthPage
      initialMode={authMode}
      onBack={() => go('landing')}
      onSubmit={async ({ mode, email, pwd }) => {
        if (mode === 'signup') { await axRegister(email, pwd); go('onb1'); }
        else { await axLogin(email, pwd); go('app'); }
      }}
    />;
  }

  if (route === 'onb1') {
    return <OnbStep1
      value={onbCtx}
      onChange={setOnbCtx}
      onNext={() => go('onb2')}
    />;
  }
  if (route === 'onb2') {
    return <OnbStep2 ctx={onbCtx} onBack={() => go('onb1')} onNext={async () => {
      // Le profil est sauvegardé AVANT l'étape carte (redirection Stripe),
      // pour que la mémoire soit complète quoi qu'il arrive ensuite.
      try {
        await axSaveProfile({
          company_name: onbCtx.companyName || null,
          website: onbCtx.website || null,
          positioning: onbCtx.positioning || null,
          sector: onbCtx.sector || null,
          funding_stage: onbCtx.stage || null,
          main_challenge: onbCtx.challenge || null,
          target_market: onbCtx.geo || null,
          founding_year: onbCtx.foundingYear ? parseInt(onbCtx.foundingYear, 10) : null,
          team_size: onbCtx.teamSize || null,
          country: onbCtx.country || null,
          client_segment: onbCtx.clientSegment || null,
          known_competitors: onbCtx.competitors || null,
        });
      } catch (e) { /* non bloquant */ }
      go('onb4');
    }} />;
  }
  if (route === 'onb3') {
    return <OnbStep3
      ctx={onbCtx}
      onLaunch={(seedQ) => {
        // Jamais de lancement automatique : la question suggérée PRÉ-REMPLIT
        // le composer, l'utilisateur décide d'envoyer.
        try {
          if (seedQ) localStorage.setItem('axial_seed_q', seedQ);
          else localStorage.removeItem('axial_seed_q');
        } catch (e) {}
        go('app');
      }}
    />;
  }
  if (route === 'onb4') {
    return <OnbStep4 onBack={() => go('onb2')} />;
  }

  if (route === 'recipient') {
    return <RecipientView onBack={() => go('app')} />;
  }

  // ---- main app ----
  const active = conversations.find((c) => c.id === activeId);
  const lang = window.AXIAL_LANG || 'fr';

  // topbar adapts to sub-route
  let topbarTitle = null;
  if (subRoute === 'conversations') {
    topbarTitle = (
      <>
        <span className="crumb">{t('nav.conversations')}</span> / <span>{active ? active.title : t('nav.new_analysis')}</span>
      </>
    );
  } else {
    topbarTitle = <span>{t('nav.' + subRoute)}</span>;
  }

  const topbar = (
    <>
      <div className="topbar-title">{topbarTitle}</div>
      <div className="topbar-actions">
        <span className="chip" onClick={() => setSubRoute('credits')} style={{ cursor: 'pointer' }}>
          <Icon name="zap" size={11} /> {axBal == null ? '…' : axBal} {t('topbar.credits')}
        </span>
        <button className="icon-btn" title={t('topbar.settings')} onClick={() => setSubRoute('settings')}>
          <Icon name="settings" size={16} />
        </button>
      </div>
    </>
  );

  return (
    <>
      <AppShell
        user={axUser || { name: '', email: '', initials: '·' }}
        conversations={conversations}
        activeId={activeId}
        onPickConv={(id) => { setSubRoute('conversations'); openConversation(id); }}
        onNewChat={handleNewChat}
        onLogout={() => { axClearToken(); go('landing'); }}
        topbar={topbar}
        subRoute={subRoute}
        onSubRoute={(r) => {
          setSubRoute(r);
          if (r === 'reports') setReportsState('empty');
          if (r === 'agents') setAgentsState('library');
        }}>

        {subRoute === 'conversations' && (
          <ConversationsRegion
            conversations={conversations}
            activeId={activeId}
            setActiveId={openConversation}
            onSendInActive={handleSendInActive}
            onSendNew={handleSendNew}
            onNewChat={() => { setActiveId(null); }}
            suggestedPrompts={suggested}
            streamingSpeed={tweaks.streamingSpeed}
            showCitePanelFor={showCitePanelFor}
            setShowCitePanelFor={setShowCitePanelFor}
          />
        )}

        {subRoute === 'reports' && reportsState === 'empty' && (
          <ReportsEmpty onStart={startReport} />
        )}
        {subRoute === 'reports' && reportsState === 'generating' && (
          <ReportsGenerating onDone={() => {}} />
        )}
        {subRoute === 'reports' && reportsState === 'editor' && (
          <ReportsEditor
            data={reportData}
            onBack={() => setReportsState('empty')}
            openShare={() => setShowShare(true)}
          />
        )}
        {subRoute === 'reports' && reportsState === 'quota' && (
          <ReportsQuota onClose={() => setReportsState('empty')} />
        )}

        {subRoute === 'agents' && agentsState === 'library' && (
          <AgentsLibrary
            key={agentsRefresh}
            onCreate={() => setShowWizard(true)}
            onOpenSession={(a) => { setActiveAgent(a); setAgentsState('session'); }}
          />
        )}
        {subRoute === 'agents' && agentsState === 'session' && activeAgent && (
          <AgentSession agent={activeAgent} onBack={() => setAgentsState('library')} />
        )}

        {subRoute === 'memory' && <MemorySurface />}
        {subRoute === 'credits' && <CreditsSurface />}
        {subRoute === 'docs' && <DocsSurface />}
        {subRoute === 'settings' && <SettingsSurface />}
      </AppShell>

      {showConflict && <SourceConflictModal onClose={() => setShowConflict(false)} />}
      {showShare && (
        <ShareModal
          onClose={() => setShowShare(false)}
          onOpenRecipient={() => { setShowShare(false); go('recipient'); }}
        />
      )}
      {showWizard && (
        <AgentWizard
          onClose={() => setShowWizard(false)}
          onCreate={async (body) => {
            try { await axCreateWatch(body); } catch (e) { /* surfaced by empty list */ }
            setShowWizard(false);
            setAgentsRefresh((n) => n + 1);
          }}
        />
      )}

      <TweaksPanel title="Tweaks">
        <TweakSection title={lang === 'fr' ? 'Ambiance' : 'Mood'}>
          <TweakSlider
            label={lang === 'fr' ? 'Intensité des glows' : 'Glow intensity'}
            value={tweaks.glowAmount}
            min={0} max={1.6} step={0.1}
            onChange={(v) => setTweak('glowAmount', v)}
          />
          <TweakColor
            label={lang === 'fr' ? 'Accent violet' : 'Violet accent'}
            value={tweaks.primaryAccent}
            onChange={(v) => setTweak('primaryAccent', v)}
          />
        </TweakSection>
        <TweakSection title="Conversation">
          <TweakSlider
            label={lang === 'fr' ? 'Vitesse de streaming' : 'Streaming speed'}
            help={lang === 'fr' ? '0 = instantané · plus haut = plus rapide' : '0 = instant · higher = faster'}
            value={tweaks.streamingSpeed}
            min={0} max={20} step={1}
            onChange={(v) => setTweak('streamingSpeed', v)}
          />
        </TweakSection>
        <TweakSection title={lang === 'fr' ? 'États de rapport' : 'Report states'}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            <button className="btn btn-secondary btn-sm" onClick={() => { setSubRoute('reports'); setReportsState('empty'); }}>{lang === 'fr' ? 'Vide' : 'Empty'}</button>
            <button className="btn btn-secondary btn-sm" onClick={() => { setSubRoute('reports'); setReportsState('generating'); }}>{lang === 'fr' ? 'Génération' : 'Generating'}</button>
            <button className="btn btn-secondary btn-sm" onClick={() => { setSubRoute('reports'); setReportsState('editor'); }}>{lang === 'fr' ? 'Éditeur' : 'Editor'}</button>
            <button className="btn btn-secondary btn-sm" onClick={() => { setSubRoute('reports'); setReportsState('editor'); setShowConflict(true); }}>{lang === 'fr' ? 'Conflit' : 'Conflict'}</button>
            <button className="btn btn-secondary btn-sm" onClick={() => { setSubRoute('reports'); setReportsState('quota'); }}>{lang === 'fr' ? 'Quota' : 'Quota'}</button>
          </div>
        </TweakSection>
        <TweakSection title={lang === 'fr' ? 'Partage' : 'Sharing'}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            <button className="btn btn-secondary btn-sm" onClick={() => setShowShare(true)}>{lang === 'fr' ? 'Modale Partage' : 'Share modal'}</button>
            <button className="btn btn-secondary btn-sm" onClick={() => go('recipient')}>{lang === 'fr' ? 'Vue destinataire' : 'Recipient view'}</button>
          </div>
        </TweakSection>
        <TweakSection title="Onboarding">
          <TweakToggle
            label={lang === 'fr' ? 'Bandeau checklist (étape 3)' : 'Checklist banner (step 3)'}
            value={tweaks.showChecklistStrip}
            onChange={(v) => setTweak('showChecklistStrip', v)}
          />
        </TweakSection>
        <TweakSection title={lang === 'fr' ? 'Navigation' : 'Navigation'}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            <button className="btn btn-secondary btn-sm" onClick={() => go('landing')}>Landing</button>
            <button className="btn btn-secondary btn-sm" onClick={() => go('auth')}>Auth</button>
            <button className="btn btn-secondary btn-sm" onClick={() => go('onb1')}>Onb 1</button>
            <button className="btn btn-secondary btn-sm" onClick={() => go('onb2')}>Onb 2</button>
            <button className="btn btn-secondary btn-sm" onClick={() => go('onb3')}>Onb 3</button>
            <button className="btn btn-secondary btn-sm" onClick={() => go('app')}>App</button>
          </div>
        </TweakSection>
      </TweaksPanel>
    </>
  );
}

/* ---------- helpers ---------- */
function makeFakeAiResponse(question) {
  const lang = window.AXIAL_LANG || 'fr';
  if (lang === 'en') {
    return {
      role: 'ai',
      content: [
        "Good question. Three angles stand out as priorities to investigate",
        { cite: 1 },
        ".\n\n",
        "1. Frame the scope — segment, geography, horizon. Without this, any strategic answer is too generic to act on.\n\n",
        "2. Identify structural friction — what blocks or slows the decision today",
        { cite: 2 },
        ". Often a mix of missing signal and untested assumptions.\n\n",
        "3. Define the success criterion — what makes you call this 'investigated'? Time, depth, citation level required?\n\nWould you like me to dig into one of these angles with figures?"
      ],
      sources: [
        { id: 1, title: "Axial — Strategic framing methodology 2026", excerpt: "Well-framed strategic questions converge 4× faster than open queries, at equal answer depth.", source: "Axial Lab · Internal note · 2026", link: "https://axial.intelligence/methodology" },
        { id: 2, title: "McKinsey — Decision Velocity Report", excerpt: "Founders who explicitly enumerate decision criteria before research close 38% faster on strategic moves.", source: "McKinsey & Company · 2024", link: "https://www.mckinsey.com/decision-velocity-2024" }
      ]
    };
  }
  return {
    role: 'ai',
    content: [
      "Bonne question. Trois angles ressortent à instruire en priorité",
      { cite: 1 },
      ".\n\n",
      "1. Cadrer le périmètre — segment, géographie, horizon. Sans cela, toute réponse stratégique est trop générique pour engager.\n\n",
      "2. Identifier les points de friction structurels — ce qui bloque ou ralentit la décision aujourd'hui",
      { cite: 2 },
      ". Souvent un mélange de signal manquant et d'hypothèses non testées.\n\n",
      "3. Préciser le critère de succès — qu'est-ce qui vous fera dire « instruit » ? Délai, profondeur, niveau de citation requis ?\n\nSouhaitez-vous que je creuse l'un de ces angles avec des données chiffrées ?"
    ],
    sources: [
      { id: 1, title: "Axial — Méthodologie de cadrage stratégique 2026", excerpt: "Les questions stratégiques bien cadrées convergent 4× plus vite que les requêtes ouvertes, à profondeur de réponse égale.", source: "Axial Lab · Note interne · 2026", link: "https://axial.intelligence/methodologie" },
      { id: 2, title: "McKinsey — Decision Velocity Report", excerpt: "Founders who explicitly enumerate decision criteria before research close 38% faster on strategic moves.", source: "McKinsey & Company · 2024", link: "https://www.mckinsey.com/decision-velocity-2024" }
    ]
  };
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);



export default App;
