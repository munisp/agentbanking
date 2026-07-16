#!/usr/bin/env python3
"""
Automated Incident Response Service
Responds to security events from Wazuh SIEM with automated playbooks
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Severity(Enum):
    """Incident severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(Enum):
    """Incident status"""
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class Incident:
    """Security incident data structure"""
    id: str
    rule_id: str
    severity: Severity
    status: IncidentStatus
    title: str
    description: str
    source_ip: str
    target: str
    timestamp: datetime
    mitre_tactics: List[str]
    evidence: Dict
    playbook: str


class IncidentResponsePlaybooks:
    """Automated incident response playbooks"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.apisix_url = config.get("apisix_url", "http://apisix:9180/apisix/admin")
        self.apisix_key = config.get("apisix_key")
        self.openappsec_url = config.get("openappsec_url", "http://openappsec:8080")
        self.pagerduty_key = config.get("pagerduty_key")
        self.jira_url = config.get("jira_url")
        self.jira_token = config.get("jira_token")
    
    async def execute_playbook(self, incident: Incident):
        """Execute incident response playbook"""
        logger.info(f"Executing playbook '{incident.playbook}' for incident {incident.id}")
        
        playbook_map = {
            "sql_injection_attack": self.sql_injection_playbook,
            "xss_attack": self.xss_playbook,
            "ddos_attack": self.ddos_playbook,
            "brute_force_attack": self.brute_force_playbook,
            "account_takeover": self.account_takeover_playbook,
            "data_exfiltration": self.data_exfiltration_playbook,
            "zero_day_threat": self.zero_day_playbook,
            "coordinated_attack": self.coordinated_attack_playbook
        }
        
        playbook_func = playbook_map.get(incident.playbook)
        if playbook_func:
            await playbook_func(incident)
        else:
            logger.warning(f"Unknown playbook: {incident.playbook}")
            await self.default_playbook(incident)
    
    async def sql_injection_playbook(self, incident: Incident):
        """Playbook for SQL injection attacks"""
        logger.info(f"[SQL Injection] Responding to incident {incident.id}")
        
        # Step 1: Block source IP
        await self.block_ip(incident.source_ip, duration="24h", reason="SQL Injection Attack")
        
        # Step 2: Alert SOC team
        await self.alert_soc(
            incident=incident,
            channel="pagerduty",
            priority="high",
            message=f"SQL Injection attack detected from {incident.source_ip}"
        )
        
        # Step 3: Create JIRA ticket
        ticket_id = await self.create_ticket(
            incident=incident,
            system="jira",
            title=f"SQL Injection Attack - {incident.source_ip}",
            priority="high"
        )
        
        # Step 4: Capture forensics
        await self.capture_forensics(incident, duration="1h")
        
        # Step 5: Check if data was accessed
        data_accessed = await self.check_data_access(incident)
        if data_accessed:
            await self.notify_affected_users(incident)
        
        logger.info(f"[SQL Injection] Playbook completed for incident {incident.id}")
    
    async def xss_playbook(self, incident: Incident):
        """Playbook for XSS attacks"""
        logger.info(f"[XSS] Responding to incident {incident.id}")
        
        # Step 1: Block source IP
        await self.block_ip(incident.source_ip, duration="12h", reason="XSS Attack")
        
        # Step 2: Alert SOC team
        await self.alert_soc(
            incident=incident,
            channel="slack",
            priority="medium",
            message=f"XSS attack detected from {incident.source_ip}"
        )
        
        # Step 3: Create ticket
        await self.create_ticket(
            incident=incident,
            system="jira",
            title=f"XSS Attack - {incident.source_ip}",
            priority="medium"
        )
        
        # Step 4: Enable enhanced XSS protection
        await self.enable_enhanced_protection(incident.target, protection_type="xss")
        
        logger.info(f"[XSS] Playbook completed for incident {incident.id}")
    
    async def ddos_attack_playbook(self, incident: Incident):
        """Playbook for DDoS attacks"""
        logger.info(f"[DDoS] Responding to incident {incident.id}")
        
        # Step 1: Enable aggressive rate limiting
        await self.enable_rate_limiting(aggressive=True)
        
        # Step 2: Activate CDN protection
        await self.activate_cdn_protection()
        
        # Step 3: Block attack sources
        await self.block_attack_sources(incident, auto=True)
        
        # Step 4: Scale infrastructure
        await self.scale_infrastructure(incident, auto=True)
        
        # Step 5: Alert SOC with P1 priority
        await self.alert_soc(
            incident=incident,
            channel="pagerduty",
            priority="critical",
            message=f"DDoS attack in progress - {incident.description}"
        )
        
        logger.info(f"[DDoS] Playbook completed for incident {incident.id}")
    
    async def brute_force_playbook(self, incident: Incident):
        """Playbook for brute force attacks"""
        logger.info(f"[Brute Force] Responding to incident {incident.id}")
        
        # Step 1: Block source IP
        await self.block_ip(incident.source_ip, duration="48h", reason="Brute Force Attack")
        
        # Step 2: Enable CAPTCHA for login endpoint
        await self.enable_captcha(incident.target)
        
        # Step 3: Force MFA for affected accounts
        await self.force_mfa(incident)
        
        # Step 4: Alert SOC
        await self.alert_soc(
            incident=incident,
            channel="slack",
            priority="high",
            message=f"Brute force attack from {incident.source_ip}"
        )
        
        logger.info(f"[Brute Force] Playbook completed for incident {incident.id}")
    
    async def account_takeover_playbook(self, incident: Incident):
        """Playbook for account takeover attempts"""
        logger.info(f"[Account Takeover] Responding to incident {incident.id}")
        
        # Step 1: Suspend account temporarily
        user_id = incident.evidence.get("user_id")
        await self.suspend_account(user_id, temporary=True)
        
        # Step 2: Force password reset
        await self.force_password_reset(user_id)
        
        # Step 3: Invalidate all sessions
        await self.invalidate_sessions(user_id)
        
        # Step 4: Notify user
        await self.notify_user(
            user_id=user_id,
            channel="email+sms",
            message="Suspicious activity detected on your account. Please reset your password."
        )
        
        # Step 5: Enable mandatory MFA
        await self.enable_mfa(user_id, mandatory=True)
        
        # Step 6: Investigate scope
        await self.investigate_scope(incident)
        
        logger.info(f"[Account Takeover] Playbook completed for incident {incident.id}")
    
    async def data_exfiltration_playbook(self, incident: Incident):
        """Playbook for data exfiltration attempts"""
        logger.info(f"[Data Exfiltration] Responding to incident {incident.id}")
        
        # Step 1: Block source IP immediately
        await self.block_ip(incident.source_ip, duration="permanent", reason="Data Exfiltration")
        
        # Step 2: Alert SOC with critical priority
        await self.alert_soc(
            incident=incident,
            channel="pagerduty",
            priority="critical",
            message=f"Data exfiltration attempt detected from {incident.source_ip}"
        )
        
        # Step 3: Capture full forensics
        await self.capture_forensics(incident, duration="24h", full=True)
        
        # Step 4: Analyze data accessed
        await self.analyze_data_accessed(incident)
        
        # Step 5: Notify compliance team
        await self.notify_compliance(incident)
        
        # Step 6: Initiate breach protocol if confirmed
        if incident.evidence.get("confirmed_breach"):
            await self.initiate_breach_protocol(incident)
        
        logger.info(f"[Data Exfiltration] Playbook completed for incident {incident.id}")
    
    async def zero_day_playbook(self, incident: Incident):
        """Playbook for zero-day threats"""
        logger.info(f"[Zero-Day] Responding to incident {incident.id}")
        
        # Step 1: Block immediately
        await self.block_ip(incident.source_ip, duration="permanent", reason="Zero-Day Threat")
        
        # Step 2: Create custom signature
        await self.create_custom_signature(incident)
        
        # Step 3: Alert SOC with critical priority
        await self.alert_soc(
            incident=incident,
            channel="pagerduty",
            priority="critical",
            message=f"Zero-day threat detected: {incident.description}"
        )
        
        # Step 4: Notify security vendors
        await self.notify_security_vendors(incident)
        
        # Step 5: Deploy emergency patches if available
        await self.deploy_emergency_patches(incident)
        
        logger.info(f"[Zero-Day] Playbook completed for incident {incident.id}")
    
    async def coordinated_attack_playbook(self, incident: Incident):
        """Playbook for coordinated attacks"""
        logger.info(f"[Coordinated Attack] Responding to incident {incident.id}")
        
        # Step 1: Identify all attack sources
        attack_sources = await self.identify_attack_sources(incident)
        
        # Step 2: Block all sources
        for source_ip in attack_sources:
            await self.block_ip(source_ip, duration="permanent", reason="Coordinated Attack")
        
        # Step 3: Enable war room mode
        await self.enable_war_room_mode()
        
        # Step 4: Alert all stakeholders
        await self.alert_stakeholders(incident, priority="critical")
        
        # Step 5: Activate incident response team
        await self.activate_incident_response_team(incident)
        
        logger.info(f"[Coordinated Attack] Playbook completed for incident {incident.id}")
    
    async def default_playbook(self, incident: Incident):
        """Default playbook for unknown incident types"""
        logger.info(f"[Default] Responding to incident {incident.id}")
        
        # Step 1: Block source IP
        await self.block_ip(incident.source_ip, duration="6h", reason=incident.title)
        
        # Step 2: Alert SOC
        await self.alert_soc(
            incident=incident,
            channel="slack",
            priority="medium",
            message=f"Security incident detected: {incident.title}"
        )
        
        # Step 3: Create ticket
        await self.create_ticket(
            incident=incident,
            system="jira",
            title=incident.title,
            priority="medium"
        )
        
        logger.info(f"[Default] Playbook completed for incident {incident.id}")
    
    # Helper methods for playbook actions
    
    async def block_ip(self, ip: str, duration: str, reason: str):
        """Block IP address in APISIX"""
        logger.info(f"Blocking IP {ip} for {duration} - Reason: {reason}")
        
        async with aiohttp.ClientSession() as session:
            # Add IP to blocklist via APISIX Admin API
            url = f"{self.apisix_url}/global_rules/1"
            headers = {"X-API-KEY": self.apisix_key}
            
            # Get current blocklist
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    plugins = data.get("node", {}).get("value", {}).get("plugins", {})
                else:
                    plugins = {}
            
            # Add IP to ip-restriction plugin
            if "ip-restriction" not in plugins:
                plugins["ip-restriction"] = {"blacklist": []}
            
            if ip not in plugins["ip-restriction"]["blacklist"]:
                plugins["ip-restriction"]["blacklist"].append(ip)
            
            # Update global rule
            payload = {"plugins": plugins}
            async with session.put(url, headers=headers, json=payload) as response:
                if response.status in [200, 201]:
                    logger.info(f"Successfully blocked IP {ip}")
                else:
                    logger.error(f"Failed to block IP {ip}: {response.status}")
    
    async def alert_soc(self, incident: Incident, channel: str, priority: str, message: str):
        """Alert SOC team"""
        logger.info(f"Alerting SOC via {channel} with priority {priority}: {message}")
        
        if channel == "pagerduty" and self.pagerduty_key:
            await self._send_pagerduty_alert(incident, priority, message)
        elif channel == "slack":
            await self._send_slack_alert(incident, priority, message)
        else:
            logger.warning(f"Unknown alert channel: {channel}")
    
    async def _send_pagerduty_alert(self, incident: Incident, priority: str, message: str):
        """Send alert to PagerDuty"""
        async with aiohttp.ClientSession() as session:
            url = "https://events.pagerduty.com/v2/enqueue"
            headers = {"Content-Type": "application/json"}
            
            payload = {
                "routing_key": self.pagerduty_key,
                "event_action": "trigger",
                "payload": {
                    "summary": message,
                    "severity": priority,
                    "source": "openappsec-apisix",
                    "custom_details": {
                        "incident_id": incident.id,
                        "rule_id": incident.rule_id,
                        "source_ip": incident.source_ip,
                        "target": incident.target
                    }
                }
            }
            
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 202:
                    logger.info("PagerDuty alert sent successfully")
                else:
                    logger.error(f"Failed to send PagerDuty alert: {response.status}")
    
    async def _send_slack_alert(self, incident: Incident, priority: str, message: str):
        """Send alert to Slack"""
        # Implementation would use Slack webhook
        logger.info(f"Slack alert: {message}")
    
    async def create_ticket(self, incident: Incident, system: str, title: str, priority: str) -> str:
        """Create ticket in ticketing system"""
        logger.info(f"Creating {system} ticket: {title}")
        
        if system == "jira" and self.jira_url and self.jira_token:
            return await self._create_jira_ticket(incident, title, priority)
        else:
            logger.warning(f"Unknown ticketing system: {system}")
            return "TICKET-UNKNOWN"
    
    async def _create_jira_ticket(self, incident: Incident, title: str, priority: str) -> str:
        """Create JIRA ticket"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.jira_url}/rest/api/2/issue"
            headers = {
                "Authorization": f"Bearer {self.jira_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "fields": {
                    "project": {"key": "SEC"},
                    "summary": title,
                    "description": incident.description,
                    "issuetype": {"name": "Security Incident"},
                    "priority": {"name": priority.capitalize()},
                    "labels": ["security", "automated", incident.playbook]
                }
            }
            
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 201:
                    data = await response.json()
                    ticket_id = data.get("key")
                    logger.info(f"JIRA ticket created: {ticket_id}")
                    return ticket_id
                else:
                    logger.error(f"Failed to create JIRA ticket: {response.status}")
                    return "TICKET-ERROR"
    
    async def capture_forensics(self, incident: Incident, duration: str, full: bool = False):
        """Capture forensic data"""
        logger.info(f"Capturing forensics for {duration} (full={full})")
        # Implementation would capture logs, network traffic, etc.
    
    async def check_data_access(self, incident: Incident) -> bool:
        """Check if data was accessed"""
        logger.info("Checking if data was accessed...")
        # Implementation would query database audit logs
        return False
    
    async def notify_affected_users(self, incident: Incident):
        """Notify affected users"""
        logger.info("Notifying affected users...")
        # Implementation would send notifications
    
    async def enable_enhanced_protection(self, target: str, protection_type: str):
        """Enable enhanced protection"""
        logger.info(f"Enabling enhanced {protection_type} protection for {target}")
    
    async def enable_rate_limiting(self, aggressive: bool = False):
        """Enable rate limiting"""
        logger.info(f"Enabling rate limiting (aggressive={aggressive})")
    
    async def activate_cdn_protection(self):
        """Activate CDN protection"""
        logger.info("Activating CDN protection")
    
    async def block_attack_sources(self, incident: Incident, auto: bool = False):
        """Block attack sources"""
        logger.info(f"Blocking attack sources (auto={auto})")
    
    async def scale_infrastructure(self, incident: Incident, auto: bool = False):
        """Scale infrastructure"""
        logger.info(f"Scaling infrastructure (auto={auto})")
    
    async def enable_captcha(self, target: str):
        """Enable CAPTCHA"""
        logger.info(f"Enabling CAPTCHA for {target}")
    
    async def force_mfa(self, incident: Incident):
        """Force MFA"""
        logger.info("Forcing MFA for affected accounts")
    
    async def suspend_account(self, user_id: str, temporary: bool = False):
        """Suspend user account"""
        logger.info(f"Suspending account {user_id} (temporary={temporary})")
    
    async def force_password_reset(self, user_id: str):
        """Force password reset"""
        logger.info(f"Forcing password reset for {user_id}")
    
    async def invalidate_sessions(self, user_id: str):
        """Invalidate user sessions"""
        logger.info(f"Invalidating sessions for {user_id}")
    
    async def notify_user(self, user_id: str, channel: str, message: str):
        """Notify user"""
        logger.info(f"Notifying user {user_id} via {channel}: {message}")
    
    async def enable_mfa(self, user_id: str, mandatory: bool = False):
        """Enable MFA"""
        logger.info(f"Enabling MFA for {user_id} (mandatory={mandatory})")
    
    async def investigate_scope(self, incident: Incident):
        """Investigate incident scope"""
        logger.info("Investigating incident scope...")
    
    async def analyze_data_accessed(self, incident: Incident):
        """Analyze data accessed"""
        logger.info("Analyzing data accessed...")
    
    async def notify_compliance(self, incident: Incident):
        """Notify compliance team"""
        logger.info("Notifying compliance team...")
    
    async def initiate_breach_protocol(self, incident: Incident):
        """Initiate breach protocol"""
        logger.info("Initiating breach protocol...")
    
    async def create_custom_signature(self, incident: Incident):
        """Create custom signature"""
        logger.info("Creating custom signature...")
    
    async def notify_security_vendors(self, incident: Incident):
        """Notify security vendors"""
        logger.info("Notifying security vendors...")
    
    async def deploy_emergency_patches(self, incident: Incident):
        """Deploy emergency patches"""
        logger.info("Deploying emergency patches...")
    
    async def identify_attack_sources(self, incident: Incident) -> List[str]:
        """Identify attack sources"""
        logger.info("Identifying attack sources...")
        return [incident.source_ip]
    
    async def enable_war_room_mode(self):
        """Enable war room mode"""
        logger.info("Enabling war room mode...")
    
    async def alert_stakeholders(self, incident: Incident, priority: str):
        """Alert stakeholders"""
        logger.info(f"Alerting stakeholders with priority {priority}")
    
    async def activate_incident_response_team(self, incident: Incident):
        """Activate incident response team"""
        logger.info("Activating incident response team...")


