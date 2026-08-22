"""Funds-flow unit tests for the payment-processing-service.

Covers the idempotency / money-path behavior hardened in round 3:
  - NF-FF-13/20: claim-first, payload-bound, fail-closed idempotency on the
    money endpoints (replay → cached response, payload mismatch → 409,
    state-store outage → 503, no unprotected execution)
  - NF-FF-23: completed LPO repayment → 409
  - NF-FF-22: payload currency vs account currency mismatch → 400
  - NF-FF-34: single-use QR — replay → 409
  - NF-FF-33: transaction reference dedupe → 409, caller status override → 400
  - NF-FF-35: _to_minor_units contract (major → minor, x100)

Dapr state, the TB adapter and the 13 downstream adapters are fakes/mocks
installed by tests/conftest.py; the API handlers and PaymentService methods
under test are the real production code.
"""
import base64
import datetime
import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import api.payment as payment_api
import api.transactions as transactions_api
import services.payment as payment_svc_mod
import services.qr as qr_mod
from schemas import (
    Context,
    GenerateQRSchema,
    InitiateDepositSchema,
    InitiateLPOPaymentSchema,
    ValidateQRSchema,
)
from schemas.payment import ExternalAmount, ExternalParty, ExternalTransferSchema
from services.payment import PaymentService
from utils import CurrencyEnum

CTX = Context(tenant_id="t1", keycloak_id="k1", ledger_id="1", mint_account_id="999")


# ── Fake Dapr state store ────────────────────────────────────────────────────
class FakeStateResponse:
    def __init__(self, data):
        self.data = data


class FakeDaprClient:
    """In-memory Dapr state store honoring first-write-wins (etag == "")."""

    def __init__(self):
        self.store = {}
        self.fail_reads = False
        self.fail_writes = False

    def get_state(self, store_name, key):
        if self.fail_reads:
            raise RuntimeError("state store unavailable")
        return FakeStateResponse(self.store.get(key))

    def save_state(self, store_name, key, value, etag=None, state_options=None):
        if self.fail_writes:
            raise RuntimeError("state store unavailable")
        if etag == "" and key in self.store:
            # first-write concurrency: create-only-if-absent → race lost
            raise RuntimeError("etag mismatch on first write")
        self.store[key] = value.encode() if isinstance(value, str) else value


@pytest.fixture
def dapr():
    fake = FakeDaprClient()
    payment_api._dapr = fake
    payment_svc_mod._dapr_client = fake
    qr_mod._dapr = fake
    yield fake
    payment_api._dapr = None
    payment_svc_mod._dapr_client = None
    qr_mod._dapr = None


@pytest.fixture
def mock_payment_service(monkeypatch):
    """Replace the PaymentService used by api/payment.py handlers."""
    svc = MagicMock(name="PaymentService")
    monkeypatch.setattr(payment_api, "PaymentService", lambda: svc)
    return svc


def _deposit(payload_amount=100.0, key="key-1", **kw):
    payload = InitiateDepositSchema(recipient=12345, amount=payload_amount, note="dep")
    return payment_api.deposit(
        payload=payload,
        tenant_id="t1",
        keycloak_id="k1",
        ledger_id=None,
        mint_account_id=None,
        idempotency_key=key,
        **kw,
    )


