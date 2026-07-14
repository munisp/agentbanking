"""Tests for pos-ml-engine Python sidecar."""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import detect_anomalies, check_compliance, analyze_sentiment, score_fraud_risk, state

def test_anomaly_detection_normal():
    """Normal transaction should not be anomalous."""
    result = detect_anomalies({
        "id": "test_1", "amount": 5000, "agent_id": "agent_test",
        "type": "transfer"
    })
    assert result["transaction_id"] == "test_1"
    assert isinstance(result["anomaly_score"], (int, float))
    assert result["risk_level"] in ("low", "medium", "high")

def test_anomaly_detection_high_value():
    """Very high value transaction should trigger anomaly."""
    result = detect_anomalies({
        "id": "test_2", "amount": 50_000_000, "agent_id": "agent_new",
        "type": "transfer"
    })
    assert result["is_anomalous"] == True
    assert result["anomaly_score"] > 0
    assert any(a["type"] == "high_value_new_agent" for a in result["anomalies"])

def test_compliance_clean():
    """Clean entity should pass compliance."""
    result = check_compliance({
        "id": "ent_1", "name": "John Doe", "type": "individual",
        "country": "NG", "amount": 100000
    })
    assert result["compliant"] == True
    assert result["risk_score"] == 0

def test_compliance_sanctions():
    """Sanctioned entity should fail compliance."""
    result = check_compliance({
        "id": "ent_2", "name": "SANCTIONED_ENTITY_001",
        "type": "organization", "country": "NG", "amount": 100000
    })
    assert result["compliant"] == False
    assert result["risk_level"] == "critical"
    assert any(f["type"] == "sanctions_match" for f in result["flags"])

def test_compliance_high_risk_country():
    """Entity from high-risk country should be flagged."""
    result = check_compliance({
        "id": "ent_3", "name": "Test Entity",
        "type": "organization", "country": "IR", "amount": 100000
    })
    assert result["compliant"] == False
    assert any(f["type"] == "high_risk_country" for f in result["flags"])

def test_compliance_aml_threshold():
    """Amount above CBN threshold should trigger AML flag."""
    result = check_compliance({
        "id": "ent_4", "name": "Big Corp",
        "type": "organization", "country": "NG", "amount": 6_000_000
    })
    assert any(f["type"] == "aml_threshold" for f in result["flags"])
    assert result["requires_ctr"] == True

def test_sentiment_positive():
    """Positive text should return positive sentiment."""
    result = analyze_sentiment("This service is excellent and amazing! I love it!")
    assert result["sentiment"] == "positive"
    assert result["positive_score"] > 0

def test_sentiment_negative():
    """Negative text should return negative sentiment."""
    result = analyze_sentiment("This is terrible and awful. The worst experience ever.")
    assert result["sentiment"] == "negative"
    assert result["negative_score"] < 0

def test_sentiment_neutral():
    """Neutral text should return neutral sentiment."""
    result = analyze_sentiment("The transaction was processed today.")
    assert result["sentiment"] == "neutral"

def test_fraud_scoring():
    """Fraud scoring should return valid result."""
    result = score_fraud_risk({
        "id": "txn_test", "amount": 100000, "agent_id": "agent_fraud_test",
        "device_id": "device_001", "ip_address": "192.168.1.1",
        "recipient": "recipient_001"
    })
    assert result["fraud_score"] >= 0
    assert result["risk_level"] in ("low", "medium", "high")
    assert result["action"] in ("allow", "review", "block")

def test_fraud_high_value():
    """High-value transaction should increase fraud score."""
    result = score_fraud_risk({
        "id": "txn_hv", "amount": 3_000_000, "agent_id": "agent_hv",
        "device_id": "new_device", "ip_address": "10.0.0.1",
        "recipient": "new_recipient"
    })
    assert result["fraud_score"] > 0
    assert "high_value_transaction" in result["factors"] or "very_high_value" in result["factors"]

if __name__ == "__main__":
    tests = [
        test_anomaly_detection_normal,
        test_anomaly_detection_high_value,
        test_compliance_clean,
        test_compliance_sanctions,
        test_compliance_high_risk_country,
        test_compliance_aml_threshold,
        test_sentiment_positive,
        test_sentiment_negative,
        test_sentiment_neutral,
        test_fraud_scoring,
        test_fraud_high_value,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  ✅ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {len(tests)} tests")
    sys.exit(1 if failed else 0)
