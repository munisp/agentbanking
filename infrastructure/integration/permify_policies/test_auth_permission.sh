#!/bin/bash

# Test auth service permission check endpoint

USER_ID="a4d5b298-1ef0-40d2-bac5-d39006e0366a"
TENANT_ID="bpmgd"
PERMISSION="view_analytics"
ENTITY_TYPE="platform"
ENTITY_ID="bpmgd"

echo "Testing auth service permission check..."
echo "User: $USER_ID"
echo "Permission: $PERMISSION"
echo "Entity: $ENTITY_TYPE:$ENTITY_ID"
echo ""

# Note: You may need to add authentication headers if required
# -H "Authorization: Bearer YOUR_TOKEN"

curl -v -X POST "https://54agent.upi.dev/auth/permissions/check-permission?permission=${PERMISSION}&entity_type=${ENTITY_TYPE}&entity_id=${ENTITY_ID}&user_id=${USER_ID}" \
  -H "Content-Type: application/json" \
  -H "x-tenant-id: ${TENANT_ID}" \
  -H "x-keycloak-realm: 54agent" \
  -H "x-keycloak-pub-key: MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA..." | jq .
