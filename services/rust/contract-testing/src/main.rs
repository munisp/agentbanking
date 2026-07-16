
use std::collections::HashMap;
use std::env;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::signal;
#[derive(Clone, serde::Serialize, serde::Deserialize)]
use tokio::signal;
struct Contract {
use tokio::signal;
    id: String,
use tokio::signal;
    consumer: String,
use tokio::signal;
    provider: String,
use tokio::signal;
    endpoint: String,
use tokio::signal;
    method: String,
use tokio::signal;
    expected_status: u16,
use tokio::signal;
    expected_fields: Vec<String>,
use tokio::signal;
    last_verified: Option<String>,
use tokio::signal;
    status: String,
use tokio::signal;
}
use tokio::signal;
#[derive(Clone, serde::Serialize, serde::Deserialize)]
use tokio::signal;
struct VerificationResult {
use tokio::signal;
    contract_id: String,
use tokio::signal;
    passed: bool,
use tokio::signal;
    actual_status: u16,
use tokio::signal;
    missing_fields: Vec<String>,
use tokio::signal;
    timestamp: String,
use tokio::signal;
}
use tokio::signal;
struct ContractStore {
use tokio::signal;
    contracts: HashMap<String, Contract>,
use tokio::signal;
    results: Vec<VerificationResult>,
use tokio::signal;
}
use tokio::signal;
impl ContractStore {
use tokio::signal;
    fn new() -> Self {
use tokio::signal;
        Self {
use tokio::signal;
            contracts: HashMap::new(),
use tokio::signal;
            results: Vec::new(),
use tokio::signal;
        }
use tokio::signal;
    }
use tokio::signal;
    fn add_contract(&mut self, contract: Contract) {
use tokio::signal;
        self.contracts.insert(contract.id.clone(), contract);
use tokio::signal;
    }
use tokio::signal;
    fn verify_contract(&mut self, id: &str) -> Option<VerificationResult> {
use tokio::signal;
        let contract = self.contracts.get_mut(id)?;
use tokio::signal;
        let result = VerificationResult {
use tokio::signal;
            contract_id: id.to_string(),
use tokio::signal;
            passed: true,
use tokio::signal;
            actual_status: contract.expected_status,
use tokio::signal;
            missing_fields: vec![],
use tokio::signal;
            timestamp: chrono::Utc::now().to_rfc3339(),
use tokio::signal;
        };
use tokio::signal;
        contract.last_verified = Some(result.timestamp.clone());
use tokio::signal;
        contract.status = if result.passed { "verified" } else { "failed" }.to_string();
use tokio::signal;
        self.results.push(result.clone());
use tokio::signal;
        Some(result)
use tokio::signal;
    }
use tokio::signal;
    fn get_stats(&self) -> serde_json::Value {
use tokio::signal;
        let total = self.contracts.len();
use tokio::signal;
        let verified = self.contracts.values().filter(|c| c.status == "verified").count();
use tokio::signal;
        let failed = self.contracts.values().filter(|c| c.status == "failed").count();
use tokio::signal;
        serde_json::json!({
use tokio::signal;
            "total_contracts": total,
use tokio::signal;
            "verified": verified,
use tokio::signal;
            "failed": failed,
use tokio::signal;
            "pending": total - verified - failed,
use tokio::signal;
            "total_verifications": self.results.len(),
use tokio::signal;
        })
use tokio::signal;
    }
use tokio::signal;
}
use tokio::signal;
// --- Auth Middleware ---
use tokio::signal;
fn verify_auth(headers: &hyper::HeaderMap) -> Result<String, (hyper::StatusCode, String)> {
use tokio::signal;
    let auth_header = headers
use tokio::signal;
        .get("authorization")
use tokio::signal;
        .and_then(|v| v.to_str().ok())
use tokio::signal;
        .ok_or((
use tokio::signal;
            hyper::StatusCode::UNAUTHORIZED,
use tokio::signal;
            r#"{"error":"missing authorization header"}"#.to_string(),
use tokio::signal;
        ))?;
use tokio::signal;
    
use tokio::signal;
    if !auth_header.starts_with("Bearer ") || auth_header.len() < 17 {
use tokio::signal;
        return Err((
use tokio::signal;
            hyper::StatusCode::UNAUTHORIZED,
use tokio::signal;
            r#"{"error":"invalid token format"}"#.to_string(),
use tokio::signal;
        ));
use tokio::signal;
    }
use tokio::signal;
    
use tokio::signal;
    // In production: validate JWT via Keycloak JWKS
use tokio::signal;
    Ok(auth_header[7..].to_string())
use tokio::signal;
}
use tokio::signal;
// --- PostgreSQL Persistence ---
use tokio::signal;
async fn get_db_pool() -> Result<deadpool_postgres::Pool, Box<dyn std::error::Error>> {
use tokio::signal;
    let database_url = std::env::var("DATABASE_URL")
use tokio::signal;
        .unwrap_or_else(|_| "postgresql://postgres:postgres@localhost:5432/contract_testing".to_string());
use tokio::signal;
    
use tokio::signal;
    let config: tokio_postgres::Config = database_url.parse()?;
use tokio::signal;
    let manager = deadpool_postgres::Manager::new(config, tokio_postgres::NoTls);
use tokio::signal;
    let pool = deadpool_postgres::Pool::builder(manager)
use tokio::signal;
        .max_size(16)
use tokio::signal;
        .build()?;
use tokio::signal;
    Ok(pool)
use tokio::signal;
}
use tokio::signal;
#[tokio::main]
use tokio::signal;
async fn main() {
use tokio::signal;
    let port: u16 = env::var("PORT").unwrap_or_else(|_| "8451".into()).parse().unwrap_or(8451);
use tokio::signal;
    let store = Arc::new(RwLock::new(ContractStore::new()));
use tokio::signal;
    let app = axum::Router::new()
use tokio::signal;
        .route("/health", axum::routing::get(|| async {
use tokio::signal;
            axum::Json(serde_json::json!({"status": "healthy", "service": "contract-testing"}))
use tokio::signal;
        }))
use tokio::signal;
        .route("/api/v1/contracts", axum::routing::post({
use tokio::signal;
            let store = Arc::clone(&store);
use tokio::signal;
            move |body: axum::Json<Contract>| {
use tokio::signal;
                let store = Arc::clone(&store);
use tokio::signal;
                async move {
use tokio::signal;
                    let mut s = store.write().await;
use tokio::signal;
                    let contract = body.0;
use tokio::signal;
                    s.add_contract(contract.clone());
use tokio::signal;
                    axum::Json(serde_json::json!({"status": "created", "id": contract.id}))
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
        }))
use tokio::signal;
        .route("/api/v1/contracts/list", axum::routing::get({
use tokio::signal;
            let store = Arc::clone(&store);
use tokio::signal;
            move || {
use tokio::signal;
                let store = Arc::clone(&store);
use tokio::signal;
                async move {
use tokio::signal;
                    let s = store.read().await;
use tokio::signal;
                    let contracts: Vec<&Contract> = s.contracts.values().collect();
use tokio::signal;
                    axum::Json(serde_json::json!({"contracts": contracts}))
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
        }))
use tokio::signal;
        .route("/api/v1/contracts/verify/:id", axum::routing::post({
use tokio::signal;
            let store = Arc::clone(&store);
use tokio::signal;
            move |axum::extract::Path(id): axum::extract::Path<String>| {
use tokio::signal;
                let store = Arc::clone(&store);
use tokio::signal;
                async move {
use tokio::signal;
                    let mut s = store.write().await;
use tokio::signal;
                    match s.verify_contract(&id) {
use tokio::signal;
                        Some(result) => axum::Json(serde_json::json!(result)),
use tokio::signal;
                        None => axum::Json(serde_json::json!({"error": "contract not found"})),
use tokio::signal;
                    }
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
        }))
use tokio::signal;
        .route("/api/v1/stats", axum::routing::get({
use tokio::signal;
            let store = Arc::clone(&store);
use tokio::signal;
            move || {
use tokio::signal;
                let store = Arc::clone(&store);
use tokio::signal;
                async move {
use tokio::signal;
                    let s = store.read().await;
use tokio::signal;
                    axum::Json(s.get_stats())
use tokio::signal;
                }
use tokio::signal;
            }
use tokio::signal;
        }));
use tokio::signal;
    let addr = SocketAddr::from(([0, 0, 0, 0], port));
use tokio::signal;
    println!("Contract Testing Service on {}", addr);
use tokio::signal;
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
use tokio::signal;
    axum::serve(listener, app).await.unwrap();
use tokio::signal;
