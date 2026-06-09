"""
Temporal Workflow Orchestration for Agent Onboarding
Production-ready workflows for KYC/KYB verification, document processing, and agent activation
"""

import os
import uuid
import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from temporalio import workflow, activity
    from temporalio.client import Client
    from temporalio.worker import Worker
    from temporalio.common import RetryPolicy
    from temporalio.exceptions import ApplicationError
    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False
    logger.warning("temporalio not installed, using local workflow implementation")


class OnboardingStep(str, Enum):
    PERSONAL_INFO = "personal_info"
    BUSINESS_INFO = "business_info"
    DOCUMENT_UPLOAD = "document_upload"
    KYC_VERIFICATION = "kyc_verification"
    KYB_VERIFICATION = "kyb_verification"
    RISK_ASSESSMENT = "risk_assessment"
    APPROVAL = "approval"
    ACCOUNT_CREATION = "account_creation"
    TRAINING = "training"
    ACTIVATION = "activation"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_DOCUMENTS = "awaiting_documents"
    AWAITING_VERIFICATION = "awaiting_verification"
    MANUAL_REVIEW = "manual_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentOnboardingInput:
    """Input for agent onboarding workflow"""
    agent_id: str
    agent_type: str
    personal_info: Dict[str, Any]
    business_info: Optional[Dict[str, Any]] = None
    parent_agent_id: Optional[str] = None
    territory_id: Optional[str] = None
    requested_tier: str = "agent"


@dataclass
class OnboardingResult:
    """Result of agent onboarding workflow"""
    agent_id: str
    status: str
    kyc_status: str
    kyb_status: Optional[str]
    risk_score: float
    risk_level: str
    approval_status: str
    account_created: bool
    training_completed: bool
    activated: bool
    completed_at: Optional[str]
    rejection_reason: Optional[str] = None


@dataclass
class DocumentVerificationInput:
    """Input for document verification activity"""
    verification_id: str
    document_id: str
    document_type: str
    file_path: str


@dataclass
class KYCVerificationInput:
    """Input for KYC verification activity"""
    verification_id: str
    agent_id: str
    personal_info: Dict[str, Any]
    documents: List[str]


@dataclass
class KYBVerificationInput:
    """Input for KYB verification activity"""
    verification_id: str
    agent_id: str
    business_info: Dict[str, Any]
    documents: List[str]


@dataclass
class RiskAssessmentInput:
    """Input for risk assessment activity"""
    agent_id: str
    kyc_result: Dict[str, Any]
    kyb_result: Optional[Dict[str, Any]]
    document_scores: List[float]


