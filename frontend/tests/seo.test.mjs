// robots.txt et sitemap.xml de l'app (suivi du trafic, 18/09) : les pages
// de partage privées et l'API restent hors index, les pages publiques y sont.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const racine = join(dirname(fileURLToPath(import.meta.url)), '..');
const robots = readFileSync(join(racine, 'app/robots.ts'), 'utf8');
const sitemap = readFileSync(join(racine, 'app/sitemap.ts'), 'utf8');

test('robots : /p/ et /api/ interdits, sitemap déclaré', () => {
  assert.match(robots, /disallow: \["\/api\/", "\/p\/", "\/version"\]/);
  assert.match(robots, /sitemap: "https:\/\/app\.axial-ia\.fr\/sitemap\.xml"/);
});

test('sitemap : landing et trois pages légales, rien de privé', () => {
  for (const chemin of ['/`', '/legal/cgu', '/legal/confidentialite', '/legal/mentions']) {
    assert.ok(sitemap.includes(chemin), chemin);
  }
  assert.doesNotMatch(sitemap, /\/p\/|\/api\//);
});
