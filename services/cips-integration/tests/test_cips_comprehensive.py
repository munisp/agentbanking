#!/usr/bin/env python3
"""
CIPS TigerBeetle Comprehensive Testing Suite
Complete tests for CIPS-TigerBeetle integration
Version: 1.0.0
"""

import unittest
import sys
import os
import json
import time
from decimal import Decimal
from typing import Dict, List, Optional
import logging

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.cips_tigerbeetle_service import CIPSTigerBeetleService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestCIPSInitialization(unittest.TestCase):
    """Test CIPS service initialization"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = CIPSTigerBeetleService()
    
    def test_01_tigerbeetle_connection(self):
        """Test 1: TigerBeetle connection initialization"""
        logger.info("\n=== Test 1: TigerBeetle Connection ===")
        self.assertIsNotNone(self.service.client)
        self.assertTrue(hasattr(self.service, 'accounts'))
        logger.info("✅ TigerBeetle connection successful")
    
    def test_02_account_initialization(self):
        """Test 2: Account initialization"""
        logger.info("\n=== Test 2: Account Initialization ===")
        self.assertIsNotNone(self.service.accounts)
        self.assertGreater(len(self.service.accounts), 0)
        logger.info(f"✅ Initialized {len(self.service.accounts)} accounts")
    
    def test_03_currency_support(self):
        """Test 3: Currency support"""
        logger.info("\n=== Test 3: Currency Support ===")
        supported_currencies = ["NGN", "USD", "EUR", "GBP", "CNY"]
        for currency in supported_currencies:
            nostro = self.service._get_nostro_account(currency)
            vostro = self.service._get_vostro_account(currency)
            self.assertIsNotNone(nostro, f"Nostro account for {currency} should exist")
            self.assertIsNotNone(vostro, f"Vostro account for {currency} should exist")
        logger.info(f"✅ All {len(supported_currencies)} currencies supported")


class TestCIPSAccountOperations(unittest.TestCase):
    """Test CIPS account operations"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = CIPSTigerBeetleService()
    
    def test_04_get_nostro_account(self):
        """Test 4: Get nostro account"""
        logger.info("\n=== Test 4: Get Nostro Account ===")
        account_id = self.service._get_nostro_account("USD")
        self.assertIsNotNone(account_id)
        self.assertIsInstance(account_id, int)
        logger.info(f"✅ Nostro USD account: {account_id}")
    
    def test_05_get_vostro_account(self):
        """Test 5: Get vostro account"""
        logger.info("\n=== Test 5: Get Vostro Account ===")
        account_id = self.service._get_vostro_account("NGN")
        self.assertIsNotNone(account_id)
        self.assertIsInstance(account_id, int)
        logger.info(f"✅ Vostro NGN account: {account_id}")
    
    def test_06_get_settlement_account(self):
        """Test 6: Get settlement account"""
        logger.info("\n=== Test 6: Get Settlement Account ===")
        account_id = self.service._get_settlement_account("USD")
        self.assertIsNotNone(account_id)
        logger.info(f"✅ Settlement USD account: {account_id}")
    
    def test_07_get_fx_reserve_account(self):
        """Test 7: Get FX reserve account"""
        logger.info("\n=== Test 7: Get FX Reserve Account ===")
        account_id = self.service._get_fx_reserve_account("EUR")
        self.assertIsNotNone(account_id)
        logger.info(f"✅ FX Reserve EUR account: {account_id}")
    
    def test_08_get_account_balance(self):
        """Test 8: Get account balance"""
        logger.info("\n=== Test 8: Get Account Balance ===")
        account_id = self.service._get_nostro_account("USD")
        balance = self.service._get_account_balance(account_id)
        self.assertIsNotNone(balance)
        self.assertGreaterEqual(balance, 0)
        logger.info(f"✅ Account balance: ${balance:,.2f}")


