#!/bin/bash

# Test writing relationships to Permify multiple times
# This simulates the multi-write approach to ensure all pods receive data

USER_ID="a4d5b298-1ef0-40d2-bac5-d39006e0366a"
TENANT_ID="bpmgd"
ROLE="admin"
ENTITY_TYPE="platform"
ENTITY_ID="bpmgd"

echo "Testing multi-write approach to Permify..."
echo "Writing relationship 15 times to hit all pods..."
echo ""

# Write relationship 15 times
SUCCESS_COUNT=0
for i in {1..15}; do
  RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:3476/v1/tenants/${TENANT_ID}/relationships/write" \
    -H "Content-Type: application/json" \
    -d "{
      \"tuples\": [
        {
          \"entity\": {
            \"type\": \"${ENTITY_TYPE}\",
            \"id\": \"${ENTITY_ID}\"
          },
          \"relation\": \"${ROLE}\",
          \"subject\": {
            \"type\": \"user\",
            \"id\": \"${USER_ID}\"
          }
        }
      ]
    }")
  
  HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
  
  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    echo "✓ Write attempt $i: Success (HTTP $HTTP_CODE)"
  else
    echo "✗ Write attempt $i: Failed (HTTP $HTTP_CODE)"
  fi
done

echo ""
echo "Write summary: $SUCCESS_COUNT/15 successful"
echo ""
echo "Now testing permission check 10 times to verify consistency..."
echo ""

# Test permission check 10 times
ALLOWED_COUNT=0
for i in {1..10}; do
  RESPONSE=$(curl -s -X POST "http://localhost:3476/v1/tenants/${TENANT_ID}/permissions/check" \
    -H "Content-Type: application/json" \
    -d "{
      \"metadata\": {
        \"schema_version\": \"\",
        \"snap_token\": \"\",
        \"depth\": 20
      },
      \"entity\": {
        \"type\": \"${ENTITY_TYPE}\",
        \"id\": \"${ENTITY_ID}\"
      },
      \"permission\": \"view_analytics\",
      \"subject\": {
        \"type\": \"user\",
        \"id\": \"${USER_ID}\"
      }
    }")
  
  CAN=$(echo "$RESPONSE" | jq -r '.can')
  
  if [ "$CAN" = "CHECK_RESULT_ALLOWED" ]; then
    ALLOWED_COUNT=$((ALLOWED_COUNT + 1))
    echo "✓ Check $i: ALLOWED"
  else
    echo "✗ Check $i: DENIED"
  fi
  
  sleep 0.2
done

echo ""
echo "Permission check summary: $ALLOWED_COUNT/10 allowed"
echo ""

if [ $ALLOWED_COUNT -eq 10 ]; then
  echo "✅ SUCCESS: All permission checks returned ALLOWED"
  echo "   Multi-write approach works! All pods have consistent data."
else
  echo "⚠️  INCONSISTENT: Only $ALLOWED_COUNT/10 checks returned ALLOWED"
  echo "   Some pods may not have received the relationship."
  echo "   Try increasing write attempts or check Permify pod logs."
fi
