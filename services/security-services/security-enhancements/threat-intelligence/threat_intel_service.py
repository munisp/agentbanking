#!/usr/bin/env python3
"""
Threat Intelligence Integration Service
Integrates OpenCTI, AlienVault OTX, and Abuse.ch threat feeds
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Set, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ThreatIndicator:
    """Threat indicator data structure"""
    indicator_type: str  # ip, domain, url, hash, signature
    value: str
    threat_type: str  # malware, botnet, exploit, phishing
    severity: str  # critical, high, medium, low
    source: str  # opencti, otx, abuse_ch
    first_seen: datetime
    last_seen: datetime
    confidence: float  # 0.0 - 1.0
    tags: List[str]
    description: str


class OpenCTIClient:
    """OpenCTI threat intelligence client"""
    
    def __init__(self, url: str, api_key: str):
        self.url = url
        self.api_key = api_key
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def fetch_indicators(self, hours: int = 24) -> List[ThreatIndicator]:
        """Fetch threat indicators from OpenCTI"""
        query = """
        query GetIndicators($first: Int, $after: String) {
            indicators(first: $first, after: $after, 
                      filters: [{key: "created_at", 
                                operator: gt, 
                                values: ["%s"]}]) {
                edges {
                    node {
                        id
                        pattern
                        pattern_type
                        valid_from
                        valid_until
                        x_opencti_score
                        description
                        objectLabel {
                            edges {
                                node {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
        """ % (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        try:
            async with self.session.post(
                f"{self.url}/graphql",
                json={"query": query, "variables": {"first": 1000}}
            ) as response:
                data = await response.json()
                
                indicators = []
                for edge in data.get("data", {}).get("indicators", {}).get("edges", []):
                    node = edge["node"]
                    
                    # Parse STIX pattern
                    pattern = node["pattern"]
                    indicator_type, value = self._parse_stix_pattern(pattern)
                    
                    # Extract tags
                    tags = [
                        label["node"]["value"]
                        for label in node.get("objectLabel", {}).get("edges", [])
                    ]
                    
                    indicators.append(ThreatIndicator(
                        indicator_type=indicator_type,
                        value=value,
                        threat_type=self._classify_threat(tags),
                        severity=self._map_severity(node.get("x_opencti_score", 50)),
                        source="opencti",
                        first_seen=datetime.fromisoformat(node["valid_from"].replace("Z", "+00:00")),
                        last_seen=datetime.fromisoformat(node.get("valid_until", node["valid_from"]).replace("Z", "+00:00")),
                        confidence=node.get("x_opencti_score", 50) / 100.0,
                        tags=tags,
                        description=node.get("description", "")
                    ))
                
                logger.info(f"Fetched {len(indicators)} indicators from OpenCTI")
                return indicators
                
        except Exception as e:
            logger.error(f"Error fetching OpenCTI indicators: {e}")
            return []
    
    def _parse_stix_pattern(self, pattern: str) -> tuple:
        """Parse STIX pattern to extract indicator type and value"""
        # Example: [ipv4-addr:value = '192.168.1.1']
        if "ipv4-addr:value" in pattern or "ipv6-addr:value" in pattern:
            value = pattern.split("'")[1]
            return "ip", value
        elif "domain-name:value" in pattern:
            value = pattern.split("'")[1]
            return "domain", value
        elif "url:value" in pattern:
            value = pattern.split("'")[1]
            return "url", value
        elif "file:hashes" in pattern:
            value = pattern.split("'")[1]
            return "hash", value
        else:
            return "unknown", pattern
    
    def _classify_threat(self, tags: List[str]) -> str:
        """Classify threat type from tags"""
        tag_str = " ".join(tags).lower()
        if any(word in tag_str for word in ["malware", "trojan", "ransomware"]):
            return "malware"
        elif any(word in tag_str for word in ["botnet", "c2", "command"]):
            return "botnet"
        elif any(word in tag_str for word in ["exploit", "cve", "vulnerability"]):
            return "exploit"
        elif any(word in tag_str for word in ["phishing", "scam"]):
            return "phishing"
        else:
            return "unknown"
    
    def _map_severity(self, score: int) -> str:
        """Map OpenCTI score to severity"""
        if score >= 80:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"


class AlienVaultOTXClient:
    """AlienVault OTX threat intelligence client"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://otx.alienvault.com/api/v1"
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"X-OTX-API-KEY": self.api_key}
        )
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def fetch_indicators(self, hours: int = 24) -> List[ThreatIndicator]:
        """Fetch threat indicators from AlienVault OTX"""
        try:
            # Fetch recent pulses
            modified_since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            
            async with self.session.get(
                f"{self.base_url}/pulses/subscribed",
                params={"modified_since": modified_since, "limit": 100}
            ) as response:
                data = await response.json()
                
                indicators = []
                for pulse in data.get("results", []):
                    for indicator in pulse.get("indicators", []):
                        indicators.append(ThreatIndicator(
                            indicator_type=indicator["type"],
                            value=indicator["indicator"],
                            threat_type=self._classify_threat(pulse.get("tags", [])),
                            severity=self._map_severity(pulse.get("TLP", "white")),
                            source="alienvault_otx",
                            first_seen=datetime.fromisoformat(indicator.get("created", pulse["created"]).replace("Z", "+00:00")),
                            last_seen=datetime.fromisoformat(pulse.get("modified", pulse["created"]).replace("Z", "+00:00")),
                            confidence=0.8,  # OTX generally high confidence
                            tags=pulse.get("tags", []),
                            description=pulse.get("description", "")
                        ))
                
                logger.info(f"Fetched {len(indicators)} indicators from AlienVault OTX")
                return indicators
                
        except Exception as e:
            logger.error(f"Error fetching OTX indicators: {e}")
            return []
    
    def _classify_threat(self, tags: List[str]) -> str:
        """Classify threat type from tags"""
        tag_str = " ".join(tags).lower()
        if any(word in tag_str for word in ["malware", "trojan", "ransomware"]):
            return "malware"
        elif any(word in tag_str for word in ["botnet", "c2"]):
            return "botnet"
        elif any(word in tag_str for word in ["exploit", "cve"]):
            return "exploit"
        elif any(word in tag_str for word in ["phishing"]):
            return "phishing"
        else:
            return "unknown"
    
    def _map_severity(self, tlp: str) -> str:
        """Map TLP to severity"""
        tlp_map = {
            "red": "critical",
            "amber": "high",
            "green": "medium",
            "white": "low"
        }
        return tlp_map.get(tlp.lower(), "medium")


class AbuseCHClient:
    """Abuse.ch threat intelligence client"""
    
    def __init__(self):
        self.base_url = "https://urlhaus-api.abuse.ch/v1"
        self.feodo_url = "https://feodotracker.abuse.ch/downloads/ipblocklist.json"
        self.sslbl_url = "https://sslbl.abuse.ch/blacklist/sslblacklist.json"
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def fetch_indicators(self, hours: int = 24) -> List[ThreatIndicator]:
        """Fetch threat indicators from Abuse.ch"""
        indicators = []
        
        # Fetch URLhaus data
        indicators.extend(await self._fetch_urlhaus())
        
        # Fetch Feodo Tracker data
        indicators.extend(await self._fetch_feodo())
        
        # Fetch SSL Blacklist data
        indicators.extend(await self._fetch_sslbl())
        
        logger.info(f"Fetched {len(indicators)} indicators from Abuse.ch")
        return indicators
    
    async def _fetch_urlhaus(self) -> List[ThreatIndicator]:
        """Fetch URLhaus malware URLs"""
        try:
            async with self.session.post(
                f"{self.base_url}/urls/recent/",
                data={"limit": 100}
            ) as response:
                data = await response.json()
                
                indicators = []
                for url_data in data.get("urls", []):
                    indicators.append(ThreatIndicator(
                        indicator_type="url",
                        value=url_data["url"],
                        threat_type="malware",
                        severity="high",
                        source="abuse_ch_urlhaus",
                        first_seen=datetime.fromisoformat(url_data["date_added"].replace("Z", "+00:00")),
                        last_seen=datetime.utcnow(),
                        confidence=0.9,
                        tags=url_data.get("tags", []),
                        description=f"Malware: {url_data.get('threat', 'unknown')}"
                    ))
                
                return indicators
                
        except Exception as e:
            logger.error(f"Error fetching URLhaus data: {e}")
            return []
    
    async def _fetch_feodo(self) -> List[ThreatIndicator]:
        """Fetch Feodo Tracker botnet IPs"""
        try:
            async with self.session.get(self.feodo_url) as response:
                data = await response.json()
                
                indicators = []
                for entry in data:
                    indicators.append(ThreatIndicator(
                        indicator_type="ip",
                        value=entry["ip_address"],
                        threat_type="botnet",
                        severity="critical",
                        source="abuse_ch_feodo",
                        first_seen=datetime.fromisoformat(entry["first_seen"].replace("Z", "+00:00")),
                        last_seen=datetime.fromisoformat(entry.get("last_seen", entry["first_seen"]).replace("Z", "+00:00")),
                        confidence=0.95,
                        tags=[entry.get("malware", "unknown")],
                        description=f"Botnet C2: {entry.get('malware', 'unknown')}"
                    ))
                
                return indicators
                
        except Exception as e:
            logger.error(f"Error fetching Feodo data: {e}")
            return []
    
    async def _fetch_sslbl(self) -> List[ThreatIndicator]:
        """Fetch SSL Blacklist data"""
        try:
            async with self.session.get(self.sslbl_url) as response:
                data = await response.json()
                
                indicators = []
                for entry in data:
                    indicators.append(ThreatIndicator(
                        indicator_type="hash",
                        value=entry["sha1_hash"],
                        threat_type="malware",
                        severity="high",
                        source="abuse_ch_sslbl",
                        first_seen=datetime.fromisoformat(entry["listing_date"].replace("Z", "+00:00")),
                        last_seen=datetime.utcnow(),
                        confidence=0.9,
                        tags=[entry.get("reason", "unknown")],
                        description=f"Malicious SSL: {entry.get('reason', 'unknown')}"
                    ))
                
                return indicators
                
        except Exception as e:
            logger.error(f"Error fetching SSL Blacklist data: {e}")
            return []


class ThreatIntelligenceService:
    """Main threat intelligence service"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.indicators: Dict[str, ThreatIndicator] = {}
        self.update_interval = config.get("update_interval", 300)  # 5 minutes
        self.running = False
    
    async def start(self):
        """Start threat intelligence service"""
        self.running = True
        logger.info("Starting Threat Intelligence Service")
        
        while self.running:
            try:
                await self.update_indicators()
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error in threat intelligence update loop: {e}")
                await asyncio.sleep(60)
    
    async def stop(self):
        """Stop threat intelligence service"""
        self.running = False
        logger.info("Stopping Threat Intelligence Service")
    
    async def update_indicators(self):
        """Update threat indicators from all sources"""
        logger.info("Updating threat indicators...")
        
        all_indicators = []
        
        # Fetch from OpenCTI
        if self.config.get("opencti", {}).get("enabled", False):
            async with OpenCTIClient(
                url=self.config["opencti"]["url"],
                api_key=self.config["opencti"]["api_key"]
            ) as client:
                indicators = await client.fetch_indicators(hours=24)
                all_indicators.extend(indicators)
        
        # Fetch from AlienVault OTX
        if self.config.get("otx", {}).get("enabled", False):
            async with AlienVaultOTXClient(
                api_key=self.config["otx"]["api_key"]
            ) as client:
                indicators = await client.fetch_indicators(hours=24)
                all_indicators.extend(indicators)
        
        # Fetch from Abuse.ch
        if self.config.get("abuse_ch", {}).get("enabled", True):
            async with AbuseCHClient() as client:
                indicators = await client.fetch_indicators(hours=24)
                all_indicators.extend(indicators)
        
        # Deduplicate and store indicators
        for indicator in all_indicators:
            key = hashlib.sha256(f"{indicator.indicator_type}:{indicator.value}".encode()).hexdigest()
            
            if key in self.indicators:
                # Update existing indicator
                existing = self.indicators[key]
                existing.last_seen = max(existing.last_seen, indicator.last_seen)
                existing.confidence = max(existing.confidence, indicator.confidence)
                existing.tags = list(set(existing.tags + indicator.tags))
            else:
                # Add new indicator
                self.indicators[key] = indicator
        
        logger.info(f"Updated threat intelligence: {len(self.indicators)} total indicators")
        
        # Export to openappsec
        await self.export_to_openappsec()
    
    async def export_to_openappsec(self):
        """Export indicators to openappsec"""
        # Group indicators by type
        ip_blocklist = [
            ind.value for ind in self.indicators.values()
            if ind.indicator_type == "ip" and ind.severity in ["critical", "high"]
        ]
        
        domain_blocklist = [
            ind.value for ind in self.indicators.values()
            if ind.indicator_type == "domain" and ind.severity in ["critical", "high"]
        ]
        
        url_blocklist = [
            ind.value for ind in self.indicators.values()
            if ind.indicator_type == "url" and ind.severity in ["critical", "high"]
        ]
        
        # Write to files for openappsec to consume
        with open("/etc/openappsec/threat-intel/ip_blocklist.txt", "w") as f:
            f.write("\n".join(ip_blocklist))
        
        with open("/etc/openappsec/threat-intel/domain_blocklist.txt", "w") as f:
            f.write("\n".join(domain_blocklist))
        
        with open("/etc/openappsec/threat-intel/url_blocklist.txt", "w") as f:
            f.write("\n".join(url_blocklist))
        
        logger.info(f"Exported {len(ip_blocklist)} IPs, {len(domain_blocklist)} domains, {len(url_blocklist)} URLs to openappsec")
    
    def check_indicator(self, indicator_type: str, value: str) -> Optional[ThreatIndicator]:
        """Check if an indicator is in the threat intelligence database"""
        key = hashlib.sha256(f"{indicator_type}:{value}".encode()).hexdigest()
        return self.indicators.get(key)


# Main entry point
if __name__ == "__main__":
    config = {
        "update_interval": 300,
        "opencti": {
            "enabled": True,
            "url": "https://opencti.platform.ng",
            "api_key": "CHANGE_ME"
        },
        "otx": {
            "enabled": True,
            "api_key": "CHANGE_ME"
        },
        "abuse_ch": {
            "enabled": True
        }
    }
    
    service = ThreatIntelligenceService(config)
    
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("Shutting down...")

