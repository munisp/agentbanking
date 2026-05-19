#!/usr/bin/env bash
# =============================================================================
# setup-branch-protection.sh — Apply GitHub Branch Protection Rules
# =============================================================================
#
# Applies branch protection rules defined in .github/branch-protection.json
# to the 54Link POS Shell repository using the GitHub REST API.
#
# Usage:
#   ./scripts/setup-branch-protection.sh [--repo OWNER/REPO] [--dry-run]
#
# Prerequisites:
#   - GITHUB_TOKEN env var with repo admin permissions
#   - curl, jq
#
# Example:
#   GITHUB_TOKEN=ghp_xxx ./scripts/setup-branch-protection.sh --repo 54link/pos-shell
#
# =============================================================================

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
die()     { error "$*"; exit 1; }

# ── Defaults ──────────────────────────────────────────────────────────────────
REPO="${GITHUB_REPO:-54link/pos-shell}"
DRY_RUN=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$REPO_ROOT/.github/branch-protection.json"
GITHUB_API="https://api.github.com"

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)       REPO="$2";    shift 2 ;;
    --dry-run)    DRY_RUN=true; shift   ;;
    --help|-h)
      echo "Usage: $0 [--repo OWNER/REPO] [--dry-run]"
      echo ""
      echo "Options:"
      echo "  --repo OWNER/REPO   GitHub repository (default: 54link/pos-shell)"
      echo "  --dry-run           Show what would be applied without making changes"
      echo ""
      echo "Environment variables:"
      echo "  GITHUB_TOKEN        GitHub personal access token (required)"
      exit 0
      ;;
    *) die "Unknown argument: $1" ;;
  esac
done

# ── Validation ────────────────────────────────────────────────────────────────
[[ -z "${GITHUB_TOKEN:-}" ]] && die "GITHUB_TOKEN environment variable is required"
[[ ! -f "$CONFIG_FILE" ]] && die "Config file not found: $CONFIG_FILE"
command -v curl >/dev/null 2>&1 || die "curl is required"
command -v jq   >/dev/null 2>&1 || die "jq is required"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     54Link POS Shell — GitHub Branch Protection Setup        ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
info "Repository:  $REPO"
info "Config file: $CONFIG_FILE"
[[ "$DRY_RUN" == "true" ]] && warn "DRY RUN MODE — no changes will be made"
echo ""

