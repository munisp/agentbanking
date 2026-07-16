import { KeycloakAdminApiClient } from "../../lib/keycloakAdminApiClient";

export const provisionKeycloakRealm = async (realm: string) => {
  await KeycloakAdminApiClient.get_instance().create_realm(realm);

  // Enable Sub in Lightweight Access Token - Required for Login
  await KeycloakAdminApiClient.get_instance().enable_sub_in_lightweight_token(realm);

  const public_rsa_key = await KeycloakAdminApiClient.get_instance().get_public_rsa_key(realm);

  return {
    realm,
    public_rsa_key,
  };
};
