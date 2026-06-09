import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
"""
Master Main Application
Registers all 162 microservices with complete routing
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys
import os
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app

# --- PostgreSQL Persistence ---
import asyncpg
from contextlib import asynccontextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/python")
_db_pool = None

async def get_db_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _db_pool

async def close_db_pool():
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None

app = FastAPI(
    title="Remittance Platform - Complete API",
    description="Unified API for all 162 microservices",
    version="1.0.0"
)

from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
apply_middleware(app, enable_auth=True)
setup_logging("agent-banking-platform---complete-api")
app.include_router(metrics_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register all service routers
try:
    # Critical Services (Top 10 - manually implemented)
    from agent_service.router import router as agent_router
    app.include_router(agent_router, tags=["agent-service"])
    logger.info("✅ Registered: agent-service")
except Exception as e:
    logger.warning(f"⚠️  Could not register agent-service: {e}")

try:
    from commission_service.router import router as commission_router
    app.include_router(commission_router, tags=["commission-service"])
    logger.info("✅ Registered: commission-service")
except Exception as e:
    logger.warning(f"⚠️  Could not register commission-service: {e}")

try:
    from transaction_history.router import router as transaction_router
    app.include_router(transaction_router, tags=["transaction-history"])
    logger.info("✅ Registered: transaction-history")
except Exception as e:
    logger.warning(f"⚠️  Could not register transaction-history: {e}")

try:
    from payout_service.router import router as payout_router
    app.include_router(payout_router, tags=["payout-service"])
    logger.info("✅ Registered: payout-service")
except Exception as e:
    logger.warning(f"⚠️  Could not register payout-service: {e}")

try:
    from fraud_detection.router import router as fraud_router
    app.include_router(fraud_router, tags=["fraud-detection"])
    logger.info("✅ Registered: fraud-detection")
except Exception as e:
    logger.warning(f"⚠️  Could not register fraud-detection: {e}")

try:
    from audit_service.router import router as audit_router
    app.include_router(audit_router, tags=["audit-service"])
    logger.info("✅ Registered: audit-service")
except Exception as e:
    logger.warning(f"⚠️  Could not register audit-service: {e}")

try:
    from kyc_service.router import router as kyc_router
    app.include_router(kyc_router, tags=["kyc-service"])
    logger.info("✅ Registered: kyc-service")
except Exception as e:
    logger.warning(f"⚠️  Could not register kyc-service: {e}")

try:
    from compliance_service.router import router as compliance_router
    app.include_router(compliance_router, tags=["compliance-service"])
    logger.info("✅ Registered: compliance-service")
except Exception as e:
    logger.warning(f"⚠️  Could not register compliance-service: {e}")

try:
    from reporting_engine.router import router as reporting_router
    app.include_router(reporting_router, tags=["reporting-engine"])
    logger.info("✅ Registered: reporting-engine")
except Exception as e:
    logger.warning(f"⚠️  Could not register reporting-engine: {e}")

try:
    from email_service.router import router as email_router
    app.include_router(email_router, tags=["email-service"])
    logger.info("✅ Registered: email-service")
except Exception as e:
    logger.warning(f"⚠️  Could not register email-service: {e}")

# Auto-register all services - COMPLETE LIST OF ALL 162 ROUTERS
# This list includes all services with router.py files in the backend/python-services directory
SERVICE_MODULES = [
    # Agent & Hierarchy Services
    "agent_ecommerce_platform", "agent_hierarchy_service", "agent_training",
    "agent_commerce_integration", "agent_performance",
    # AI/ML Services
    "ai_ml_services", "ai_orchestration", "neural_network_service", "gnn_engine",
    "ai_document_validation", "cocoindex_service", "epr_kgqa_service", "ml_engine",
    "ollama_service",
    # E-commerce & Marketplace Services
    "amazon_ebay_integration", "amazon_service", "ecommerce_service", "gaming_integration", "gaming_service",
    "ebay_service", "jumia_service", "konga_service", "marketplace_integration",
    "inventory_management", "metaverse_service",
    # Analytics & Data Services
    "analytics_service", "customer_analytics", "data_warehouse", "etl_pipeline", "unified_analytics",
    "analytics_dashboard", "business_intelligence", "monitoring_dashboard", "monitoring",
    # Communication Services
    "communication_service", "communication_shared", "discord_service", "messenger_service",
    "push_notification_service", "rcs_service", "sms_service", "snapchat_service", "telegram_service",
    "tiktok_service", "translation_service", "unified_communication_hub", "unified_communication_service",
    "voice_ai_service", "voice_assistant_service", "whatsapp_order_service", "whatsapp_service",
    "communication_gateway", "instagram_service", "twitter_service", "wechat_service",
    "whatsapp_ai_bot", "multilingual_integration_service", "notification_service",
    "omnichannel_middleware", "websocket_service", "sms_gateway",
    # Authentication & Security Services
    "authentication_service", "security_monitoring",
    "mfa", "rbac", "security_alert", "background_check",
    # Compliance & KYC/KYB Services
    "compliance_workflows", "kyb_verification", "compliance_kyc",
    "aml_monitoring", "compliance_reporting", "kyc_kyb_service", "kyc_enhanced",
    # Core Banking & Financial Services
    "core_banking", "credit_scoring", "global_payment_gateway", "loyalty_service", "settlement_service",
    "float_service", "loan_management", "payment_gateway", "reconciliation_service",
    "biller_integration", "promotion_service", "investment_service", "recurring_payments",
    "refund_service", "rewards", "rewards_service", "multi_currency_accounts",
    # Payment Integration Services
    "payment", "payment_corridors", "payment_processing",
    "cips_integration", "fps_integration", "nibss_integration", "open_banking",
    "papss_integration", "sepa_instant", "upi_connector", "upi_integration",
    # Stablecoin & DeFi Services
    "stablecoin_defi", "stablecoin_integration", "stablecoin_v2",
    # Integration Services
    "api_gateway", "falkordb_service", "fluvio_streaming", "google_assistant_service", "hierarchy_service",
    "hybrid_engine", "integration_layer", "integrations", "lakehouse_service", "multi_ocr_service",
    "ocr_processing", "offline_sync", "pos_integration", "risk_assessment", "rule_engine",
    "supply_chain", "sync_manager", "territory_management", "tigerbeetle_sync", "tigerbeetle_zig",
    "unified_streaming", "ussd_service", "workflow_orchestration", "workflow_service", "zapier_integration",
    "workflow_integration", "integration_service", "middleware_integration",
    "platform_middleware", "zapier_service", "white_label_api",
    # Customer & Onboarding Services
    "customer_service", "onboarding_service", "user_onboarding_enhanced",
    # Document Services
    "document_management", "document_processing",
    # Dispute & Art Services
    "dispute_resolution", "art_agent_service",
    # Backup & Database Services
    "backup_service", "database", "postgres_production",
    # Device & Edge Services
    "device_management", "edge_computing", "edge_deployment",
    # Geospatial & Territory Services
    "geospatial_service",
    # QR Code & Telco Services
    "qr_code_service", "telco_integration",
    # Reporting & Scheduling Services
    "reporting_service", "scheduler_service",
    # User Management
    "user_management",
    # Platform & Infrastructure Services
    "enhanced_platform", "infrastructure", "performance_optimization",
    # Cross-Border Services
    "cross_border",
    # Transaction Scoring & COA Services
    "transaction_scoring", "chart_of_accounts",
    # Projections & Targets
    "projections_targets",
    # QR Ticket Verification
    "qr_ticket_verification",
    # Admin Services (sub-modules)
    "admin_services",
    # CDP Service
    "cdp_service",
    # Enterprise Services (sub-modules)
    "enterprise_services",
    # Financial Services (sub-modules)
    "financial_services",
    # Payment Gateway Service
    "payment_gateway_service",
    # Security Services (sub-modules)
    "security_services",
]

registered_count = 10  # Already registered 10 critical services
failed_count = 0

for service_module in SERVICE_MODULES:
    try:
        # Convert to proper module name (replace - with _)
        module_name = service_module.replace("-", "_")
        router_module = __import__(f"{module_name}.router", fromlist=['router'])
        router = getattr(router_module, 'router')
        app.include_router(router, tags=[service_module])
        registered_count += 1
        logger.info(f"✅ Registered: {service_module}")
    except Exception as e:
        failed_count += 1
        logger.debug(f"⚠️  Could not register {service_module}: {e}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Remittance Platform API",
        "version": "1.0.0",
        "services_registered": registered_count,
        "services_failed": failed_count,
        "total_services": registered_count + failed_count
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": registered_count
    }

@app.get("/services")
async def list_services():
    """List all registered services"""
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": route.name
            })
    return {
        "total_routes": len(routes),
        "routes": routes
    }


@app.on_event("startup")
async def _startup():
    await get_db_pool()

@app.on_event("shutdown")
async def _shutdown():
    await close_db_pool()

if __name__ == "__main__":
    import uvicorn
    logger.info(f"🚀 Starting Remittance Platform API")
    logger.info(f"📊 Registered Services: {registered_count}")
    logger.info(f"⚠️  Failed Services: {failed_count}")
    uvicorn.run(app, host="0.0.0.0", port=8000)

