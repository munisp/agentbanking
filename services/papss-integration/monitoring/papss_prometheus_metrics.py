"""
PAPSS Prometheus Metrics Exporter
Export PAPSS payment metrics to Prometheus for monitoring and alerting
"""

from prometheus_client import Counter, Gauge, Histogram, Summary, Info, generate_latest, REGISTRY
from prometheus_client.core import CollectorRegistry
from flask import Flask, Response
import time
from decimal import Decimal
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class PAPSSPrometheusMetrics:
    """Prometheus metrics for PAPSS payments"""
    
    def __init__(self, registry=REGISTRY) -> None:
        """Initialize Prometheus metrics"""
        self.registry = registry
        
        # Payment counters
        self.payments_total = Counter(
            'papss_payments_total',
            'Total number of PAPSS payments',
            ['trade_corridor', 'source_currency', 'target_currency', 'payment_type'],
            registry=self.registry
        )
        
        self.payments_successful = Counter(
            'papss_payments_successful_total',
            'Total number of successful PAPSS payments',
            ['trade_corridor', 'source_currency', 'target_currency'],
            registry=self.registry
        )
        
        self.payments_failed = Counter(
            'papss_payments_failed_total',
            'Total number of failed PAPSS payments',
            ['trade_corridor', 'source_currency', 'target_currency', 'error_type'],
            registry=self.registry
        )
        
        self.payments_reversed = Counter(
            'papss_payments_reversed_total',
            'Total number of reversed PAPSS payments',
            ['trade_corridor', 'reason'],
            registry=self.registry
        )
        
        # Payment amount metrics
        self.payment_amount = Histogram(
            'papss_payment_amount',
            'PAPSS payment amount distribution',
            ['source_currency'],
            buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000, 5000000],
            registry=self.registry
        )
        
        self.payment_volume_total = Counter(
            'papss_payment_volume_total',
            'Total payment volume in USD equivalent',
            ['trade_corridor'],
            registry=self.registry
        )
        
        # Processing time metrics
        self.payment_processing_time = Histogram(
            'papss_payment_processing_time_seconds',
            'PAPSS payment processing time in seconds',
            ['trade_corridor', 'payment_type'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
            registry=self.registry
        )
        
        self.tigerbeetle_operation_time = Histogram(
            'papss_tigerbeetle_operation_time_seconds',
            'TigerBeetle operation time in seconds',
            ['operation_type'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
            registry=self.registry
        )
        
        # FX metrics
        self.fx_conversions_total = Counter(
            'papss_fx_conversions_total',
            'Total number of FX conversions',
            ['source_currency', 'target_currency'],
            registry=self.registry
        )
        
        self.fx_rate = Gauge(
            'papss_fx_rate',
            'Current FX rate',
            ['source_currency', 'target_currency'],
            registry=self.registry
        )
        
        self.fx_spread = Gauge(
            'papss_fx_spread_percentage',
            'FX spread percentage',
            ['source_currency', 'target_currency'],
            registry=self.registry
        )
        
        # Mobile money metrics
        self.mobile_money_payments = Counter(
            'papss_mobile_money_payments_total',
            'Total mobile money payments',
            ['sender_operator', 'receiver_operator', 'country'],
            registry=self.registry
        )
        
        self.mobile_money_failures = Counter(
            'papss_mobile_money_failures_total',
            'Total mobile money payment failures',
            ['operator', 'error_type'],
            registry=self.registry
        )
        
        # Trade corridor metrics
        self.corridor_payments = Counter(
            'papss_corridor_payments_total',
            'Total payments per trade corridor',
            ['corridor'],
            registry=self.registry
        )
        
        self.corridor_volume = Counter(
            'papss_corridor_volume_usd_total',
            'Total payment volume per corridor in USD',
            ['corridor'],
            registry=self.registry
        )
        
        # Settlement metrics
        self.settlements_total = Counter(
            'papss_settlements_total',
            'Total number of settlements',
            ['trade_corridor', 'currency'],
            registry=self.registry
        )
        
        self.settlement_amount = Histogram(
            'papss_settlement_amount',
            'Settlement amount distribution',
            ['currency'],
            buckets=[10000, 50000, 100000, 500000, 1000000, 5000000, 10000000],
            registry=self.registry
        )
        
        # Compliance metrics
        self.compliance_checks_total = Counter(
            'papss_compliance_checks_total',
            'Total compliance checks performed',
            ['check_type', 'result'],
            registry=self.registry
        )
        
        self.high_risk_payments = Counter(
            'papss_high_risk_payments_total',
            'Total high-risk payments flagged',
            ['risk_category'],
            registry=self.registry
        )
        
        # System metrics
        self.active_connections = Gauge(
            'papss_active_connections',
            'Number of active connections',
            registry=self.registry
        )
        
        self.tigerbeetle_connection_status = Gauge(
            'papss_tigerbeetle_connection_status',
            'TigerBeetle connection status (1=connected, 0=disconnected)',
            registry=self.registry
        )
        
        self.database_connection_pool_size = Gauge(
            'papss_database_connection_pool_size',
            'Database connection pool size',
            ['state'],  # active, idle
            registry=self.registry
        )
        
        # Error metrics
        self.errors_total = Counter(
            'papss_errors_total',
            'Total number of errors',
            ['error_type', 'severity'],
            registry=self.registry
        )
        
        # Performance metrics
        self.throughput = Gauge(
            'papss_throughput_tps',
            'Current throughput in transactions per second',
            registry=self.registry
        )
        
        self.queue_size = Gauge(
            'papss_queue_size',
            'Number of payments in queue',
            ['queue_type'],
            registry=self.registry
        )
        
        # Account balance metrics
        self.account_balance = Gauge(
            'papss_account_balance',
            'Account balance',
            ['account_type', 'currency'],
            registry=self.registry
        )
        
        # API metrics
        self.api_requests_total = Counter(
            'papss_api_requests_total',
            'Total API requests',
            ['endpoint', 'method', 'status_code'],
            registry=self.registry
        )
        
        self.api_request_duration = Histogram(
            'papss_api_request_duration_seconds',
            'API request duration',
            ['endpoint', 'method'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
            registry=self.registry
        )
        
        # Info metrics
        self.papss_info = Info(
            'papss_service',
            'PAPSS service information',
            registry=self.registry
        )
        
        self.papss_info.info({
            'version': '1.0.0',
            'environment': 'production',
            'supported_corridors': 'EAC,ECOWAS,SADC,CEMAC',
            'supported_currencies': 'NGN,KES,GHS,ZAR,EGP,TZS,UGX,XOF,XAF'
        })
        
        logger.info("Prometheus metrics initialized")
    
    # Payment tracking methods
    def record_payment(self, trade_corridor: str, source_currency: str, target_currency: str,
                      payment_type: str, amount: Decimal) -> None:
        """Record a new payment"""
        self.payments_total.labels(
            trade_corridor=trade_corridor,
            source_currency=source_currency,
            target_currency=target_currency,
            payment_type=payment_type
        ).inc()
        
        self.payment_amount.labels(source_currency=source_currency).observe(float(amount))
        self.corridor_payments.labels(corridor=trade_corridor).inc()
    
    def record_payment_success(self, trade_corridor: str, source_currency: str, target_currency: str,
                               processing_time: float) -> None:
        """Record successful payment"""
        self.payments_successful.labels(
            trade_corridor=trade_corridor,
            source_currency=source_currency,
            target_currency=target_currency
        ).inc()
        
        self.payment_processing_time.labels(
            trade_corridor=trade_corridor,
            payment_type='standard'
        ).observe(processing_time)
    
    def record_payment_failure(self, trade_corridor: str, source_currency: str, target_currency: str,
                              error_type: str) -> None:
        """Record failed payment"""
        self.payments_failed.labels(
            trade_corridor=trade_corridor,
            source_currency=source_currency,
            target_currency=target_currency,
            error_type=error_type
        ).inc()
    
    def record_payment_reversal(self, trade_corridor: str, reason: str) -> None:
        """Record payment reversal"""
        self.payments_reversed.labels(
            trade_corridor=trade_corridor,
            reason=reason
        ).inc()
    
    # FX tracking methods
    def record_fx_conversion(self, source_currency: str, target_currency: str, rate: Decimal, spread: Decimal) -> None:
        """Record FX conversion"""
        self.fx_conversions_total.labels(
            source_currency=source_currency,
            target_currency=target_currency
        ).inc()
        
        self.fx_rate.labels(
            source_currency=source_currency,
            target_currency=target_currency
        ).set(float(rate))
        
        self.fx_spread.labels(
            source_currency=source_currency,
            target_currency=target_currency
        ).set(float(spread))
    
    # Mobile money tracking methods
    def record_mobile_money_payment(self, sender_operator: str, receiver_operator: str, country: str) -> None:
        """Record mobile money payment"""
        self.mobile_money_payments.labels(
            sender_operator=sender_operator,
            receiver_operator=receiver_operator,
            country=country
        ).inc()
    
    def record_mobile_money_failure(self, operator: str, error_type: str) -> None:
        """Record mobile money failure"""
        self.mobile_money_failures.labels(
            operator=operator,
            error_type=error_type
        ).inc()
    
    # Settlement tracking methods
    def record_settlement(self, trade_corridor: str, currency: str, amount: Decimal) -> None:
        """Record settlement"""
        self.settlements_total.labels(
            trade_corridor=trade_corridor,
            currency=currency
        ).inc()
        
        self.settlement_amount.labels(currency=currency).observe(float(amount))
    
    # Compliance tracking methods
    def record_compliance_check(self, check_type: str, result: str) -> None:
        """Record compliance check"""
        self.compliance_checks_total.labels(
            check_type=check_type,
            result=result
        ).inc()
    
    def record_high_risk_payment(self, risk_category: str) -> None:
        """Record high-risk payment"""
        self.high_risk_payments.labels(risk_category=risk_category).inc()
    
    # System tracking methods
    def update_active_connections(self, count: int) -> None:
        """Update active connections count"""
        self.active_connections.set(count)
    
    def update_tigerbeetle_status(self, connected: bool) -> None:
        """Update TigerBeetle connection status"""
        self.tigerbeetle_connection_status.set(1 if connected else 0)
    
    def update_database_pool(self, active: int, idle: int) -> None:
        """Update database connection pool metrics"""
        self.database_connection_pool_size.labels(state='active').set(active)
        self.database_connection_pool_size.labels(state='idle').set(idle)
    
    def record_error(self, error_type: str, severity: str) -> None:
        """Record error"""
        self.errors_total.labels(
            error_type=error_type,
            severity=severity
        ).inc()
    
    def update_throughput(self, tps: float) -> None:
        """Update throughput metric"""
        self.throughput.set(tps)
    
    def update_queue_size(self, queue_type: str, size: int) -> None:
        """Update queue size"""
        self.queue_size.labels(queue_type=queue_type).set(size)
    
    def update_account_balance(self, account_type: str, currency: str, balance: Decimal) -> None:
        """Update account balance"""
        self.account_balance.labels(
            account_type=account_type,
            currency=currency
        ).set(float(balance))
    
    # API tracking methods
    def record_api_request(self, endpoint: str, method: str, status_code: int, duration: float) -> None:
        """Record API request"""
        self.api_requests_total.labels(
            endpoint=endpoint,
            method=method,
            status_code=str(status_code)
        ).inc()
        
        self.api_request_duration.labels(
            endpoint=endpoint,
            method=method
        ).observe(duration)
    
    def record_tigerbeetle_operation(self, operation_type: str, duration: float) -> None:
        """Record TigerBeetle operation"""
        self.tigerbeetle_operation_time.labels(
            operation_type=operation_type
        ).observe(duration)


# Flask app for metrics endpoint
app = Flask(__name__)
# ─── Security Hardening (CVE-2024-34069, CVE-2026-27205) ─────────────────────
import os as _os
_flask_env = _os.getenv("FLASK_ENV", _os.getenv("APP_ENV", "production")).lower()
if _flask_env != "development":
    app.config["DEBUG"] = False
    app.config["TESTING"] = False
    _os.environ["WERKZEUG_DEBUG_PIN"] = "off"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SECRET_KEY"] = _os.getenv("FLASK_SECRET_KEY", _os.urandom(32).hex())

@app.after_request
def _add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers.pop("Server", None)
    return response
# ─────────────────────────────────────────────────────────────────────────────

metrics = PAPSSPrometheusMetrics()


@app.route('/metrics')
def metrics_endpoint() -> None:
    """Prometheus metrics endpoint"""
    return Response(generate_latest(metrics.registry), mimetype='text/plain')


@app.route('/health')
def health() -> Dict[str, Any]:
    """Health check endpoint"""
    return {'status': 'healthy', 'service': 'papss-metrics'}


if __name__ == '__main__':
    # Example usage
    print("Starting PAPSS Prometheus metrics exporter...")
    
    # Simulate some metrics
    metrics.record_payment('EAC', 'NGN', 'KES', 'personal', Decimal('500000'))
    metrics.record_payment_success('EAC', 'NGN', 'KES', 1.5)
    metrics.record_fx_conversion('NGN', 'KES', Decimal('0.32'), Decimal('0.02'))
    metrics.record_mobile_money_payment('OPAY', 'MPESA', 'NG')
    metrics.update_tigerbeetle_status(True)
    metrics.update_throughput(150.5)
    
    # Start Flask app
    app.run(host='0.0.0.0', port=8081)