class IncidentResponseService:
    """Main incident response service"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.playbooks = IncidentResponsePlaybooks(config)
        self.wazuh_url = config.get("wazuh_url", "https://wazuh-manager:55000")
        self.wazuh_user = config.get("wazuh_user", "wazuh-wui")
        self.wazuh_password = config.get("wazuh_password")
        self.running = False
    
    async def start(self):
        """Start incident response service"""
        self.running = True
        logger.info("Starting Incident Response Service")
        
        while self.running:
            try:
                await self.poll_incidents()
                await asyncio.sleep(10)  # Poll every 10 seconds
            except Exception as e:
                logger.error(f"Error in incident response loop: {e}")
                await asyncio.sleep(30)
    
    async def stop(self):
        """Stop incident response service"""
        self.running = False
        logger.info("Stopping Incident Response Service")
    
    async def poll_incidents(self):
        """Poll for new incidents from Wazuh"""
        try:
            import aiohttp
            
            wazuh_url = os.getenv('WAZUH_API_URL', 'https://localhost:55000')
            wazuh_user = os.getenv('WAZUH_API_USER', 'wazuh')
            wazuh_password = os.getenv('WAZUH_API_PASSWORD', 'wazuh')
            
            async with aiohttp.ClientSession() as session:
                # Authenticate with Wazuh
                async with session.post(
                    f"{wazuh_url}/security/user/authenticate",
                    auth=aiohttp.BasicAuth(wazuh_user, wazuh_password),
                    ssl=False
                ) as auth_response:
                    if auth_response.status == 200:
                        auth_data = await auth_response.json()
                        token = auth_data['data']['token']
                        
                        # Query for recent alerts (last 5 minutes)
                        headers = {'Authorization': f'Bearer {token}'}
                        async with session.get(
                            f"{wazuh_url}/alerts",
                            headers=headers,
                            params={
                                'limit': 100,
                                'sort': '-timestamp',
                                'q': 'rule.level>=7'  # High severity alerts only
                            },
                            ssl=False
                        ) as alerts_response:
                            if alerts_response.status == 200:
                                data = await alerts_response.json()
                                alerts = data.get('data', {}).get('affected_items', [])
                                
                                logger.info(f"Polled {len(alerts)} new alerts from Wazuh")
                                
                                # Process each alert
                                for alert in alerts:
                                    await self.handle_incident(alert)
                                    
                                return alerts
                            else:
                                logger.error(f"Failed to query alerts: {alerts_response.status}")
                    else:
                        logger.error(f"Wazuh authentication failed: {auth_response.status}")
                        
        except Exception as e:
            logger.error(f"Error polling Wazuh incidents: {e}")
        
        return []
    
    async def handle_incident(self, alert: Dict):
        """Handle security incident"""
        # Parse alert into Incident object
        incident = self._parse_alert(alert)
        
        # Execute appropriate playbook
        await self.playbooks.execute_playbook(incident)
    
    def _parse_alert(self, alert: Dict) -> Incident:
        """Parse Wazuh alert into Incident object"""
        try:
            # Extract alert details
            rule = alert.get('rule', {})
            agent = alert.get('agent', {})
            data = alert.get('data', {})
            
            # Map Wazuh rule level to severity
            rule_level = rule.get('level', 0)
            if rule_level >= 12:
                severity = IncidentSeverity.CRITICAL
            elif rule_level >= 9:
                severity = IncidentSeverity.HIGH
            elif rule_level >= 7:
                severity = IncidentSeverity.MEDIUM
            else:
                severity = IncidentSeverity.LOW
            
            # Determine incident type from rule groups
            rule_groups = rule.get('groups', [])
            if 'authentication_failed' in rule_groups:
                incident_type = IncidentType.AUTHENTICATION_FAILURE
            elif 'intrusion_detection' in rule_groups or 'ids' in rule_groups:
                incident_type = IncidentType.INTRUSION_ATTEMPT
            elif 'malware' in rule_groups:
                incident_type = IncidentType.MALWARE_DETECTED
            elif 'web' in rule_groups or 'attack' in rule_groups:
                incident_type = IncidentType.SUSPICIOUS_ACTIVITY
            elif 'policy_violation' in rule_groups:
                incident_type = IncidentType.POLICY_VIOLATION
            else:
                incident_type = IncidentType.SUSPICIOUS_ACTIVITY
            
            # Create Incident object
            incident = Incident(
                incident_id=f"wazuh_{alert.get('id', uuid.uuid4().hex[:16])}",
                incident_type=incident_type,
                severity=severity,
                source_ip=data.get('srcip', 'unknown'),
                destination_ip=data.get('dstip', agent.get('ip', 'unknown')),
                timestamp=alert.get('timestamp', datetime.now().isoformat()),
                description=rule.get('description', 'Security alert from Wazuh'),
                affected_systems=[agent.get('name', 'unknown')],
                status=IncidentStatus.DETECTED,
                metadata={
                    'rule_id': rule.get('id'),
                    'rule_description': rule.get('description'),
                    'rule_level': rule_level,
                    'agent_id': agent.get('id'),
                    'agent_name': agent.get('name'),
                    'full_log': alert.get('full_log', ''),
                    'decoder': alert.get('decoder', {})
                }
            )
            
            logger.info(
                f"Parsed Wazuh alert: {incident.incident_id}, "
                f"type: {incident_type.value}, severity: {severity.value}"
            )
            
            return incident
            
        except Exception as e:
            logger.error(f"Error parsing Wazuh alert: {e}")
            # Return a default incident on parse error
            return Incident(
                incident_id=f"parse_error_{uuid.uuid4().hex[:16]}",
                incident_type=IncidentType.SUSPICIOUS_ACTIVITY,
                severity=IncidentSeverity.MEDIUM,
                source_ip='unknown',
                destination_ip='unknown',
                timestamp=datetime.now().isoformat(),
                description=f"Failed to parse Wazuh alert: {str(e)}",
                affected_systems=['unknown'],
                status=IncidentStatus.DETECTED,
                metadata={'error': str(e), 'raw_alert': str(alert)}
            )


# Main entry point
if __name__ == "__main__":
    config = {
        "apisix_url": "http://apisix:9180/apisix/admin",
        "apisix_key": "CHANGE_ME",
        "openappsec_url": "http://openappsec:8080",
        "pagerduty_key": "CHANGE_ME",
        "jira_url": "https://jira.platform.ng",
        "jira_token": "CHANGE_ME",
        "wazuh_url": "https://wazuh-manager:55000",
        "wazuh_user": "wazuh-wui",
        "wazuh_password": "CHANGE_ME"
    }
    
    service = IncidentResponseService(config)
    
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("Shutting down...")

