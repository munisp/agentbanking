"""
VPN Detector Test Examples
Demonstrates VPN detection functionality
"""

from utils.vpn_detector import VPNDetector, detect_vpn


def test_vpn_detection():
    """Test VPN detection with various IPs"""

    print("=" * 60)
    print("VPN DETECTION TESTS")
    print("=" * 60)

    # Test cases
    test_ips = [
        # Regular IPs (likely clean)
        ("8.8.8.8", "Google DNS"),
        ("1.1.1.1", "Cloudflare DNS"),
        # Private IPs (should be skipped)
        ("192.168.1.1", "Private IP"),
        ("10.0.0.1", "Private IP"),
        ("127.0.0.1", "Localhost"),
        # Datacenter IPs (will be detected if in range)
        ("52.1.1.1", "AWS IP Range"),
        ("35.184.1.1", "Google Cloud IP Range"),
        ("13.64.1.1", "Azure IP Range"),
        ("104.131.1.1", "DigitalOcean IP Range"),
    ]

    for ip, description in test_ips:
        print(f"\n{description}: {ip}")
        print("-" * 60)

        result = detect_vpn(ip)

        print(f"  Is VPN:        {result['is_vpn']}")
        print(f"  Is Tor:        {result['is_tor']}")
        print(f"  Is Proxy:      {result['is_proxy']}")
        print(f"  Is Datacenter: {result['is_datacenter']}")
        print(f"  Threat Level:  {result['threat_level']}")
        print(f"  Detection:     {result['detection_method']}")

        # Determine action
        if result["is_tor"]:
            print("  ❌ ACTION: BLOCK (Tor)")
        elif result["is_vpn"]:
            print("  ❌ ACTION: BLOCK (VPN)")
        elif result["is_datacenter"]:
            print("  ⚠️  ACTION: BLOCK (Datacenter)")
        else:
            print("  ✅ ACTION: ALLOW")

    print("\n" + "=" * 60)


def test_reverse_dns():
    """Test reverse DNS lookup functionality"""

    print("\n" + "=" * 60)
    print("REVERSE DNS LOOKUP TESTS")
    print("=" * 60)

    test_ips = [
        "8.8.8.8",  # Google DNS (should have rDNS)
        "1.1.1.1",  # Cloudflare (should have rDNS)
        "192.168.1.1",  # Private (may not have rDNS)
    ]

    for ip in test_ips:
        hostname = VPNDetector._get_hostname(ip)
        print(f"\nIP: {ip}")
        print(f"Hostname: {hostname if hostname else 'No reverse DNS'}")

    print("\n" + "=" * 60)


def test_ip_range_check():
    """Test IP range matching"""

    print("\n" + "=" * 60)
    print("IP RANGE CHECK TESTS")
    print("=" * 60)

    # Test known datacenter ranges
    test_cases = [
        ("52.1.1.1", True, "AWS IP - should match"),
        ("35.184.1.1", True, "GCP IP - should match"),
        ("8.8.8.8", False, "Google DNS - should NOT match"),
        ("104.131.1.1", True, "DigitalOcean - should match"),
    ]

    for ip, expected, description in test_cases:
        is_datacenter = VPNDetector._is_datacenter_ip(ip)
        status = "✅ PASS" if is_datacenter == expected else "❌ FAIL"
        print(f"\n{status} - {description}")
        print(f"  IP: {ip}")
        print(f"  Expected: {expected}, Got: {is_datacenter}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("\n🔍 VPN DETECTOR TEST SUITE\n")

    test_vpn_detection()
    test_reverse_dns()
    test_ip_range_check()

    print("\n✅ All tests completed!\n")

    print("=" * 60)
    print("CONFIGURATION")
    print("=" * 60)
    print("\nTo configure VPN blocking, set these environment variables:")
    print("  BLOCK_VPN=true          # Block VPN connections (default: true)")
    print("  BLOCK_TOR=true          # Block Tor connections (default: true)")
    print("  BLOCK_DATACENTER=false  # Block datacenter IPs (default: false)")
    print("\nExample .env:")
    print("  BLOCK_VPN=true")
    print("  BLOCK_TOR=true")
    print("  BLOCK_DATACENTER=true")
    print("=" * 60)