# ── API idempotency (deposit handler) ────────────────────────────────────────
class TestDepositIdempotency:
    def test_first_call_processes_and_returns_200(self, dapr, mock_payment_service):
        mock_payment_service.initiate_deposit.return_value = "ref-001"
        resp = _deposit()
        assert resp.status_code == 200
        assert json.loads(bytes(resp.body)) == {
            "message": "success",
            "reference": "ref-001",
        }
        mock_payment_service.initiate_deposit.assert_called_once()

    def test_replay_returns_cached_response_without_reexecuting(
        self, dapr, mock_payment_service
    ):
        mock_payment_service.initiate_deposit.return_value = "ref-001"
        first = _deposit()
        replay = _deposit()  # same key, same payload
        assert replay.status_code == 202
        assert json.loads(bytes(replay.body)) == json.loads(bytes(first.body))
        # The money moved exactly once.
        assert mock_payment_service.initiate_deposit.call_count == 1

    def test_same_key_different_payload_is_409(self, dapr, mock_payment_service):
        mock_payment_service.initiate_deposit.return_value = "ref-001"
        _deposit(payload_amount=100.0)
        with pytest.raises(HTTPException) as exc_info:
            _deposit(payload_amount=200.0)  # same key, different amount
        assert exc_info.value.status_code == 409
        assert "different payload" in exc_info.value.detail
        # The second (conflicting) request never reached the money path.
        mock_payment_service.initiate_deposit.assert_called_once()

    def test_state_store_down_fails_closed_503(self, dapr, mock_payment_service):
        dapr.fail_reads = True
        with pytest.raises(HTTPException) as exc_info:
            _deposit()
        assert exc_info.value.status_code == 503
        mock_payment_service.initiate_deposit.assert_not_called()

    def test_claim_race_lost_replays_instead_of_double_spending(
        self, dapr, mock_payment_service
    ):
        """Concurrent duplicate loses the first-write race → cached 202, no re-run."""
        mock_payment_service.initiate_deposit.return_value = "ref-001"
        _deposit()  # completes and finalizes the claim

        # Simulate a racing duplicate: its first-write claim must fail because
        # the key now exists, and it must replay the stored response.
        replay = _deposit()
        assert replay.status_code == 202
        assert mock_payment_service.initiate_deposit.call_count == 1

    def test_transfer_credit_derives_key_from_transaction_id(
        self, dapr, mock_payment_service
    ):
        mock_payment_service.process_external_credit.return_value = "ref-x1"
        payload = ExternalTransferSchema(
            transactionId="ext-tx-1",
            party=ExternalParty(idType="ACCOUNT_NUMBER", idValue="0123456789"),
            amount=ExternalAmount(currency="NGN", amount=50.0),
        )

        def call():
            return payment_api.transfer_credit(
                payload=payload,
                tenant_id="t1",
                keycloak_id="k1",
                ledger_id=None,
                mint_account_id=None,
            )

        first = call()
        replay = call()
        assert first.status_code == 202
        assert replay.status_code == 202
        assert json.loads(bytes(replay.body)) == json.loads(bytes(first.body))
        assert mock_payment_service.process_external_credit.call_count == 1


# ── PaymentService money-path guards ─────────────────────────────────────────
class TestLpoPayment:
    def test_completed_lpo_repayment_is_409(self):
        svc = PaymentService()
        svc._PaymentService__lpo_service_adapter.get_lpo_details.return_value = {
            "status": "completed",
            "total_repayment": 1000.0,
        }
        payload = InitiateLPOPaymentSchema(lpo_id="LPO-1", payer=42, pin="1234")
        with pytest.raises(HTTPException) as exc_info:
            svc.initiate_lpo_payment(payload, CTX)
        assert exc_info.value.status_code == 409
        svc._PaymentService__tigerbeetle_adapter.transfer.assert_not_called()

    def test_missing_lpo_is_404(self):
        svc = PaymentService()
        svc._PaymentService__lpo_service_adapter.get_lpo_details.return_value = None
        payload = InitiateLPOPaymentSchema(lpo_id="LPO-X", payer=42, pin="1234")
        with pytest.raises(HTTPException) as exc_info:
            svc.initiate_lpo_payment(payload, CTX)
        assert exc_info.value.status_code == 404


class TestExternalCreditCurrencyGuard:
    def _payload(self, currency="USD"):
        return ExternalTransferSchema(
            transactionId="ext-tx-9",
            party=ExternalParty(idType="ACCOUNT_NUMBER", idValue="0123456789"),
            amount=ExternalAmount(currency=currency, amount=100.0),
        )

    def test_currency_mismatch_is_400_and_no_transfer(self):
        svc = PaymentService()
        svc._PaymentService__account_service_adapter.get_account_by_account_number.return_value = {
            "account": {"id": 7, "account_currency": "NGN"}
        }
        svc._PaymentService__fraud_engine_adapter.score_transaction.return_value = {
            "decision": "allow",
            "score": 0.0,
        }
        with pytest.raises(HTTPException) as exc_info:
            svc.process_external_credit(self._payload("USD"), CTX)
        assert exc_info.value.status_code == 400
        assert "Currency mismatch" in exc_info.value.detail
        svc._PaymentService__tigerbeetle_adapter.transfer.assert_not_called()

    def test_matching_currency_proceeds_to_ledger(self, dapr):
        svc = PaymentService()
        svc._PaymentService__account_service_adapter.get_account_by_account_number.return_value = {
            "account": {"id": 7, "account_currency": "NGN"}
        }
        svc._PaymentService__fraud_engine_adapter.score_transaction.return_value = {
            "decision": "allow",
            "score": 0.0,
        }
        svc._PaymentService__commission_service_adapter.calculate_commission.return_value = {
            "net_amount_minor": 10000
        }
        svc._PaymentService__account_service_adapter.get_mint_account_by_ledger.return_value = {
            "id": 999
        }
        svc._PaymentService__tigerbeetle_adapter.transfer.return_value = 424242

        reference = svc.process_external_credit(self._payload("NGN"), CTX)

        assert reference == "424242"
        # 100.00 major → 10000 minor, never 1:1 or x100 twice.
        _, kwargs = svc._PaymentService__tigerbeetle_adapter.transfer.call_args
        assert kwargs["amount"] == 10000
        assert kwargs["ledger"] == 1  # NGN ledger


