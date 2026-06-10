import unittest
from cips_tigerbeetle_service import CIPSTigerBeetleService

import os
class TestCIPSService(unittest.TestCase):

    def setUp(self):
        self.service = CIPSTigerBeetleService()

    def test_connection(self):
        self.assertTrue(self.service.connected)

    def test_cross_border_payment(self):
        payment_details = {
            "payment_id": "test_cips_payment_456",
            "sender_account": "test_sender_cips",
            "receiver_account": "test_receiver_cips",
            "amount": 50000,
            "source_currency": "USD",
            "target_currency": "CNY",
            "fx_rate": 6.8,
            "correspondent_banks": {"receiver": {"bic": "TESTBIC"}}
        }
        result = self.service.process_cross_border_payment(**payment_details)
        self.assertTrue(result["success"])
        self.assertIn("transfer_ids", result)

if __name__ == '__main__':
    unittest.main()