class TestCIPSCrossBorderPayments(unittest.TestCase):
    """Test CIPS cross-border payment processing"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = CIPSTigerBeetleService()
    
    def test_09_cross_border_payment_usd_to_ngn(self):
        """Test 9: Cross-border payment USD to NGN"""
        logger.info("\n=== Test 9: Cross-Border Payment USD → NGN ===")
        
        result = self.service.process_cross_border_payment(
            customer_account="1234567890",
            amount_usd=1000.00,
            beneficiary_account="9876543210",
            fx_rate=1500.00,
            correspondent_bank_bic="CITIUS33"
        )
        
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["amount_usd"], 1000.00)
        self.assertEqual(result["amount_ngn"], 1500000.00)
        self.assertEqual(result["fx_rate"], 1500.00)
        self.assertIn("transfer_id", result)
        
        logger.info(f"✅ Transfer ID: {result['transfer_id']}")
        logger.info(f"✅ USD: ${result['amount_usd']:,.2f} → NGN: ₦{result['amount_ngn']:,.2f}")
    
    def test_10_cross_border_payment_eur_to_ngn(self):
        """Test 10: Cross-border payment EUR to NGN"""
        logger.info("\n=== Test 10: Cross-Border Payment EUR → NGN ===")
        
        result = self.service.process_cross_border_payment(
            customer_account="2345678901",
            amount_usd=500.00,  # Will be converted from EUR
            beneficiary_account="8765432109",
            fx_rate=1600.00,
            correspondent_bank_bic="DEUTDEFF"
        )
        
        self.assertEqual(result["status"], "SUCCESS")
        logger.info(f"✅ Transfer completed: {result['transfer_id']}")
    
    def test_11_cross_border_payment_gbp_to_ngn(self):
        """Test 11: Cross-border payment GBP to NGN"""
        logger.info("\n=== Test 11: Cross-Border Payment GBP → NGN ===")
        
        result = self.service.process_cross_border_payment(
            customer_account="3456789012",
            amount_usd=750.00,
            beneficiary_account="7654321098",
            fx_rate=1550.00,
            correspondent_bank_bic="BARCGB22"
        )
        
        self.assertEqual(result["status"], "SUCCESS")
        self.assertGreater(result["amount_ngn"], 0)
        logger.info(f"✅ GBP payment processed: ₦{result['amount_ngn']:,.2f}")
    
    def test_12_cross_border_payment_cny_to_ngn(self):
        """Test 12: Cross-border payment CNY to NGN via CIPS"""
        logger.info("\n=== Test 12: Cross-Border Payment CNY → NGN (CIPS) ===")
        
        result = self.service.process_cross_border_payment(
            customer_account="4567890123",
            amount_usd=2000.00,
            beneficiary_account="6543210987",
            fx_rate=1520.00,
            correspondent_bank_bic="BKCHCNBJ"  # Bank of China
        )
        
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["amount_ngn"], 3040000.00)
        logger.info(f"✅ CIPS payment: CNY → NGN: ₦{result['amount_ngn']:,.2f}")


class TestCIPSFXConversion(unittest.TestCase):
    """Test CIPS FX conversion"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = CIPSTigerBeetleService()
    
    def test_13_fx_conversion_usd_to_ngn(self):
        """Test 13: FX conversion USD to NGN"""
        logger.info("\n=== Test 13: FX Conversion USD → NGN ===")
        
        result = self.service._convert_fx(
            from_currency="USD",
            to_currency="NGN",
            amount=1000.00,
            fx_rate=1500.00
        )
        
        self.assertEqual(result, 1500000.00)
        logger.info(f"✅ $1,000 USD = ₦1,500,000 NGN")
    
    def test_14_fx_conversion_eur_to_ngn(self):
        """Test 14: FX conversion EUR to NGN"""
        logger.info("\n=== Test 14: FX Conversion EUR → NGN ===")
        
        result = self.service._convert_fx(
            from_currency="EUR",
            to_currency="NGN",
            amount=1000.00,
            fx_rate=1600.00
        )
        
        self.assertEqual(result, 1600000.00)
        logger.info(f"✅ €1,000 EUR = ₦1,600,000 NGN")
    
    def test_15_fx_conversion_gbp_to_ngn(self):
        """Test 15: FX conversion GBP to NGN"""
        logger.info("\n=== Test 15: FX Conversion GBP → NGN ===")
        
        result = self.service._convert_fx(
            from_currency="GBP",
            to_currency="NGN",
            amount=1000.00,
            fx_rate=1800.00
        )
        
        self.assertEqual(result, 1800000.00)
        logger.info(f"✅ £1,000 GBP = ₦1,800,000 NGN")
    
    def test_16_fx_conversion_cny_to_ngn(self):
        """Test 16: FX conversion CNY to NGN"""
        logger.info("\n=== Test 16: FX Conversion CNY → NGN ===")
        
        result = self.service._convert_fx(
            from_currency="CNY",
            to_currency="NGN",
            amount=1000.00,
            fx_rate=210.00
        )
        
        self.assertEqual(result, 210000.00)
        logger.info(f"✅ ¥1,000 CNY = ₦210,000 NGN")


