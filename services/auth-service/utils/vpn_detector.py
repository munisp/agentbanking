"""
VPN and Proxy Detection Utility
Detects VPNs, proxies, and datacenter IPs without external libraries.
"""

import socket
import re
from typing import Dict, Optional
from .helpers import create_logger

logger = create_logger(__name__)


class VPNDetector:
    """Detects VPN, proxy, Tor, and datacenter IPs using built-in Python libraries."""

    # Known VPN/Proxy/Datacenter providers (hostname patterns)
    VPN_PATTERNS = [
        r"vpn",
        r"proxy",
        r"anonymizer",
        r"hide",
        r"tunnel",
        r"private",
        r"nordvpn",
        r"expressvpn",
        r"surfshark",
        r"protonvpn",
        r"cyberghost",
        r"ipvanish",
        r"purevpn",
        r"vyprvpn",
        r"windscribe",
        r"tunnelbear",
        r"hma",
        r"hidemyass",
        r"torguard",
        r"mullvad",
    ]

    TOR_PATTERNS = [
        r"tor-exit",
        r"torexit",
        r"tor\.exit",
        r"\.onion",
    ]

    DATACENTER_PATTERNS = [
        r"aws",
        r"amazon",
        r"ec2",
        r"azure",
        r"google",
        r"gcp",
        r"digitalocean",
        r"linode",
        r"vultr",
        r"ovh",
        r"hetzner",
        r"contabo",
        r"cloudflare",
        r"fastly",
        r"akamai",
        r"rackspace",
        r"hosting",
        r"server",
        r"cloud",
        r"datacenter",
        r"vps",
        r"dedicated",
    ]

    # Known datacenter IP ranges (CIDR notation)
    # This is a small subset - in production, you'd want a more comprehensive list
    DATACENTER_IP_RANGES = [
        # AWS (sample ranges)
        "3.5.0.0/16",
        "13.248.0.0/16",
        "18.208.0.0/13",
        "52.0.0.0/8",
        "54.0.0.0/8",
        # Google Cloud (sample)
        "34.64.0.0/10",
        "35.184.0.0/13",
        # Azure (sample)
        "13.64.0.0/11",
        "20.33.0.0/16",
        "40.64.0.0/10",
        # DigitalOcean (sample)
        "104.131.0.0/16",
        "159.65.0.0/16",
        "167.71.0.0/16",
        # Linode (sample)
        "45.79.0.0/16",
        "66.175.208.0/20",
        "96.126.96.0/19",
    ]

    @staticmethod
    def detect(ip_address: str) -> Dict[str, bool]:
        """
        Detect if an IP is VPN, Tor, Proxy, or Datacenter.

        Args:
            ip_address: The IP address to check

        Returns:
            Dict with detection results:
            {
                'is_vpn': bool,
                'is_tor': bool,
                'is_proxy': bool,
                'is_datacenter': bool,
                'threat_level': str  # 'low', 'medium', 'high', 'critical'
            }
        """
        result = {
            "is_vpn": False,
            "is_tor": False,
            "is_proxy": False,
            "is_datacenter": False,
            "threat_level": "low",
            "detection_method": None,
        }

        try:
            # Skip detection for localhost/private IPs
            if VPNDetector._is_private_ip(ip_address):
                logger.info(f"Skipping VPN detection for private IP: {ip_address}")
                return result

            # 1. Reverse DNS lookup
            hostname = VPNDetector._get_hostname(ip_address)
            if hostname:
                logger.info(f"Reverse DNS for {ip_address}: {hostname}")

                # Check for Tor
                if VPNDetector._check_patterns(hostname, VPNDetector.TOR_PATTERNS):
                    result["is_tor"] = True
                    result["threat_level"] = "critical"
                    result["detection_method"] = "reverse_dns_tor"
                    logger.warning(f"Tor detected for IP {ip_address}: {hostname}")
                    return result

                # Check for VPN
                if VPNDetector._check_patterns(hostname, VPNDetector.VPN_PATTERNS):
                    result["is_vpn"] = True
                    result["is_proxy"] = True  # VPNs are also proxies
                    result["threat_level"] = "high"
                    result["detection_method"] = "reverse_dns_vpn"
                    logger.warning(f"VPN detected for IP {ip_address}: {hostname}")
                    return result

                # Check for Datacenter
                if VPNDetector._check_patterns(
                    hostname, VPNDetector.DATACENTER_PATTERNS
                ):
                    result["is_datacenter"] = True
                    result["threat_level"] = "high"
                    result["detection_method"] = "reverse_dns_datacenter"
                    logger.warning(
                        f"Datacenter IP detected for {ip_address}: {hostname}"
                    )
                    return result

            # 2. Check against known datacenter IP ranges
            if VPNDetector._is_datacenter_ip(ip_address):
                result["is_datacenter"] = True
                result["threat_level"] = "high"
                result["detection_method"] = "ip_range_datacenter"
                logger.warning(
                    f"Datacenter IP detected (IP range match) for {ip_address}"
                )
                return result

            logger.info(f"No VPN/Proxy/Tor detected for IP {ip_address}")

        except Exception as e:
            logger.error(f"Error during VPN detection for {ip_address}: {e}")

        return result

    @staticmethod
    def _get_hostname(ip_address: str) -> Optional[str]:
        """Get hostname from IP via reverse DNS lookup."""
        try:
            hostname, _, _ = socket.gethostbyaddr(ip_address)
            return hostname.lower()
        except socket.herror:
            # No reverse DNS record
            return None
        except socket.gaierror:
            # Invalid IP or DNS resolution failed
            return None
        except Exception as e:
            logger.error(f"Error in reverse DNS lookup for {ip_address}: {e}")
            return None

    @staticmethod
    def _check_patterns(hostname: str, patterns: list) -> bool:
        """Check if hostname matches any pattern in the list."""
        for pattern in patterns:
            if re.search(pattern, hostname, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _is_private_ip(ip_address: str) -> bool:
        """Check if IP is private/localhost."""
        try:
            parts = ip_address.split(".")
            if len(parts) != 4:
                return False

            first_octet = int(parts[0])
            second_octet = int(parts[1])

            # Localhost
            if first_octet == 127:
                return True

            # Private ranges
            if first_octet == 10:  # 10.0.0.0/8
                return True
            if first_octet == 172 and 16 <= second_octet <= 31:  # 172.16.0.0/12
                return True
            if first_octet == 192 and second_octet == 168:  # 192.168.0.0/16
                return True

            # Link-local
            if first_octet == 169 and second_octet == 254:  # 169.254.0.0/16
                return True

            return False
        except (ValueError, IndexError):
            return False

    @staticmethod
    def _is_datacenter_ip(ip_address: str) -> bool:
        """
        Check if IP belongs to known datacenter ranges.
        This is a simplified check - for production, use a comprehensive database.
        """
        try:
            ip_int = VPNDetector._ip_to_int(ip_address)

            for cidr in VPNDetector.DATACENTER_IP_RANGES:
                if VPNDetector._ip_in_range(ip_int, cidr):
                    return True

            return False
        except Exception as e:
            logger.error(f"Error checking datacenter IP range for {ip_address}: {e}")
            return False

    @staticmethod
    def _ip_to_int(ip_address: str) -> int:
        """Convert IP address to integer."""
        parts = ip_address.split(".")
        return (
            int(parts[0]) << 24
            | int(parts[1]) << 16
            | int(parts[2]) << 8
            | int(parts[3])
        )

    @staticmethod
    def _ip_in_range(ip_int: int, cidr: str) -> bool:
        """Check if IP (as int) is in CIDR range."""
        network, prefix = cidr.split("/")
        network_int = VPNDetector._ip_to_int(network)
        prefix_len = int(prefix)

        # Create netmask
        mask = (0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF

        return (ip_int & mask) == (network_int & mask)


# Convenience function
def detect_vpn(ip_address: str) -> Dict[str, bool]:
    """
    Detect if IP is using VPN/Proxy/Tor.

    Usage:
        result = detect_vpn("8.8.8.8")
        if result['is_vpn']:
            # Handle VPN detection
    """
    return VPNDetector.detect(ip_address)
