import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { validerIdentifiants, emailNormalise } from '../app/_prototype/auth_validation.js';

test('identifiants : chaque refus a un message, un bon couple passe', () => {
  assert.match(validerIdentifiants({ mode: 'signup', email: '', pwd: 'x' }), /adresse email/);
  assert.match(validerIdentifiants({ mode: 'signup', email: 'jean@axial', pwd: 'Abcdefgh1' }), /incompl/);
  assert.match(validerIdentifiants({ mode: 'signup', email: 'jean @axial.fr', pwd: 'Abcdefgh1' }), /incompl/);
  assert.match(validerIdentifiants({ mode: 'signup', email: 'jean@axial.fr', pwd: '' }), /mot de passe/);
  assert.match(validerIdentifiants({ mode: 'signup', email: 'jean@axial.fr', pwd: 'court' }), /8 caract/);
  assert.equal(validerIdentifiants({ mode: 'signup', email: ' Jean@Axial.fr ', pwd: 'Abcdefgh1' }), null);
  assert.equal(validerIdentifiants({ mode: 'login', email: 'jean@axial.fr', pwd: 'court' }), null, 'en connexion, la longueur ne se juge pas ici');
});

test('email normalisé : espaces et casse', () => {
  assert.equal(emailNormalise(' Jean@Axial.FR '), 'jean@axial.fr');
});

test('App.jsx : formulaire sans validation native, validation explicite branchée', () => {
  const app = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'app/_prototype/App.jsx'), 'utf8');
  assert.match(app, /import \{[^}]*validerIdentifiants[^}]*\} from "\.\/auth_validation"/);
  const debut = app.indexOf('function AuthPage(');
  const form = app.slice(app.indexOf('<form onSubmit={submit} className="auth-fields"', debut), app.indexOf('<p className="auth-foot">', debut));
  assert.match(form, /noValidate/);
  assert.doesNotMatch(form, /\brequired\b/);
  assert.doesNotMatch(form, /minLength=/);
  assert.match(app, /const message = validerIdentifiants\(\{ mode, email, pwd \}\)/);
  for (const m of ['Renseignez votre adresse email.', 'Cette adresse email semble incomplète (ex. vous@entreprise.com).', 'Renseignez votre mot de passe.', 'Le mot de passe doit faire au moins 8 caractères.']) {
    assert.ok(app.includes(`"${m}": `), 'traduction EN de : ' + m);
  }
});
