# Suivi du trafic — Search Console d'abord, puis Analytics, Bing, Clarity (18/09/2026)

Deux sites distincts : le site vitrine `axial-ia.fr` (hébergé ailleurs,
derrière Cloudflare, robots.txt présent, pas de sitemap ni de script de
mesure) et l'app `app.axial-ia.fr` (VPS, Next.js). Une propriété Search
Console de type **domaine** couvre les deux.

## 1. Google Search Console (fait côté app, à finir côté compte Google)

Constat : le DNS de `axial-ia.fr` porte déjà un enregistrement
`google-site-verification=…` → une propriété de domaine a très probablement
été vérifiée (par toi ou pour le site vitrine). Livré le 18/09 sur l'app :
`https://app.axial-ia.fr/robots.txt` (autorise `/` et `/legal/`, interdit
`/api/`, `/p/` — pages de partage privées — et `/version`),
`https://app.axial-ia.fr/sitemap.xml` (landing + 3 pages légales), et une
balise de vérification optionnelle (`NEXT_PUBLIC_GSC_VERIFICATION` dans
`frontend/.env.local`, rebuild) si une propriété « préfixe d'URL » était
nécessaire.

À faire par Miradie (5 minutes, compte Google) :
1. Ouvrir https://search.google.com/search-console et vérifier qu'une
   propriété `axial-ia.fr` (domaine) existe. Sinon : « Ajouter une
   propriété » → Domaine → `axial-ia.fr` → l'enregistrement TXT existe déjà,
   cliquer « Vérifier ».
2. Dans la propriété : Sitemaps → ajouter `https://app.axial-ia.fr/sitemap.xml`.
3. Pour le site vitrine, faire générer un sitemap par son hébergeur et
   l'ajouter aussi ; sinon l'indexation passe par les liens.
4. Après 48 h : Performances (requêtes, pages, CTR), Pages (indexées / exclues).
   Les `/p/…` apparaîtront en « exclues par robots », c'est voulu.

## 2. Google Analytics 4 (ouvert)

Ce que ça apporte : pages vues par écran de l'app, sources de trafic,
conversions (inscription, premier rapport). Contrainte : la CNIL exige un
consentement préalable pour GA4 en configuration standard ; il faut donc un
bandeau cookies (ou une configuration « exemptée » très réduite). Plan : ID
`NEXT_PUBLIC_GA_ID` dans `.env.local`, script `gtag` chargé APRÈS
consentement dans `layout.tsx`, bandeau minimal FR/EN, et événements
`inscription`, `rapport_lance`, `conversation_envoyee` posés dans `App.jsx`.
Alternative sans consentement : les métriques serveur déjà en base (Pilotage)
couvrent l'usage produit ; GA4 sert surtout à l'amont (acquisition).

## 3. Bing Webmaster Tools (ouvert)

Import direct depuis Search Console (bouton « Importer depuis GSC ») : aucune
vérification supplémentaire. À faire après l'étape 1. Même sitemap.

## 4. Microsoft Clarity (ouvert)

Cartes de chaleur et enregistrements de sessions. Utile sur la landing et
l'onboarding ; à **ne pas** activer sur les écrans de conversation et de
rapport (contenu confidentiel des utilisateurs enregistré chez Microsoft).
Plan : `NEXT_PUBLIC_CLARITY_ID`, script chargé après consentement et
seulement sur les routes `landing`, `auth`, `onb*`, masquage des champs de
saisie (`data-clarity-mask`).

## Ordre proposé
1. Search Console (étape 1 ci-dessus, aujourd'hui).
2. Bing par import (2 minutes, quand 1 est fait).
3. Bandeau de consentement + GA4 (une demi-journée, décisions de wording).
4. Clarity sur la landing et l'onboarding (une heure, une fois le bandeau en place).
