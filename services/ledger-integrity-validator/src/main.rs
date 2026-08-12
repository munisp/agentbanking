use std::collections::HashMap;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use std::thread;
use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, Deserialize)]
struct AccountBalance {
    account_id: String,
    balance: i64,
    currency: String,
    last_updated: DateTime<Utc>,
}

#[derive(Debug, Serialize)]
struct IntegrityReport {
    timestamp: DateTime<Utc>,
    total_accounts: usize,
    matched_accounts: usize,
    drifted_accounts: usize,
    total_drift_amount: i64,
    validation_status: String,
    drift_details: Vec<DriftDetail>,
    hash: String,
}

#[derive(Debug, Serialize)]
struct DriftDetail {
    account_id: String,
    tigerbeetle_balance: i64,
    postgres_balance: i64,
    drift_amount: i64,
    drift_percentage: f64,
}

fn main() {
    println!("🔍 Ledger Integrity Validator starting...");
    
    let redis_url = std::env::var("REDIS_URL").unwrap_or_else(|_| "redis://localhost:6379".to_string());
    let check_interval = std::env::var("CHECK_INTERVAL_SECONDS")
        .unwrap_or_else(|_| "300".to_string())
        .parse::<u64>()
        .unwrap_or(300);
    
    println!("📡 Connecting to Redis at: {}", redis_url);
    println!("⏰ Validation interval: {} seconds", check_interval);
    
    loop {
        match run_validation_cycle(&redis_url) {
            Ok(report) => {
                println!("✅ Validation completed: {} accounts checked, {} matched, {} drifted", 
                         report.total_accounts, report.matched_accounts, report.drifted_accounts);
                
                if report.drifted_accounts > 0 {
                    println!("🚨 DRIFT DETECTED! Total drift: {} kobo", report.total_drift_amount);
                    send_drift_alert(&redis_url, &report);
                }
            },
            Err(e) => {
                println!("❌ Validation error: {}", e);
                // Never pass silently — emit a validation-failed alert.
                send_failure_alert(&redis_url, &e);
            }
        }
        
        thread::sleep(Duration::from_secs(check_interval));
    }
}

fn run_validation_cycle(redis_url: &str) -> Result<IntegrityReport, String> {
    println!("🔍 Starting validation cycle...");
    
    // Fetch balances from both real sources. If either is unreachable the
    // validation fails loudly — it never passes by default.
    let postgres_balances = fetch_postgres_balances()
        .map_err(|e| format!("postgres source unavailable: {}", e))?;
    let tigerbeetle_balances = fetch_tigerbeetle_balances(&postgres_balances)
        .map_err(|e| format!("tigerbeetle source unavailable: {}", e))?;
    
    if tigerbeetle_balances.is_empty() && postgres_balances.is_empty() {
        return Err("both ledger sources returned zero accounts".to_string());
    }
    
    let mut drift_details = Vec::new();
    let mut total_drift = 0i64;
    let mut matched = 0usize;
    
    for (account_id, pg_balance) in &postgres_balances {
        let tb_balance = tigerbeetle_balances.get(account_id).copied().unwrap_or(0);
        let drift = pg_balance - tb_balance;
        
        if drift != 0 {
            let drift_pct = if *pg_balance != 0 {
                (drift as f64 / *pg_balance as f64) * 100.0
            } else { 100.0 };
            
            drift_details.push(DriftDetail {
                account_id: account_id.clone(),
                tigerbeetle_balance: tb_balance,
                postgres_balance: *pg_balance,
                drift_amount: drift,
                drift_percentage: drift_pct,
            });
            total_drift += drift.abs();
        } else {
            matched += 1;
        }
    }
    
    let status = if drift_details.is_empty() { "VALID" } else { "DRIFT_DETECTED" };
    
    let report = IntegrityReport {
        timestamp: Utc::now(),
        total_accounts: postgres_balances.len(),
        matched_accounts: matched,
        drifted_accounts: drift_details.len(),
        total_drift_amount: total_drift,
        validation_status: status.to_string(),
        drift_details,
        hash: calculate_report_hash(&postgres_balances, &tigerbeetle_balances),
    };
    
    store_report(redis_url, &report)?;
    Ok(report)
}

