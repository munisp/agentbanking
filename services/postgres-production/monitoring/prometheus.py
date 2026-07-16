#!/usr/bin/env python3
"""
Prometheus Metrics Exporter for PostgreSQL
Exports database metrics for monitoring
"""

from typing import Any, Dict, List, Optional, Union, Tuple

from prometheus_client import start_http_server, Gauge, Counter, Histogram
from sqlalchemy import text
import time
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.database import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define metrics
db_connections_active = Gauge('postgres_connections_active', 'Number of active database connections')
db_connections_idle = Gauge('postgres_connections_idle', 'Number of idle database connections')
db_connections_total = Gauge('postgres_connections_total', 'Total number of database connections')

db_size_bytes = Gauge('postgres_database_size_bytes', 'Database size in bytes')
db_table_count = Gauge('postgres_table_count', 'Number of tables in database')

user_count_total = Gauge('postgres_users_total', 'Total number of users')
user_count_active = Gauge('postgres_users_active', 'Number of active users')
user_count_verified = Gauge('postgres_users_verified', 'Number of KYC verified users')

pix_keys_total = Gauge('postgres_pix_keys_total', 'Total number of PIX keys')
pix_keys_active = Gauge('postgres_pix_keys_active', 'Number of active PIX keys')

transfers_total = Counter('postgres_transfers_total', 'Total number of transfers')
transfers_completed = Counter('postgres_transfers_completed', 'Number of completed transfers')
transfers_failed = Counter('postgres_transfers_failed', 'Number of failed transfers')

cdc_events_total = Counter('postgres_cdc_events_total', 'Total CDC events')
cdc_events_processed = Counter('postgres_cdc_events_processed', 'Processed CDC events')
cdc_events_pending = Gauge('postgres_cdc_events_pending', 'Pending CDC events')

query_duration = Histogram('postgres_query_duration_seconds', 'Query execution time')


class PostgreSQLMetricsExporter:
    """Export PostgreSQL metrics to Prometheus"""
    
    def __init__(self, db_manager) -> None:
        self.db = db_manager
    
    def collect_connection_metrics(self) -> None:
        """Collect connection pool metrics"""
        try:
            with self.db.get_session() as session:
                # Active connections
                result = session.execute(text("""
                    SELECT count(*) FROM pg_stat_activity 
                    WHERE state = 'active' AND datname = current_database()
                """))
                db_connections_active.set(result.scalar())
                
                # Idle connections
                result = session.execute(text("""
                    SELECT count(*) FROM pg_stat_activity 
                    WHERE state = 'idle' AND datname = current_database()
                """))
                db_connections_idle.set(result.scalar())
                
                # Total connections
                result = session.execute(text("""
                    SELECT count(*) FROM pg_stat_activity 
                    WHERE datname = current_database()
                """))
                db_connections_total.set(result.scalar())
        
        except Exception as e:
            logger.error(f"Error collecting connection metrics: {e}")
    
    def collect_database_metrics(self) -> None:
        """Collect database size and table metrics"""
        try:
            with self.db.get_session() as session:
                # Database size
                result = session.execute(text("""
                    SELECT pg_database_size(current_database())
                """))
                db_size_bytes.set(result.scalar())
                
                # Table count
                result = session.execute(text("""
                    SELECT count(*) FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """))
                db_table_count.set(result.scalar())
        
        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
    
    def collect_user_metrics(self) -> None:
        """Collect user metrics"""
        try:
            with self.db.get_session() as session:
                # Total users
                result = session.execute(text("SELECT count(*) FROM users"))
                user_count_total.set(result.scalar())
                
                # Active users
                result = session.execute(text("""
                    SELECT count(*) FROM users WHERE is_active = true
                """))
                user_count_active.set(result.scalar())
                
                # Verified users
                result = session.execute(text("""
                    SELECT count(*) FROM users WHERE kyc_status = 'verified'
                """))
                user_count_verified.set(result.scalar())
        
        except Exception as e:
            logger.error(f"Error collecting user metrics: {e}")
    
    def collect_pix_key_metrics(self) -> None:
        """Collect PIX key metrics"""
        try:
            with self.db.get_session() as session:
                # Total PIX keys
                result = session.execute(text("SELECT count(*) FROM pix_keys"))
                pix_keys_total.set(result.scalar())
                
                # Active PIX keys
                result = session.execute(text("""
                    SELECT count(*) FROM pix_keys WHERE is_active = true
                """))
                pix_keys_active.set(result.scalar())
        
        except Exception as e:
            logger.error(f"Error collecting PIX key metrics: {e}")
    
    def collect_transfer_metrics(self) -> None:
        """Collect transfer metrics"""
        try:
            with self.db.get_session() as session:
                # Total transfers
                result = session.execute(text("SELECT count(*) FROM transfer_metadata"))
                count = result.scalar()
                transfers_total._value.set(count)
                
                # Completed transfers
                result = session.execute(text("""
                    SELECT count(*) FROM transfer_metadata WHERE status = 'completed'
                """))
                count = result.scalar()
                transfers_completed._value.set(count)
                
                # Failed transfers
                result = session.execute(text("""
                    SELECT count(*) FROM transfer_metadata WHERE status = 'failed'
                """))
                count = result.scalar()
                transfers_failed._value.set(count)
        
        except Exception as e:
            logger.error(f"Error collecting transfer metrics: {e}")
    
    def collect_cdc_metrics(self) -> None:
        """Collect CDC event metrics"""
        try:
            with self.db.get_session() as session:
                # Total CDC events
                result = session.execute(text("SELECT count(*) FROM cdc_events"))
                count = result.scalar()
                cdc_events_total._value.set(count)
                
                # Processed events
                result = session.execute(text("""
                    SELECT count(*) FROM cdc_events WHERE processed = true
                """))
                count = result.scalar()
                cdc_events_processed._value.set(count)
                
                # Pending events
                result = session.execute(text("""
                    SELECT count(*) FROM cdc_events WHERE processed = false
                """))
                cdc_events_pending.set(result.scalar())
        
        except Exception as e:
            logger.error(f"Error collecting CDC metrics: {e}")
    
    def collect_all_metrics(self) -> None:
        """Collect all metrics"""
        start_time = time.time()
        
        self.collect_connection_metrics()
        self.collect_database_metrics()
        self.collect_user_metrics()
        self.collect_pix_key_metrics()
        self.collect_transfer_metrics()
        self.collect_cdc_metrics()
        
        duration = time.time() - start_time
        query_duration.observe(duration)
        
        logger.info(f"Metrics collected in {duration:.3f}s")


def main() -> None:
    """Main entry point"""
    # Initialize database
    db_manager = DatabaseManager()
    db_manager.initialize()
    
    # Create exporter
    exporter = PostgreSQLMetricsExporter(db_manager)
    
    # Start Prometheus HTTP server
    port = int(os.getenv('METRICS_PORT', '9090'))
    start_http_server(port)
    logger.info(f"🚀 Prometheus metrics server started on port {port}")
    logger.info(f"📊 Metrics available at http://localhost:{port}/metrics")
    
    # Collect metrics every 15 seconds
    try:
        while True:
            exporter.collect_all_metrics()
            time.sleep(15)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down metrics exporter...")
        db_manager.close()


if __name__ == '__main__':
    main()

