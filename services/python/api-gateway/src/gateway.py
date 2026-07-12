#!/usr/bin/env python3
"""
API Gateway Service
Central routing and load balancing for all microservices
"""

from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import logging
import requests
import time
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

CORS(app)

# Service registry
SERVICES = {
    "fraud-detection": {
        "url": "http://localhost:5001",
        "health_endpoint": "/health",
        "status": "unknown"
    },
    "payment-processing": {
        "url": "http://localhost:5002", 
        "health_endpoint": "/health",
        "status": "unknown"
    },
    "user-management": {
        "url": "http://localhost:5003",
        "health_endpoint": "/health", 
        "status": "unknown"
    }
}

# Route mappings
ROUTE_MAPPINGS = {
    "/api/v1/fraud": "fraud-detection",
    "/api/v1/payment": "payment-processing",
    "/api/v1/user": "user-management",
    "/api/v1/kyc": "user-management"
}

class APIGateway:
    def __init__(self) -> None:
        self.request_count = 0
        self.last_health_check = {}
    
    def check_service_health(self, service_name: str) -> bool:
        """Check if a service is healthy"""
        service = SERVICES.get(service_name)
        if not service:
            return False
        
        try:
            response = requests.get(
                f"{service['url']}{service['health_endpoint']}", 
                timeout=5
            )
            healthy = response.status_code == 200
            SERVICES[service_name]['status'] = 'healthy' if healthy else 'unhealthy'
            self.last_health_check[service_name] = datetime.utcnow().isoformat()
            return healthy
        except Exception as e:
            logger.error(f"Health check failed for {service_name}: {e}")
            SERVICES[service_name]['status'] = 'unhealthy'
            return False
    
    def route_request(self, path: str, method: str, **kwargs) -> Dict[str, Any]:
        """Route request to appropriate service"""
        self.request_count += 1
        
        # Find matching service
        service_name = None
        for route_prefix, svc in ROUTE_MAPPINGS.items():
            if path.startswith(route_prefix):
                service_name = svc
                break
        
        if not service_name:
            return {
                "success": False,
                "error": "No service found for this route",
                "status_code": 404
            }
        
        # Check service health
        if not self.check_service_health(service_name):
            return {
                "success": False,
                "error": f"Service {service_name} is unavailable",
                "status_code": 503
            }
        
        # Forward request
        service_url = SERVICES[service_name]['url']
        full_url = f"{service_url}{path}"
        
        try:
            if method == 'GET':
                response = requests.get(full_url, params=kwargs.get('params'), timeout=30)
            elif method == 'POST':
                response = requests.post(full_url, json=kwargs.get('json'), timeout=30)
            elif method == 'PUT':
                response = requests.put(full_url, json=kwargs.get('json'), timeout=30)
            elif method == 'DELETE':
                response = requests.delete(full_url, timeout=30)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported method: {method}",
                    "status_code": 405
                }
            
            return {
                "success": True,
                "data": response.json() if response.content else {},
                "status_code": response.status_code
            }
            
        except Exception as e:
            logger.error(f"Request forwarding failed: {e}")
            return {
                "success": False,
                "error": "Service request failed",
                "status_code": 500
            }

# Initialize gateway
gateway = APIGateway()

@app.route('/health', methods=['GET'])
def health_check() -> None:
    """Gateway health check"""
    return jsonify({
        "success": True,
        "service": "API Gateway",
        "status": "healthy",
        "services": SERVICES,
        "request_count": gateway.request_count,
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route('/api/v1/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def route_api_request(subpath) -> Tuple:
    """Route API requests to appropriate services"""
    full_path = f"/api/v1/{subpath}"
    method = request.method
    
    kwargs = {}
    if method == 'GET':
        kwargs['params'] = request.args.to_dict()
    elif method in ['POST', 'PUT']:
        kwargs['json'] = request.get_json()
    
    result = gateway.route_request(full_path, method, **kwargs)
    
    return jsonify(result['data'] if result['success'] else {"error": result['error']}), result['status_code']

@app.route('/gateway/services', methods=['GET'])
def get_services() -> None:
    """Get registered services status"""
    return jsonify({
        "success": True,
        "services": SERVICES,
        "route_mappings": ROUTE_MAPPINGS
    })

if __name__ == '__main__':
    logger.info("Starting API Gateway Service...")
    app.run(host='0.0.0.0', port=5000, debug=False)