// fetch_tigerbeetle_balances queries the real TigerBeetle HTTP facade
// (tigerbeetle-core) for every account known to Postgres. Any account whose
// balance cannot be read fails the whole validation.
fn fetch_tigerbeetle_balances(pg_balances: &HashMap<String, i64>) -> Result<HashMap<String, i64>, String> {
    let tb_url = std::env::var("TIGERBEETLE_HTTP_URL")
        .or_else(|_| std::env::var("TIGERBEETLE_CORE_URL"))
        .map_err(|_| "TIGERBEETLE_HTTP_URL/TIGERBEETLE_CORE_URL not set".to_string())?;
    let base = tb_url.trim_end_matches('/').to_string();
    
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(15))
        .build()
        .map_err(|e| e.to_string())?;
    
    let mut balances = HashMap::new();
    for account_id in pg_balances.keys() {
        let numeric_id: u64 = match account_id.parse() {
            Ok(v) => v,
            Err(_) => {
                println!("⚠️  Skipping non-TigerBeetle account id '{}' (not numeric)", account_id);
                continue;
            }
        };
        #[derive(Deserialize)]
        struct BalanceResponse { balance: i64 }
        let url = format!("{}/api/v1/accounts/{}/balance", base, numeric_id);
        let resp = client.get(&url).send().map_err(|e| format!("{}: {}", url, e))?;
        if !resp.status().is_success() {
            return Err(format!("tigerbeetle balance lookup failed for account {}: HTTP {}", account_id, resp.status()));
        }
        let body: BalanceResponse = resp.json().map_err(|e| e.to_string())?;
        balances.insert(account_id.clone(), body.balance);
    }
    
    if balances.is_empty() && !pg_balances.is_empty() {
        return Err("no tigerbeetle-mapped accounts could be read".to_string());
    }
    Ok(balances)
}

// fetch_postgres_balances queries the real Postgres billing ledger balances.
fn fetch_postgres_balances() -> Result<HashMap<String, i64>, String> {
    let pg_url = std::env::var("POSTGRES_URL")
        .or_else(|_| std::env::var("DATABASE_URL"))
        .map_err(|_| "POSTGRES_URL/DATABASE_URL not set".to_string())?;
    
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| e.to_string())?;
    
    runtime.block_on(async move {
        let (client, connection) = tokio_postgres::connect(&pg_url, tokio_postgres::NoTls)
            .await
            .map_err(|e| format!("connect: {}", e))?;
        tokio::spawn(async move {
            if let Err(e) = connection.await {
                eprintln!("postgres connection error: {}", e);
            }
        });
        
        let rows = client
            .query(
                "SELECT account_id, COALESCE(SUM(amount), 0)::bigint \
                 FROM platform_billing_ledger GROUP BY account_id",
                &[],
            )
            .await
            .map_err(|e| format!("query: {}", e))?;
        
        let mut balances = HashMap::new();
        for row in rows {
            let account_id: String = row.get(0);
            let balance: i64 = row.get(1);
            balances.insert(account_id, balance);
        }
        Ok(balances)
    })
}

fn calculate_report_hash(pg: &HashMap<String, i64>, tb: &HashMap<String, i64>) -> String {
    use sha2::{Sha256, Digest};
    let mut hasher = Sha256::new();
    let mut accounts: Vec<_> = pg.keys().collect();
    accounts.sort();
    for account in accounts {
        hasher.update(account.as_bytes());
        hasher.update(pg[account].to_be_bytes());
        hasher.update(tb.get(account).unwrap_or(&0).to_be_bytes());
    }
    hex::encode(hasher.finalize())
}

fn store_report(redis_url: &str, report: &IntegrityReport) -> Result<(), String> {
    let client = redis::Client::open(redis_url).map_err(|e| e.to_string())?;
    let mut conn = client.get_connection().map_err(|e| e.to_string())?;
    
    let report_json = serde_json::to_string(report).map_err(|e| e.to_string())?;
    let timestamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
    
    let _: () = redis::cmd("SET")
        .arg("ledger_integrity:latest")
        .arg(&report_json)
        .query(&mut conn)
        .map_err(|e| e.to_string())?;
    
    let _: () = redis::cmd("ZADD")
        .arg("ledger_integrity:history")
        .arg(timestamp)
        .arg(&report_json)
        .query(&mut conn)
        .map_err(|e| e.to_string())?;
    
    Ok(())
}

fn send_drift_alert(redis_url: &str, report: &IntegrityReport) {
    let client = redis::Client::open(redis_url).unwrap();
    let mut conn = client.get_connection().unwrap();
    
    let alert = serde_json::json!({
        "type": "LEDGER_DRIFT_ALERT",
        "severity": "CRITICAL",
        "timestamp": report.timestamp,
        "drift_amount": report.total_drift_amount,
        "drifted_accounts": report.drifted_accounts,
        "report_hash": report.hash,
    });
    
    let _: () = redis::cmd("PUBLISH")
        .arg("ledger_alerts")
        .arg(alert.to_string())
        .query(&mut conn)
        .unwrap();
}

// send_failure_alert emits a validation-failed alert when a source is
// unreachable — the validator never silently skips a cycle.
fn send_failure_alert(redis_url: &str, error: &str) {
    if let Ok(client) = redis::Client::open(redis_url) {
        if let Ok(mut conn) = client.get_connection() {
            let alert = serde_json::json!({
                "type": "LEDGER_VALIDATION_FAILED",
                "severity": "CRITICAL",
                "timestamp": Utc::now(),
                "error": error,
            });
            let _: Result<(), _> = redis::cmd("PUBLISH")
                .arg("ledger_alerts")
                .arg(alert.to_string())
                .query(&mut conn);
        }
    }
}
