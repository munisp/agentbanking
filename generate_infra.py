#!/usr/bin/env python3
"""
Generate Helm charts and APISIX routes for services missing them.

- Helm chart: Scaffold with standard account-service template
- APISIX route: Standard path-prefix pattern at /{service-name}/*
"""
import os
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
CHARTS_DIR = os.path.join(BASE, "infrastructure/charts")
ROUTES_DIR = os.path.join(BASE, "infrastructure/apisix-resources/routes")
SERVICES_DIR = os.path.join(BASE, "services")
TEMPLATE_CHART = "account-service"

DEPLOYABLE_MARKERS = [
    "Dockerfile", "main.go", "go.mod", "main.py",
    "pyproject.toml", "package.json", "index.ts", "index.js",
    "requirements.txt",
]

# Skip these entirely — they're gateways, infra, shared libs, or mobile apps
SKIP_CHART = {
    "api-gateway", "apisix-gateway", "infrastructure", "shared",
    "scripts", "android-native", "ios-native", "blockchain",
    "dapr-sidecar", "postgres-production", "database",
    # underscore duplicates of hyphenated versions
    "agent_embedded_finance", "agent_scorecard",
}

# Skip APISIX routes for these — internal infra, mobile, or already have subdomain routes
SKIP_ROUTE = {
    "api-gateway", "apisix-gateway", "infrastructure", "shared",
    "scripts", "android-native", "ios-native", "blockchain",
    "dapr-sidecar", "postgres-production", "database",
    "agent_embedded_finance", "agent_scorecard",
    # UI apps that use subdomain-based routing
    "agent-dashboard", "admin-dashboard", "customer-portal",
    "verification-ui", "agent-business-dashboard",
    "analytics-dashboard", "monitoring-dashboard",
}


def is_deployable(svc_dir: str) -> bool:
    return any(os.path.exists(os.path.join(svc_dir, m)) for m in DEPLOYABLE_MARKERS)


def generate_chart(svc: str) -> None:
    chart_dir = os.path.join(CHARTS_DIR, svc)
    tmpl_dir = os.path.join(CHARTS_DIR, TEMPLATE_CHART, "templates")
    os.makedirs(os.path.join(chart_dir, "templates"), exist_ok=True)

    # Chart.yaml
    with open(os.path.join(chart_dir, "Chart.yaml"), "w") as f:
        f.write(f"apiVersion: v2\n"
                f"name: {svc}\n"
                f"description: 54agent {svc} Helm Chart\n"
                f"type: application\n"
                f"version: 0.0.1\n"
                f'appVersion: "1.0.0"\n')

    # values.yaml
    with open(os.path.join(chart_dir, "values.yaml"), "w") as f:
        f.write(
            f"replicaCount: 1\n"
            f"image:\n"
            f"  repository: registry.digitalocean.com/talentgraph-auth/54agent-{svc}\n"
            f"  pullPolicy: IfNotPresent\n"
            f"  tag: 0.0.1\n"
            f'nameOverride: ""\n'
            f'fullnameOverride: ""\n'
            f"serviceAccount:\n"
            f"  create: false\n"
            f"  name: 54agent\n"
            f"podAnnotations: {{}}\n"
            f"podLabels: {{}}\n"
            f"podSecurityContext: {{}}\n"
            f"securityContext: {{}}\n"
            f"service:\n"
            f"  type: ClusterIP\n"
            f"  port: 80\n"
            f"  targetPort: 80\n"
            f"resources:\n"
            f"  requests:\n"
            f"    cpu: 100m\n"
            f"    memory: 128Mi\n"
            f"  limits:\n"
            f"    cpu: 250m\n"
            f"    memory: 500Mi\n"
            f"autoscaling:\n"
            f"  enabled: true\n"
            f"  minReplicas: 2\n"
            f"  maxReplicas: 10\n"
            f"  targetCPUUtilizationPercentage: 70\n"
            f"livenessProbe:\n"
            f"  httpGet:\n"
            f"    path: /health\n"
            f"    port: http\n"
            f"  initialDelaySeconds: 30\n"
            f"  periodSeconds: 30\n"
            f"  failureThreshold: 3\n"
            f"  timeoutSeconds: 5\n"
            f"readinessProbe:\n"
            f"  httpGet:\n"
            f"    path: /health\n"
            f"    port: http\n"
            f"  initialDelaySeconds: 15\n"
            f"  periodSeconds: 10\n"
            f"  failureThreshold: 3\n"
            f"  timeoutSeconds: 5\n"
            f"volumes: []\n"
            f"volumeMounts: []\n"
            f"nodeSelector: {{}}\n"
            f"tolerations: []\n"
            f"affinity: {{}}\n"
            f"dapr:\n"
            f"  appId: {svc}\n"
            f"  appPort: 80\n"
            f"  enableMetrics: true\n"
            f"  enabled: true\n"
            f"  metricsPort: 9099\n"
            f'  sidecarListenAddresses: "0.0.0.0"\n'
            f"  cpu-request: 100m\n"
            f"  cpu-limit: 300m\n"
            f"  memory-request: 250Mi\n"
            f"  memory-limit: 1000Mi\n"
            f"secrets: {{}}\n"
        )

    # Template files — substitute "account-service" → svc throughout
    for tmpl in ["_helpers.tpl", "deployment.yaml", "service.yaml",
                 "secret.yaml", "serviceaccount.yaml"]:
        src = os.path.join(tmpl_dir, tmpl)
        if not os.path.exists(src):
            continue
        with open(src) as f:
            content = f.read()
        content = content.replace("account-service", svc)
        with open(os.path.join(chart_dir, "templates", tmpl), "w") as f:
            f.write(content)


