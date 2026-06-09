#!/usr/bin/env python3
"""
Production PostgreSQL API
Complete REST API with authentication, validation, error handling
"""

from typing import Any, Dict, List, Optional, Union, Tuple

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from functools import wraps
import jwt
import uuid
from datetime import datetime, timedelta
import logging

from config.database import DatabaseManager
from database_service import (
    UserService, PIXKeyService, TransferMetadataService,
    ComplianceService, CDCService
)
from models import KYCStatus, PIXKeyType, TransferStatus

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['JWT_EXPIRATION_HOURS'] = 24

# Initialize database
db_manager = DatabaseManager()
db_manager.initialize()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Authentication decorator
def require_auth(f) -> Tuple:
    @wraps(f)
    def decorated(*args, **kwargs) -> Tuple:
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'No authorization token provided'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            g.user_id = uuid.UUID(payload['user_id'])
            g.email = payload['email']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        except Exception as e:
            return jsonify({'error': f'Authentication failed: {str(e)}'}), 401
        
        return f(*args, **kwargs)
    
    return decorated


# Health check
@app.route('/health', methods=['GET'])
def health_check() -> Tuple:
    """Health check endpoint"""
    db_healthy = db_manager.health_check()
    
    return jsonify({
        'success': True,
        'service': 'PostgreSQL Production API',
        'version': '1.0.0',
        'database': 'healthy' if db_healthy else 'unhealthy',
        'timestamp': datetime.utcnow().isoformat(),
        'features': [
            'User management',
            'PIX key resolution',
            'Transfer metadata',
            'Compliance tracking',
            'CDC integration with TigerBeetle',
            'Full ACID transactions',
            'SSL/TLS encryption',
            'JWT authentication'
        ]
    }), 200 if db_healthy else 503


