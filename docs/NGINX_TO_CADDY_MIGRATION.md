# NGINX to Caddy Migration Guide

This document outlines the procedure for migrating the 54Link platform's edge proxy from NGINX to Caddy.

## Why Caddy?

Caddy replaces NGINX at the edge to solve two critical operational gaps:
1. **Automatic Certificate Management**: Eliminates manual `certbot` runs, cron jobs, and NGINX reloads. Caddy handles Let's Encrypt issuance, renewal, and OCSP stapling natively with zero downtime.
2. **On-Demand TLS for Tenants**: Enables the white-label product feature by automatically provisioning TLS certificates for tenant custom domains (e.g., `bank.partner.ng`) the first time a user visits them, validated against the `tenantBranding` database table.
3. **HTTP/3 (QUIC) Support**: Improves latency on poor mobile networks (critical for PAX POS terminals).

## Architecture Changes

- **APISIX**: Remains the primary API Gateway. Caddy sits *in front* of APISIX, terminating TLS and forwarding traffic via `reverse_proxy`.
- **OpenAppSec**: Remains inline. It transparently inspects traffic between Caddy and the backend services.
- **Keycloak**: Remains the identity provider. Caddy proxies `auth.54link.ng` directly to Keycloak.

## Migration Steps (Docker Compose)

1. **Stop NGINX and Certbot**
   ```bash
   docker-compose stop nginx certbot
   docker-compose rm -f nginx certbot
   ```

2. **Start Caddy**
   ```bash
   # Ensure .env has the new CADDY_* variables
   docker-compose -f docker-compose.yml -f infra/caddy/docker-compose.caddy.yml up -d caddy
   ```

3. **Verify**
   ```bash
   curl -I https://54link.ng
   # Should show: Server: Caddy
   ```

## Migration Steps (Kubernetes)

1. **Apply Caddy Manifests**
   ```bash
   kubectl apply -k infra/k8s/caddy/
   ```

2. **Update DNS**
   Point your domain's A/AAAA records (or CNAME) to the new Caddy LoadBalancer external IP.

3. **Remove NGINX Ingress**
   Once DNS has propagated and traffic is flowing through Caddy:
   ```bash
   kubectl delete -f infra/k8s/nginx-ingress/
   # Or if using Helm: helm uninstall ingress-nginx -n ingress-nginx
   ```

## Tenant Custom Domains (On-Demand TLS)

When a tenant configures a custom domain (e.g., `app.theirbank.com`):
1. They point a CNAME record to `54link.ng`.
2. The first time a user visits `https://app.theirbank.com`, Caddy pauses the TLS handshake.
3. Caddy makes an internal HTTP GET request to the `api-server-ts` validation endpoint: `/internal/caddy/validate-domain?domain=app.theirbank.com`.
4. If the API returns `200 OK` (domain exists in DB), Caddy immediately provisions a Let's Encrypt certificate, completes the handshake, and serves the site.
5. If the API returns `403 Forbidden` (domain unknown), Caddy drops the connection, preventing abuse.

*Note: The first request takes ~2-5 seconds while the certificate is issued. Subsequent requests are instantaneous.*