def generate_route(svc: str) -> None:
    route_path = os.path.join(ROUTES_DIR, f"{svc}.yaml")
    with open(route_path, "w") as f:
        f.write(
            f"# {svc}\n"
            f"apiVersion: apisix.apache.org/v2\n"
            f"kind: ApisixRoute\n"
            f"metadata:\n"
            f"  name: 54agent-{svc}-route\n"
            f"  namespace: 54agent\n"
            f"spec:\n"
            f"  ingressClassName: apisix\n"
            f"  http:\n"
            f"    - name: rule-1\n"
            f"      priority: 10\n"
            f"      match:\n"
            f"        hosts:\n"
            f"          - 54agent.upi.dev\n"
            f"        paths:\n"
            f"          - /{svc}/*\n"
            f"      backends:\n"
            f"        - serviceName: {svc}\n"
            f"          servicePort: 80\n"
            f"      plugins:\n"
            f"        - name: proxy-rewrite\n"
            f"          enable: true\n"
            f"          config:\n"
            f"            regex_uri:\n"
            f'              - "^/{svc}/(.*)"\n'
            f'              - "/$1"\n'
            f"        - name: cors\n"
            f"          enable: true\n"
            f"          config:\n"
            f'            allow_origins: "*"\n'
            f'            allow_methods: "*"\n'
            f'            allow_headers: "*"\n'
            f'            expose_headers: "*"\n'
            f"        - name: limit-req\n"
            f"          enable: true\n"
            f"          config:\n"
            f"            rate: 30\n"
            f"            burst: 15\n"
            f'            key: "remote_addr"\n'
        )


charts_created = []
routes_created = []
skipped = []

# ── Step 1: process every service directory ───────────────────────────────────
for svc in sorted(os.listdir(SERVICES_DIR)):
    svc_dir = os.path.join(SERVICES_DIR, svc)
    if not os.path.isdir(svc_dir):
        continue

    if svc in SKIP_CHART:
        skipped.append(svc)
        continue

    if not is_deployable(svc_dir):
        skipped.append(f"{svc} (not deployable)")
        continue

    if not os.path.isdir(os.path.join(CHARTS_DIR, svc)):
        generate_chart(svc)
        charts_created.append(svc)

    if svc not in SKIP_ROUTE and not os.path.exists(os.path.join(ROUTES_DIR, f"{svc}.yaml")):
        generate_route(svc)
        routes_created.append(svc)

# ── Step 2: routes for existing charts that have no route ────────────────────
for chart in sorted(os.listdir(CHARTS_DIR)):
    if chart in SKIP_ROUTE:
        continue
    if not os.path.exists(os.path.join(ROUTES_DIR, f"{chart}.yaml")):
        generate_route(chart)
        routes_created.append(f"{chart} (from existing chart)")

# ── Step 3: charts for routes that reference services without charts ──────────
# Only services that are not the deprecated placeholder and have no service dir
route_only_svcs = {
    "transaction-ledger-rust",  # has route, no service dir, needs chart
    "compliance-kyc",           # has route, service dir found, covered by step 1 if deployable
}
for svc in route_only_svcs:
    route_file = os.path.join(ROUTES_DIR, f"{svc}.yaml")
    chart_dir = os.path.join(CHARTS_DIR, svc)
    if os.path.exists(route_file) and not os.path.isdir(chart_dir):
        generate_chart(svc)
        charts_created.append(f"{svc} (from existing route)")

print(f"\nHelm charts created : {len(charts_created)}")
for s in charts_created:
    print(f"  + {s}")

print(f"\nAPISIX routes created: {len(routes_created)}")
for s in routes_created:
    print(f"  + {s}")

print(f"\nSkipped: {len(skipped)}")
