# Publication de Charles Tech 221 sur Cloudflare

Le site est servi par le Worker `charles-tech-221` et un conteneur Python
(Cloudflare Containers). Domaine principal : https://www.charlestech221.com —
`charlestech221.com` redirige vers `www` (redirection 301 dans `src/index.js`).

## Données

- Base SQLite `/data/charlestech.db` dans le conteneur, répliquée en continu
  (Litestream) dans le bucket R2 `charlestech221-uploads`, préfixe `litestream/`.
  Elle est restaurée depuis R2 à chaque démarrage du conteneur.
- Fichiers des clients : même bucket R2.
- Une seule instance de conteneur (`max_instances: 1`) : ne pas augmenter,
  SQLite n'accepte qu'un seul écrivain.

## Secrets à définir une fois

```
npx wrangler secret put SECRET_KEY
npx wrangler secret put ADMIN_PASSWORD
npx wrangler secret put EMPLOYEE_PASSWORD
```

`SECRET_KEY` : au moins 32 caractères aléatoires. Les secrets R2
(`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`) sont déjà configurés.

## Déploiement

Docker n'est pas installé sur le poste : l'image est construite par
Workers Builds (Cloudflare) à chaque `git push` sur `main` du dépôt GitHub
`mountamou/charles-tech-221`. Commande de déploiement : `npx wrangler deploy`.

## Validation avant ouverture commerciale

Tester les inscriptions, droits client/équipe, factures et paiements sur
le site en ligne. Les protections contre les tentatives de connexion et
le spam, les limites de dépôt de fichiers, la récupération de mot de passe
et les informations de confidentialité restent à finaliser avant cette ouverture.
Les paiements Wave/Orange Money restent des déclarations vérifiées manuellement.
