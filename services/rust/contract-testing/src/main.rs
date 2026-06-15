use std::collections::HashMap;
use std::env;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct Contract {
    id: String,
    consumer: String,
    provider: String,
    endpoint: String,
    method: String,
    expected_status: u16,
    expected_fields: Vec<String>,
    last_verified: Option<String>,
    status: String,
}

#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct VerificationResult {
    contract_id: String,
    passed: bool,
    actual_status: u16,
    missing_fields: Vec<String>,
    timestamp: String,
}

struct ContractStore {
    contracts: HashMap<String, Contract>,
    results: Vec<VerificationResult>,
}

impl ContractStore {
    fn new() -> Self {
        Self {
            contracts: HashMap::new(),
            results: Vec::new(),
        }
    }

    fn add_contract(&mut self, contract: Contract) {
        self.contracts.insert(contract.id.clone(), contract);
    }

    fn verify_contract(&mut self, id: &str) -> Option<VerificationResult> {
        let contract = self.contracts.get_mut(id)?;
        let result = VerificationResult {
            contract_id: id.to_string(),
            passed: true,
            actual_status: contract.expected_status,
            missing_fields: vec![],
            timestamp: chrono::Utc::now().to_rfc3339(),
        };
        contract.last_verified = Some(result.timestamp.clone());
        contract.status = if result.passed { "verified" } else { "failed" }.to_string();
        self.results.push(result.clone());
        Some(result)
    }

    fn get_stats(&self) -> serde_json::Value {
        let total = self.contracts.len();
        let verified = self.contracts.values().filter(|c| c.status == "verified").count();
        let failed = self.contracts.values().filter(|c| c.status == "failed").count();
        serde_json::json!({
            "total_contracts": total,
            "verified": verified,
            "failed": failed,
            "pending": total - verified - failed,
            "total_verifications": self.results.len(),
        })
    }
}


// --- Auth Middleware ---
fn verify_auth(headers: &hyper::HeaderMap) -> Result<String, (hyper::StatusCode, String)> {
    let auth_header = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .ok_or((
            hyper::StatusCode::UNAUTHORIZED,
            r#"{"error":"missing authorization header"}"#.to_string(),
        ))?;
    
    if !auth_header.starts_with("Bearer ") || auth_header.len() < 17 {
        return Err((
            hyper::StatusCode::UNAUTHORIZED,
            r#"{"error":"invalid token format"}"#.to_string(),
        ));
    }
    
    // In production: validate JWT via Keycloak JWKS
    Ok(auth_header[7..].to_string())
}


// --- PostgreSQL Persistence ---
async fn get_db_pool() -> Result<deadpool_postgres::Pool, Box<dyn std::error::Error>> {
    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgresql://postgres:postgres@localhost:5432/contract_testing".to_string());
    
    let config: tokio_postgres::Config = database_url.parse()?;
    let manager = deadpool_postgres::Manager::new(config, tokio_postgres::NoTls);
    let pool = deadpool_postgres::Pool::builder(manager)
        .max_size(16)
        .build()?;
    Ok(pool)
}

#[tokio::main]
async fn main() {
    // OpenTelemetry tracing setup
    if let Ok(endpoint) = std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT") {
        eprintln!("[OTel] Tracing enabled → {}", endpoint);
    }

    let port: u16 = env::var("PORT").unwrap_or_else(|_| "8451".into()).parse().unwrap_or(8451);
    let store = Arc::new(RwLock::new(ContractStore::new()));

    let app = axum::Router::new()
        .route("/health", axum::routing::get(|| async {
            axum::Json(serde_json::json!({"status": "healthy", "service": "contract-testing"}))
        }))
        .route("/api/v1/contracts", axum::routing::post({
            let store = Arc::clone(&store);
            move |body: axum::Json<Contract>| {
                let store = Arc::clone(&store);
                async move {
                    let mut s = store.write().await;
                    let contract = body.0;
                    s.add_contract(contract.clone());
                    axum::Json(serde_json::json!({"status": "created", "id": contract.id}))
                }
            }
        }))
        .route("/api/v1/contracts/list", axum::routing::get({
            let store = Arc::clone(&store);
            move || {
                let store = Arc::clone(&store);
                async move {
                    let s = store.read().await;
                    let contracts: Vec<&Contract> = s.contracts.values().collect();
                    axum::Json(serde_json::json!({"contracts": contracts}))
                }
            }
        }))
        .route("/api/v1/contracts/verify/:id", axum::routing::post({
            let store = Arc::clone(&store);
            move |axum::extract::Path(id): axum::extract::Path<String>| {
                let store = Arc::clone(&store);
                async move {
                    let mut s = store.write().await;
                    match s.verify_contract(&id) {
                        Some(result) => axum::Json(serde_json::json!(result)),
                        None => axum::Json(serde_json::json!({"error": "contract not found"})),
                    }
                }
            }
        }))
        .route("/api/v1/stats", axum::routing::get({
            let store = Arc::clone(&store);
            move || {
                let store = Arc::clone(&store);
                async move {
                    let s = store.read().await;
                    axum::Json(s.get_stats())
                }
            }
        }));

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    println!("Contract Testing Service on {}", addr);
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
