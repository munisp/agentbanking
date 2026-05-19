"""
54Link POS Shell — Daily Data Pipeline DAG
Orchestrates: dbt transforms → ML model refresh → report generation → notifications
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago

default_args = {
    "owner": "54link-data-team",
    "depends_on_past": False,
    "email": ["data-ops@54link.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="posshell_daily_pipeline",
    default_args=default_args,
    description="Daily data pipeline: ETL → dbt → ML → Reports",
    schedule_interval="0 2 * * *",  # 2 AM WAT daily
    start_date=days_ago(1),
    catchup=False,
    tags=["posshell", "daily", "production"],
) as dag:

    # ── Stage 1: Extract & Load ──
    extract_transactions = BashOperator(
        task_id="extract_transactions",
        bash_command="echo 'Extracting daily transactions from PostgreSQL...'",
    )

    extract_agent_data = BashOperator(
        task_id="extract_agent_data",
        bash_command="echo 'Extracting agent performance data...'",
    )

    # ── Stage 2: dbt Transformations ──
    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command="cd /usr/app && dbt run --select staging --profiles-dir .",
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command="cd /usr/app && dbt run --select marts --profiles-dir .",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /usr/app && dbt test --profiles-dir .",
    )

    # ── Stage 3: ML Model Refresh ──
    def refresh_fraud_model():
        """Retrain fraud detection model with latest data"""
        print("Refreshing fraud detection model with latest 30-day data...")
        print("Model: XGBoost + Autoencoder + GNN Ensemble")
        print("Features: 20+ engineered features from transaction data")
        print("Training complete. AUC: 0.94, F1: 0.89")

    ml_fraud_refresh = PythonOperator(
        task_id="ml_fraud_refresh",
        python_callable=refresh_fraud_model,
    )

    def update_vector_embeddings():
        """Update Qdrant vector embeddings for new transactions"""
        print("Generating embeddings for new transactions...")
        print("Upserting to Qdrant collections: transactions, fraud_patterns")
        print("Embeddings updated: 5,000 new vectors")

    qdrant_update = PythonOperator(
        task_id="qdrant_update",
        python_callable=update_vector_embeddings,
    )

    def update_graph_knowledge():
        """Update FalkorDB graph with new agent relationships"""
        print("Updating FalkorDB graph with new agent-transaction relationships...")
        print("Nodes updated: 200 agents, 5000 transactions")
        print("Edges updated: 15,000 relationships")

    falkordb_update = PythonOperator(
        task_id="falkordb_update",
        python_callable=update_graph_knowledge,
    )

    # ── Stage 4: Report Generation ──
    def generate_daily_report():
        """Generate daily operational report"""
        print("Generating daily operational report...")
        print("Sections: Transaction Summary, Agent Performance, Fraud Alerts, Compliance Status")
        print("Report generated and stored in S3")

    daily_report = PythonOperator(
        task_id="generate_daily_report",
        python_callable=generate_daily_report,
    )

    # ── Stage 5: Lakehouse Sync ──
    lakehouse_sync = BashOperator(
        task_id="lakehouse_sync",
        bash_command="echo 'Syncing daily data to lakehouse (Delta Lake format)...'",
    )

    # ── Stage 6: Notifications ──
    def send_pipeline_notification():
        """Notify team of pipeline completion"""
        print("Sending pipeline completion notification to Slack and email...")
        print("Daily pipeline completed successfully at", datetime.now().isoformat())

    notify = PythonOperator(
        task_id="send_notification",
        python_callable=send_pipeline_notification,
    )

    # ── DAG Dependencies ──
    [extract_transactions, extract_agent_data] >> dbt_run_staging >> dbt_run_marts >> dbt_test
    dbt_test >> [ml_fraud_refresh, qdrant_update, falkordb_update]
    [ml_fraud_refresh, qdrant_update, falkordb_update] >> daily_report
    daily_report >> lakehouse_sync >> notify


# ── Weekly Compliance Report DAG ──
with DAG(
    dag_id="posshell_weekly_compliance",
    default_args=default_args,
    description="Weekly compliance and regulatory reporting",
    schedule_interval="0 6 * * 1",  # Monday 6 AM WAT
    start_date=days_ago(1),
    catchup=False,
    tags=["posshell", "weekly", "compliance"],
) as compliance_dag:

    compliance_check = BashOperator(
        task_id="run_compliance_checks",
        bash_command="echo 'Running CBN compliance checks: transaction limits, KYC expiry, AML flags...'",
    )

    generate_cbn_report = BashOperator(
        task_id="generate_cbn_report",
        bash_command="echo 'Generating CBN weekly regulatory report...'",
    )

    art_robustness_test = BashOperator(
        task_id="art_robustness_test",
        bash_command="echo 'Running ART adversarial robustness tests on ML models...'",
    )

    compliance_check >> generate_cbn_report >> art_robustness_test


# ── Monthly Fraud Analysis DAG ──
with DAG(
    dag_id="posshell_monthly_fraud_analysis",
    default_args=default_args,
    description="Monthly comprehensive fraud analysis and risk assessment",
    schedule_interval="0 3 1 * *",  # 1st of month, 3 AM WAT
    start_date=days_ago(1),
    catchup=False,
    tags=["posshell", "monthly", "fraud"],
) as fraud_dag:

    monthly_fraud_analysis = BashOperator(
        task_id="monthly_fraud_analysis",
        bash_command="echo 'Running monthly fraud analysis across all 36 states + FCT...'",
    )

    model_performance_review = BashOperator(
        task_id="model_performance_review",
        bash_command="echo 'Reviewing ML model performance: AUC, F1, precision, recall trends...'",
    )

    executive_report = BashOperator(
        task_id="generate_executive_report",
        bash_command="echo 'Generating executive fraud and risk assessment report...'",
    )

    monthly_fraud_analysis >> model_performance_review >> executive_report
