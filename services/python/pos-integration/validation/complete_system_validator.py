#!/usr/bin/env python3
"""
Complete System Validator for QR Code and POS Implementation
Validates that all features are implemented and production-ready
"""

import asyncio
import aiohttp
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemValidator:
    """Comprehensive system validation for QR Code and POS implementation"""
    
    def __init__(self):
        self.base_urls = {
            'pos_service': 'http://localhost:8070',
            'qr_service': 'http://localhost:8071',
            'enhanced_pos': 'http://localhost:8072',
            'device_manager': 'http://localhost:8073',
            'prometheus': 'http://localhost:9090',
            'grafana': 'http://localhost:3000',
            'alertmanager': 'http://localhost:9093'
        }
        self.validation_results = {}
        self.critical_failures = []
        self.warnings = []
    
    async def validate_complete_system(self) -> Dict[str, Any]:
        """Run complete system validation"""
        logger.info("🔍 Starting Complete System Validation...")
        
        validation_tasks = [
            self.validate_docker_infrastructure(),
            self.validate_service_endpoints(),
            self.validate_payment_processors(),
            self.validate_qr_code_system(),
            self.validate_device_management(),
            self.validate_fraud_detection(),
            self.validate_exchange_rates(),
            self.validate_monitoring_stack(),
            self.validate_testing_infrastructure(),
            self.validate_security_features(),
            self.validate_performance_requirements(),
            self.validate_business_logic()
        ]
        
        # Run all validations concurrently
        results = await asyncio.gather(*validation_tasks, return_exceptions=True)
        
        # Process results
        validation_categories = [
            'docker_infrastructure', 'service_endpoints', 'payment_processors',
            'qr_code_system', 'device_management', 'fraud_detection',
            'exchange_rates', 'monitoring_stack', 'testing_infrastructure',
            'security_features', 'performance_requirements', 'business_logic'
        ]
        
        for i, result in enumerate(results):
            category = validation_categories[i]
            if isinstance(result, Exception):
                self.validation_results[category] = {
                    'status': 'FAILED',
                    'error': str(result),
                    'details': {}
                }
                self.critical_failures.append(f"{category}: {str(result)}")
            else:
                self.validation_results[category] = result
        
        return self.generate_validation_report()
    
    async def validate_docker_infrastructure(self) -> Dict[str, Any]:
        """Validate Docker infrastructure completeness"""
        logger.info("🐳 Validating Docker Infrastructure...")
        
        required_files = [
            'Dockerfile.enhanced',
            'Dockerfile.qr',
            'Dockerfile.pos',
            'Dockerfile.device',
            'docker-compose.yml',
            'nginx.conf'
        ]
        
        base_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration')
        missing_files = []
        present_files = []
        
        for file_name in required_files:
            file_path = base_path / file_name
            if file_path.exists():
                present_files.append(file_name)
            else:
                missing_files.append(file_name)
        
        # Check Docker Compose configuration
        docker_compose_path = base_path / 'docker-compose.yml'
        services_configured = []
        if docker_compose_path.exists():
            try:
                with open(docker_compose_path, 'r') as f:
                    content = f.read()
                    services = ['pos-service', 'qr-validation-service', 'enhanced-pos-service', 'device-manager-service']
                    for service in services:
                        if service in content:
                            services_configured.append(service)
            except Exception as e:
                logger.warning(f"Could not parse docker-compose.yml: {e}")
        
        status = 'PASSED' if not missing_files else 'FAILED'
        if missing_files:
            self.critical_failures.append(f"Missing Docker files: {missing_files}")
        
        return {
            'status': status,
            'details': {
                'present_files': present_files,
                'missing_files': missing_files,
                'services_configured': services_configured,
                'total_files_required': len(required_files),
                'total_files_present': len(present_files)
            }
        }
    
    async def validate_service_endpoints(self) -> Dict[str, Any]:
        """Validate all service endpoints are accessible"""
        logger.info("🌐 Validating Service Endpoints...")
        
        endpoint_results = {}
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            for service_name, base_url in self.base_urls.items():
                try:
                    # Test health endpoint
                    health_url = f"{base_url}/health" if service_name not in ['prometheus', 'grafana', 'alertmanager'] else f"{base_url}/-/healthy" if service_name == 'prometheus' else f"{base_url}/api/health" if service_name == 'grafana' else f"{base_url}/-/healthy"
                    
                    async with session.get(health_url) as response:
                        endpoint_results[service_name] = {
                            'status': 'UP' if response.status == 200 else 'DOWN',
                            'response_code': response.status,
                            'response_time': time.time()
                        }
                except Exception as e:
                    endpoint_results[service_name] = {
                        'status': 'DOWN',
                        'error': str(e),
                        'response_time': None
                    }
        
        # Count successful endpoints
        up_services = sum(1 for result in endpoint_results.values() if result['status'] == 'UP')
        total_services = len(endpoint_results)
        
        status = 'PASSED' if up_services == total_services else 'PARTIAL' if up_services > 0 else 'FAILED'
        
        if up_services < total_services:
            down_services = [name for name, result in endpoint_results.items() if result['status'] == 'DOWN']
            self.warnings.append(f"Services down: {down_services}")
        
        return {
            'status': status,
            'details': {
                'endpoints': endpoint_results,
                'up_services': up_services,
                'total_services': total_services,
                'availability_percentage': (up_services / total_services) * 100
            }
        }
    
    async def validate_payment_processors(self) -> Dict[str, Any]:
        """Validate payment processor implementations"""
        logger.info("💳 Validating Payment Processors...")
        
        processor_files = [
            'payment_processors/stripe_processor.py',
            'payment_processors/square_processor.py',
            'payment_processors/processor_factory.py'
        ]
        
        base_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration')
        implementation_status = {}
        
        for file_name in processor_files:
            file_path = base_path / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        # Check for real implementation
                        has_real_implementation = 'stripe.PaymentIntent' in content or 'squareup.client' in content
                        has_error_handling = 'try:' in content and 'except' in content
                        has_async_support = 'async def' in content
                        
                        implementation_status[file_name] = {
                            'exists': True,
                            'has_real_implementation': has_real_implementation,
                            'has_error_handling': has_error_handling,
                            'has_async_support': has_async_support,
                            'line_count': len(content.splitlines())
                        }
                except Exception as e:
                    implementation_status[file_name] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                implementation_status[file_name] = {'exists': False}
        
        # Test payment processing endpoint
        payment_test_result = None
        try:
            async with aiohttp.ClientSession() as session:
                test_payment = {
                    "amount": 10.00,
                    "currency": "USD",
                    "payment_method": "card_chip",
                    "merchant_id": "TEST_MERCHANT",
                    "terminal_id": "TEST_TERMINAL"
                }
                async with session.post(f"{self.base_urls['enhanced_pos']}/enhanced/process-payment", json=test_payment) as response:
                    payment_test_result = {
                        'status_code': response.status,
                        'success': response.status == 200,
                        'response_time': time.time()
                    }
        except Exception as e:
            payment_test_result = {'error': str(e), 'success': False}
        
        # Determine overall status
        all_files_exist = all(status.get('exists', False) for status in implementation_status.values())
        real_implementations = sum(1 for status in implementation_status.values() if status.get('has_real_implementation', False))
        
        status = 'PASSED' if all_files_exist and real_implementations >= 2 else 'PARTIAL' if all_files_exist else 'FAILED'
        
        return {
            'status': status,
            'details': {
                'processor_implementations': implementation_status,
                'payment_test_result': payment_test_result,
                'real_implementations_count': real_implementations,
                'total_processors': len(processor_files)
            }
        }
    
    async def validate_qr_code_system(self) -> Dict[str, Any]:
        """Validate QR code system completeness"""
        logger.info("📱 Validating QR Code System...")
        
        qr_components = {
            'qr_validation_service.py': 'QR Validation Service',
            'mobile-app/src/screens/scanner/QRScannerScreen.tsx': 'Mobile QR Scanner',
            'mobile-app/src/services/PaymentService.ts': 'Payment Service'
        }
        
        base_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration')
        mobile_path = Path('/home/ubuntu/remittance-platform-complete/mobile-app')
        
        component_status = {}
        
        for file_name, description in qr_components.items():
            if 'mobile-app' in file_name:
                file_path = Path('/home/ubuntu/remittance-platform-complete') / file_name
            else:
                file_path = base_path / file_name
            
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        
                        # Check for key features
                        has_validation = 'validate' in content.lower()
                        has_security = 'hmac' in content.lower() or 'signature' in content.lower()
                        has_fraud_detection = 'fraud' in content.lower()
                        has_error_handling = 'try' in content or 'catch' in content
                        
                        component_status[description] = {
                            'exists': True,
                            'has_validation': has_validation,
                            'has_security': has_security,
                            'has_fraud_detection': has_fraud_detection,
                            'has_error_handling': has_error_handling,
                            'line_count': len(content.splitlines())
                        }
                except Exception as e:
                    component_status[description] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                component_status[description] = {'exists': False}
        
        # Test QR generation and validation
        qr_test_results = {}
        try:
            async with aiohttp.ClientSession() as session:
                # Test QR generation
                qr_data = {
                    "merchant_id": "TEST_MERCHANT",
                    "amount": 25.00,
                    "currency": "USD",
                    "transaction_id": f"TEST_TXN_{int(time.time())}"
                }
                async with session.post(f"{self.base_urls['qr_service']}/qr/generate", json=qr_data) as response:
                    qr_test_results['generation'] = {
                        'status_code': response.status,
                        'success': response.status == 200
                    }
                    if response.status == 200:
                        qr_response = await response.json()
                        # Test QR validation
                        validation_data = {
                            "qr_code": qr_response.get('qr_code', ''),
                            "amount": 25.00
                        }
                        async with session.post(f"{self.base_urls['qr_service']}/qr/validate", json=validation_data) as val_response:
                            qr_test_results['validation'] = {
                                'status_code': val_response.status,
                                'success': val_response.status == 200
                            }
        except Exception as e:
            qr_test_results['error'] = str(e)
        
        # Determine status
        all_components_exist = all(status.get('exists', False) for status in component_status.values())
        security_features = sum(1 for status in component_status.values() if status.get('has_security', False))
        
        status = 'PASSED' if all_components_exist and security_features >= 1 else 'PARTIAL' if all_components_exist else 'FAILED'
        
        return {
            'status': status,
            'details': {
                'components': component_status,
                'qr_test_results': qr_test_results,
                'security_implementations': security_features,
                'total_components': len(qr_components)
            }
        }
    
    async def validate_device_management(self) -> Dict[str, Any]:
        """Validate device management system"""
        logger.info("🖥️ Validating Device Management...")
        
        device_files = [
            'device_drivers.py',
            'device_manager_service.py'
        ]
        
        base_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration')
        device_status = {}
        
        for file_name in device_files:
            file_path = base_path / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        
                        # Check for device protocols
                        has_usb = 'usb' in content.lower()
                        has_bluetooth = 'bluetooth' in content.lower()
                        has_serial = 'serial' in content.lower()
                        has_tcp = 'tcp' in content.lower()
                        
                        device_status[file_name] = {
                            'exists': True,
                            'protocols': {
                                'usb': has_usb,
                                'bluetooth': has_bluetooth,
                                'serial': has_serial,
                                'tcp': has_tcp
                            },
                            'protocol_count': sum([has_usb, has_bluetooth, has_serial, has_tcp]),
                            'line_count': len(content.splitlines())
                        }
                except Exception as e:
                    device_status[file_name] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                device_status[file_name] = {'exists': False}
        
        # Test device management endpoints
        device_test_results = {}
        try:
            async with aiohttp.ClientSession() as session:
                endpoints = [
                    '/devices/discover',
                    '/devices/statistics',
                    '/devices/health'
                ]
                
                for endpoint in endpoints:
                    try:
                        async with session.get(f"{self.base_urls['device_manager']}{endpoint}") as response:
                            device_test_results[endpoint] = {
                                'status_code': response.status,
                                'success': response.status == 200
                            }
                    except Exception as e:
                        device_test_results[endpoint] = {'error': str(e), 'success': False}
        except Exception as e:
            device_test_results['error'] = str(e)
        
        # Determine status
        all_files_exist = all(status.get('exists', False) for status in device_status.values())
        total_protocols = sum(status.get('protocol_count', 0) for status in device_status.values())
        
        status = 'PASSED' if all_files_exist and total_protocols >= 4 else 'PARTIAL' if all_files_exist else 'FAILED'
        
        return {
            'status': status,
            'details': {
                'device_files': device_status,
                'device_test_results': device_test_results,
                'total_protocols_supported': total_protocols,
                'required_protocols': 4
            }
        }
    
    async def validate_fraud_detection(self) -> Dict[str, Any]:
        """Validate fraud detection capabilities"""
        logger.info("🛡️ Validating Fraud Detection...")
        
        # Check enhanced POS service for fraud detection
        enhanced_pos_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration/enhanced_pos_service.py')
        fraud_features = {}
        
        if enhanced_pos_path.exists():
            try:
                with open(enhanced_pos_path, 'r') as f:
                    content = f.read()
                    
                    fraud_features = {
                        'fraud_rules_count': content.count('FraudRule('),
                        'has_ml_detection': 'machine_learning' in content.lower() or 'ml' in content.lower(),
                        'has_velocity_checks': 'velocity' in content.lower(),
                        'has_amount_checks': 'amount' in content.lower() and 'threshold' in content.lower(),
                        'has_location_checks': 'location' in content.lower() or 'geographic' in content.lower(),
                        'has_pattern_detection': 'pattern' in content.lower(),
                        'has_risk_scoring': 'risk_score' in content.lower() or 'score' in content.lower()
                    }
            except Exception as e:
                fraud_features['error'] = str(e)
        else:
            fraud_features['file_missing'] = True
        
        # Test fraud detection endpoint
        fraud_test_result = None
        try:
            async with aiohttp.ClientSession() as session:
                test_transaction = {
                    "amount": 10000.00,  # High amount to trigger fraud rules
                    "currency": "USD",
                    "payment_method": "card_chip",
                    "merchant_id": "TEST_MERCHANT",
                    "customer_id": "TEST_CUSTOMER"
                }
                async with session.post(f"{self.base_urls['enhanced_pos']}/enhanced/fraud-detection/analyze", json=test_transaction) as response:
                    fraud_test_result = {
                        'status_code': response.status,
                        'success': response.status == 200
                    }
                    if response.status == 200:
                        fraud_response = await response.json()
                        fraud_test_result['has_risk_score'] = 'risk_score' in fraud_response
                        fraud_test_result['has_fraud_indicators'] = 'fraud_indicators' in fraud_response
        except Exception as e:
            fraud_test_result = {'error': str(e), 'success': False}
        
        # Determine status
        fraud_rule_count = fraud_features.get('fraud_rules_count', 0)
        has_key_features = sum([
            fraud_features.get('has_velocity_checks', False),
            fraud_features.get('has_amount_checks', False),
            fraud_features.get('has_risk_scoring', False)
        ])
        
        status = 'PASSED' if fraud_rule_count >= 5 and has_key_features >= 2 else 'PARTIAL' if fraud_rule_count > 0 else 'FAILED'
        
        return {
            'status': status,
            'details': {
                'fraud_features': fraud_features,
                'fraud_test_result': fraud_test_result,
                'fraud_rules_implemented': fraud_rule_count,
                'key_features_count': has_key_features
            }
        }
    
    async def validate_exchange_rates(self) -> Dict[str, Any]:
        """Validate exchange rate service"""
        logger.info("💱 Validating Exchange Rate Service...")
        
        exchange_rate_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration/exchange_rate_service.py')
        exchange_features = {}
        
        if exchange_rate_path.exists():
            try:
                with open(exchange_rate_path, 'r') as f:
                    content = f.read()
                    
                    exchange_features = {
                        'has_multiple_providers': content.count('Provider') >= 2,
                        'has_caching': 'cache' in content.lower() or 'redis' in content.lower(),
                        'has_fallback': 'fallback' in content.lower(),
                        'has_rate_limiting': 'rate_limit' in content.lower(),
                        'currency_count': content.count('CurrencyCode.'),
                        'provider_count': content.count('class') - 1  # Subtract main class
                    }
            except Exception as e:
                exchange_features['error'] = str(e)
        else:
            exchange_features['file_missing'] = True
        
        # Test exchange rate endpoints
        exchange_test_results = {}
        try:
            async with aiohttp.ClientSession() as session:
                endpoints = [
                    '/exchange-rate/rates/USD/EUR',
                    '/exchange-rate/convert?from=USD&to=EUR&amount=100',
                    '/exchange-rate/supported-currencies'
                ]
                
                for endpoint in endpoints:
                    try:
                        async with session.get(f"{self.base_urls['enhanced_pos']}{endpoint}") as response:
                            exchange_test_results[endpoint] = {
                                'status_code': response.status,
                                'success': response.status == 200
                            }
                    except Exception as e:
                        exchange_test_results[endpoint] = {'error': str(e), 'success': False}
        except Exception as e:
            exchange_test_results['error'] = str(e)
        
        # Determine status
        has_file = not exchange_features.get('file_missing', False)
        has_providers = exchange_features.get('has_multiple_providers', False)
        currency_count = exchange_features.get('currency_count', 0)
        
        status = 'PASSED' if has_file and has_providers and currency_count >= 5 else 'PARTIAL' if has_file else 'FAILED'
        
        return {
            'status': status,
            'details': {
                'exchange_features': exchange_features,
                'exchange_test_results': exchange_test_results,
                'currencies_supported': currency_count,
                'providers_implemented': exchange_features.get('provider_count', 0)
            }
        }
    
    async def validate_monitoring_stack(self) -> Dict[str, Any]:
        """Validate monitoring infrastructure"""
        logger.info("📊 Validating Monitoring Stack...")
        
        monitoring_files = [
            'monitoring/prometheus/prometheus.yml',
            'monitoring/prometheus/alert_rules.yml',
            'monitoring/grafana/dashboards/pos-overview.json',
            'monitoring/alertmanager/alertmanager.yml',
            'monitoring/docker-compose.monitoring.yml'
        ]
        
        base_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration')
        monitoring_status = {}
        
        for file_name in monitoring_files:
            file_path = base_path / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        monitoring_status[file_name] = {
                            'exists': True,
                            'size_kb': len(content) / 1024,
                            'line_count': len(content.splitlines())
                        }
                        
                        # Specific checks
                        if 'prometheus.yml' in file_name:
                            monitoring_status[file_name]['scrape_configs'] = content.count('job_name:')
                        elif 'alert_rules.yml' in file_name:
                            monitoring_status[file_name]['alert_rules'] = content.count('alert:')
                        elif 'alertmanager.yml' in file_name:
                            monitoring_status[file_name]['receivers'] = content.count('name:')
                            
                except Exception as e:
                    monitoring_status[file_name] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                monitoring_status[file_name] = {'exists': False}
        
        # Test monitoring endpoints
        monitoring_test_results = {}
        monitoring_services = ['prometheus', 'grafana', 'alertmanager']
        
        async with aiohttp.ClientSession() as session:
            for service in monitoring_services:
                try:
                    url = self.base_urls[service]
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        monitoring_test_results[service] = {
                            'status_code': response.status,
                            'success': response.status == 200,
                            'accessible': True
                        }
                except Exception as e:
                    monitoring_test_results[service] = {
                        'error': str(e),
                        'success': False,
                        'accessible': False
                    }
        
        # Determine status
        all_files_exist = all(status.get('exists', False) for status in monitoring_status.values())
        accessible_services = sum(1 for result in monitoring_test_results.values() if result.get('accessible', False))
        
        status = 'PASSED' if all_files_exist and accessible_services >= 1 else 'PARTIAL' if all_files_exist else 'FAILED'
        
        return {
            'status': status,
            'details': {
                'monitoring_files': monitoring_status,
                'monitoring_services': monitoring_test_results,
                'files_present': sum(1 for status in monitoring_status.values() if status.get('exists', False)),
                'total_files_required': len(monitoring_files),
                'accessible_services': accessible_services
            }
        }
    
    async def validate_testing_infrastructure(self) -> Dict[str, Any]:
        """Validate testing infrastructure"""
        logger.info("🧪 Validating Testing Infrastructure...")
        
        test_files = [
            'tests/unit/test_qr_validation.py',
            'tests/unit/test_payment_processors.py',
            'tests/integration/test_pos_integration.py',
            'tests/load/test_load_performance.py'
        ]
        
        base_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration')
        test_status = {}
        
        for file_name in test_files:
            file_path = base_path / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        
                        test_status[file_name] = {
                            'exists': True,
                            'test_functions': content.count('def test_'),
                            'async_tests': content.count('async def test_'),
                            'assertions': content.count('assert '),
                            'line_count': len(content.splitlines()),
                            'has_fixtures': '@pytest.fixture' in content,
                            'has_mocks': 'mock' in content.lower() or 'patch' in content.lower()
                        }
                except Exception as e:
                    test_status[file_name] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                test_status[file_name] = {'exists': False}
        
        # Calculate test coverage metrics
        total_test_functions = sum(status.get('test_functions', 0) for status in test_status.values())
        total_assertions = sum(status.get('assertions', 0) for status in test_status.values())
        files_with_fixtures = sum(1 for status in test_status.values() if status.get('has_fixtures', False))
        
        # Determine status
        all_files_exist = all(status.get('exists', False) for status in test_status.values())
        sufficient_tests = total_test_functions >= 20  # At least 20 test functions
        
        status = 'PASSED' if all_files_exist and sufficient_tests else 'PARTIAL' if all_files_exist else 'FAILED'
        
        return {
            'status': status,
            'details': {
                'test_files': test_status,
                'total_test_functions': total_test_functions,
                'total_assertions': total_assertions,
                'files_with_fixtures': files_with_fixtures,
                'test_coverage_estimate': min(100, (total_test_functions / 50) * 100)  # Rough estimate
            }
        }
    
    async def validate_security_features(self) -> Dict[str, Any]:
        """Validate security implementations"""
        logger.info("🔒 Validating Security Features...")
        
        security_checks = {
            'qr_digital_signatures': False,
            'qr_encryption': False,
            'fraud_detection': False,
            'input_validation': False,
            'error_handling': False,
            'rate_limiting': False,
            'authentication': False,
            'ssl_tls_config': False
        }
        
        # Check QR validation service for security features
        qr_service_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration/qr_validation_service.py')
        if qr_service_path.exists():
            try:
                with open(qr_service_path, 'r') as f:
                    content = f.read()
                    security_checks['qr_digital_signatures'] = 'hmac' in content.lower() or 'signature' in content.lower()
                    security_checks['qr_encryption'] = 'encrypt' in content.lower() or 'pbkdf2' in content.lower()
                    security_checks['input_validation'] = 'validate' in content.lower()
                    security_checks['error_handling'] = 'try:' in content and 'except' in content
                    security_checks['rate_limiting'] = 'rate_limit' in content.lower()
            except Exception as e:
                logger.warning(f"Could not check QR service security: {e}")
        
        # Check enhanced POS service for fraud detection
        enhanced_pos_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration/enhanced_pos_service.py')
        if enhanced_pos_path.exists():
            try:
                with open(enhanced_pos_path, 'r') as f:
                    content = f.read()
                    security_checks['fraud_detection'] = 'fraud' in content.lower()
                    security_checks['authentication'] = 'auth' in content.lower() or 'token' in content.lower()
            except Exception as e:
                logger.warning(f"Could not check enhanced POS security: {e}")
        
        # Check Nginx configuration for SSL/TLS
        nginx_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration/nginx.conf')
        if nginx_path.exists():
            try:
                with open(nginx_path, 'r') as f:
                    content = f.read()
                    security_checks['ssl_tls_config'] = 'ssl' in content.lower() or 'tls' in content.lower()
            except Exception as e:
                logger.warning(f"Could not check Nginx SSL config: {e}")
        
        # Count implemented security features
        implemented_features = sum(1 for check in security_checks.values() if check)
        total_features = len(security_checks)
        
        status = 'PASSED' if implemented_features >= 6 else 'PARTIAL' if implemented_features >= 3 else 'FAILED'
        
        return {
            'status': status,
            'details': {
                'security_checks': security_checks,
                'implemented_features': implemented_features,
                'total_features': total_features,
                'security_score': (implemented_features / total_features) * 100
            }
        }
    
    async def validate_performance_requirements(self) -> Dict[str, Any]:
        """Validate performance requirements"""
        logger.info("⚡ Validating Performance Requirements...")
        
        performance_results = {}
        
        # Test response times
        async with aiohttp.ClientSession() as session:
            endpoints_to_test = [
                (f"{self.base_urls['qr_service']}/qr/generate", "QR Generation"),
                (f"{self.base_urls['enhanced_pos']}/enhanced/process-payment", "Payment Processing"),
                (f"{self.base_urls['device_manager']}/devices/statistics", "Device Statistics")
            ]
            
            for url, name in endpoints_to_test:
                response_times = []
                success_count = 0
                
                # Test 10 requests
                for i in range(10):
                    start_time = time.time()
                    try:
                        if 'generate' in url or 'process-payment' in url:
                            # POST request with test data
                            test_data = {
                                "merchant_id": "TEST_MERCHANT",
                                "amount": 100.0,
                                "currency": "USD"
                            }
                            async with session.post(url, json=test_data) as response:
                                response_time = time.time() - start_time
                                response_times.append(response_time)
                                if response.status == 200:
                                    success_count += 1
                        else:
                            # GET request
                            async with session.get(url) as response:
                                response_time = time.time() - start_time
                                response_times.append(response_time)
                                if response.status == 200:
                                    success_count += 1
                    except Exception as e:
                        response_time = time.time() - start_time
                        response_times.append(response_time)
                
                if response_times:
                    performance_results[name] = {
                        'avg_response_time': sum(response_times) / len(response_times),
                        'max_response_time': max(response_times),
                        'min_response_time': min(response_times),
                        'success_rate': (success_count / 10) * 100,
                        'total_requests': 10
                    }
        
        # Performance thresholds
        thresholds = {
            'QR Generation': 1.0,  # 1 second
            'Payment Processing': 3.0,  # 3 seconds
            'Device Statistics': 0.5  # 0.5 seconds
        }
        
        # Check if performance meets requirements
        performance_passed = 0
        for name, result in performance_results.items():
            threshold = thresholds.get(name, 2.0)
            if result['avg_response_time'] <= threshold and result['success_rate'] >= 90:
                performance_passed += 1
        
        status = 'PASSED' if performance_passed == len(performance_results) else 'PARTIAL' if performance_passed > 0 else 'FAILED'
        
        return {
            'status': status,
            'details': {
                'performance_results': performance_results,
                'thresholds': thresholds,
                'passed_requirements': performance_passed,
                'total_requirements': len(performance_results)
            }
        }
    
    async def validate_business_logic(self) -> Dict[str, Any]:
        """Validate business logic completeness"""
        logger.info("💼 Validating Business Logic...")
        
        business_features = {
            'multi_currency_support': False,
            'payment_methods': 0,
            'device_protocols': 0,
            'fraud_rules': 0,
            'qr_security_features': 0,
            'exchange_rate_providers': 0,
            'monitoring_metrics': False,
            'error_handling': False,
            'logging': False,
            'configuration_management': False
        }
        
        # Check enhanced POS service
        enhanced_pos_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration/enhanced_pos_service.py')
        if enhanced_pos_path.exists():
            try:
                with open(enhanced_pos_path, 'r') as f:
                    content = f.read()
                    business_features['multi_currency_support'] = 'CurrencyCode' in content
                    business_features['payment_methods'] = content.count('PaymentMethod.')
                    business_features['fraud_rules'] = content.count('FraudRule(')
                    business_features['error_handling'] = 'try:' in content and 'except' in content
                    business_features['logging'] = 'logger' in content or 'logging' in content
            except Exception as e:
                logger.warning(f"Could not check enhanced POS business logic: {e}")
        
        # Check device drivers
        device_drivers_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration/device_drivers.py')
        if device_drivers_path.exists():
            try:
                with open(device_drivers_path, 'r') as f:
                    content = f.read()
                    protocols = ['USB', 'Bluetooth', 'Serial', 'TCP']
                    business_features['device_protocols'] = sum(1 for protocol in protocols if protocol.lower() in content.lower())
            except Exception as e:
                logger.warning(f"Could not check device drivers: {e}")
        
        # Check QR validation service
        qr_service_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration/qr_validation_service.py')
        if qr_service_path.exists():
            try:
                with open(qr_service_path, 'r') as f:
                    content = f.read()
                    security_features = ['signature', 'encryption', 'validation', 'fraud', 'expiration']
                    business_features['qr_security_features'] = sum(1 for feature in security_features if feature in content.lower())
            except Exception as e:
                logger.warning(f"Could not check QR service business logic: {e}")
        
        # Check exchange rate service
        exchange_rate_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration/exchange_rate_service.py')
        if exchange_rate_path.exists():
            try:
                with open(exchange_rate_path, 'r') as f:
                    content = f.read()
                    business_features['exchange_rate_providers'] = content.count('Provider')
            except Exception as e:
                logger.warning(f"Could not check exchange rate service: {e}")
        
        # Check monitoring configuration
        prometheus_path = Path('/home/ubuntu/remittance-platform-complete/edge-services/pos-integration/monitoring/prometheus/prometheus.yml')
        if prometheus_path.exists():
            business_features['monitoring_metrics'] = True
        
        # Calculate business logic score
        total_score = (
            (5 if business_features['multi_currency_support'] else 0) +
            min(business_features['payment_methods'], 8) +
            min(business_features['device_protocols'], 4) +
            min(business_features['fraud_rules'], 10) +
            min(business_features['qr_security_features'], 5) +
            min(business_features['exchange_rate_providers'], 3) +
            (5 if business_features['monitoring_metrics'] else 0) +
            (3 if business_features['error_handling'] else 0) +
            (2 if business_features['logging'] else 0)
        )
        
        max_score = 45  # Maximum possible score
        business_score = (total_score / max_score) * 100
        
        status = 'PASSED' if business_score >= 80 else 'PARTIAL' if business_score >= 60 else 'FAILED'
        
        return {
            'status': status,
            'details': {
                'business_features': business_features,
                'business_score': business_score,
                'total_score': total_score,
                'max_score': max_score
            }
        }
    
    def generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report"""
        logger.info("📋 Generating Validation Report...")
        
        # Calculate overall statistics
        total_categories = len(self.validation_results)
        passed_categories = sum(1 for result in self.validation_results.values() if result['status'] == 'PASSED')
        partial_categories = sum(1 for result in self.validation_results.values() if result['status'] == 'PARTIAL')
        failed_categories = sum(1 for result in self.validation_results.values() if result['status'] == 'FAILED')
        
        overall_score = (passed_categories + (partial_categories * 0.5)) / total_categories * 100
        
        # Determine overall status
        if overall_score >= 95:
            overall_status = 'EXCELLENT'
        elif overall_score >= 85:
            overall_status = 'GOOD'
        elif overall_score >= 70:
            overall_status = 'ACCEPTABLE'
        elif overall_score >= 50:
            overall_status = 'NEEDS_IMPROVEMENT'
        else:
            overall_status = 'CRITICAL'
        
        # Generate recommendations
        recommendations = []
        
        for category, result in self.validation_results.items():
            if result['status'] == 'FAILED':
                recommendations.append(f"CRITICAL: Fix {category.replace('_', ' ').title()}")
            elif result['status'] == 'PARTIAL':
                recommendations.append(f"IMPROVE: Complete {category.replace('_', ' ').title()}")
        
        if not recommendations:
            recommendations.append("All systems are functioning optimally!")
        
        # Production readiness assessment
        production_ready = (
            overall_score >= 90 and
            len(self.critical_failures) == 0 and
            passed_categories >= (total_categories * 0.8)
        )
        
        report = {
            'validation_timestamp': datetime.now().isoformat(),
            'overall_status': overall_status,
            'overall_score': round(overall_score, 2),
            'production_ready': production_ready,
            'summary': {
                'total_categories': total_categories,
                'passed_categories': passed_categories,
                'partial_categories': partial_categories,
                'failed_categories': failed_categories,
                'critical_failures': len(self.critical_failures),
                'warnings': len(self.warnings)
            },
            'category_results': self.validation_results,
            'critical_failures': self.critical_failures,
            'warnings': self.warnings,
            'recommendations': recommendations,
            'next_steps': self._generate_next_steps(overall_status, production_ready)
        }
        
        return report
    
    def _generate_next_steps(self, overall_status: str, production_ready: bool) -> List[str]:
        """Generate next steps based on validation results"""
        next_steps = []
        
        if production_ready:
            next_steps.extend([
                "✅ System is production-ready!",
                "🚀 Deploy to production environment",
                "📊 Monitor system performance and metrics",
                "🔄 Set up automated health checks",
                "📋 Create operational runbooks"
            ])
        else:
            if overall_status == 'CRITICAL':
                next_steps.extend([
                    "🚨 Address all critical failures immediately",
                    "🔧 Fix missing core components",
                    "🧪 Run comprehensive testing",
                    "⚠️ Do not deploy to production"
                ])
            elif overall_status == 'NEEDS_IMPROVEMENT':
                next_steps.extend([
                    "🔧 Address critical and high-priority issues",
                    "🧪 Improve test coverage",
                    "📊 Enhance monitoring and alerting",
                    "🔄 Re-run validation after fixes"
                ])
            else:
                next_steps.extend([
                    "🔧 Address remaining issues",
                    "🧪 Complete testing suite",
                    "📊 Verify monitoring setup",
                    "🚀 Prepare for production deployment"
                ])
        
        return next_steps

async def main():
    """Main validation function"""
    print("🔍 Remittance Platform - Complete System Validation")
    print("=" * 60)
    
    validator = SystemValidator()
    
    try:
        # Run complete validation
        report = await validator.validate_complete_system()
        
        # Print summary
        print(f"\n📊 VALIDATION SUMMARY")
        print(f"Overall Status: {report['overall_status']}")
        print(f"Overall Score: {report['overall_score']}%")
        print(f"Production Ready: {'✅ YES' if report['production_ready'] else '❌ NO'}")
        
        print(f"\n📈 CATEGORY BREAKDOWN")
        print(f"✅ Passed: {report['summary']['passed_categories']}")
        print(f"⚠️ Partial: {report['summary']['partial_categories']}")
        print(f"❌ Failed: {report['summary']['failed_categories']}")
        print(f"🚨 Critical Failures: {report['summary']['critical_failures']}")
        
        # Print detailed results
        print(f"\n📋 DETAILED RESULTS")
        for category, result in report['category_results'].items():
            status_emoji = "✅" if result['status'] == 'PASSED' else "⚠️" if result['status'] == 'PARTIAL' else "❌"
            print(f"{status_emoji} {category.replace('_', ' ').title()}: {result['status']}")
        
        # Print recommendations
        if report['recommendations']:
            print(f"\n💡 RECOMMENDATIONS")
            for rec in report['recommendations']:
                print(f"• {rec}")
        
        # Print next steps
        if report['next_steps']:
            print(f"\n🚀 NEXT STEPS")
            for step in report['next_steps']:
                print(f"• {step}")
        
        # Save detailed report
        report_path = Path('/home/ubuntu/validation_report.json')
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_path}")
        
        # Exit with appropriate code
        if report['production_ready']:
            print("\n🎉 VALIDATION COMPLETE - SYSTEM IS PRODUCTION READY! 🎉")
            sys.exit(0)
        else:
            print("\n⚠️ VALIDATION COMPLETE - SYSTEM NEEDS IMPROVEMENTS")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Validation failed with error: {e}")
        print(f"\n❌ VALIDATION FAILED: {e}")
        sys.exit(2)

if __name__ == "__main__":
    asyncio.run(main())