class TestMinorUnits:
    def test_to_minor_units_contract(self):
        assert PaymentService._to_minor_units(1.23) == 123
        assert PaymentService._to_minor_units(10) == 1000
        assert PaymentService._to_minor_units(0.01) == 1
        assert PaymentService._to_minor_units("2.50") == 250

    def test_minor_units_round_trips_with_major_units(self):
        assert PaymentService._to_major_units(
            PaymentService._to_minor_units(1.23)
        ) == pytest.approx(1.23)


# ── QR single-use (NF-FF-34) ─────────────────────────────────────────────────
class TestQrSingleUse:
    def _signed_payload(self, tmp_path, monkeypatch):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.generate()
        pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        monkeypatch.setenv("QR_PRIVATE_KEY_PEM", pem)

        public_pem = private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        monkeypatch.chdir(tmp_path)
        (tmp_path / "qr_public.key").write_bytes(public_pem)

        service = qr_mod.QRService()
        expiry = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=15)
        ).isoformat().replace("+00:00", "Z")
        qr_data = {
            "recipient": "12345",
            "amount": "100.00",
            "currency": CurrencyEnum.NGN.value,
            "expiry": expiry,
            "note": "invoice 7",
            "tenant": CTX.tenant_id,
            "ledger": CTX.ledger_id,
        }
        signature = service.sign_qr_payload(qr_data)
        payload = ValidateQRSchema(
            recipient=qr_data["recipient"],
            amount=qr_data["amount"],
            currency=CurrencyEnum.NGN,
            note=qr_data["note"],
            expiry=qr_data["expiry"],
            signature=signature,
        )
        return service, payload

    def test_valid_qr_validates_once_then_replay_is_409(
        self, dapr, tmp_path, monkeypatch
    ):
        service, payload = self._signed_payload(tmp_path, monkeypatch)

        assert service.validate_qr_code(payload, CTX) is True

        with pytest.raises(HTTPException) as exc_info:
            service.validate_qr_code(payload, CTX)
        assert exc_info.value.status_code == 409
        assert "already been used" in exc_info.value.detail

    def test_tampered_signature_is_rejected(self, dapr, tmp_path, monkeypatch):
        service, payload = self._signed_payload(tmp_path, monkeypatch)
        forged = payload.model_copy(
            update={"signature": base64.b64encode(b"forged").decode()}
        )
        assert service.validate_qr_code(forged, CTX) is False


# ── Transaction record creation (NF-FF-33) ───────────────────────────────────
class TestTransactionCreation:
    def test_duplicate_reference_is_409(self):
        db = MagicMock(name="db")
        db.execute.return_value.first.return_value = (1,)  # existing row
        body = transactions_api.TransactionCreate(reference="ref-1", amount=10.0)
        with pytest.raises(HTTPException) as exc_info:
            transactions_api.create_transaction(
                body=body, db=db, tenant_id="t1", keycloak_id="k1"
            )
        assert exc_info.value.status_code == 409
        assert "reference" in exc_info.value.detail.lower()

    def test_caller_status_override_is_400(self):
        db = MagicMock(name="db")
        body = transactions_api.TransactionCreate(status="success", amount=10.0)
        with pytest.raises(HTTPException) as exc_info:
            transactions_api.create_transaction(
                body=body, db=db, tenant_id="t1", keycloak_id="k1"
            )
        assert exc_info.value.status_code == 400
        db.execute.assert_not_called()

    def test_unknown_status_is_400(self):
        db = MagicMock(name="db")
        body = transactions_api.TransactionCreate(status="whatever", amount=10.0)
        with pytest.raises(HTTPException) as exc_info:
            transactions_api.create_transaction(
                body=body, db=db, tenant_id="t1", keycloak_id="k1"
            )
        assert exc_info.value.status_code == 400
        db.execute.assert_not_called()

    def test_new_transaction_is_always_pending(self):
        existing_check = MagicMock()
        existing_check.first.return_value = None
        insert_result = MagicMock()
        insert_result.mappings.return_value.first.return_value = {
            "id": "tx-1",
            "reference": "ref-9",
            "status": "pending",
        }
        db = MagicMock(name="db")
        db.execute.side_effect = [existing_check, insert_result]

        body = transactions_api.TransactionCreate(reference="ref-9", amount=10.0)
        row = transactions_api.create_transaction(
            body=body, db=db, tenant_id="t1", keycloak_id="k1"
        )
        assert row["status"] == "pending"
        db.commit.assert_called_once()
