import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Enhanced POS Service
Advanced fraud detection, multi-currency support, and comprehensive analytics
"""

import asyncio
import json
import logging
import math
import os
import time
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
import statistics

import httpx
import pandas as pd
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("enhanced-pos-service")
app.include_router(metrics_router)

from pydantic import BaseModel, Field, validator
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Integer, Boolean, JSON, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import aioredis

from pos_service import POSService, PaymentMethod, TransactionStatus, POSTransaction
from device_drivers import device_manager, DeviceCommand, DeviceInfo, DeviceProtocol
from qr_validation_service import QRValidationService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CurrencyCode(str):
    """ISO 4217 currency codes"""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CAD = "CAD"
    AUD = "AUD"
    CHF = "CHF"
    CNY = "CNY"
    INR = "INR"
    BRL = "BRL"

@dataclass
class ExchangeRate:
    from_currency: str
    to_currency: str
    rate: Decimal
    timestamp: datetime
    source: str = "internal"

@dataclass
class FraudRule:
    rule_id: str
    name: str
    description: str
    condition: str  # Python expression
    action: str  # "block", "flag", "require_approval"
    severity: str  # "low", "medium", "high", "critical"
    enabled: bool = True

@dataclass
class TransactionAnalytics:
    transaction_id: str
    risk_score: float
    fraud_indicators: List[str]
    velocity_score: float
    amount_score: float
    location_score: float
    device_score: float
    behavioral_score: float
    recommendation: str

class EnhancedPOSService(POSService):
    """Enhanced POS service with advanced features"""
    
    def __init__(self):
        super().__init__()
        self.qr_service = QRValidationService()
        self.exchange_rates: Dict[str, ExchangeRate] = {}
        self.fraud_rules: List[FraudRule] = []
        self.transaction_cache: Dict[str, Any] = {}
        self.analytics_cache: Dict[str, TransactionAnalytics] = {}
        self.currency_precision = {
            "USD": 2, "EUR": 2, "GBP": 2, "JPY": 0,
            "CAD": 2, "AUD": 2, "CHF": 2, "CNY": 2,
            "INR": 2, "BRL": 2
        }
        
        # Initialize fraud rules
        self._initialize_fraud_rules()
        
        # Start background tasks
        asyncio.create_task(self._update_exchange_rates())
        asyncio.create_task(self._analytics_processor())
    
    def _initialize_fraud_rules(self):
        """Initialize fraud detection rules"""
        self.fraud_rules = [
            FraudRule(
                rule_id="high_amount",
                name="High Amount Transaction",
                description="Transaction amount exceeds daily limit",
                condition="amount > 5000",
                action="require_approval",
                severity="high"
            ),
            FraudRule(
                rule_id="velocity_check",
                name="High Velocity Transactions",
                description="Too many transactions in short time",
                condition="transaction_count_last_hour > 10",
                action="flag",
                severity="medium"
            ),
            FraudRule(
                rule_id="unusual_time",
                name="Unusual Transaction Time",
                description="Transaction outside normal hours",
                condition="hour < 6 or hour > 23",
                action="flag",
                severity="low"
            ),
            FraudRule(
                rule_id="round_amount",
                name="Round Amount Pattern",
                description="Suspicious round amounts",
                condition="amount % 100 == 0 and amount >= 1000",
                action="flag",
                severity="medium"
            ),
            FraudRule(
                rule_id="device_change",
                name="Device Change Pattern",
                description="Different device than usual",
                condition="device_id != usual_device_id",
                action="flag",
                severity="low"
            ),
            FraudRule(
                rule_id="geographic_anomaly",
                name="Geographic Anomaly",
                description="Transaction from unusual location",
                condition="distance_from_usual_location > 100",
                action="require_approval",
                severity="high"
            ),
            FraudRule(
                rule_id="duplicate_transaction",
                name="Duplicate Transaction",
                description="Identical transaction within short time",
                condition="duplicate_in_last_minutes < 5",
                action="block",
                severity="critical"
            ),
        ]
    
    async def _update_exchange_rates(self):
        """Update exchange rates periodically"""
        while True:
            try:
                await self._fetch_exchange_rates()
                await asyncio.sleep(3600)  # Update every hour
            except Exception as e:
                logger.error(f"Exchange rate update failed: {e}")
                await asyncio.sleep(300)  # Retry in 5 minutes
    
    async def _fetch_exchange_rates(self):
        """Fetch current exchange rates from live API with static fallback"""
        base_currency = "USD"
        target_currencies = list(self.currency_precision.keys())
        base_rates = None
        source = "static_fallback"
        
        api_key = os.getenv("EXCHANGE_RATE_API_KEY", "")
        if api_key:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{base_currency}",
                        timeout=15.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("result") == "success":
                            rates_raw = data.get("conversion_rates", {})
                            base_rates = {c: rates_raw[c] for c in target_currencies if c in rates_raw}
                            source = "exchangerate-api.com"
                            logger.info("Fetched live exchange rates from exchangerate-api.com")
            except Exception as e:
                logger.warning(f"Live exchange rate fetch failed, falling back to static rates: {e}")
        
        if base_rates is None:
            base_rates = {
                "USD": 1.0, "EUR": 0.85, "GBP": 0.73, "JPY": 110.0,
                "CAD": 1.25, "AUD": 1.35, "CHF": 0.92, "CNY": 6.45,
                "INR": 74.5, "BRL": 5.2,
            }
            logger.info("Using static fallback exchange rates")
        
        try:
            for from_curr, from_rate in base_rates.items():
                for to_curr, to_rate in base_rates.items():
                    if from_curr != to_curr:
                        rate = Decimal(str(to_rate / from_rate)).quantize(
                            Decimal('0.0001'), rounding=ROUND_HALF_UP
                        )
                        self.exchange_rates[f"{from_curr}_{to_curr}"] = ExchangeRate(
                            from_currency=from_curr,
                            to_currency=to_curr,
                            rate=rate,
                            timestamp=datetime.utcnow(),
                            source=source
                        )
            
            logger.info(f"Updated {len(self.exchange_rates)} exchange rates (source: {source})")
            
        except Exception as e:
            logger.error(f"Failed to build exchange rate matrix: {e}")
    
    def convert_currency(self, amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
        """Convert amount between currencies"""
        if from_currency == to_currency:
            return amount
        
        rate_key = f"{from_currency}_{to_currency}"
        if rate_key not in self.exchange_rates:
            raise ValueError(f"Exchange rate not available: {rate_key}")
        
        exchange_rate = self.exchange_rates[rate_key]
        
        # Check if rate is recent (within 2 hours)
        if datetime.utcnow() - exchange_rate.timestamp > timedelta(hours=2):
            logger.warning(f"Exchange rate is stale: {rate_key}")
        
        converted_amount = amount * exchange_rate.rate
        
        # Round to currency precision
        precision = self.currency_precision.get(to_currency, 2)
        return converted_amount.quantize(
            Decimal('0.' + '0' * precision), rounding=ROUND_HALF_UP
        )
    
    async def _analytics_processor(self):
        """Process transaction analytics in background"""
        while True:
            try:
                # Process pending analytics
                await self._process_pending_analytics()
                await asyncio.sleep(30)  # Process every 30 seconds
            except Exception as e:
                logger.error(f"Analytics processing error: {e}")
                await asyncio.sleep(60)
    
    async def _process_pending_analytics(self):
        """Process pending transaction analytics"""
        try:
            # Get recent transactions that need analysis
            db = self.get_db_session()
            
            recent_transactions = db.query(POSTransaction).filter(
                POSTransaction.created_at >= datetime.utcnow() - timedelta(hours=1)
            ).all()
            
            for transaction in recent_transactions:
                if transaction.transaction_id not in self.analytics_cache:
                    analytics = await self._analyze_transaction(transaction)
                    self.analytics_cache[transaction.transaction_id] = analytics
            
            db.close()
            
        except Exception as e:
            logger.error(f"Analytics processing failed: {e}")
    
    async def _analyze_transaction(self, transaction: POSTransaction) -> TransactionAnalytics:
        """Analyze transaction for fraud and patterns"""
        try:
            fraud_indicators = []
            scores = {
                "velocity": 0.0,
                "amount": 0.0,
                "location": 0.0,
                "device": 0.0,
                "behavioral": 0.0
            }
            
            # Velocity analysis
            velocity_score = await self._calculate_velocity_score(transaction)
            scores["velocity"] = velocity_score
            
            if velocity_score > 0.7:
                fraud_indicators.append("high_velocity")
            
            # Amount analysis
            amount_score = await self._calculate_amount_score(transaction)
            scores["amount"] = amount_score
            
            if amount_score > 0.8:
                fraud_indicators.append("suspicious_amount")
            
            # Location analysis
            location_score = await self._calculate_location_score(transaction)
            scores["location"] = location_score
            
            if location_score > 0.6:
                fraud_indicators.append("location_anomaly")
            
            # Device analysis
            device_score = await self._calculate_device_score(transaction)
            scores["device"] = device_score
            
            if device_score > 0.5:
                fraud_indicators.append("device_anomaly")
            
            # Behavioral analysis
            behavioral_score = await self._calculate_behavioral_score(transaction)
            scores["behavioral"] = behavioral_score
            
            if behavioral_score > 0.7:
                fraud_indicators.append("behavioral_anomaly")
            
            # Calculate overall risk score
            risk_score = (
                scores["velocity"] * 0.3 +
                scores["amount"] * 0.25 +
                scores["location"] * 0.2 +
                scores["device"] * 0.15 +
                scores["behavioral"] * 0.1
            )
            
            # Determine recommendation
            if risk_score > 0.8:
                recommendation = "block"
            elif risk_score > 0.6:
                recommendation = "require_approval"
            elif risk_score > 0.4:
                recommendation = "flag"
            else:
                recommendation = "approve"
            
            return TransactionAnalytics(
                transaction_id=transaction.transaction_id,
                risk_score=risk_score,
                fraud_indicators=fraud_indicators,
                velocity_score=scores["velocity"],
                amount_score=scores["amount"],
                location_score=scores["location"],
                device_score=scores["device"],
                behavioral_score=scores["behavioral"],
                recommendation=recommendation
            )
            
        except Exception as e:
            logger.error(f"Transaction analysis failed: {e}")
            return TransactionAnalytics(
                transaction_id=transaction.transaction_id,
                risk_score=0.0,
                fraud_indicators=["analysis_error"],
                velocity_score=0.0,
                amount_score=0.0,
                location_score=0.0,
                device_score=0.0,
                behavioral_score=0.0,
                recommendation="manual_review"
            )
    
    async def _calculate_velocity_score(self, transaction: POSTransaction) -> float:
        """Calculate velocity-based risk score"""
        try:
            db = self.get_db_session()
            
            # Count transactions in last hour
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            hour_count = db.query(POSTransaction).filter(
                POSTransaction.merchant_id == transaction.merchant_id,
                POSTransaction.terminal_id == transaction.terminal_id,
                POSTransaction.created_at >= hour_ago
            ).count()
            
            # Count transactions in last 10 minutes
            ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
            ten_min_count = db.query(POSTransaction).filter(
                POSTransaction.merchant_id == transaction.merchant_id,
                POSTransaction.terminal_id == transaction.terminal_id,
                POSTransaction.created_at >= ten_min_ago
            ).count()
            
            db.close()
            
            # Calculate velocity score (0-1)
            hour_score = min(hour_count / 20.0, 1.0)  # Max 20 per hour
            ten_min_score = min(ten_min_count / 5.0, 1.0)  # Max 5 per 10 min
            
            return max(hour_score, ten_min_score)
            
        except Exception as e:
            logger.error(f"Velocity score calculation failed: {e}")
            return 0.0
    
    async def _calculate_amount_score(self, transaction: POSTransaction) -> float:
        """Calculate amount-based risk score"""
        try:
            amount = transaction.amount
            
            # Check for round amounts
            round_score = 0.0
            if amount % 100 == 0 and amount >= 1000:
                round_score = 0.5
            elif amount % 1000 == 0:
                round_score = 0.8
            
            # Check for suspicious amounts
            suspicious_amounts = [999.99, 1000.00, 1500.00, 2000.00, 2500.00, 5000.00]
            suspicious_score = 0.0
            if amount in suspicious_amounts:
                suspicious_score = 0.9
            
            # Check for high amounts
            high_amount_score = 0.0
            if amount > 10000:
                high_amount_score = 1.0
            elif amount > 5000:
                high_amount_score = 0.7
            elif amount > 2000:
                high_amount_score = 0.4
            
            return max(round_score, suspicious_score, high_amount_score)
            
        except Exception as e:
            logger.error(f"Amount score calculation failed: {e}")
            return 0.0
    
    async def _calculate_location_score(self, transaction: POSTransaction) -> float:
        """Calculate location-based risk score using terminal geolocation data"""
        try:
            db = self.get_db_session()
            
            terminal_location = db.execute(
                "SELECT latitude, longitude FROM merchant_terminals WHERE terminal_id = :tid",
                {"tid": transaction.terminal_id}
            ).fetchone()
            
            transaction_location = db.execute(
                "SELECT latitude, longitude FROM pos_transactions "
                "WHERE transaction_id = :txid AND latitude IS NOT NULL",
                {"txid": transaction.transaction_id}
            ).fetchone()
            
            db.close()
            
            if not terminal_location or not transaction_location:
                return 0.3
            
            term_lat, term_lon = terminal_location
            tx_lat, tx_lon = transaction_location
            
            if term_lat is None or tx_lat is None:
                return 0.3
            
            R = 6371000
            lat1, lat2 = math.radians(term_lat), math.radians(tx_lat)
            dlat = math.radians(tx_lat - term_lat)
            dlon = math.radians(tx_lon - term_lon)
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            distance_m = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            
            allowed_radius = 500.0
            if distance_m <= allowed_radius:
                return 0.1
            elif distance_m <= allowed_radius * 5:
                return 0.4 + 0.3 * (distance_m / (allowed_radius * 5))
            else:
                return min(1.0, 0.7 + 0.3 * (distance_m / (allowed_radius * 10)))
            
        except Exception as e:
            logger.error(f"Location score calculation failed: {e}")
            return 0.3
    
    async def _calculate_device_score(self, transaction: POSTransaction) -> float:
        """Calculate device-based risk score"""
        try:
            # Check if device is known and trusted
            device_info = device_manager.get_device_info(transaction.terminal_id)
            
            if not device_info:
                return 0.8  # Unknown device
            
            if device_info.status != "connected":
                return 0.6  # Device not properly connected
            
            # Check device capabilities
            if not any(cap.name == "process_payment" for cap in device_info.capabilities):
                return 0.7  # Device not capable of payments
            
            return 0.1  # Known, trusted device
            
        except Exception as e:
            logger.error(f"Device score calculation failed: {e}")
            return 0.0
    
    async def _calculate_behavioral_score(self, transaction: POSTransaction) -> float:
        """Calculate behavioral-based risk score"""
        try:
            db = self.get_db_session()
            
            # Get historical transactions for pattern analysis
            week_ago = datetime.utcnow() - timedelta(days=7)
            historical = db.query(POSTransaction).filter(
                POSTransaction.merchant_id == transaction.merchant_id,
                POSTransaction.created_at >= week_ago
            ).all()
            
            db.close()
            
            if len(historical) < 5:
                return 0.3  # Not enough data
            
            # Analyze patterns
            amounts = [t.amount for t in historical]
            times = [t.created_at.hour for t in historical]
            
            # Check amount deviation
            avg_amount = statistics.mean(amounts)
            amount_deviation = abs(transaction.amount - avg_amount) / avg_amount
            amount_score = min(amount_deviation, 1.0)
            
            # Check time pattern
            avg_hour = statistics.mean(times)
            hour_deviation = abs(transaction.created_at.hour - avg_hour) / 12.0
            time_score = min(hour_deviation, 1.0)
            
            return (amount_score + time_score) / 2.0
            
        except Exception as e:
            logger.error(f"Behavioral score calculation failed: {e}")
            return 0.0
    
    async def process_enhanced_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment with enhanced fraud detection"""
        try:
            # Pre-process fraud check
            fraud_check = await self._pre_fraud_check(payment_data)
            
            if fraud_check["action"] == "block":
                return {
                    "success": False,
                    "error": "Transaction blocked by fraud detection",
                    "fraud_score": fraud_check["risk_score"],
                    "fraud_indicators": fraud_check["indicators"]
                }
            
            # Currency conversion if needed
            if payment_data.get("target_currency"):
                original_amount = Decimal(str(payment_data["amount"]))
                converted_amount = self.convert_currency(
                    original_amount,
                    payment_data["currency"],
                    payment_data["target_currency"]
                )
                payment_data["original_amount"] = float(original_amount)
                payment_data["original_currency"] = payment_data["currency"]
                payment_data["amount"] = float(converted_amount)
                payment_data["currency"] = payment_data["target_currency"]
                payment_data["exchange_rate"] = float(
                    self.exchange_rates[f"{payment_data['original_currency']}_{payment_data['currency']}"].rate
                )
            
            # Process payment through base service
            result = await super().process_payment(payment_data)
            
            # Post-process analytics
            if result.get("success"):
                transaction_id = result.get("transaction_id")
                if transaction_id:
                    # Queue for analytics processing
                    self.transaction_cache[transaction_id] = {
                        "payment_data": payment_data,
                        "result": result,
                        "timestamp": datetime.utcnow(),
                        "fraud_check": fraud_check
                    }
            
            return result
            
        except Exception as e:
            logger.error(f"Enhanced payment processing failed: {e}")
            return {
                "success": False,
                "error": "Payment processing error"
            }
    
    async def _pre_fraud_check(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-process fraud detection"""
        try:
            indicators = []
            risk_score = 0.0
            
            amount = payment_data.get("amount", 0)
            merchant_id = payment_data.get("merchant_id", "")
            terminal_id = payment_data.get("terminal_id", "")
            
            # Apply fraud rules
            for rule in self.fraud_rules:
                if not rule.enabled:
                    continue
                
                try:
                    # Create evaluation context
                    context = {
                        "amount": amount,
                        "merchant_id": merchant_id,
                        "terminal_id": terminal_id,
                        "hour": datetime.utcnow().hour,
                        "transaction_count_last_hour": await self._get_transaction_count_last_hour(merchant_id, terminal_id),
                        "duplicate_in_last_minutes": await self._check_duplicate_transaction(payment_data),
                        "device_id": terminal_id,
                        "usual_device_id": await self._get_usual_device_id(merchant_id),
                        "distance_from_usual_location": await self._get_location_distance(merchant_id),
                    }
                    
                    # Evaluate rule condition
                    if eval(rule.condition, {"__builtins__": {}}, context):
                        indicators.append(rule.rule_id)
                        
                        # Add to risk score based on severity
                        severity_weights = {
                            "low": 0.1,
                            "medium": 0.3,
                            "high": 0.6,
                            "critical": 1.0
                        }
                        risk_score += severity_weights.get(rule.severity, 0.1)
                        
                        # Check for blocking action
                        if rule.action == "block":
                            return {
                                "action": "block",
                                "risk_score": 1.0,
                                "indicators": indicators,
                                "triggered_rule": rule.rule_id
                            }
                
                except Exception as e:
                    logger.error(f"Fraud rule evaluation failed for {rule.rule_id}: {e}")
            
            # Determine action based on risk score
            if risk_score > 0.8:
                action = "require_approval"
            elif risk_score > 0.5:
                action = "flag"
            else:
                action = "approve"
            
            return {
                "action": action,
                "risk_score": min(risk_score, 1.0),
                "indicators": indicators
            }
            
        except Exception as e:
            logger.error(f"Pre-fraud check failed: {e}")
            return {
                "action": "manual_review",
                "risk_score": 0.5,
                "indicators": ["fraud_check_error"]
            }
    
    async def _get_transaction_count_last_hour(self, merchant_id: str, terminal_id: str) -> int:
        """Get transaction count in last hour"""
        try:
            db = self.get_db_session()
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            count = db.query(POSTransaction).filter(
                POSTransaction.merchant_id == merchant_id,
                POSTransaction.terminal_id == terminal_id,
                POSTransaction.created_at >= hour_ago
            ).count()
            
            db.close()
            return count
            
        except Exception as e:
            logger.error(f"Transaction count query failed: {e}")
            return 0
    
    async def _check_duplicate_transaction(self, payment_data: Dict[str, Any]) -> int:
        """Check for duplicate transactions in last N minutes"""
        try:
            db = self.get_db_session()
            five_min_ago = datetime.utcnow() - timedelta(minutes=5)
            
            # Look for identical amount and merchant
            duplicates = db.query(POSTransaction).filter(
                POSTransaction.merchant_id == payment_data.get("merchant_id"),
                POSTransaction.amount == payment_data.get("amount"),
                POSTransaction.created_at >= five_min_ago
            ).count()
            
            db.close()
            return duplicates
            
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return 0
    
    async def _get_usual_device_id(self, merchant_id: str) -> str:
        """Get the most commonly used device for merchant"""
        try:
            db = self.get_db_session()
            week_ago = datetime.utcnow() - timedelta(days=7)
            
            # Get most frequent terminal
            result = db.query(POSTransaction.terminal_id).filter(
                POSTransaction.merchant_id == merchant_id,
                POSTransaction.created_at >= week_ago
            ).all()
            
            db.close()
            
            if result:
                terminal_ids = [r[0] for r in result]
                return max(set(terminal_ids), key=terminal_ids.count)
            
            return ""
            
        except Exception as e:
            logger.error(f"Usual device query failed: {e}")
            return ""
    
    async def _get_location_distance(self, merchant_id: str) -> float:
        """Get distance from usual merchant location using geolocation data"""
        try:
            db = self.get_db_session()
            
            recent_locations = db.execute(
                "SELECT latitude, longitude FROM pos_transactions "
                "WHERE merchant_id = :mid AND latitude IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 20",
                {"mid": merchant_id}
            ).fetchall()
            
            db.close()
            
            if len(recent_locations) < 2:
                return 0.0
            
            lats = [row[0] for row in recent_locations if row[0] is not None]
            lons = [row[1] for row in recent_locations if row[1] is not None]
            
            if not lats or not lons:
                return 0.0
            
            avg_lat = sum(lats) / len(lats)
            avg_lon = sum(lons) / len(lons)
            
            latest_lat, latest_lon = recent_locations[0]
            if latest_lat is None or latest_lon is None:
                return 0.0
            
            R = 6371.0
            lat1, lat2 = math.radians(avg_lat), math.radians(latest_lat)
            dlat = math.radians(latest_lat - avg_lat)
            dlon = math.radians(latest_lon - avg_lon)
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            distance_km = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            
            return distance_km
            
        except Exception as e:
            logger.error(f"Location distance calculation failed: {e}")
            return 0.0
    
    def get_db_session(self) -> Session:
        """Get database session"""
        return SessionLocal()
    
    async def get_transaction_analytics(self, transaction_id: str) -> Optional[TransactionAnalytics]:
        """Get analytics for a transaction"""
        return self.analytics_cache.get(transaction_id)
    
    async def get_fraud_rules(self) -> List[FraudRule]:
        """Get all fraud rules"""
        return self.fraud_rules
    
    async def update_fraud_rule(self, rule_id: str, updates: Dict[str, Any]) -> bool:
        """Update a fraud rule"""
        for rule in self.fraud_rules:
            if rule.rule_id == rule_id:
                for key, value in updates.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                return True
        return False
    
    async def get_exchange_rates(self) -> Dict[str, ExchangeRate]:
        """Get current exchange rates"""
        return self.exchange_rates
    
    async def get_supported_currencies(self) -> List[str]:
        """Get list of supported currencies"""
        return list(self.currency_precision.keys())

# Create enhanced service instance
enhanced_pos_service = EnhancedPOSService()

# FastAPI app for enhanced POS endpoints
app = FastAPI(title="Enhanced POS Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await enhanced_pos_service.qr_service.init_redis()

@app.post("/enhanced/process-payment")
async def process_enhanced_payment_endpoint(payment_data: Dict[str, Any]):
    """Process payment with enhanced fraud detection"""
    return await enhanced_pos_service.process_enhanced_payment(payment_data)

@app.get("/enhanced/analytics/{transaction_id}")
async def get_transaction_analytics_endpoint(transaction_id: str):
    """Get transaction analytics"""
    analytics = await enhanced_pos_service.get_transaction_analytics(transaction_id)
    if analytics:
        return asdict(analytics)
    else:
        raise HTTPException(status_code=404, detail="Analytics not found")

@app.get("/enhanced/fraud-rules")
async def get_fraud_rules_endpoint():
    """Get fraud detection rules"""
    rules = await enhanced_pos_service.get_fraud_rules()
    return [asdict(rule) for rule in rules]

@app.put("/enhanced/fraud-rules/{rule_id}")
async def update_fraud_rule_endpoint(rule_id: str, updates: Dict[str, Any]):
    """Update fraud detection rule"""
    success = await enhanced_pos_service.update_fraud_rule(rule_id, updates)
    if success:
        return {"success": True}
    else:
        raise HTTPException(status_code=404, detail="Rule not found")

@app.get("/enhanced/exchange-rates")
async def get_exchange_rates_endpoint():
    """Get current exchange rates"""
    rates = await enhanced_pos_service.get_exchange_rates()
    return {k: asdict(v) for k, v in rates.items()}

@app.get("/enhanced/currencies")
async def get_supported_currencies_endpoint():
    """Get supported currencies"""
    return await enhanced_pos_service.get_supported_currencies()

@app.post("/enhanced/convert-currency")
async def convert_currency_endpoint(
    amount: float,
    from_currency: str,
    to_currency: str
):
    """Convert currency"""
    try:
        converted = enhanced_pos_service.convert_currency(
            Decimal(str(amount)),
            from_currency,
            to_currency
        )
        return {
            "original_amount": amount,
            "original_currency": from_currency,
            "converted_amount": float(converted),
            "converted_currency": to_currency,
            "exchange_rate": float(enhanced_pos_service.exchange_rates[f"{from_currency}_{to_currency}"].rate)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/enhanced/health")
async def enhanced_health_check():
    """Enhanced health check"""
    return {
        "status": "healthy",
        "service": "Enhanced POS Service",
        "timestamp": datetime.utcnow().isoformat(),
        "features": {
            "fraud_detection": True,
            "multi_currency": True,
            "analytics": True,
            "device_management": True,
            "qr_validation": True
        },
        "exchange_rates_count": len(enhanced_pos_service.exchange_rates),
        "fraud_rules_count": len(enhanced_pos_service.fraud_rules),
        "analytics_cache_size": len(enhanced_pos_service.analytics_cache)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "enhanced_pos_service:app",
        host="0.0.0.0",
        port=8072,
        reload=False,
        log_level="info"
    )