# ── GitHub API helper ─────────────────────────────────────────────────────────
gh_api() {
  local method="$1"
  local endpoint="$2"
  local data="${3:-}"

  local url="$GITHUB_API$endpoint"
  local args=(-s -X "$method" -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28")

  if [[ -n "$data" ]]; then
    args+=(-H "Content-Type: application/json" -d "$data")
  fi

  curl "${args[@]}" "$url"
}

# ── Verify token and repo access ──────────────────────────────────────────────
info "Verifying repository access..."
REPO_INFO=$(gh_api GET "/repos/$REPO" 2>/dev/null)
if echo "$REPO_INFO" | jq -e '.message == "Not Found"' >/dev/null 2>&1; then
  die "Repository '$REPO' not found or token lacks access"
fi
REPO_NAME=$(echo "$REPO_INFO" | jq -r '.full_name')
success "Repository access confirmed: $REPO_NAME"
echo ""

# ── Apply protection for a single branch ─────────────────────────────────────
apply_branch_protection() {
  local branch="$1"
  local config="$2"

  info "Applying protection to branch: ${BOLD}$branch${NC}"

  # Build the GitHub API payload from our config
  local payload
  payload=$(echo "$config" | jq '{
    required_status_checks: .required_status_checks,
    enforce_admins: .enforce_admins,
    required_pull_request_reviews: .required_pull_request_reviews,
    restrictions: .restrictions,
    allow_force_pushes: .allow_force_pushes,
    allow_deletions: .allow_deletions,
    block_creations: .block_creations,
    required_conversation_resolution: .required_conversation_resolution,
    lock_branch: .lock_branch,
    allow_fork_syncing: .allow_fork_syncing,
    required_linear_history: .required_linear_history,
    required_signatures: .required_signatures
  }')

  if [[ "$DRY_RUN" == "true" ]]; then
    warn "  [DRY RUN] Would PUT /repos/$REPO/branches/$branch/protection"
    echo "  Payload:"
    echo "$payload" | jq '.' | sed 's/^/    /'
    echo ""
    return 0
  fi

  # For wildcard patterns (e.g. release/*), use rulesets API instead
  if [[ "$branch" == *"*"* ]]; then
    info "  Using Rulesets API for wildcard pattern: $branch"
    apply_ruleset "$branch" "$config"
    return 0
  fi

  local response
  response=$(gh_api PUT "/repos/$REPO/branches/$branch/protection" "$payload")

  if echo "$response" | jq -e '.url' >/dev/null 2>&1; then
    success "  Branch protection applied to: $branch"

    # Apply required signatures separately (separate API endpoint)
    local require_sigs
    require_sigs=$(echo "$config" | jq -r '.required_signatures // false')
    if [[ "$require_sigs" == "true" ]]; then
      gh_api POST "/repos/$REPO/branches/$branch/protection/required_signatures" >/dev/null
      success "  Required signatures enabled for: $branch"
    fi
  else
    local msg
    msg=$(echo "$response" | jq -r '.message // "Unknown error"')
    error "  Failed to apply protection to $branch: $msg"
    echo "  Full response: $(echo "$response" | jq '.')" >&2
    return 1
  fi
  echo ""
}

# ── Apply ruleset for wildcard patterns ───────────────────────────────────────
apply_ruleset() {
  local pattern="$1"
  local config="$2"

  local required_checks
  required_checks=$(echo "$config" | jq '[.required_status_checks.contexts[] | {type: "check_run", parameters: {context: .}}]')

  local ruleset_payload
  ruleset_payload=$(jq -n \
    --arg name "Protect $pattern" \
    --arg pattern "$pattern" \
    --argjson checks "$required_checks" \
    '{
      name: $name,
      target: "branch",
      enforcement: "active",
      conditions: {
        ref_name: {
          include: ["refs/heads/" + $pattern],
          exclude: []
        }
      },
      rules: [
        { type: "deletion" },
        { type: "non_fast_forward" },
        { type: "required_status_checks", parameters: { strict_required_status_checks_policy: true, required_status_checks: $checks } },
        { type: "pull_request", parameters: { required_approving_review_count: 2, dismiss_stale_reviews_on_push: true, require_code_owner_review: true, require_last_push_approval: true } }
      ]
    }')

  local response
  response=$(gh_api POST "/repos/$REPO/rulesets" "$ruleset_payload")

  if echo "$response" | jq -e '.id' >/dev/null 2>&1; then
    success "  Ruleset created for pattern: $pattern (id: $(echo "$response" | jq -r '.id'))"
  else
    local msg
    msg=$(echo "$response" | jq -r '.message // "Unknown error"')
    warn "  Could not create ruleset for $pattern: $msg (may already exist)"
  fi
  echo ""
}

# ── Process all branches in config ───────────────────────────────────────────
echo -e "${BOLD}Applying branch protection rules...${NC}"
echo ""

BRANCHES=$(jq -r 'keys[] | select(startswith("_") | not)' "$CONFIG_FILE")
TOTAL=$(echo "$BRANCHES" | wc -l | tr -d ' ')
APPLIED=0
FAILED=0

while IFS= read -r branch; do
  config=$(jq -r --arg b "$branch" '.[$b]' "$CONFIG_FILE")

  if apply_branch_protection "$branch" "$config"; then
    ((APPLIED++)) || true
  else
    ((FAILED++)) || true
  fi
done <<< "$BRANCHES"

# ── Add CODEOWNERS file if missing ────────────────────────────────────────────
CODEOWNERS_FILE="$REPO_ROOT/.github/CODEOWNERS"
if [[ ! -f "$CODEOWNERS_FILE" ]]; then
  info "Creating CODEOWNERS file..."
  cat > "$CODEOWNERS_FILE" << 'CODEOWNERS'
# 54Link POS Shell — Code Owners
# These owners are automatically requested for review on PRs.
# See: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners

# Global owners (required for all PRs)
*                           @54link/platform-team

# Security-sensitive files require security team review
server/_core/               @54link/security-team @54link/platform-team
.github/workflows/          @54link/security-team @54link/platform-team
.gitleaks.toml              @54link/security-team
scripts/rotate-secrets.sh   @54link/security-team
scripts/bootstrap-production.sh @54link/security-team

# Financial logic requires fintech team review
server/routers/transactions.ts  @54link/fintech-team @54link/platform-team
server/routers/settlement.ts    @54link/fintech-team @54link/platform-team
server/routers/agentManagement.ts @54link/fintech-team

# CBN compliance requires compliance team review
services/python/cbn-reporting-engine/ @54link/compliance-team @54link/platform-team
server/routers/cbnReporting.ts        @54link/compliance-team

# MDM requires device team review
server/routers/mdm.ts              @54link/device-team @54link/platform-team
services/go/mdm-compliance-engine/ @54link/device-team
android-native/                    @54link/device-team

# Database schema changes require DBA review
drizzle/schema.ts   @54link/dba-team @54link/platform-team
drizzle/            @54link/dba-team

# Infrastructure changes require DevOps review
docker-compose*.yml     @54link/devops-team
infra/                  @54link/devops-team
monitoring/             @54link/devops-team
nginx.conf              @54link/devops-team
CODEOWNERS

  success "CODEOWNERS file created"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                    Setup Complete                            ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Branches processed: ${BOLD}$TOTAL${NC}"
echo -e "  Applied:            ${GREEN}${BOLD}$APPLIED${NC}"
[[ $FAILED -gt 0 ]] && echo -e "  Failed:             ${RED}${BOLD}$FAILED${NC}"
echo ""

if [[ "$DRY_RUN" == "false" ]]; then
  echo -e "${BOLD}Next steps:${NC}"
  echo "  1. Verify rules in GitHub → Settings → Branches"
  echo "  2. Add SNYK_TOKEN to GitHub → Settings → Secrets → Actions"
  echo "  3. Invite team members to @54link/security-team, @54link/fintech-team, etc."
  echo "  4. Enable 'Require signed commits' in GitHub UI (Settings → Branches)"
  echo ""
fi

[[ $FAILED -gt 0 ]] && exit 1 || exit 0