# User Management Endpoints
@app.route('/api/v1/users', methods=['POST'])
def create_user() -> Tuple:
    """Create new user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['email', 'phone', 'full_name', 'country_code', 'tigerbeetle_account_id']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        user_service = UserService(db_manager)
        user = user_service.create_user(
            email=data['email'],
            phone=data['phone'],
            full_name=data['full_name'],
            country_code=data['country_code'],
            tigerbeetle_account_id=data['tigerbeetle_account_id']
        )
        
        # Generate JWT token
        token = jwt.encode({
            'user_id': str(user.id),
            'email': user.email,
            'exp': datetime.utcnow() + timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'success': True,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'phone': user.phone,
                'full_name': user.full_name,
                'country_code': user.country_code,
                'tigerbeetle_account_id': user.tigerbeetle_account_id,
                'kyc_status': user.kyc_status.value,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat()
            },
            'token': token
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/users/<user_id>', methods=['GET'])
@require_auth
def get_user(user_id) -> Tuple:
    """Get user by ID"""
    try:
        user_service = UserService(db_manager)
        user = user_service.get_user_by_id(uuid.UUID(user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'success': True,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'phone': user.phone,
                'full_name': user.full_name,
                'country_code': user.country_code,
                'tigerbeetle_account_id': user.tigerbeetle_account_id,
                'kyc_status': user.kyc_status.value,
                'kyc_verified_at': user.kyc_verified_at.isoformat() if user.kyc_verified_at else None,
                'aml_risk_score': user.aml_risk_score,
                'is_active': user.is_active,
                'is_blocked': user.is_blocked,
                'created_at': user.created_at.isoformat(),
                'last_login_at': user.last_login_at.isoformat() if user.last_login_at else None
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/users/<user_id>/kyc', methods=['PUT'])
@require_auth
def update_kyc_status(user_id) -> Tuple:
    """Update user KYC status"""
    try:
        data = request.get_json()
        
        if 'status' not in data:
            return jsonify({'error': 'Missing required field: status'}), 400
        
        try:
            status = KYCStatus[data['status'].upper()]
        except KeyError:
            return jsonify({'error': f'Invalid KYC status: {data["status"]}'}), 400
        
        user_service = UserService(db_manager)
        user = user_service.update_kyc_status(
            user_id=uuid.UUID(user_id),
            status=status,
            kyc_data=data.get('kyc_data')
        )
        
        return jsonify({
            'success': True,
            'user': {
                'id': str(user.id),
                'kyc_status': user.kyc_status.value,
                'kyc_verified_at': user.kyc_verified_at.isoformat() if user.kyc_verified_at else None
            }
        }), 200
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error updating KYC status: {e}")
        return jsonify({'error': str(e)}), 500


# PIX Key Management Endpoints
@app.route('/api/v1/pix-keys', methods=['POST'])
@require_auth
def create_pix_key() -> Tuple:
    """Create new PIX key"""
    try:
        data = request.get_json()
        
        required = ['pix_key', 'user_id', 'tigerbeetle_account_id', 'key_type']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        try:
            key_type = PIXKeyType[data['key_type'].upper()]
        except KeyError:
            return jsonify({'error': f'Invalid PIX key type: {data["key_type"]}'}), 400
        
        pix_service = PIXKeyService(db_manager)
        pix_key = pix_service.create_pix_key(
            pix_key=data['pix_key'],
            user_id=uuid.UUID(data['user_id']),
            tigerbeetle_account_id=data['tigerbeetle_account_id'],
            key_type=key_type,
            is_primary=data.get('is_primary', False)
        )
        
        return jsonify({
            'success': True,
            'pix_key': {
                'pix_key': pix_key.pix_key,
                'user_id': str(pix_key.user_id),
                'tigerbeetle_account_id': pix_key.tigerbeetle_account_id,
                'key_type': pix_key.key_type.value,
                'is_primary': pix_key.is_primary,
                'is_active': pix_key.is_active,
                'verified_at': pix_key.verified_at.isoformat() if pix_key.verified_at else None,
                'created_at': pix_key.created_at.isoformat()
            }
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating PIX key: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/pix-keys/<pix_key>', methods=['GET'])
def resolve_pix_key(pix_key) -> Tuple:
    """Resolve PIX key to TigerBeetle account"""
    try:
        pix_service = PIXKeyService(db_manager)
        pix = pix_service.resolve_pix_key(pix_key)
        
        if not pix:
            return jsonify({'error': 'PIX key not found'}), 404
        
        return jsonify({
            'success': True,
            'pix_key': pix.pix_key,
            'user_id': str(pix.user_id),
            'tigerbeetle_account_id': pix.tigerbeetle_account_id,
            'key_type': pix.key_type.value,
            'is_primary': pix.is_primary,
            'note': 'For account balance, query TigerBeetle with this account_id'
        }), 200
    
    except Exception as e:
        logger.error(f"Error resolving PIX key: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/users/<user_id>/pix-keys', methods=['GET'])
@require_auth
def get_user_pix_keys(user_id) -> Tuple:
    """Get all PIX keys for user"""
    try:
        pix_service = PIXKeyService(db_manager)
        pix_keys = pix_service.get_user_pix_keys(uuid.UUID(user_id))
        
        return jsonify({
            'success': True,
            'count': len(pix_keys),
            'pix_keys': [{
                'pix_key': pix.pix_key,
                'tigerbeetle_account_id': pix.tigerbeetle_account_id,
                'key_type': pix.key_type.value,
                'is_primary': pix.is_primary,
                'is_active': pix.is_active,
                'created_at': pix.created_at.isoformat()
            } for pix in pix_keys]
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting user PIX keys: {e}")
        return jsonify({'error': str(e)}), 500


# Transfer Metadata Endpoints
@app.route('/api/v1/transfers', methods=['POST'])
@require_auth
def create_transfer_metadata() -> Tuple:
    """Create transfer metadata (amounts are in TigerBeetle)"""
    try:
        data = request.get_json()
        
        required = ['tigerbeetle_transfer_id', 'user_id', 'currency_code', 'corridor']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        transfer_service = TransferMetadataService(db_manager)
        transfer = transfer_service.create_transfer_metadata(
            tigerbeetle_transfer_id=data['tigerbeetle_transfer_id'],
            user_id=uuid.UUID(data['user_id']),
            from_pix_key=data.get('from_pix_key'),
            to_pix_key=data.get('to_pix_key'),
            currency_code=data['currency_code'],
            corridor=data['corridor'],
            description=data.get('description'),
            reference_number=data.get('reference_number'),
            external_id=data.get('external_id'),
            metadata=data.get('metadata', {})
        )
        
        return jsonify({
            'success': True,
            'transfer': {
                'id': str(transfer.id),
                'tigerbeetle_transfer_id': transfer.tigerbeetle_transfer_id,
                'user_id': str(transfer.user_id),
                'from_pix_key': transfer.from_pix_key,
                'to_pix_key': transfer.to_pix_key,
                'currency_code': transfer.currency_code,
                'corridor': transfer.corridor,
                'status': transfer.status.value,
                'reference_number': transfer.reference_number,
                'created_at': transfer.created_at.isoformat()
            },
            'note': 'For transfer amount and balance, query TigerBeetle directly'
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating transfer metadata: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/transfers/<transfer_id>/status', methods=['PUT'])
@require_auth
def update_transfer_status(transfer_id) -> Tuple:
    """Update transfer status"""
    try:
        data = request.get_json()
        
        if 'status' not in data:
            return jsonify({'error': 'Missing required field: status'}), 400
        
        try:
            status = TransferStatus[data['status'].upper()]
        except KeyError:
            return jsonify({'error': f'Invalid transfer status: {data["status"]}'}), 400
        
        transfer_service = TransferMetadataService(db_manager)
        transfer = transfer_service.update_transfer_status(
            transfer_id=uuid.UUID(transfer_id),
            status=status
        )
        
        return jsonify({
            'success': True,
            'transfer': {
                'id': str(transfer.id),
                'status': transfer.status.value,
                'updated_at': transfer.updated_at.isoformat(),
                'completed_at': transfer.completed_at.isoformat() if transfer.completed_at else None
            }
        }), 200
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error updating transfer status: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/users/<user_id>/transfers', methods=['GET'])
@require_auth
def get_user_transfers(user_id) -> Tuple:
    """Get user transfer history"""
    try:
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 100)  # Max 100 transfers
        
        transfer_service = TransferMetadataService(db_manager)
        transfers = transfer_service.get_user_transfers(uuid.UUID(user_id), limit=limit)
        
        return jsonify({
            'success': True,
            'count': len(transfers),
            'transfers': [{
                'id': str(t.id),
                'tigerbeetle_transfer_id': t.tigerbeetle_transfer_id,
                'from_pix_key': t.from_pix_key,
                'to_pix_key': t.to_pix_key,
                'currency_code': t.currency_code,
                'corridor': t.corridor,
                'status': t.status.value,
                'reference_number': t.reference_number,
                'created_at': t.created_at.isoformat(),
                'completed_at': t.completed_at.isoformat() if t.completed_at else None
            } for t in transfers],
            'note': 'For transfer amounts, query TigerBeetle with tigerbeetle_transfer_id'
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting user transfers: {e}")
        return jsonify({'error': str(e)}), 500


# Compliance Endpoints
@app.route('/api/v1/compliance/check', methods=['POST'])
@require_auth
def create_compliance_check() -> Tuple:
    """Create compliance check record"""
    try:
        data = request.get_json()
        
        required = ['entity_type', 'entity_id', 'check_type', 'status', 'risk_score']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        compliance_service = ComplianceService(db_manager)
        record = compliance_service.create_compliance_record(
            entity_type=data['entity_type'],
            entity_id=uuid.UUID(data['entity_id']),
            check_type=data['check_type'],
            status=data['status'],
            risk_score=data['risk_score'],
            risk_level=data.get('risk_level'),
            findings=data.get('findings'),
            check_provider=data.get('check_provider')
        )
        
        return jsonify({
            'success': True,
            'compliance_record': {
                'id': str(record.id),
                'entity_type': record.entity_type,
                'entity_id': str(record.entity_id),
                'check_type': record.check_type,
                'status': record.status,
                'risk_score': record.risk_score,
                'risk_level': record.risk_level,
                'created_at': record.created_at.isoformat()
            }
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating compliance record: {e}")
        return jsonify({'error': str(e)}), 500


# CDC Endpoints (Internal)
@app.route('/api/internal/cdc/events', methods=['POST'])
def create_cdc_event() -> Tuple:
    """Create CDC event from TigerBeetle (internal endpoint)"""
    try:
        # Verify internal API key
        api_key = request.headers.get('X-Internal-API-Key')
        if api_key != 'your-internal-api-key-change-in-production':
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.get_json()
        
        required = ['event_type', 'tigerbeetle_id', 'event_data']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        cdc_service = CDCService(db_manager)
        event = cdc_service.create_cdc_event(
            event_type=data['event_type'],
            tigerbeetle_id=data['tigerbeetle_id'],
            event_data=data['event_data']
        )
        
        return jsonify({
            'success': True,
            'event_id': event.id,
            'created_at': event.created_at.isoformat()
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating CDC event: {e}")
        return jsonify({'error': str(e)}), 500


# Error handlers
@app.errorhandler(404)
def not_found(error) -> Tuple:
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error) -> Tuple:
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    print("🚀 Starting PostgreSQL Production API on port 5433")
    print("📊 Features: User management, PIX keys, Transfer metadata, Compliance, CDC")
    print("🔒 Security: JWT authentication, SSL/TLS ready")
    app.run(host='0.0.0.0', port=5433, debug=False)

