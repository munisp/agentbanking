/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_TENANT_ID: string;
  readonly VITE_KEYCLOAK_REALM: string;
  readonly VITE_KEYCLOAK_PUB_KEY: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