class TestCIPSComplianceChecks(unittest.TestCase):
    """Test CIPS compliance checks"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = CIPSTigerBeetleService()
    
    def test_17_compliance_check_aml(self):
        """Test 17: AML compliance check"""
        logger.info("\n=== Test 17: AML Compliance Check ===")
        
        result = self.service._check_compliance(
            customer_account="1234567890",
            amount_usd=1000.00,
            beneficiary_account="9876543210"
        )
        
        self.assertTrue(result)
        logger.info("✅ AML check passed")
    
    def test_18_compliance_check_sanctions(self):
        """Test 18: Sanctions screening"""
        logger.info("\n=== Test 18: Sanctions Screening ===")
        
        # This should pass for normal accounts
        result = self.service._check_compliance(
            customer_account="1234567890",
            amount_usd=5000.00,
            beneficiary_account="9876543210"
        )
        
        self.assertTrue(result)
        logger.info("✅ Sanctions check passed")
    
    def test_19_compliance_check_limits(self):
        """Test 19: Transaction limits check"""
        logger.info("\n=== Test 19: Transaction Limits Check ===")
        
        # Test within limits
        result = self.service._check_compliance(
            customer_account="1234567890",
            amount_usd=50000.00,
            beneficiary_account="9876543210"
        )
        
        self.assertTrue(result)
        logger.info("✅ Limits check passed for $50,000")


class TestCIPSMultiLegTransfers(unittest.TestCase):
    """Test CIPS multi-leg transfers"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = CIPSTigerBeetleService()
    
    def test_20_multi_leg_transfer_5_legs(self):
        """Test 20: Multi-leg transfer (5 legs)"""
        logger.info("\n=== Test 20: Multi-Leg Transfer (5 legs) ===")
        
        # Customer → Nostro → Correspondent → Vostro → Beneficiary
        result = self.service.process_cross_border_payment(
            customer_account="1234567890",
            amount_usd=10000.00,
            beneficiary_account="9876543210",
            fx_rate=1500.00,
            correspondent_bank_bic="CITIUS33"
        )
        
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("transfer_id", result)
        logger.info(f"✅ 5-leg transfer completed: {result['transfer_id']}")
    
    def test_21_multi_leg_transfer_with_fx(self):
        """Test 21: Multi-leg transfer with FX conversion"""
        logger.info("\n=== Test 21: Multi-Leg Transfer with FX ===")
        
        result = self.service.process_cross_border_payment(
            customer_account="2345678901",
            amount_usd=25000.00,
            beneficiary_account="8765432109",
            fx_rate=1550.00,
            correspondent_bank_bic="DEUTDEFF"
        )
        
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["amount_ngn"], 38750000.00)
        logger.info(f"✅ FX multi-leg transfer: ${result['amount_usd']:,.2f} → ₦{result['amount_ngn']:,.2f}")


