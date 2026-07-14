#!/usr/bin/env python3
"""
CIPS Prometheus Metrics Exporter
Complete monitoring and metrics for CIPS integration
Version: 1.0.0
"""

from prometheus_client import Counter, Histogram, Gauge, Summary, Info, start_http_server
import time
import logging
from typing import Dict, Optional
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CIPSPrometheusMetrics:
    """Prometheus metrics for CIPS integration"""
    
    def __init__(self, port: int = 9090) -> None:
        """
        Initialize Prometheus metrics
        
        Args:
            port: Port to expose metrics on
        """
        self.port = port
        
        # Service info
        self.service_info = Info("cips_service", "CIPS service information")
        self.service_info.info({
            "version": "1.0.0",
            "service": "cips-integration",
            "platform": "nigerian-remittance"
        })
        
        # Request metrics
        self.requests_total = Counter(
            "cips_requests_total",
            "Total number of CIPS requests",
            ["method", "status"]
        )
        
        self.requests_in_progress = Gauge(
            "cips_requests_in_progress",
            "Number of CIPS requests currently in progress",
            ["method"]
        )
        
        self.request_duration_seconds = Histogram(
            "cips_request_duration_seconds",
            "CIPS request duration in seconds",
            ["method"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        
        self.request_size_bytes = Summary(
            "cips_request_size_bytes",
            "CIPS request size in bytes",
            ["method"]
        )
        
        self.response_size_bytes = Summary(
            "cips_response_size_bytes",
            "CIPS response size in bytes",
            ["method"]
        )
        
        # Transfer metrics
        self.transfers_total = Counter(
            "cips_transfers_total",
            "Total number of CIPS transfers",
            ["currency", "status"]
        )
        
        self.transfer_amount_total = Counter(
            "cips_transfer_amount_total",
            "Total transfer amount",
            ["currency"]
        )
        
        self.transfer_processing_duration_seconds = Histogram(
            "cips_transfer_processing_duration_seconds",
            "Transfer processing duration in seconds",
            ["currency"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )
        
        self.transfers_pending = Gauge(
            "cips_transfers_pending",
            "Number of pending transfers",
            ["currency"]
        )
        
        self.transfers_failed = Counter(
            "cips_transfers_failed",
            "Total number of failed transfers",
            ["currency", "error_code"]
        )
        
        # ISO 20022 message metrics
        self.iso20022_messages_total = Counter(
            "cips_iso20022_messages_total",
            "Total number of ISO 20022 messages",
            ["message_type", "direction"]
        )
        
        self.iso20022_message_size_bytes = Histogram(
            "cips_iso20022_message_size_bytes",
            "ISO 20022 message size in bytes",
            ["message_type"],
            buckets=[100, 500, 1000, 5000, 10000, 50000, 100000]
        )
        
        self.iso20022_parsing_duration_seconds = Histogram(
            "cips_iso20022_parsing_duration_seconds",
            "ISO 20022 message parsing duration in seconds",
            ["message_type"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
        )
        
        # Network metrics
        self.network_status = Gauge(
            "cips_network_status",
            "CIPS network status (1=online, 0=offline)"
        )
        
        self.network_latency_seconds = Histogram(
            "cips_network_latency_seconds",
            "CIPS network latency in seconds",
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
        )
        
        self.network_errors_total = Counter(
            "cips_network_errors_total",
            "Total number of network errors",
            ["error_type"]
        )
        
        self.network_retries_total = Counter(
            "cips_network_retries_total",
            "Total number of network retries",
            ["reason"]
        )
        
        # TigerBeetle metrics
        self.tigerbeetle_operations_total = Counter(
            "cips_tigerbeetle_operations_total",
            "Total number of TigerBeetle operations",
            ["operation", "status"]
        )
        
        self.tigerbeetle_operation_duration_seconds = Histogram(
            "cips_tigerbeetle_operation_duration_seconds",
            "TigerBeetle operation duration in seconds",
            ["operation"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
        )
        
        self.tigerbeetle_account_balance = Gauge(
            "cips_tigerbeetle_account_balance",
            "TigerBeetle account balance",
            ["account_type", "currency"]
        )
        
        # Compliance metrics
        self.compliance_checks_total = Counter(
            "cips_compliance_checks_total",
            "Total number of compliance checks",
            ["check_type", "result"]
        )
        
        self.compliance_check_duration_seconds = Histogram(
            "cips_compliance_check_duration_seconds",
            "Compliance check duration in seconds",
            ["check_type"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
        )
        
        self.compliance_violations_total = Counter(
            "cips_compliance_violations_total",
            "Total number of compliance violations",
            ["violation_type"]
        )
        
        self.compliance_risk_score = Histogram(
            "cips_compliance_risk_score",
            "Compliance risk score distribution",
            buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        )
        
        # Database metrics
        self.database_operations_total = Counter(
            "cips_database_operations_total",
            "Total number of database operations",
            ["operation", "status"]
        )
        
        self.database_operation_duration_seconds = Histogram(
            "cips_database_operation_duration_seconds",
            "Database operation duration in seconds",
            ["operation"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
        )
        
        self.database_connection_pool_size = Gauge(
            "cips_database_connection_pool_size",
            "Database connection pool size"
        )
        
        self.database_connection_pool_active = Gauge(
            "cips_database_connection_pool_active",
            "Active database connections"
        )
        
        # Settlement metrics
        self.settlements_total = Counter(
            "cips_settlements_total",
            "Total number of settlements",
            ["currency", "status"]
        )
        
        self.settlement_amount_total = Counter(
            "cips_settlement_amount_total",
            "Total settlement amount",
            ["currency"]
        )
        
        self.settlement_net_position = Gauge(
            "cips_settlement_net_position",
            "Settlement net position",
            ["currency"]
        )
        
        # Error metrics
        self.errors_total = Counter(
            "cips_errors_total",
            "Total number of errors",
            ["error_code", "component"]
        )
        
        self.error_rate = Gauge(
            "cips_error_rate",
            "Current error rate (errors per second)"
        )
        
        # Performance metrics
        self.throughput_tps = Gauge(
            "cips_throughput_tps",
            "Current throughput in transactions per second"
        )
        
        self.cpu_usage_percent = Gauge(
            "cips_cpu_usage_percent",
            "CPU usage percentage"
        )
        
        self.memory_usage_bytes = Gauge(
            "cips_memory_usage_bytes",
            "Memory usage in bytes"
        )
        
        # Business metrics
        self.daily_volume_usd = Gauge(
            "cips_daily_volume_usd",
            "Daily transaction volume in USD"
        )
        
        self.daily_transaction_count = Gauge(
            "cips_daily_transaction_count",
            "Daily transaction count"
        )
        
        self.average_transaction_size_usd = Gauge(
            "cips_average_transaction_size_usd",
            "Average transaction size in USD"
        )
        
        logger.info(f"Prometheus metrics initialized on port {port}")
    
    def start_server(self) -> None:
        """Start Prometheus metrics server"""
        try:
            start_http_server(self.port)
            logger.info(f"Prometheus metrics server started on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {str(e)}")
            raise
    
    # Decorator for tracking request metrics
    def track_request(self, method: str) -> None:
        """Decorator to track request metrics"""
        def decorator(func) -> None:
            @wraps(func)
            def wrapper(*args, **kwargs) -> None:
                self.requests_in_progress.labels(method=method).inc()
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    status = "success"
                    return result
                except Exception as e:
                    status = "error"
                    raise
                finally:
                    duration = time.time() - start_time
                    self.requests_in_progress.labels(method=method).dec()
                    self.requests_total.labels(method=method, status=status).inc()
                    self.request_duration_seconds.labels(method=method).observe(duration)
            
            return wrapper
        return decorator
    
    # Decorator for tracking transfer metrics
    def track_transfer(self, currency: str) -> None:
        """Decorator to track transfer metrics"""
        def decorator(func) -> None:
            @wraps(func)
            def wrapper(*args, **kwargs) -> None:
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    status = result.get("status", "unknown")
                    amount = result.get("amount_usd", 0)
                    
                    self.transfers_total.labels(currency=currency, status=status).inc()
                    self.transfer_amount_total.labels(currency=currency).inc(amount)
                    
                    return result
                except Exception as e:
                    self.transfers_failed.labels(currency=currency, error_code="exception").inc()
                    raise
                finally:
                    duration = time.time() - start_time
                    self.transfer_processing_duration_seconds.labels(currency=currency).observe(duration)
            
            return wrapper
        return decorator
    
    def record_iso20022_message(self, message_type: str, direction: str, size_bytes: int, parsing_duration: float) -> None:
        """Record ISO 20022 message metrics"""
        self.iso20022_messages_total.labels(message_type=message_type, direction=direction).inc()
        self.iso20022_message_size_bytes.labels(message_type=message_type).observe(size_bytes)
        self.iso20022_parsing_duration_seconds.labels(message_type=message_type).observe(parsing_duration)
    
    def update_network_status(self, is_online: bool) -> None:
        """Update network status"""
        self.network_status.set(1 if is_online else 0)
    
    def record_network_latency(self, latency_seconds: float) -> None:
        """Record network latency"""
        self.network_latency_seconds.observe(latency_seconds)
    
    def record_network_error(self, error_type: str) -> None:
        """Record network error"""
        self.network_errors_total.labels(error_type=error_type).inc()
    
    def record_network_retry(self, reason: str) -> None:
        """Record network retry"""
        self.network_retries_total.labels(reason=reason).inc()
    
    def record_tigerbeetle_operation(self, operation: str, status: str, duration: float) -> None:
        """Record TigerBeetle operation"""
        self.tigerbeetle_operations_total.labels(operation=operation, status=status).inc()
        self.tigerbeetle_operation_duration_seconds.labels(operation=operation).observe(duration)
    
    def update_tigerbeetle_balance(self, account_type: str, currency: str, balance: float) -> None:
        """Update TigerBeetle account balance"""
        self.tigerbeetle_account_balance.labels(account_type=account_type, currency=currency).set(balance)
    
    def record_compliance_check(self, check_type: str, result: str, duration: float, risk_score: Optional[float] = None) -> None:
        """Record compliance check"""
        self.compliance_checks_total.labels(check_type=check_type, result=result).inc()
        self.compliance_check_duration_seconds.labels(check_type=check_type).observe(duration)
        
        if risk_score is not None:
            self.compliance_risk_score.observe(risk_score)
    
    def record_compliance_violation(self, violation_type: str) -> None:
        """Record compliance violation"""
        self.compliance_violations_total.labels(violation_type=violation_type).inc()
    
    def record_database_operation(self, operation: str, status: str, duration: float) -> None:
        """Record database operation"""
        self.database_operations_total.labels(operation=operation, status=status).inc()
        self.database_operation_duration_seconds.labels(operation=operation).observe(duration)
    
    def update_database_pool(self, pool_size: int, active_connections: int) -> None:
        """Update database connection pool metrics"""
        self.database_connection_pool_size.set(pool_size)
        self.database_connection_pool_active.set(active_connections)
    
    def record_settlement(self, currency: str, status: str, amount: float, net_position: float) -> None:
        """Record settlement"""
        self.settlements_total.labels(currency=currency, status=status).inc()
        self.settlement_amount_total.labels(currency=currency).inc(amount)
        self.settlement_net_position.labels(currency=currency).set(net_position)
    
    def record_error(self, error_code: str, component: str) -> None:
        """Record error"""
        self.errors_total.labels(error_code=error_code, component=component).inc()
    
    def update_error_rate(self, rate: float) -> None:
        """Update error rate"""
        self.error_rate.set(rate)
    
    def update_throughput(self, tps: float) -> None:
        """Update throughput"""
        self.throughput_tps.set(tps)
    
    def update_resource_usage(self, cpu_percent: float, memory_bytes: int) -> None:
        """Update resource usage"""
        self.cpu_usage_percent.set(cpu_percent)
        self.memory_usage_bytes.set(memory_bytes)
    
    def update_business_metrics(self, daily_volume_usd: float, daily_count: int, avg_size_usd: float) -> None:
        """Update business metrics"""
        self.daily_volume_usd.set(daily_volume_usd)
        self.daily_transaction_count.set(daily_count)
        self.average_transaction_size_usd.set(avg_size_usd)


# Example usage
if __name__ == "__main__":
    # Initialize metrics
    metrics = CIPSPrometheusMetrics(port=9090)
    
    # Start server
    metrics.start_server()
    
    logger.info("Prometheus metrics server running on http://localhost:9090/metrics")
    
    # Simulate some metrics
    while True:
        # Simulate transfer
        metrics.transfers_total.labels(currency="USD", status="SUCCESS").inc()
        metrics.transfer_amount_total.labels(currency="USD").inc(1000.00)
        metrics.transfer_processing_duration_seconds.labels(currency="USD").observe(0.5)
        
        # Simulate ISO 20022 message
        metrics.record_iso20022_message("pacs.008", "outbound", 5000, 0.01)
        
        # Update network status
        metrics.update_network_status(True)
        metrics.record_network_latency(0.05)
        
        # Update throughput
        metrics.update_throughput(50.0)
        
        time.sleep(5)

