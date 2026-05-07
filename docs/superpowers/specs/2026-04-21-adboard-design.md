# AdBoard — Plateforme publicitaire multi-clients
**Date :** 2026-04-21  
**Statut :** Approuvé  
**Propriétaire :** Philippe Gauthier — Tête à Papineau Marketing Créatif

---

## Vue d'ensemble

AdBoard est une application web hébergée qui centralise les données publicitaires Meta Ads et Google Ads de tous les clients de l'agence. Elle offre une vue 360° admin pour l'équipe et des portails en lecture seule pour chaque client.

**Point de départ :** le projet `meta_ads_dashboard` existant (Python) qui extrait les données Meta Ads d'un seul compte et les pousse dans Google Sheets. AdBoard remplace et étend ce script.

---

## Stack technique

| Composant | Technologie |
|---|---|
| Backend | Python — Flask |
| Base de données | PostgreSQL (Neon.tech — free tier) |
| Scheduler | APScheduler (intégré dans Flask) |
| Frontend | Jinja2 + HTMX + Chart.js |
| Hébergement | Railway |
| Auth | Flask-Login + JWT pour les liens clients |
| Meta Ads | facebook-business SDK (existant) |
| Google Ads | google-ads Python SDK |

---

## Architecture

```
[ Browser — HTMX + Chart.js ]
        ↕ HTML partials / JSON
[ Flask App ]
   ├── Routes admin (vue 360°, gestion clients, accès)
   ├── Routes portail client (lecture seule)
   ├── Routes API (sync manuelle, données JSON pour charts)
   └── APScheduler (sync toutes les heures)
        ↕                        ↕
[ PostgreSQL ]         [ Meta API + Google Ads API ]
```

Tout tient dans un seul processus Flask déployé sur Railway. Un seul service à gérer.

---

## Modèle de données

### `clients`
- `id`, `name`, `slug`
- `meta_account_id` (optionnel)
- `google_customer_id` (optionnel)
- `secret_token` — token UUID pour le lien de portail client
- `is_active`, `created_at`

### `team_members`
- `id`, `email`, `password_hash`, `name`
- `role` — `superadmin | admin | user`
- `created_at`, `last_login_at`

### `team_member_clients` *(table de liaison)*
- Relie un `team_member` (role=user) aux clients qu'il peut voir
- Les rôles `superadmin` et `admin` voient tous les clients sans entrée dans cette table

### `client_users`
- `id`, `client_id`, `email`, `password_hash`
- `created_at`, `last_login_at`
- Comptes optionnels pour les clients qui veulent un login permanent

### `ad_metrics`
- `id`, `client_id`, `platform` (`meta | google`), `level` (`campaign | adset`)
- `date`, `campaign_id`, `campaign_name`, `adset_id`, `adset_name`
- Métriques : `impressions`, `reach`, `frequency`, `clicks`, `ctr`, `cpc`, `cpm`, `spend`, `purchases`, `revenue`, `roas`
- `synced_at`

### `sync_logs`
- `id`, `client_id`, `platform`, `status` (`success | error`), `rows_fetched`, `error_message`, `ran_at`

---

## Fonctionnalités

### 1. Vue admin 360°
- KPIs globaux agrégés : dépenses totales, revenus, ROAS moyen, clics totaux, clients actifs
- Filtres : période (7j / 30j / 90j) et plateforme (Toutes / Meta / Google)
- Tableau de tous les clients avec métriques clés, badges de plateformes actives, et indicateur de sync
- Chaque ligne cliquable → vue détail du client

### 2. Vue détail client (admin)
- KPIs du client pour la période sélectionnée
- Graphique dépenses par jour (Meta vs Google empilés)
- Tableau des campagnes avec drill-down vers les adsets
- Historique des synchronisations

### 3. Portail client (lecture seule)
- Accessible via lien secret `/client/<secret_token>` ou login email/mot de passe
- Mêmes KPIs et graphiques que la vue détail, mais limités aux données du client
- Badge "Lecture seule" visible, branding Tête à Papineau en nav
- Aucune action d'écriture possible

### 4. Synchronisation des données
- APScheduler déclenche une sync toutes les heures pour tous les clients actifs
- Ordre : Meta Ads en premier, Google Ads ensuite, client par client
- En cas d'erreur sur un client, on continue les autres et on log l'erreur
- Bouton "Sync maintenant" déclenche une sync manuelle immédiate (admin et user)
- Indicateur de dernière sync affiché dans la nav

### 5. Gestion des accès (admin)
- **Équipe** : inviter par email, assigner un rôle, révoquer, voir dernière connexion
- **Portails clients** : générer/révoquer le lien secret, créer un compte client optionnel
- **Rôles** : voir tableau des permissions par rôle

---

## Rôles et permissions

| Permission | Super Admin | Admin | Utilisateur | Client |
|---|:---:|:---:|:---:|:---:|
| Voir tous les clients | ✓ | ✓ | △ assignés | — |
| Ajouter / modifier un client | ✓ | ✓ | — | — |
| Gérer les membres d'équipe | ✓ | △ pas superadmin | — | — |
| Créer / révoquer liens clients | ✓ | ✓ | — | — |
| Lancer une sync manuelle | ✓ | ✓ | ✓ | — |
| Portail lecture seule | — | — | — | ✓ |

---

## Authentification

### Équipe (admin / user)
- Login email + mot de passe → session Flask-Login
- Mot de passe haché avec bcrypt
- Invitation par email : lien tokenisé valide 48h

### Clients
- **Lien secret** : `/client/<uuid_token>` — pas de compte requis, accès direct
- **Compte optionnel** : email + mot de passe → JWT stocké en cookie
- Un admin peut révoquer le token secret et en générer un nouveau à tout moment

---

## Design visuel

Palette de marque Tête à Papineau :
- **Orange principal** : `#E95526`
- **Bordeaux foncé** : `#451519` (navigation)
- **Beige** : `#E4D4BA` (bordures, accents secondaires)
- **Fond** : `#FAF7F2` (blanc cassé chaud)
- **Texte** : `#2D1A1A`

Police : Segoe UI / system-ui (pas de dépendance externe).

---

## Déploiement

- **Railway** : un seul service Flask + PostgreSQL add-on (ou Neon externe)
- `Procfile` : `web: gunicorn --workers 1 app:app` — APScheduler nécessite un seul worker pour éviter les syncs en double
- La migration de la base de données se fait via Flask-Migrate au démarrage
- **Email** : Resend (free tier — 3 000 emails/mois) pour les invitations d'équipe

### Variables d'environnement
- `DATABASE_URL`, `SECRET_KEY`, `FLASK_ENV`
- `META_ACCESS_TOKEN` — un seul token utilisateur Meta qui a accès à tous les comptes clients (via Business Manager). Le `meta_account_id` de chaque client est stocké en base.
- `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_REFRESH_TOKEN` — credentials OAuth2 partagés. Le `google_customer_id` de chaque client est stocké en base.
- `RESEND_API_KEY`

---

## Réutilisation du code existant

- `meta_fetcher.py` → adapté pour accepter un `account_id` en paramètre (au lieu de la variable globale)
- `config.py` → remplacé par la config Flask centralisée
- `sheets_uploader.py` → supprimé (remplacé par PostgreSQL)
- `requirements.txt` → étendu avec les nouvelles dépendances

---

## Hors portée (v1)

- Notifications / alertes email automatiques (ROAS sous un seuil, etc.)
- Export PDF des rapports
- Comparaison côte à côte entre deux clients
- Application mobile
