#!/bin/bash
set -euo pipefail

NAMESPACE="54agent"

echo "=== Scanning deployments in namespace: $NAMESPACE ==="
echo ""

# Build a map of pod → ownerDeployment via ReplicaSet
get_deployment_for_pod() {
  local pod_json="$1"
  local rs
  rs=$(echo "$pod_json" | jq -r '.metadata.ownerReferences[]? | select(.kind=="ReplicaSet") | .name')
  [ -z "$rs" ] && return
  kubectl get rs -n "$NAMESPACE" "$rs" -o json 2>/dev/null \
    | jq -r '.metadata.ownerReferences[]? | select(.kind=="Deployment") | .name'
}

echo "Finding deployments with non-running pods (Evicted, Pending, CrashLoop, etc.)..."
NOT_RUNNING=""

# Get all pods that are NOT in phase Running
while IFS= read -r pod_name; do
  pod_json=$(kubectl get pod -n "$NAMESPACE" "$pod_name" -o json 2>/dev/null)
  dep=$(get_deployment_for_pod "$pod_json")
  [ -n "$dep" ] && NOT_RUNNING="$NOT_RUNNING $dep"
done < <(kubectl get pods -n "$NAMESPACE" -o json \
  | jq -r '.items[] | select(.status.phase != "Running") | .metadata.name')

# Also catch Running-phase pods with non-ready containers (CrashLoopBackOff etc.)
while IFS= read -r pod_name; do
  pod_json=$(kubectl get pod -n "$NAMESPACE" "$pod_name" -o json 2>/dev/null)
  dep=$(get_deployment_for_pod "$pod_json")
  [ -n "$dep" ] && NOT_RUNNING="$NOT_RUNNING $dep"
done < <(kubectl get pods -n "$NAMESPACE" -o json \
  | jq -r '
      .items[]
      | select(.status.phase == "Running")
      | select(
          .status.containerStatuses[]?
          | (.ready == false) or (.state.waiting != null)
        )
      | .metadata.name
    ')

NOT_RUNNING=$(echo "$NOT_RUNNING" | tr ' ' '\n' | sort -u | grep -v '^$' || true)

# --- Deployments where actual running pod count > 1 ---
echo "Finding deployments with multiple actual pods..."
MULTI_POD=""
while IFS= read -r dep; do
  count=$(kubectl get pods -n "$NAMESPACE" -l "$(kubectl get deployment -n "$NAMESPACE" "$dep" \
    -o json | jq -r '.spec.selector.matchLabels | to_entries | map("\(.key)=\(.value)") | join(",")')" \
    --field-selector=status.phase=Running -o json 2>/dev/null | jq '.items | length')
  [ "$count" -gt 1 ] && MULTI_POD="$MULTI_POD $dep"
done < <(kubectl get deployments -n "$NAMESPACE" -o json | jq -r '.items[].metadata.name')

MULTI_POD=$(echo "$MULTI_POD" | tr ' ' '\n' | sort -u | grep -v '^$' || true)

# --- Combine ---
ALL_TO_DELETE=$(printf "%s\n%s\n" "$NOT_RUNNING" "$MULTI_POD" | sort -u | grep -v '^$' || true)

echo ""
echo "=== Deployments with non-running / unhealthy pods ==="
if [ -z "$NOT_RUNNING" ]; then echo "(none)"; else echo "$NOT_RUNNING"; fi

echo ""
echo "=== Deployments with multiple running pods ==="
if [ -z "$MULTI_POD" ]; then echo "(none)"; else echo "$MULTI_POD"; fi

echo ""
echo "=== TOTAL to delete ==="
if [ -z "$ALL_TO_DELETE" ]; then
  echo "(none — nothing to clean up)"
  exit 0
fi
echo "$ALL_TO_DELETE"

echo ""
read -r -p "Delete all of the above deployments? [y/N] " CONFIRM
if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo "$ALL_TO_DELETE" | xargs -I{} kubectl delete deployment {} -n "$NAMESPACE"
  echo "Done."
else
  echo "Aborted — no changes made."
fi
