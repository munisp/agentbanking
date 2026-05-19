# Keycloak Setup Guide — 54Link POS Shell

This guide covers provisioning the Keycloak realm required for admin/supervisor authentication in the 54Link POS Shell. POS agents use a separate PIN-based auth flow and do not require Keycloak accounts.

---

## Prerequisites

- Keycloak 22+ running and accessible (self-hosted or Keycloak.cloud)
- Admin console access
- Your production domain (e.g. `https://pos.54link.com`)

---

## Step 1: Import the Realm

The fastest path is to import the pre-configured realm export.

1. Open the Keycloak Admin Console → **Master** realm → **Create Realm**.
2. Click **Browse** and select `keycloak/54link-realm.json` from this repository.
3. Click **Create**.

The realm `54link` will be created with the `pos-shell` client, role definitions, password policy, and protocol mappers pre-configured.

---

## Step 2: Update Redirect URIs

After import, update the client redirect URIs to match your actual domain:

1. In the `54link` realm, go to **Clients** → `pos-shell` → **Settings**.
2. Replace `https://<YOUR_DOMAIN>` with your actual domain in:
   - **Valid redirect URIs**: `https://pos.54link.com/api/auth/callback`
   - **Valid post logout redirect URIs**: `https://pos.54link.com/`
   - **Web origins**: `https://pos.54link.com`
3. Click **Save**.

---

## Step 3: Get the Client Secret

1. In `pos-shell` client → **Credentials** tab.
2. Copy the **Client secret** value.

---

## Step 4: Configure Environment Variables

Add the following secrets to the application (via the Secrets panel or `.env`):

| Variable                 | Value                              | Example                   |
| ------------------------ | ---------------------------------- | ------------------------- |
| `KEYCLOAK_URL`           | Base URL of your Keycloak instance | `https://auth.54link.com` |
| `KEYCLOAK_REALM`         | Realm name                         | `54link`                  |
| `KEYCLOAK_CLIENT_ID`     | Client ID                          | `pos-shell`               |
| `KEYCLOAK_CLIENT_SECRET` | Client secret from Step 3          | `abc123...`               |

The server will perform OIDC discovery at:

```
{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration
```

---

## Step 5: Create Admin Users

1. In the `54link` realm → **Users** → **Add user**.
2. Fill in username, email, first/last name. Click **Create**.
3. Go to **Credentials** → set a temporary password.
4. Go to **Role mapping** → assign the `admin` or `supervisor` realm role.

The user's Keycloak `sub` (subject ID) will be stored in the `users.keycloakSub` column on first login.

---

## Step 6: Verify Connectivity

Hit the health endpoint after deploying:

```bash
curl https://pos.54link.com/api/health
```

Expected response:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "keycloak": "configured",
  "db": "connected"
}
```

The `keycloak` field will show `"configured"` when `KEYCLOAK_URL` is set, or `"not configured"` if the env var is missing.

---

## Auth Flow Reference

```
Browser → GET /api/auth/login
        → 302 to Keycloak Authorization endpoint
        → User authenticates at Keycloak
        → 302 back to /api/auth/callback?code=...&state=...
        → Server exchanges code for tokens (PKCE)
        → Server validates ID token (RS256, JWKS)
        → Server upserts user in DB (keycloakSub)
        → Server sets kc_session cookie (HttpOnly, Secure, SameSite=None)
        → 302 to returnPath (default: /)

Browser → GET /api/auth/logout
        → Server clears kc_session cookie
        → 302 to Keycloak end-session endpoint
        → Keycloak clears SSO session
        → 302 to post_logout_redirect_uri (/)
```

---

## Roles

| Role         | Access                                                                         |
| ------------ | ------------------------------------------------------------------------------ |
| `admin`      | Full Admin Panel access, agent management, settlement, MDM, compliance reports |
| `supervisor` | Supervisor dashboard, agent oversight, dispute resolution                      |
| `user`       | Basic authenticated access (no admin panel)                                    |

Roles are mapped from Keycloak realm roles into the `users.role` column on each login. The mapping is: `admin` → `admin`, `supervisor` → `supervisor`, anything else → `user`.

---

## Troubleshooting

| Symptom                   | Cause                          | Fix                                                                                           |
| ------------------------- | ------------------------------ | --------------------------------------------------------------------------------------------- |
| `OIDC discovery failed`   | Wrong `KEYCLOAK_URL` or realm  | Verify `{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration` is reachable |
| `JWT verification failed` | Clock skew > 5s                | Sync server time with NTP                                                                     |
| `Invalid redirect_uri`    | URI not registered in client   | Add exact URI to Valid redirect URIs in Keycloak                                              |
| `Cookie not set`          | HTTP (not HTTPS) in production | Ensure `Secure` flag is compatible with your proxy config                                     |
| Login loop                | `kc_session` cookie blocked    | Check browser SameSite/Secure settings; ensure HTTPS                                          |
