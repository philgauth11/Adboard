# Redesign : Marques & Accès

**Date :** 2026-05-05
**Statut :** Approuvé

## Contexte

Le système actuel a deux types d'utilisateurs distincts (TeamMember pour l'équipe, ClientUser pour les portails clients) avec deux interfaces séparées (/admin/ et /client/). Le nouveau système unifie tout sous un seul login et deux rôles simples.

## Objectif

- Remplacer "Client" par "Marque" dans l'interface
- Unifier TeamMember + ClientUser en un seul modèle utilisateur avec rôles Admin / Client
- Supprimer le portail client séparé (/client/)
- Tous les utilisateurs se connectent via /auth/login et accèdent à /admin/

---

## 1. Modèle de données

### Changements dans `TeamMember`

- `role` : valeurs valides passent de `superadmin / admin / user` à **`admin / client`**
- Aucune nouvelle colonne, aucune nouvelle table

### Suppression de `ClientUser`

- Le modèle `ClientUser` est supprimé
- Les `ClientUser` existants sont migrés vers `TeamMember` avec `role="client"`

### `Client` (entité en DB)

- Nom de la table et du modèle **inchangés** en base de données
- Renommé "Marque" uniquement dans l'interface utilisateur

### `TeamMemberClient` (inchangé)

- Lie les utilisateurs `client` aux marques auxquelles ils ont accès
- Les utilisateurs `admin` n'ont pas d'entrées dans cette table — leur accès est total

### Migration des données

```sql
-- Fusionner superadmin/admin/user → admin
UPDATE team_members SET role = 'admin' WHERE role IN ('superadmin', 'admin', 'user');

-- Migrer ClientUser → TeamMember avec role='client'
INSERT INTO team_members (email, name, role, password_hash, created_at)
SELECT email, email, 'client', password_hash, created_at FROM client_users;

-- Recréer les liens TeamMemberClient pour les nouveaux utilisateurs client
-- (fait manuellement via l'interface après migration)
```

---

## 2. Routes

### Supprimées

| Route | Raison |
|---|---|
| `GET/POST /client/<token>` | Portail supprimé |
| `GET/POST /client/login` | Portail supprimé |
| `GET/POST /client/dashboard` | Portail supprimé |
| `GET /admin/access/client/<id>/rotate-token` | Token portail inutile |

### Modifiées

| Avant | Après |
|---|---|
| `/admin/client/<id>` | `/admin/marque/<id>` |
| `/api/client/<id>/chart` | `/api/marque/<id>/chart` |
| `/api/sync/<id>` | Inchangé |

### Comportement par rôle

- **Admin** : accès complet à toutes les routes `/admin/`
- **Client** : accès à `/admin/` et `/admin/marque/<id>` pour ses marques assignées uniquement. Redirigé vers 403 sinon. Onglet "Accès" masqué dans la nav.

---

## 3. Interface — Page Accès (`/admin/access/`)

### Section "Marques"

- Lister les marques actives
- Formulaire : créer une marque (nom, compte Meta, compte Google)
- Bouton désactiver par marque

### Section "Utilisateurs"

- Lister tous les utilisateurs avec leur rôle et marques assignées
- Formulaire d'invitation : email, nom, rôle (Admin ou Client)
  - Si rôle = Client : checkboxes multi-sélection des marques
  - Si rôle = Admin : pas de sélection (accès total automatique)
- Modifier les marques assignées à un client existant (inline ou modal)
- Révoquer l'accès (supprimer le mot de passe)

### Navigation

- **Admin** : "Vue globale" + "Accès"
- **Client** : "Vue globale" uniquement

---

## 4. Decorators

`require_role("admin")` remplace `require_role("superadmin", "admin")` partout.

`can_see_client()` sur `TeamMember` reste inchangé — retourne `True` si admin, vérifie `TeamMemberClient` si client.

---

## 5. Ce qui n'est pas dans ce scope

- Pas de changement à la sync Meta/Google
- Pas de changement aux fetchers
- Pas de nouvelle fonctionnalité de dashboard
- Les tests existants seront mis à jour pour refléter les nouveaux rôles
