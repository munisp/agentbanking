#!/usr/bin/env python3
"""
CIPS Network Client with ISO 20022 Messaging
Complete implementation for CIPS network integration
Version: 1.0.0
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
import requests
import json
import uuid
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ISO20022MessageBuilder:
    """ISO 20022 Message Builder for CIPS"""
    
    @staticmethod
    def create_pacs008_credit_transfer(payment_data: Dict) -> str:
        """
        Create ISO 20022 pacs.008 message (FIToFICstmrCdtTrf)
        Credit Transfer between Financial Institutions
        """
        # Root element
        root = ET.Element(
            "Document",
            xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"
        )
        
        # FIToFICstmrCdtTrf
        fit_to_fit = ET.SubElement(root, "FIToFICstmrCdtTrf")
        
        # Group Header
        grp_hdr = ET.SubElement(fit_to_fit, "GrpHdr")
        ET.SubElement(grp_hdr, "MsgId").text = payment_data.get("message_id", str(uuid.uuid4()))
        ET.SubElement(grp_hdr, "CreDtTm").text = datetime.now(timezone.utc).isoformat()
        ET.SubElement(grp_hdr, "NbOfTxs").text = "1"
        
        # Settlement Information
        sttlm_inf = ET.SubElement(grp_hdr, "SttlmInf")
        ET.SubElement(sttlm_inf, "SttlmMtd").text = "CLRG"  # Clearing
        
        # Instructing Agent
        instg_agt = ET.SubElement(grp_hdr, "InstgAgt")
        fin_instn_id = ET.SubElement(instg_agt, "FinInstnId")
        ET.SubElement(fin_instn_id, "BICFI").text = payment_data.get("instructing_agent_bic", "")
        
        # Instructed Agent
        instd_agt = ET.SubElement(grp_hdr, "InstdAgt")
        fin_instn_id = ET.SubElement(instd_agt, "FinInstnId")
        ET.SubElement(fin_instn_id, "BICFI").text = payment_data.get("instructed_agent_bic", "")
        
        # Credit Transfer Transaction Information
        cdt_trf_tx_inf = ET.SubElement(fit_to_fit, "CdtTrfTxInf")
        
        # Payment Identification
        pmt_id = ET.SubElement(cdt_trf_tx_inf, "PmtId")
        ET.SubElement(pmt_id, "InstrId").text = payment_data.get("instruction_id", str(uuid.uuid4()))
        ET.SubElement(pmt_id, "EndToEndId").text = payment_data.get("end_to_end_id", str(uuid.uuid4()))
        ET.SubElement(pmt_id, "TxId").text = payment_data.get("transaction_id", str(uuid.uuid4()))
        
        # Interbank Settlement Amount
        intrbnk_sttlm_amt = ET.SubElement(
            cdt_trf_tx_inf,
            "IntrBkSttlmAmt",
            Ccy=payment_data.get("currency", "USD")
        )
        intrbnk_sttlm_amt.text = f"{payment_data.get('amount', 0):.2f}"
        
        # Interbank Settlement Date
        ET.SubElement(cdt_trf_tx_inf, "IntrBkSttlmDt").text = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Charge Bearer
        ET.SubElement(cdt_trf_tx_inf, "ChrgBr").text = "SHAR"  # Shared
        
        # Debtor Agent
        dbtr_agt = ET.SubElement(cdt_trf_tx_inf, "DbtrAgt")
        fin_instn_id = ET.SubElement(dbtr_agt, "FinInstnId")
        ET.SubElement(fin_instn_id, "BICFI").text = payment_data.get("debtor_agent_bic", "")
        
        # Debtor
        dbtr = ET.SubElement(cdt_trf_tx_inf, "Dbtr")
        ET.SubElement(dbtr, "Nm").text = payment_data.get("debtor_name", "")
        
        # Debtor Account
        dbtr_acct = ET.SubElement(cdt_trf_tx_inf, "DbtrAcct")
        dbtr_id = ET.SubElement(dbtr_acct, "Id")
        ET.SubElement(dbtr_id, "IBAN").text = payment_data.get("debtor_iban", "")
        
        # Creditor Agent
        cdtr_agt = ET.SubElement(cdt_trf_tx_inf, "CdtrAgt")
        fin_instn_id = ET.SubElement(cdtr_agt, "FinInstnId")
        ET.SubElement(fin_instn_id, "BICFI").text = payment_data.get("creditor_agent_bic", "")
        
        # Creditor
        cdtr = ET.SubElement(cdt_trf_tx_inf, "Cdtr")
        ET.SubElement(cdtr, "Nm").text = payment_data.get("creditor_name", "")
        
        # Creditor Account
        cdtr_acct = ET.SubElement(cdt_trf_tx_inf, "CdtrAcct")
        cdtr_id = ET.SubElement(cdtr_acct, "Id")
        ET.SubElement(cdtr_id, "IBAN").text = payment_data.get("creditor_iban", "")
        
        # Remittance Information
        rmt_inf = ET.SubElement(cdt_trf_tx_inf, "RmtInf")
        ET.SubElement(rmt_inf, "Ustrd").text = payment_data.get("remittance_info", "")
        
        # Convert to pretty XML string
        xml_str = ET.tostring(root, encoding="unicode")
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="  ")
    
    @staticmethod
    def create_pacs002_payment_status(status_data: Dict) -> str:
        """
        Create ISO 20022 pacs.002 message (FIToFIPmtStsRpt)
        Payment Status Report
        """
        # Root element
        root = ET.Element(
            "Document",
            xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"
        )
        
        # FIToFIPmtStsRpt
        fit_to_fi_pmt_sts_rpt = ET.SubElement(root, "FIToFIPmtStsRpt")
        
        # Group Header
        grp_hdr = ET.SubElement(fit_to_fi_pmt_sts_rpt, "GrpHdr")
        ET.SubElement(grp_hdr, "MsgId").text = status_data.get("message_id", str(uuid.uuid4()))
        ET.SubElement(grp_hdr, "CreDtTm").text = datetime.now(timezone.utc).isoformat()
        
        # Transaction Information and Status
        tx_inf_and_sts = ET.SubElement(fit_to_fi_pmt_sts_rpt, "TxInfAndSts")
        
        # Original Instruction Identification
        ET.SubElement(tx_inf_and_sts, "OrgnlInstrId").text = status_data.get("original_instruction_id", "")
        ET.SubElement(tx_inf_and_sts, "OrgnlEndToEndId").text = status_data.get("original_end_to_end_id", "")
        ET.SubElement(tx_inf_and_sts, "OrgnlTxId").text = status_data.get("original_transaction_id", "")
        
        # Transaction Status
        ET.SubElement(tx_inf_and_sts, "TxSts").text = status_data.get("status", "ACCP")  # Accepted
        
        # Status Reason Information
        if "status_reason" in status_data:
            sts_rsn_inf = ET.SubElement(tx_inf_and_sts, "StsRsnInf")
            rsn = ET.SubElement(sts_rsn_inf, "Rsn")
            ET.SubElement(rsn, "Cd").text = status_data.get("status_reason", "")
        
        # Convert to pretty XML string
        xml_str = ET.tostring(root, encoding="unicode")
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="  ")
    
    @staticmethod
    def create_pacs009_financial_institution_credit_transfer(payment_data: Dict) -> str:
        """
        Create ISO 20022 pacs.009 message (FinInstnCdtTrf)
        Financial Institution Credit Transfer (for settlement)
        """
        # Root element
        root = ET.Element(
            "Document",
            xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08"
        )
        
        # FinInstnCdtTrf
        fin_instn_cdt_trf = ET.SubElement(root, "FinInstnCdtTrf")
        
        # Group Header
        grp_hdr = ET.SubElement(fin_instn_cdt_trf, "GrpHdr")
        ET.SubElement(grp_hdr, "MsgId").text = payment_data.get("message_id", str(uuid.uuid4()))
        ET.SubElement(grp_hdr, "CreDtTm").text = datetime.now(timezone.utc).isoformat()
        ET.SubElement(grp_hdr, "NbOfTxs").text = "1"
        
        # Credit Transfer Transaction Information
        cdt_trf_tx_inf = ET.SubElement(fin_instn_cdt_trf, "CdtTrfTxInf")
        
        # Payment Identification
        pmt_id = ET.SubElement(cdt_trf_tx_inf, "PmtId")
        ET.SubElement(pmt_id, "InstrId").text = payment_data.get("instruction_id", str(uuid.uuid4()))
        ET.SubElement(pmt_id, "EndToEndId").text = payment_data.get("end_to_end_id", str(uuid.uuid4()))
        
        # Interbank Settlement Amount
        intrbnk_sttlm_amt = ET.SubElement(
            cdt_trf_tx_inf,
            "IntrBkSttlmAmt",
            Ccy=payment_data.get("currency", "USD")
        )
        intrbnk_sttlm_amt.text = f"{payment_data.get('amount', 0):.2f}"
        
        # Instructing Agent
        instg_agt = ET.SubElement(cdt_trf_tx_inf, "InstgAgt")
        fin_instn_id = ET.SubElement(instg_agt, "FinInstnId")
        ET.SubElement(fin_instn_id, "BICFI").text = payment_data.get("instructing_agent_bic", "")
        
        # Instructed Agent
        instd_agt = ET.SubElement(cdt_trf_tx_inf, "InstdAgt")
        fin_instn_id = ET.SubElement(instd_agt, "FinInstnId")
        ET.SubElement(fin_instn_id, "BICFI").text = payment_data.get("instructed_agent_bic", "")
        
        # Convert to pretty XML string
        xml_str = ET.tostring(root, encoding="unicode")
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="  ")
    
    @staticmethod
    def parse_pacs002_status_response(xml_string: str) -> Dict:
        """Parse pacs.002 status response"""
        try:
            root = ET.fromstring(xml_string)
            
            # Extract namespace
            ns = {"ns": "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10"}
            
            # Extract status information
            tx_inf_and_sts = root.find(".//ns:TxInfAndSts", ns)
            
            if tx_inf_and_sts is not None:
                return {
                    "original_instruction_id": tx_inf_and_sts.findtext("ns:OrgnlInstrId", "", ns),
                    "original_end_to_end_id": tx_inf_and_sts.findtext("ns:OrgnlEndToEndId", "", ns),
                    "original_transaction_id": tx_inf_and_sts.findtext("ns:OrgnlTxId", "", ns),
                    "status": tx_inf_and_sts.findtext("ns:TxSts", "", ns),
                    "status_reason": tx_inf_and_sts.findtext(".//ns:Rsn/ns:Cd", "", ns)
                }
            
            return {}
        except Exception as e:
            logger.error(f"Error parsing pacs.002 response: {str(e)}")
            return {}


class CIPSNetworkClient:
    """CIPS Network Client with ISO 20022 Integration"""
    
    def __init__(self, config: Dict) -> None:
        """
        Initialize CIPS network client
        
        Args:
            config: Configuration dictionary with:
                - endpoint: CIPS API endpoint
                - participant_id: CIPS participant ID
                - api_key: API authentication key
                - api_secret: API secret for HMAC
                - bic_code: Institution BIC code
                - timeout: Request timeout in seconds
        """
        self.endpoint = config.get("endpoint", "https://api.cips.com.cn/v1")
        self.participant_id = config.get("participant_id")
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")
        self.bic_code = config.get("bic_code")
        self.timeout = config.get("timeout", 30)
        
        self.message_builder = ISO20022MessageBuilder()
        
        logger.info(f"CIPS Network Client initialized for participant: {self.participant_id}")
    
    def _generate_signature(self, message: str, timestamp: str) -> str:
        """Generate HMAC-SHA256 signature for authentication"""
        data = f"{timestamp}:{message}"
        signature = hmac.new(
            self.api_secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_headers(self, message: str) -> Dict[str, str]:
        """Get request headers with authentication"""
        timestamp = datetime.now(timezone.utc).isoformat()
        signature = self._generate_signature(message, timestamp)
        
        return {
            "Content-Type": "application/xml",
            "X-CIPS-Participant-ID": self.participant_id,
            "X-CIPS-API-Key": self.api_key,
            "X-CIPS-Timestamp": timestamp,
            "X-CIPS-Signature": signature,
            "X-CIPS-BIC": self.bic_code
        }
    
    def send_credit_transfer(self, payment_data: Dict) -> Dict:
        """
        Send credit transfer (pacs.008) to CIPS network
        
        Args:
            payment_data: Payment information dictionary
            
        Returns:
            Response dictionary with status and transaction details
        """
        logger.info(f"Sending credit transfer: {payment_data.get('transaction_id')}")
        
        try:
            # Create pacs.008 message
            message = self.message_builder.create_pacs008_credit_transfer(payment_data)
            
            # Send to CIPS
            response = requests.post(
                f"{self.endpoint}/payments/credit-transfer",
                data=message,
                headers=self._get_headers(message),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                # Parse response
                response_data = self.message_builder.parse_pacs002_status_response(response.text)
                
                logger.info(f"Credit transfer accepted: {response_data.get('status')}")
                
                return {
                    "status": "SUCCESS",
                    "cips_status": response_data.get("status"),
                    "transaction_id": response_data.get("original_transaction_id"),
                    "message_id": payment_data.get("message_id"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                logger.error(f"Credit transfer failed: {response.status_code} - {response.text}")
                return {
                    "status": "FAILED",
                    "error_code": response.status_code,
                    "error_message": response.text
                }
                
        except requests.exceptions.Timeout:
            logger.error("Credit transfer timeout")
            return {
                "status": "TIMEOUT",
                "error_message": "Request timeout"
            }
        except Exception as e:
            logger.error(f"Credit transfer error: {str(e)}")
            return {
                "status": "ERROR",
                "error_message": str(e)
            }
    
    def query_payment_status(self, transaction_id: str) -> Dict:
        """
        Query payment status from CIPS network
        
        Args:
            transaction_id: Original transaction ID
            
        Returns:
            Status dictionary
        """
        logger.info(f"Querying payment status: {transaction_id}")
        
        try:
            response = requests.get(
                f"{self.endpoint}/payments/{transaction_id}/status",
                headers=self._get_headers(transaction_id),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                response_data = self.message_builder.parse_pacs002_status_response(response.text)
                
                return {
                    "status": "SUCCESS",
                    "payment_status": response_data.get("status"),
                    "transaction_id": transaction_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                logger.error(f"Status query failed: {response.status_code}")
                return {
                    "status": "FAILED",
                    "error_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"Status query error: {str(e)}")
            return {
                "status": "ERROR",
                "error_message": str(e)
            }
    
    def send_settlement_transfer(self, settlement_data: Dict) -> Dict:
        """
        Send settlement transfer (pacs.009) for interbank settlement
        
        Args:
            settlement_data: Settlement information dictionary
            
        Returns:
            Response dictionary
        """
        logger.info(f"Sending settlement transfer: {settlement_data.get('instruction_id')}")
        
        try:
            # Create pacs.009 message
            message = self.message_builder.create_pacs009_financial_institution_credit_transfer(settlement_data)
            
            # Send to CIPS
            response = requests.post(
                f"{self.endpoint}/settlements/transfer",
                data=message,
                headers=self._get_headers(message),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                logger.info("Settlement transfer accepted")
                return {
                    "status": "SUCCESS",
                    "instruction_id": settlement_data.get("instruction_id"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                logger.error(f"Settlement transfer failed: {response.status_code}")
                return {
                    "status": "FAILED",
                    "error_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"Settlement transfer error: {str(e)}")
            return {
                "status": "ERROR",
                "error_message": str(e)
            }
    
    def convert_swift_mt103_to_pacs008(self, mt103_message: str) -> str:
        """
        Convert SWIFT MT103 message to ISO 20022 pacs.008
        
        Args:
            mt103_message: SWIFT MT103 message string
            
        Returns:
            ISO 20022 pacs.008 XML string
        """
        logger.info("Converting SWIFT MT103 to ISO 20022 pacs.008")
        
        # Parse MT103 (simplified - real implementation would be more complex)
        payment_data = self._parse_mt103(mt103_message)
        
        # Create pacs.008
        return self.message_builder.create_pacs008_credit_transfer(payment_data)
    
    def _parse_mt103(self, mt103_message: str) -> Dict:
        """Parse SWIFT MT103 message (simplified)"""
        # This is a simplified parser
        # Real implementation would handle all MT103 fields
        
        payment_data = {
            "message_id": str(uuid.uuid4()),
            "transaction_id": str(uuid.uuid4()),
            "currency": "USD",
            "amount": 0.0,
            "debtor_name": "",
            "creditor_name": "",
            "remittance_info": ""
        }
        
        # Extract fields from MT103
        lines = mt103_message.split("\n")
        for line in lines:
            if line.startswith(":32A:"):  # Value Date, Currency, Amount
                parts = line[5:].split()
                if len(parts) >= 2:
                    payment_data["currency"] = parts[0]
                    payment_data["amount"] = float(parts[1].replace(",", ""))
            elif line.startswith(":50:"):  # Ordering Customer
                payment_data["debtor_name"] = line[4:].strip()
            elif line.startswith(":59:"):  # Beneficiary Customer
                payment_data["creditor_name"] = line[4:].strip()
            elif line.startswith(":70:"):  # Remittance Information
                payment_data["remittance_info"] = line[4:].strip()
        
        return payment_data
    
    def get_network_status(self) -> Dict:
        """Get CIPS network status"""
        logger.info("Checking CIPS network status")
        
        try:
            response = requests.get(
                f"{self.endpoint}/status",
                headers={"X-CIPS-API-Key": self.api_key},
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    "status": "ONLINE",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                return {
                    "status": "OFFLINE",
                    "error_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"Network status check error: {str(e)}")
            return {
                "status": "ERROR",
                "error_message": str(e)
            }


# Example usage
if __name__ == "__main__":
    # Configuration
    config = {
        "endpoint": "https://api-sandbox.cips.com.cn/v1",
        "participant_id": "PARTICIPANT123",
        "api_key": "your-api-key",
        "api_secret": "your-api-secret",
        "bic_code": "CITIUS33",
        "timeout": 30
    }
    
    # Initialize client
    client = CIPSNetworkClient(config)
    
    # Example payment
    payment_data = {
        "message_id": str(uuid.uuid4()),
        "transaction_id": str(uuid.uuid4()),
        "currency": "USD",
        "amount": 10000.00,
        "debtor_name": "Test Sender",
        "debtor_iban": "US12345678901234567890",
        "debtor_agent_bic": "CITIUS33",
        "creditor_name": "Test Receiver",
        "creditor_iban": "CN98765432109876543210",
        "creditor_agent_bic": "BKCHCNBJ",
        "remittance_info": "Test payment",
        "instructing_agent_bic": "CITIUS33",
        "instructed_agent_bic": "BKCHCNBJ"
    }
    
    # Send credit transfer
    result = client.send_credit_transfer(payment_data)
    print(json.dumps(result, indent=2))
    
    # Query status
    if result.get("status") == "SUCCESS":
        status = client.query_payment_status(result["transaction_id"])
        print(json.dumps(status, indent=2))

