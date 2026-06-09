import unittest
from papss_tigerbeetle_service import PAPSSTigerBeetleService

class TestPAPSSService(unittest.TestCase):

    def setUp(self):
        self.service = PAPSSTigerBeetleService()

    def test_connection(self):
        self.assertTrue(self.service.connected)

    def test_pan_african_payment(self):
        payment_details = {
            "payment_id": "test_payment_123",
            "sender_account": "test_sender",
            "receiver_account": "test_receiver",
            "sender_country": "NG",
            "receiver_country": "GH",
            "amount": 10000,
            "source_currency": "NGN",
            "target_currency": "GHS",
            "fx_rate": 0.1,
            "trade_corridor": "ECOWAS",
            "payment_method": "MOBILE_MONEY"
        }
        result = self.service.process_pan_african_payment(**payment_details)
        self.assertTrue(result["success"])
        self.assertIn("transfer_ids", result)

if __name__ == '__main__':
    unittest.main()
