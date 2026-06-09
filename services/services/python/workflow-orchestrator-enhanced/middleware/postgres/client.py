"""PostgreSQL client for workflow state persistence"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class PostgreSQLConfig:
    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password

class PostgreSQLClient:
    def __init__(self, config: PostgreSQLConfig):
        self.config = config
        self.conn = psycopg2.connect(
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.user,
            password=config.password
        )

    def save_workflow(self, workflow_id: str, workflow_type: str, status: str, input_data: Dict[str, Any], tenant_id: str, user_id: str) -> None:
        logger.info(f"Saving workflow to PostgreSQL: {workflow_id}")
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflows (workflow_id, workflow_type, status, input_data, tenant_id, user_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (workflow_id) DO UPDATE
                SET status = EXCLUDED.status, updated_at = NOW()
                """,
                (workflow_id, workflow_type, status, psycopg2.extras.Json(input_data), tenant_id, user_id)
            )
        self.conn.commit()

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        logger.info(f"Getting workflow from PostgreSQL: {workflow_id}")
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM workflows WHERE workflow_id = %s", (workflow_id,))
            return dict(cur.fetchone()) if cur.rowcount > 0 else None

    def update_workflow_status(self, workflow_id: str, status: str) -> None:
        logger.info(f"Updating workflow status: {workflow_id} - {status}")
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE workflows SET status = %s, updated_at = NOW() WHERE workflow_id = %s",
                (status, workflow_id)
            )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