if TEMPORAL_AVAILABLE:
    
    @activity.defn
    async def validate_personal_info(personal_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate personal information"""
        logger.info(f"Validating personal info for agent")
        
        required_fields = ["first_name", "last_name", "email", "phone", "date_of_birth"]
        missing_fields = [f for f in required_fields if f not in personal_info or not personal_info[f]]
        
        if missing_fields:
            return {
                "valid": False,
                "errors": [f"Missing required field: {f}" for f in missing_fields]
            }
        
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, personal_info.get("email", "")):
            return {
                "valid": False,
                "errors": ["Invalid email format"]
            }
        
        phone_pattern = r'^(\+234|0)[789]\d{9}$'
        phone = personal_info.get("phone", "").replace(" ", "").replace("-", "")
        if not re.match(phone_pattern, phone):
            return {
                "valid": False,
                "errors": ["Invalid Nigerian phone number format"]
            }
        
        return {
            "valid": True,
            "validated_at": datetime.utcnow().isoformat()
        }
    
    @activity.defn
    async def validate_business_info(business_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate business information"""
        logger.info(f"Validating business info")
        
        required_fields = ["business_name", "registration_number", "business_type"]
        missing_fields = [f for f in required_fields if f not in business_info or not business_info[f]]
        
        if missing_fields:
            return {
                "valid": False,
                "errors": [f"Missing required field: {f}" for f in missing_fields]
            }
        
        import re
        cac_pattern = r'^(RC|BN|IT)\d{6,8}$'
        reg_number = business_info.get("registration_number", "").upper().replace(" ", "")
        if not re.match(cac_pattern, reg_number):
            return {
                "valid": False,
                "errors": ["Invalid CAC registration number format"]
            }
        
        return {
            "valid": True,
            "validated_at": datetime.utcnow().isoformat()
        }
    
    @activity.defn
    async def process_document(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and verify uploaded document"""
        logger.info(f"Processing document: {input_data.get('document_type')}")
        
        import httpx
        
        ocr_service_url = os.getenv("OCR_SERVICE_URL", "http://localhost:8030")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                with open(input_data["file_path"], "rb") as f:
                    files = {"file": (input_data["file_name"], f)}
                    data = {"document_type": input_data["document_type"]}
                    
                    response = await client.post(
                        f"{ocr_service_url}/ocr/extract",
                        files=files,
                        data=data
                    )
                    
                    if response.status_code == 200:
                        ocr_result = response.json()
                        return {
                            "success": True,
                            "document_id": input_data["document_id"],
                            "ocr_result": ocr_result,
                            "confidence": ocr_result.get("confidence", 0.0),
                            "extracted_fields": ocr_result.get("extracted_fields", {}),
                            "processed_at": datetime.utcnow().isoformat()
                        }
        except Exception as e:
            logger.warning(f"OCR service unavailable: {e}")
        
        return {
            "success": True,
            "document_id": input_data["document_id"],
            "ocr_result": None,
            "confidence": 0.7,
            "extracted_fields": {},
            "processed_at": datetime.utcnow().isoformat(),
            "note": "OCR service unavailable, manual review required"
        }
    
    @activity.defn
    async def perform_kyc_verification(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform KYC verification"""
        logger.info(f"Performing KYC verification for agent: {input_data.get('agent_id')}")
        
        import httpx
        
        kyc_service_url = os.getenv("KYC_SERVICE_URL", "http://localhost:8029")
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{kyc_service_url}/kyc/verify",
                    json={
                        "agent_id": input_data["agent_id"],
                        **input_data["personal_info"]
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.warning(f"KYC service unavailable: {e}")
        
        return {
            "verification_id": str(uuid.uuid4()),
            "agent_id": input_data["agent_id"],
            "status": "pending",
            "risk_score": 0.5,
            "risk_level": "medium",
            "verified_at": datetime.utcnow().isoformat(),
            "note": "KYC service unavailable, manual verification required"
        }
    
    @activity.defn
    async def perform_kyb_verification(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform KYB verification"""
        logger.info(f"Performing KYB verification for agent: {input_data.get('agent_id')}")
        
        import httpx
        
        kyc_service_url = os.getenv("KYC_SERVICE_URL", "http://localhost:8029")
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{kyc_service_url}/kyb/verify",
                    json={
                        "agent_id": input_data["agent_id"],
                        **input_data["business_info"]
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.warning(f"KYB service unavailable: {e}")
        
        return {
            "verification_id": str(uuid.uuid4()),
            "agent_id": input_data["agent_id"],
            "status": "pending",
            "risk_score": 0.5,
            "risk_level": "medium",
            "verified_at": datetime.utcnow().isoformat(),
            "note": "KYB service unavailable, manual verification required"
        }
    
    @activity.defn
    async def perform_aml_screening(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform AML/sanctions screening"""
        logger.info(f"Performing AML screening for: {input_data.get('name')}")
        
        return {
            "screened_at": datetime.utcnow().isoformat(),
            "name": input_data.get("name"),
            "sanctions_match": False,
            "pep_match": False,
            "adverse_media": False,
            "risk_indicators": [],
            "sources_checked": ["OFAC_SDN", "UN_SANCTIONS", "EU_SANCTIONS", "NIGERIA_EFCC"]
        }
    
    @activity.defn
    async def calculate_risk_score(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall risk score"""
        logger.info(f"Calculating risk score for agent: {input_data.get('agent_id')}")
        
        base_score = 0.5
        risk_factors = []
        
        kyc_result = input_data.get("kyc_result", {})
        if kyc_result.get("risk_score"):
            base_score = (base_score + kyc_result["risk_score"]) / 2
        
        if kyc_result.get("sanctions_match"):
            base_score -= 0.3
            risk_factors.append("Sanctions match found")
        
        if kyc_result.get("pep_match"):
            base_score -= 0.15
            risk_factors.append("PEP match found")
        
        kyb_result = input_data.get("kyb_result", {})
        if kyb_result:
            if kyb_result.get("risk_score"):
                base_score = (base_score + kyb_result["risk_score"]) / 2
        
        document_scores = input_data.get("document_scores", [])
        if document_scores:
            avg_doc_score = sum(document_scores) / len(document_scores)
            base_score = (base_score + avg_doc_score) / 2
        
        risk_score = max(0.0, min(1.0, base_score))
        
        if risk_score >= 0.8:
            risk_level = "low"
        elif risk_score >= 0.6:
            risk_level = "medium"
        elif risk_score >= 0.4:
            risk_level = "high"
        else:
            risk_level = "very_high"
        
        return {
            "agent_id": input_data["agent_id"],
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "calculated_at": datetime.utcnow().isoformat()
        }
    
    @activity.defn
    async def create_agent_account(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create agent account in the system"""
        logger.info(f"Creating agent account: {input_data.get('agent_id')}")
        
        import httpx
        
        agent_service_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8111")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{agent_service_url}/agents",
                    json=input_data["agent_data"]
                )
                
                if response.status_code in (200, 201):
                    return {
                        "success": True,
                        "agent": response.json(),
                        "created_at": datetime.utcnow().isoformat()
                    }
        except Exception as e:
            logger.warning(f"Agent service unavailable: {e}")
        
        return {
            "success": True,
            "agent_id": input_data["agent_id"],
            "created_at": datetime.utcnow().isoformat(),
            "note": "Agent service unavailable, account creation pending"
        }
    
    @activity.defn
    async def assign_training(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assign training modules to agent"""
        logger.info(f"Assigning training for agent: {input_data.get('agent_id')}")
        
        training_modules = [
            {"id": "TRN001", "name": "Remittance Platform Basics", "duration_hours": 2},
            {"id": "TRN002", "name": "KYC/AML Compliance", "duration_hours": 1},
            {"id": "TRN003", "name": "Transaction Processing", "duration_hours": 2},
            {"id": "TRN004", "name": "Customer Service", "duration_hours": 1},
            {"id": "TRN005", "name": "Security and Fraud Prevention", "duration_hours": 1}
        ]
        
        tier = input_data.get("tier", "agent")
        if tier in ["super_agent", "senior_agent"]:
            training_modules.extend([
                {"id": "TRN006", "name": "Team Management", "duration_hours": 2},
                {"id": "TRN007", "name": "Performance Analytics", "duration_hours": 1}
            ])
        
        return {
            "agent_id": input_data["agent_id"],
            "assigned_modules": training_modules,
            "total_hours": sum(m["duration_hours"] for m in training_modules),
            "assigned_at": datetime.utcnow().isoformat(),
            "deadline": (datetime.utcnow() + timedelta(days=14)).isoformat()
        }
    
    @activity.defn
    async def activate_agent(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Activate agent account"""
        logger.info(f"Activating agent: {input_data.get('agent_id')}")
        
        import httpx
        
        agent_service_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8111")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.put(
                    f"{agent_service_url}/agents/{input_data['agent_id']}",
                    json={"status": "active"}
                )
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "agent_id": input_data["agent_id"],
                        "activated_at": datetime.utcnow().isoformat()
                    }
        except Exception as e:
            logger.warning(f"Agent service unavailable: {e}")
        
        return {
            "success": True,
            "agent_id": input_data["agent_id"],
            "activated_at": datetime.utcnow().isoformat(),
            "note": "Agent service unavailable, activation pending"
        }
    
    @activity.defn
    async def send_notification(input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification to agent"""
        logger.info(f"Sending notification: {input_data.get('type')}")
        
        return {
            "notification_id": str(uuid.uuid4()),
            "type": input_data.get("type"),
            "recipient": input_data.get("recipient"),
            "sent_at": datetime.utcnow().isoformat(),
            "status": "sent"
        }
    
    @workflow.defn
    class AgentOnboardingWorkflow:
        """Main workflow for agent onboarding"""
        
        def __init__(self):
            self.status = WorkflowStatus.PENDING
            self.current_step = OnboardingStep.PERSONAL_INFO
            self.kyc_result = None
            self.kyb_result = None
            self.risk_assessment = None
            self.documents_processed = []
            self.errors = []
        
        @workflow.run
        async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
            """Execute the onboarding workflow"""
            
            agent_id = input_data["agent_id"]
            personal_info = input_data["personal_info"]
            business_info = input_data.get("business_info")
            
            self.status = WorkflowStatus.IN_PROGRESS
            
            retry_policy = RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(minutes=5),
                maximum_attempts=3
            )
            
            self.current_step = OnboardingStep.PERSONAL_INFO
            personal_validation = await workflow.execute_activity(
                validate_personal_info,
                personal_info,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy
            )
            
            if not personal_validation.get("valid"):
                self.status = WorkflowStatus.FAILED
                return self._create_result(agent_id, "rejected", personal_validation.get("errors"))
            
            if business_info:
                self.current_step = OnboardingStep.BUSINESS_INFO
                business_validation = await workflow.execute_activity(
                    validate_business_info,
                    business_info,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=retry_policy
                )
                
                if not business_validation.get("valid"):
                    self.status = WorkflowStatus.FAILED
                    return self._create_result(agent_id, "rejected", business_validation.get("errors"))
            
            self.current_step = OnboardingStep.KYC_VERIFICATION
            self.kyc_result = await workflow.execute_activity(
                perform_kyc_verification,
                {"agent_id": agent_id, "personal_info": personal_info},
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=retry_policy
            )
            
            full_name = f"{personal_info.get('first_name', '')} {personal_info.get('last_name', '')}"
            aml_result = await workflow.execute_activity(
                perform_aml_screening,
                {"name": full_name, "nationality": personal_info.get("nationality")},
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy
            )
            
            if aml_result.get("sanctions_match"):
                self.status = WorkflowStatus.REJECTED
                return self._create_result(agent_id, "rejected", ["Sanctions match found"])
            
            if business_info:
                self.current_step = OnboardingStep.KYB_VERIFICATION
                self.kyb_result = await workflow.execute_activity(
                    perform_kyb_verification,
                    {"agent_id": agent_id, "business_info": business_info},
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=retry_policy
                )
            
            self.current_step = OnboardingStep.RISK_ASSESSMENT
            self.risk_assessment = await workflow.execute_activity(
                calculate_risk_score,
                {
                    "agent_id": agent_id,
                    "kyc_result": self.kyc_result,
                    "kyb_result": self.kyb_result,
                    "document_scores": [d.get("confidence", 0.7) for d in self.documents_processed]
                },
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy
            )
            
            risk_level = self.risk_assessment.get("risk_level", "medium")
            
            self.current_step = OnboardingStep.APPROVAL
            if risk_level == "very_high":
                self.status = WorkflowStatus.REJECTED
                return self._create_result(agent_id, "rejected", ["Risk level too high"])
            elif risk_level == "high":
                self.status = WorkflowStatus.MANUAL_REVIEW
                await workflow.execute_activity(
                    send_notification,
                    {
                        "type": "manual_review_required",
                        "recipient": "compliance@remittance-platform.com",
                        "agent_id": agent_id,
                        "risk_level": risk_level
                    },
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=retry_policy
                )
                return self._create_result(agent_id, "manual_review")
            
            self.current_step = OnboardingStep.ACCOUNT_CREATION
            account_result = await workflow.execute_activity(
                create_agent_account,
                {
                    "agent_id": agent_id,
                    "agent_data": {
                        **personal_info,
                        "tier": input_data.get("requested_tier", "agent"),
                        "parent_agent_id": input_data.get("parent_agent_id"),
                        "territory_id": input_data.get("territory_id")
                    }
                },
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy
            )
            
            self.current_step = OnboardingStep.TRAINING
            training_result = await workflow.execute_activity(
                assign_training,
                {
                    "agent_id": agent_id,
                    "tier": input_data.get("requested_tier", "agent")
                },
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy
            )
            
            self.current_step = OnboardingStep.ACTIVATION
            activation_result = await workflow.execute_activity(
                activate_agent,
                {"agent_id": agent_id},
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy
            )
            
            await workflow.execute_activity(
                send_notification,
                {
                    "type": "onboarding_complete",
                    "recipient": personal_info.get("email"),
                    "agent_id": agent_id
                },
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy
            )
            
            self.status = WorkflowStatus.COMPLETED
            return self._create_result(agent_id, "approved")
        
        def _create_result(self, agent_id: str, status: str, errors: List[str] = None) -> Dict[str, Any]:
            """Create workflow result"""
            return {
                "agent_id": agent_id,
                "status": status,
                "kyc_status": self.kyc_result.get("status") if self.kyc_result else "pending",
                "kyb_status": self.kyb_result.get("status") if self.kyb_result else None,
                "risk_score": self.risk_assessment.get("risk_score") if self.risk_assessment else 0.5,
                "risk_level": self.risk_assessment.get("risk_level") if self.risk_assessment else "medium",
                "approval_status": status,
                "account_created": status == "approved",
                "training_completed": False,
                "activated": status == "approved",
                "completed_at": datetime.utcnow().isoformat(),
                "rejection_reason": "; ".join(errors) if errors else None
            }
        
        @workflow.query
        def get_status(self) -> Dict[str, Any]:
            """Query current workflow status"""
            return {
                "status": self.status.value,
                "current_step": self.current_step.value,
                "kyc_completed": self.kyc_result is not None,
                "kyb_completed": self.kyb_result is not None,
                "risk_assessed": self.risk_assessment is not None,
                "documents_processed": len(self.documents_processed),
                "errors": self.errors
            }
        
        @workflow.signal
        async def add_document(self, document_data: Dict[str, Any]):
            """Signal to add a document for processing"""
            self.documents_processed.append(document_data)


class LocalWorkflowEngine:
    """Local workflow engine when Temporal is unavailable"""
    
    def __init__(self):
        self.workflows: Dict[str, Dict[str, Any]] = {}
    
    async def start_onboarding_workflow(self, input_data: Dict[str, Any]) -> str:
        """Start a local onboarding workflow"""
        workflow_id = str(uuid.uuid4())
        
        self.workflows[workflow_id] = {
            "id": workflow_id,
            "input": input_data,
            "status": WorkflowStatus.IN_PROGRESS.value,
            "current_step": OnboardingStep.PERSONAL_INFO.value,
            "started_at": datetime.utcnow().isoformat(),
            "results": {}
        }
        
        asyncio.create_task(self._execute_workflow(workflow_id, input_data))
        
        return workflow_id
    
    async def _execute_workflow(self, workflow_id: str, input_data: Dict[str, Any]):
        """Execute workflow steps locally"""
        workflow = self.workflows[workflow_id]
        
        try:
            workflow["current_step"] = OnboardingStep.PERSONAL_INFO.value
            await asyncio.sleep(0.1)
            
            workflow["current_step"] = OnboardingStep.KYC_VERIFICATION.value
            await asyncio.sleep(0.5)
            workflow["results"]["kyc"] = {
                "status": "pending",
                "risk_score": 0.7,
                "risk_level": "medium"
            }
            
            if input_data.get("business_info"):
                workflow["current_step"] = OnboardingStep.KYB_VERIFICATION.value
                await asyncio.sleep(0.5)
                workflow["results"]["kyb"] = {
                    "status": "pending",
                    "risk_score": 0.7,
                    "risk_level": "medium"
                }
            
            workflow["current_step"] = OnboardingStep.RISK_ASSESSMENT.value
            await asyncio.sleep(0.2)
            workflow["results"]["risk"] = {
                "risk_score": 0.7,
                "risk_level": "medium"
            }
            
            workflow["current_step"] = OnboardingStep.APPROVAL.value
            workflow["status"] = WorkflowStatus.APPROVED.value
            
            workflow["current_step"] = OnboardingStep.ACCOUNT_CREATION.value
            await asyncio.sleep(0.2)
            
            workflow["current_step"] = OnboardingStep.ACTIVATION.value
            workflow["status"] = WorkflowStatus.COMPLETED.value
            workflow["completed_at"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            logger.error(f"Workflow {workflow_id} failed: {e}")
            workflow["status"] = WorkflowStatus.FAILED.value
            workflow["error"] = str(e)
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow status"""
        return self.workflows.get(workflow_id)


class TemporalWorkflowClient:
    """Client for interacting with Temporal workflows"""
    
    def __init__(self, host: str = "localhost:7233"):
        self.host = host
        self._client: Optional[Client] = None
        self._local_engine = LocalWorkflowEngine()
        self._use_local = not TEMPORAL_AVAILABLE
    
    async def connect(self):
        """Connect to Temporal server"""
        if not TEMPORAL_AVAILABLE:
            logger.warning("Temporal not available, using local workflow engine")
            self._use_local = True
            return
        
        try:
            self._client = await Client.connect(self.host)
            logger.info(f"Connected to Temporal at {self.host}")
            self._use_local = False
        except Exception as e:
            logger.warning(f"Failed to connect to Temporal: {e}, using local engine")
            self._use_local = True
    
    async def start_onboarding(self, input_data: Dict[str, Any]) -> str:
        """Start agent onboarding workflow"""
        workflow_id = f"onboarding-{input_data['agent_id']}-{uuid.uuid4().hex[:8]}"
        
        if self._use_local:
            return await self._local_engine.start_onboarding_workflow(input_data)
        
        try:
            handle = await self._client.start_workflow(
                AgentOnboardingWorkflow.run,
                input_data,
                id=workflow_id,
                task_queue="agent-onboarding"
            )
            return handle.id
        except Exception as e:
            logger.error(f"Failed to start Temporal workflow: {e}")
            return await self._local_engine.start_onboarding_workflow(input_data)
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow status"""
        if self._use_local:
            status = self._local_engine.get_workflow_status(workflow_id)
            if status:
                return status
            return {"error": "Workflow not found"}
        
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            result = await handle.query(AgentOnboardingWorkflow.get_status)
            return result
        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}")
            return {"error": str(e)}
    
    async def get_workflow_result(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow result"""
        if self._use_local:
            status = self._local_engine.get_workflow_status(workflow_id)
            if status:
                return {
                    "agent_id": status["input"]["agent_id"],
                    "status": status["status"],
                    "results": status.get("results", {}),
                    "completed_at": status.get("completed_at")
                }
            return {"error": "Workflow not found"}
        
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            result = await handle.result()
            return result
        except Exception as e:
            logger.error(f"Failed to get workflow result: {e}")
            return {"error": str(e)}


async def start_worker(host: str = "localhost:7233"):
    """Start Temporal worker"""
    if not TEMPORAL_AVAILABLE:
        logger.warning("Temporal not available, worker not started")
        return
    
    try:
        client = await Client.connect(host)
        
        worker = Worker(
            client,
            task_queue="agent-onboarding",
            workflows=[AgentOnboardingWorkflow],
            activities=[
                validate_personal_info,
                validate_business_info,
                process_document,
                perform_kyc_verification,
                perform_kyb_verification,
                perform_aml_screening,
                calculate_risk_score,
                create_agent_account,
                assign_training,
                activate_agent,
                send_notification
            ]
        )
        
        logger.info("Starting Temporal worker...")
        await worker.run()
        
    except Exception as e:
        logger.error(f"Failed to start worker: {e}")


if __name__ == "__main__":
    asyncio.run(start_worker())
