# Déploiement cloud sans installation sur ton PC

## Solution recommandée
Streamlit Community Cloud + GitHub privé + OpenAI API + Google Drive/Sheets.
Tu utilises uniquement Chrome pour importer tes photos et lancer les carrousels.

## Étape A — Préparer le dépôt GitHub (depuis le navigateur)
1. Connecte-toi à GitHub et crée un dépôt privé nommé `tiktokshop-carousel-factory`.
2. Téléverse les fichiers de ce dossier à la racine du dépôt : `app.py`, `carousel_engine.py`, `cloud_integrations.py`, `requirements.txt`.
3. Ne téléverse JAMAIS de clé API ni de fichier `secrets.toml` réel. Le fichier `.streamlit/secrets.toml.example` est un modèle sans identifiants valides.

## Étape B — Créer l'application hébergée
1. Ouvre https://share.streamlit.io/ et connecte GitHub.
2. Choisis le dépôt privé, branche `main`, fichier `app.py`.
3. Déploie l'application. Streamlit Cloud installe les dépendances depuis `requirements.txt`.
4. Dans App settings → Secrets, colle le contenu de `.streamlit/secrets.toml.example`, en remplaçant chaque valeur par tes propres identifiants.
5. Ajoute `OPENAI_API_KEY`, `OPENAI_TEXT_MODEL` et `OPENAI_IMAGE_MODEL` dans les secrets racine (les valeurs du modèle peuvent être changées selon ton accès API).

## Étape C — OpenAI API
1. Crée une clé API depuis https://platform.openai.com/api-keys.
2. Active la facturation API et vérifie l'accès à GPT Image.
3. Utilise `gpt-6.1-terra` pour l'analyse et `gpt-image-2.5-sunburst` pour l'édition/génération visuelle. L'accès aux modèles dépend de l'organisation et peut nécessiter une vérification.
4. Définis des limites de dépenses dans le tableau de bord API avant les premiers tests.

## Étape D — Google Drive et Sheets (optionnel mais prévu)
1. Dans Google Cloud Console, crée un projet et active Google Drive API et Google Sheets API.
2. Crée un compte de service et télécharge son JSON.
3. Crée un dossier Drive et une feuille Google Sheets.
4. Partage le dossier et la feuille avec l'adresse `client_email` du compte de service, avec le droit Éditeur.
5. Copie l'ID de la feuille et l'ID du dossier dans la section `[google]`.
6. Copie le contenu JSON du compte de service dans `[gcp_service_account]`.
7. Redéploie l'application. Après génération, le bouton de synchronisation archive les fichiers dans Drive et ajoute une ligne de suivi dans l'onglet `Production`.

## Utilisation
1. Ouvre l'URL privée de l'application dans Chrome.
2. Importe 1 à 8 photos de référence du produit.
3. Renseigne les informations vérifiées.
4. Clique « Générer les 7 visuels ».
5. Télécharge le ZIP ou synchronise vers Google Drive.

## Important : limites actuelles
- Cette V2 cloud traite un produit à la fois. Le traitement massif multi-produits et la file d'attente durable sont la prochaine évolution.
- Les images ne sont pas publiées automatiquement sur TikTok Shop.
- La clé API et les secrets Google restent dans les secrets du serveur, pas dans le navigateur.
- Les générations d'images API sont facturées séparément de ChatGPT.
- La fidélité visuelle doit être contrôlée avant publication.
