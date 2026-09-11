# Publication de Charles Tech 221

La configuration Render est préparée. Aucun hébergement n'a encore été créé
et le domaine charlestech221.com n'a pas été acheté.

## Étapes dans le compte du propriétaire

1. Se connecter à Render et connecter un dépôt Git privé contenant ce dossier.
2. Créer un Blueprint à partir de `render.yaml`.
3. Saisir le mot de passe administrateur dans le champ secret demandé.
4. Examiner le prix du service, de PostgreSQL et du stockage avant de valider.
5. Après déploiement, tester l'adresse HTTPS fournie par Render.
6. Acheter le .com disponible puis le rattacher dans les domaines du service.

Le serveur utilise Python 3.12. PostgreSQL est accessible par le réseau privé ;
les fichiers sont conservés sur un disque persistant. La clé de session et le
mot de passe employé sont générés par Render. Le fichier `.env`, la base locale,
les journaux et les fichiers des clients ne sont pas copiés dans l'image Docker.

Une nouvelle base distante démarre avec les catalogues et les comptes équipe.
Les clients, projets et fichiers locaux ne sont pas transférés automatiquement.
Avant une ouverture avec des données existantes, prévoir leur migration ainsi
que la sauvegarde de la base et des fichiers, avec un test de restauration.

## Validation avant ouverture commerciale

Tester les inscriptions, droits client/équipe, factures et paiements sur
l'hébergement réel. Les protections contre les tentatives de connexion et
le spam, les limites de dépôt de fichiers, la récupération de mot de passe
et les informations de confidentialité restent à finaliser avant cette ouverture.
Les paiements Wave/Orange Money restent des déclarations vérifiées manuellement.

Documentation : https://render.com/docs/blueprint-spec