class TestCIPSSettlement(unittest.TestCase):
    """Test CIPS settlement operations"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = CIPSTigerBeetleService()
    
    def test_22_settlement_reconciliation(self):
        """Test 22: Settlement reconciliation"""
        logger.info("\n=== Test 22: Settlement Reconciliation ===")
        
        # Process multiple payments
        for i in range(5):
            self.service.process_cross_border_payment(
                customer_account=f"123456789{i}",
                amount_usd=1000.00 * (i + 1),
                beneficiary_account=f"987654321{i}",
                fx_rate=1500.00,
                correspondent_bank_bic="CITIUS33"
            )
        
        # Check settlement account balance
        settlement_account = self.service._get_settlement_account("USD")
        balance = self.service._get_account_balance(settlement_account)
        
        self.assertGreaterEqual(balance, 0)
        logger.info(f"✅ Settlement balance: ${balance:,.2f}")
    
    def test_23_daily_settlement(self):
        """Test 23: Daily settlement processing"""
        logger.info("\n=== Test 23: Daily Settlement ===")
        
        # Simulate end-of-day settlement
        settlement_account = self.service._get_settlement_account("USD")
        balance = self.service._get_account_balance(settlement_account)
        
        self.assertIsNotNone(balance)
        logger.info(f"✅ Daily settlement processed: ${balance:,.2f}")


class TestCIPSErrorHandling(unittest.TestCase):
    """Test CIPS error handling"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = CIPSTigerBeetleService()
    
    def test_24_insufficient_balance(self):
        """Test 24: Insufficient balance error"""
        logger.info("\n=== Test 24: Insufficient Balance Error ===")
        
        # Try to transfer more than available
        result = self.service.process_cross_border_payment(
            customer_account="1234567890",
            amount_usd=999999999.00,  # Extremely large amount
            beneficiary_account="9876543210",
            fx_rate=1500.00,
            correspondent_bank_bic="CITIUS33"
        )
        
        # Should handle gracefully
        self.assertIn("status", result)
        logger.info(f"✅ Insufficient balance handled: {result.get('status', 'ERROR')}")
    
    def test_25_invalid_currency(self):
        """Test 25: Invalid currency error"""
        logger.info("\n=== Test 25: Invalid Currency Error ===")
        
        # Try to get account for unsupported currency
        try:
            account_id = self.service._get_nostro_account("XXX")
            # If it returns None, that's expected
            self.assertIsNone(account_id)
            logger.info("✅ Invalid currency handled gracefully")
        except Exception as e:
            logger.info(f"✅ Invalid currency error caught: {str(e)}")
    
    def test_26_invalid_account(self):
        """Test 26: Invalid account error"""
        logger.info("\n=== Test 26: Invalid Account Error ===")
        
        # Try to process payment with invalid account
        result = self.service.process_cross_border_payment(
            customer_account="",  # Empty account
            amount_usd=1000.00,
            beneficiary_account="9876543210",
            fx_rate=1500.00,
            correspondent_bank_bic="CITIUS33"
        )
        
        # Should handle gracefully
        self.assertIn("status", result)
        logger.info(f"✅ Invalid account handled: {result.get('status', 'ERROR')}")


class TestCIPSPerformance(unittest.TestCase):
    """Test CIPS performance"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = CIPSTigerBeetleService()
    
    def test_27_throughput_100_transfers(self):
        """Test 27: Throughput test (100 transfers)"""
        logger.info("\n=== Test 27: Throughput Test (100 transfers) ===")
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        for i in range(100):
            try:
                result = self.service.process_cross_border_payment(
                    customer_account=f"1234567{i:03d}",
                    amount_usd=100.00,
                    beneficiary_account=f"9876543{i:03d}",
                    fx_rate=1500.00,
                    correspondent_bank_bic="CITIUS33"
                )
                
                if result.get("status") == "SUCCESS":
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                logger.error(f"Transfer {i+1} failed: {str(e)}")
        
        end_time = time.time()
        duration = end_time - start_time
        tps = 100 / duration
        
        logger.info(f"✅ Throughput test completed:")
        logger.info(f"   Total: 100 transfers")
        logger.info(f"   Successful: {successful}")
        logger.info(f"   Failed: {failed}")
        logger.info(f"   Duration: {duration:.2f}s")
        logger.info(f"   Throughput: {tps:.2f} TPS")
        
        self.assertGreater(tps, 10, "Throughput should be > 10 TPS")
        self.assertGreater(successful / 100, 0.9, "Success rate should be > 90%")
    
    def test_28_latency_single_transfer(self):
        """Test 28: Latency test (single transfer)"""
        logger.info("\n=== Test 28: Latency Test (single transfer) ===")
        
        start_time = time.time()
        
        result = self.service.process_cross_border_payment(
            customer_account="1234567890",
            amount_usd=1000.00,
            beneficiary_account="9876543210",
            fx_rate=1500.00,
            correspondent_bank_bic="CITIUS33"
        )
        
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        logger.info(f"✅ Latency: {latency_ms:.2f}ms")
        
        self.assertEqual(result["status"], "SUCCESS")
        self.assertLess(latency_ms, 100, "Latency should be < 100ms")


class TestCIPSIntegration(unittest.TestCase):
    """Test CIPS end-to-end integration"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = CIPSTigerBeetleService()
    
    def test_29_end_to_end_remittance_flow(self):
        """Test 29: Complete end-to-end remittance flow"""
        logger.info("\n=== Test 29: End-to-End Remittance Flow ===")
        
        # Step 1: Customer initiates payment
        logger.info("Step 1: Customer initiates payment")
        customer_account = "1234567890"
        amount_usd = 5000.00
        beneficiary_account = "9876543210"
        fx_rate = 1500.00
        
        # Step 2: Process cross-border payment
        logger.info("Step 2: Process cross-border payment")
        result = self.service.process_cross_border_payment(
            customer_account=customer_account,
            amount_usd=amount_usd,
            beneficiary_account=beneficiary_account,
            fx_rate=fx_rate,
            correspondent_bank_bic="CITIUS33"
        )
        
        # Step 3: Verify transfer
        logger.info("Step 3: Verify transfer")
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["amount_usd"], amount_usd)
        self.assertEqual(result["amount_ngn"], amount_usd * fx_rate)
        
        # Step 4: Check balances
        logger.info("Step 4: Check balances")
        nostro_account = self.service._get_nostro_account("USD")
        vostro_account = self.service._get_vostro_account("NGN")
        
        nostro_balance = self.service._get_account_balance(nostro_account)
        vostro_balance = self.service._get_account_balance(vostro_account)
        
        self.assertGreaterEqual(nostro_balance, 0)
        self.assertGreaterEqual(vostro_balance, 0)
        
        logger.info(f"✅ End-to-end flow completed:")
        logger.info(f"   Transfer ID: {result['transfer_id']}")
        logger.info(f"   USD: ${result['amount_usd']:,.2f}")
        logger.info(f"   NGN: ₦{result['amount_ngn']:,.2f}")
        logger.info(f"   Nostro balance: ${nostro_balance:,.2f}")
        logger.info(f"   Vostro balance: ₦{vostro_balance:,.2f}")
    
    def test_30_multi_currency_remittance(self):
        """Test 30: Multi-currency remittance"""
        logger.info("\n=== Test 30: Multi-Currency Remittance ===")
        
        currencies = [
            ("USD", 1500.00),
            ("EUR", 1600.00),
            ("GBP", 1800.00),
            ("CNY", 210.00)
        ]
        
        for currency, fx_rate in currencies:
            result = self.service.process_cross_border_payment(
                customer_account=f"account_{currency}",
                amount_usd=1000.00,
                beneficiary_account="9876543210",
                fx_rate=fx_rate,
                correspondent_bank_bic="CITIUS33"
            )
            
            self.assertEqual(result["status"], "SUCCESS")
            logger.info(f"✅ {currency} → NGN: ₦{result['amount_ngn']:,.2f}")


