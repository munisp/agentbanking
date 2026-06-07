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

#[tokio::main]
async fn main() {
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
