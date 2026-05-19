# Environment Variables Reference

## 54Link Agency Banking Platform

All environment variables required for production deployment.

| Variable                 | Required | Default                  | Description                            |
| ------------------------ | -------- | ------------------------ | -------------------------------------- |
| `NODE_ENV`               | Yes      | `production`             | Runtime environment                    |
| `PORT`                   | No       | `3000`                   | HTTP server port                       |
| `DATABASE_URL`           | Yes      | —                        | PostgreSQL connection string           |
| `POSTGRES_URL`           | Yes      | —                        | PostgreSQL connection string (Drizzle) |
| `JWT_SECRET`             | Yes      | —                        | 256-bit secret for JWT signing         |
| `REDIS_URL`              | Yes      | `redis://localhost:6379` | Redis connection URL                   |
| `KEYCLOAK_URL`           | Yes      | —                        | Keycloak base URL                      |
| `KEYCLOAK_REALM`         | Yes      | `54link`                 | Keycloak realm name                    |
| `KEYCLOAK_CLIENT_ID`     | Yes      | `pos-shell`              | OIDC client ID                         |
| `KEYCLOAK_CLIENT_SECRET` | Yes      | —                        | OIDC client secret                     |
| `SES_SMTP_HOST`          | No       | `smtp.mailtrap.io`       | SMTP server host                       |
| `SES_SMTP_PORT`          | No       | `587`                    | SMTP server port                       |
| `SES_SMTP_USER`          | No       | —                        | SMTP username                          |
| `SES_SMTP_PASS`          | No       | —                        | SMTP password                          |
| `SES_SMTP_FROM`          | No       | `noreply@54link.ng`      | Default sender email                   |
| `MQTT_BROKER_URL`        | No       | `mqtt://localhost:1883`  | MQTT broker URL                        |
| `TEMPORAL_ADDRESS`       | No       | `localhost:7233`         | Temporal server address                |
| `AWS_ACCESS_KEY_ID`      | No       | —                        | S3 access key                          |
| `AWS_SECRET_ACCESS_KEY`  | No       | —                        | S3 secret key                          |
| `AWS_REGION`             | No       | `us-east-1`              | S3 region                              |
| `S3_BUCKET`              | No       | `54link-uploads`         | S3 bucket name                         |
| `FIDO2_RP_ID`            | No       | `54link.ng`              | WebAuthn relying party ID              |
| `FIDO2_RP_NAME`          | No       | `54Link POS`             | WebAuthn relying party name            |
| `FIDO2_ORIGIN`           | No       | `https://54link.ng`      | WebAuthn origin                        |
| `SMILE_ID_API_KEY`       | No       | —                        | Smile Identity API key                 |
| `SMILE_ID_PARTNER_ID`    | No       | —                        | Smile Identity partner ID              |