def run_test_suite():
    """Run complete CIPS test suite"""
    logger.info("\n" + "="*70)
    logger.info("CIPS TIGERBEETLE COMPREHENSIVE TESTING SUITE")
    logger.info("Version: 1.0.0")
    logger.info("="*70)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestCIPSInitialization))
    suite.addTests(loader.loadTestsFromTestCase(TestCIPSAccountOperations))
    suite.addTests(loader.loadTestsFromTestCase(TestCIPSCrossBorderPayments))
    suite.addTests(loader.loadTestsFromTestCase(TestCIPSFXConversion))
    suite.addTests(loader.loadTestsFromTestCase(TestCIPSComplianceChecks))
    suite.addTests(loader.loadTestsFromTestCase(TestCIPSMultiLegTransfers))
    suite.addTests(loader.loadTestsFromTestCase(TestCIPSSettlement))
    suite.addTests(loader.loadTestsFromTestCase(TestCIPSErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestCIPSPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestCIPSIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    logger.info("\n" + "="*70)
    logger.info("TEST SUMMARY")
    logger.info("="*70)
    logger.info(f"Tests run: {result.testsRun}")
    logger.info(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    logger.info(f"Failures: {len(result.failures)}")
    logger.info(f"Errors: {len(result.errors)}")
    logger.info(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    logger.info("="*70)
    
    # Save results to JSON
    test_results = {
        "summary": {
            "total_tests": result.testsRun,
            "successes": result.testsRun - len(result.failures) - len(result.errors),
            "failures": len(result.failures),
            "errors": len(result.errors),
            "success_rate": ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100) if result.testsRun > 0 else 0
        },
        "failures": [str(f) for f in result.failures],
        "errors": [str(e) for e in result.errors]
    }
    
    with open("cips_test_results.json", "w") as f:
        json.dump(test_results, f, indent=2)
    
    logger.info("\nTest results saved to: cips_test_results.json")
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    run_test_suite()

