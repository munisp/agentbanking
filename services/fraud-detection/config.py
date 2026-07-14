from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator, Optional
import os
import logging
import hashlib
import struct
import math

logger = logging.getLogger(__name__)

# 1. Configuration Settings
class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    DATABASE_URL: str = "sqlite:///./fraud_detection.db"
    
    ML_MODEL_THRESHOLD: float = 0.75
    RULES_ENGINE_ENABLED: bool = True
    FRAUD_ML_SERVICE_URL: str = ""
    VELOCITY_CHECK_WINDOW_HOURS: int = 24
    HIGH_VALUE_THRESHOLD_NGN: float = 500000.0
    SUSPICIOUS_COUNTRIES: str = "IR,KP,SY,CU,SD"
    MAX_VELOCITY_COUNT: int = 10
    DEVICE_FINGERPRINT_WEIGHT: float = 0.15
    GEO_ANOMALY_WEIGHT: float = 0.20
    AMOUNT_ANOMALY_WEIGHT: float = 0.25
    VELOCITY_WEIGHT: float = 0.20
    MERCHANT_RISK_WEIGHT: float = 0.10
    TIME_ANOMALY_WEIGHT: float = 0.10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# 2. Database Setup
# Use connect_args={"check_same_thread": False} for SQLite
engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 3. Dependency Injection
def get_db() -> Generator:
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class MLService:
    """
    Production fraud detection ML service using deterministic feature-based scoring.
    Computes risk scores from transaction features: amount anomaly, velocity,
    geo-anomaly, device fingerprint, merchant risk, and time-of-day patterns.
    Falls back to external ML service if FRAUD_ML_SERVICE_URL is configured.
    """
    def __init__(self, threshold: float, rules_enabled: bool):
        self.threshold = threshold
        self.rules_enabled = rules_enabled
        self._external_url = settings.FRAUD_ML_SERVICE_URL
        self._suspicious_countries = set(settings.SUSPICIOUS_COUNTRIES.split(","))

    def _compute_amount_anomaly(self, amount: float, avg_amount: float, std_amount: float) -> float:
        if std_amount <= 0:
            std_amount = max(avg_amount * 0.5, 1.0)
        z_score = abs(amount - avg_amount) / std_amount
        return min(z_score / 5.0, 1.0)

    def _compute_velocity_score(self, tx_count_24h: int, tx_count_1h: int) -> float:
        daily_score = min(tx_count_24h / settings.MAX_VELOCITY_COUNT, 1.0)
        hourly_score = min(tx_count_1h / 5.0, 1.0)
        return max(daily_score, hourly_score)

    def _compute_geo_anomaly(self, country: str, ip_country: str, usual_country: str) -> float:
        score = 0.0
        if country and ip_country and country.upper() != ip_country.upper():
            score += 0.5
        if country and usual_country and country.upper() != usual_country.upper():
            score += 0.3
        if country and country.upper() in self._suspicious_countries:
            score += 0.5
        return min(score, 1.0)

    def _compute_device_score(self, device_fingerprint: str, known_devices: list) -> float:
        if not device_fingerprint:
            return 0.3
        if known_devices and device_fingerprint not in known_devices:
            return 0.7
        return 0.0

    def _compute_time_anomaly(self, hour: int, usual_hours: list) -> float:
        if not usual_hours:
            if 1 <= hour <= 5:
                return 0.6
            return 0.1
        min_dist = min(abs(hour - h) for h in usual_hours)
        return min(min_dist / 12.0, 1.0)

    def _compute_merchant_risk(self, merchant_category: str, merchant_risk_score: float) -> float:
        high_risk_categories = {"gambling", "crypto", "adult", "money_transfer", "prepaid_cards"}
        score = merchant_risk_score if merchant_risk_score else 0.0
        if merchant_category and merchant_category.lower() in high_risk_categories:
            score = max(score, 0.6)
        return min(score, 1.0)

    def score_transaction(self, transaction_data: dict) -> float:
        if self._external_url:
            try:
                import httpx
                resp = httpx.post(
                    f"{self._external_url}/predict",
                    json=transaction_data,
                    timeout=5.0
                )
                if resp.status_code == 200:
                    return resp.json().get("score", 0.5)
            except Exception as e:
                logger.warning(f"External ML service unavailable, using local scoring: {e}")

        amount = transaction_data.get("amount", 0.0)
        avg_amount = transaction_data.get("avg_transaction_amount", 50000.0)
        std_amount = transaction_data.get("std_transaction_amount", 25000.0)
        tx_count_24h = transaction_data.get("transaction_count_24h", 0)
        tx_count_1h = transaction_data.get("transaction_count_1h", 0)
        country = transaction_data.get("country", "NG")
        ip_country = transaction_data.get("ip_country", "")
        usual_country = transaction_data.get("usual_country", "NG")
        device_fingerprint = transaction_data.get("device_fingerprint", "")
        known_devices = transaction_data.get("known_devices", [])
        hour = transaction_data.get("hour", 12)
        usual_hours = transaction_data.get("usual_active_hours", [])
        merchant_category = transaction_data.get("merchant_category", "")
        merchant_risk = transaction_data.get("merchant_risk_score", 0.0)

        amount_score = self._compute_amount_anomaly(amount, avg_amount, std_amount)
        velocity_score = self._compute_velocity_score(tx_count_24h, tx_count_1h)
        geo_score = self._compute_geo_anomaly(country, ip_country, usual_country)
        device_score = self._compute_device_score(device_fingerprint, known_devices)
        time_score = self._compute_time_anomaly(hour, usual_hours)
        merchant_score = self._compute_merchant_risk(merchant_category, merchant_risk)

        weighted_score = (
            settings.AMOUNT_ANOMALY_WEIGHT * amount_score +
            settings.VELOCITY_WEIGHT * velocity_score +
            settings.GEO_ANOMALY_WEIGHT * geo_score +
            settings.DEVICE_FINGERPRINT_WEIGHT * device_score +
            settings.TIME_ANOMALY_WEIGHT * time_score +
            settings.MERCHANT_RISK_WEIGHT * merchant_score
        )
        return min(max(weighted_score, 0.0), 0.99)

    def apply_rules(self, transaction_data: dict) -> list[str]:
        if not self.rules_enabled:
            return []

        rules_triggered = []
        amount = transaction_data.get("amount", 0)
        country = transaction_data.get("country", "").upper()
        tx_count_24h = transaction_data.get("transaction_count_24h", 0)
        tx_count_1h = transaction_data.get("transaction_count_1h", 0)
        is_new_device = transaction_data.get("is_new_device", False)
        is_new_location = transaction_data.get("is_new_location", False)
        channel = transaction_data.get("channel", "")
        beneficiary_is_new = transaction_data.get("beneficiary_is_new", False)

        if amount > settings.HIGH_VALUE_THRESHOLD_NGN:
            rules_triggered.append("RULE_HIGH_VALUE_TRANSACTION")

        if country in self._suspicious_countries:
            rules_triggered.append("RULE_SUSPICIOUS_COUNTRY")

        if tx_count_24h > settings.MAX_VELOCITY_COUNT:
            rules_triggered.append("RULE_VELOCITY_CHECK_FAIL")

        if tx_count_1h > 5:
            rules_triggered.append("RULE_BURST_VELOCITY")

        if is_new_device and amount > settings.HIGH_VALUE_THRESHOLD_NGN * 0.5:
            rules_triggered.append("RULE_NEW_DEVICE_HIGH_VALUE")

        if is_new_location and is_new_device:
            rules_triggered.append("RULE_NEW_DEVICE_NEW_LOCATION")

        if beneficiary_is_new and amount > settings.HIGH_VALUE_THRESHOLD_NGN * 0.3:
            rules_triggered.append("RULE_NEW_BENEFICIARY_HIGH_VALUE")

        hour = transaction_data.get("hour", 12)
        if 1 <= hour <= 5 and amount > settings.HIGH_VALUE_THRESHOLD_NGN * 0.2:
            rules_triggered.append("RULE_OFF_HOURS_TRANSACTION")

        return rules_triggered

    def get_decision(self, ml_score: float, rules_triggered: list[str]) -> tuple[str, str]:
        block_rules = {"RULE_SUSPICIOUS_COUNTRY", "RULE_NEW_DEVICE_NEW_LOCATION"}
        if ml_score >= self.threshold:
            return "BLOCK", f"ML Score ({ml_score:.2f}) exceeds threshold ({self.threshold:.2f})"

        triggered_block = block_rules.intersection(rules_triggered)
        if triggered_block:
            return "BLOCK", f"Rules Engine: {', '.join(triggered_block)}"

        if len(rules_triggered) >= 3:
            return "BLOCK", f"Rules Engine: {len(rules_triggered)} rules triggered (>=3 threshold)"

        if rules_triggered:
            return "REVIEW", f"Rules Engine: {len(rules_triggered)} rules triggered: {', '.join(rules_triggered)}"

        return "ALLOW", "ML Score below threshold and no critical rules triggered"


def get_ml_service() -> MLService:
    """
    Dependency to get the ML/Rules Engine service instance.
    """
    return MLService(
        threshold=settings.ML_MODEL_THRESHOLD,
        rules_enabled=settings.RULES_ENGINE_ENABLED
    )

# 5. Initialization
def init_db():
    """
    Initializes the database and creates tables.
    This should be called once at application startup.
    """
    # Import models here to ensure they are registered with Base
    from . import models 
    Base.metadata.create_all(bind=engine)
