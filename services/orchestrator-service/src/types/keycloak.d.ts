export interface IKeycloakActiveKeys {
  "RSA-OAEP": string;
  HS512: string;
  RS256: string;
  AES: string;
}

export interface IKeycloakKey {
  providerId: string;
  providerPriority: number;
  kid: string;
  status: "ACTIVE" | "INACTIVE";
  type: "RSA" | "OCT";
  algorithm: "RS256" | "AES" | "HS512" | "RSA-OAEP";
  publicKey: string;
  certificate: string;
  use: "SIG" | "ENC";
  validTo: number;
}

export interface IKeycloakKeyConfig {
  active: IKeycloakActiveKeys;
  keys: IKeycloakKey[];
}
