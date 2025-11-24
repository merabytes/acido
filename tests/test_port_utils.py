"""Unit tests for port_utils module."""

import unittest
import sys
import os

# Add parent directory to path to import acido modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from acido.utils.port_utils import (
    parse_port_spec,
    validate_port,
    validate_protocol,
    format_port_list
)


class TestPortUtils(unittest.TestCase):
    """Test cases for port utility functions."""
    
    def test_parse_port_spec_valid_udp(self):
        """Test parsing valid UDP port specification."""
        result = parse_port_spec("5060:udp")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["port"], 5060)
        self.assertEqual(result[0]["protocol"], "UDP")
    
    def test_parse_port_spec_valid_tcp(self):
        """Test parsing valid TCP port specification."""
        result = parse_port_spec("8080:tcp")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["port"], 8080)
        self.assertEqual(result[0]["protocol"], "TCP")
    
    def test_parse_port_spec_case_insensitive(self):
        """Test that protocol parsing is case insensitive."""
        result = parse_port_spec("443:TcP")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["port"], 443)
        self.assertEqual(result[0]["protocol"], "TCP")
    
    def test_parse_port_spec_range_valid(self):
        """Test parsing valid port range specification."""
        result = parse_port_spec("5060-5062:udp")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["port"], 5060)
        self.assertEqual(result[0]["protocol"], "UDP")
        self.assertEqual(result[1]["port"], 5061)
        self.assertEqual(result[1]["protocol"], "UDP")
        self.assertEqual(result[2]["port"], 5062)
        self.assertEqual(result[2]["protocol"], "UDP")
    
    def test_parse_port_spec_range_tcp(self):
        """Test parsing TCP port range."""
        result = parse_port_spec("8080-8082:tcp")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["port"], 8080)
        self.assertEqual(result[2]["port"], 8082)
        for port_info in result:
            self.assertEqual(port_info["protocol"], "TCP")
    
    def test_parse_port_spec_range_invalid_order(self):
        """Test parsing port range with invalid order (start > end)."""
        with self.assertRaises(ValueError) as context:
            parse_port_spec("5070-5060:udp")
        self.assertIn("must be less than", str(context.exception))
    
    def test_parse_port_spec_range_too_large(self):
        """Test parsing port range that's too large (>100 ports)."""
        with self.assertRaises(ValueError) as context:
            parse_port_spec("1000-1200:udp")  # 201 ports
        self.assertIn("too large", str(context.exception))
    
    def test_parse_port_spec_invalid_format(self):
        """Test parsing invalid port specification format."""
        with self.assertRaises(ValueError) as context:
            parse_port_spec("invalid")
        self.assertIn("Invalid port specification", str(context.exception))
    
    def test_parse_port_spec_missing_protocol(self):
        """Test parsing port spec without protocol."""
        with self.assertRaises(ValueError):
            parse_port_spec("8080:")
    
    def test_parse_port_spec_extra_colons(self):
        """Test parsing port spec with extra colons (should handle gracefully)."""
        with self.assertRaises(ValueError):
            parse_port_spec("8080:tcp:extra")
    
    def test_parse_port_spec_invalid_port_number(self):
        """Test parsing invalid port number."""
        with self.assertRaises(ValueError):
            parse_port_spec("99999:tcp")
    
    def test_parse_port_spec_invalid_protocol(self):
        """Test parsing invalid protocol."""
        with self.assertRaises(ValueError):
            parse_port_spec("8080:icmp")
    
    def test_validate_port_valid(self):
        """Test validating valid port numbers."""
        self.assertTrue(validate_port(1))
        self.assertTrue(validate_port(80))
        self.assertTrue(validate_port(5060))
        self.assertTrue(validate_port(65535))
    
    def test_validate_port_too_low(self):
        """Test validating port number below minimum."""
        with self.assertRaises(ValueError) as context:
            validate_port(0)
        self.assertIn("must be between 1 and 65535", str(context.exception))
    
    def test_validate_port_too_high(self):
        """Test validating port number above maximum."""
        with self.assertRaises(ValueError) as context:
            validate_port(65536)
        self.assertIn("must be between 1 and 65535", str(context.exception))
    
    def test_validate_port_invalid_type(self):
        """Test validating port with invalid type."""
        with self.assertRaises(ValueError) as context:
            validate_port("not a number")
        self.assertIn("must be an integer", str(context.exception))
    
    def test_validate_protocol_tcp(self):
        """Test validating TCP protocol."""
        self.assertTrue(validate_protocol("TCP"))
        self.assertTrue(validate_protocol("tcp"))
        self.assertTrue(validate_protocol("TcP"))
    
    def test_validate_protocol_udp(self):
        """Test validating UDP protocol."""
        self.assertTrue(validate_protocol("UDP"))
        self.assertTrue(validate_protocol("udp"))
        self.assertTrue(validate_protocol("UdP"))
    
    def test_validate_protocol_invalid(self):
        """Test validating invalid protocol."""
        with self.assertRaises(ValueError) as context:
            validate_protocol("ICMP")
        self.assertIn("must be TCP or UDP", str(context.exception))
        
        with self.assertRaises(ValueError):
            validate_protocol("HTTP")
    
    def test_format_port_list_single(self):
        """Test formatting single port."""
        ports = [{"port": 5060, "protocol": "UDP"}]
        result = format_port_list(ports)
        self.assertEqual(result, "5060/UDP")
    
    def test_format_port_list_multiple(self):
        """Test formatting multiple ports."""
        ports = [
            {"port": 5060, "protocol": "UDP"},
            {"port": 8080, "protocol": "TCP"},
            {"port": 443, "protocol": "TCP"}
        ]
        result = format_port_list(ports)
        self.assertEqual(result, "5060/UDP, 8080/TCP, 443/TCP")
    
    def test_format_port_list_empty(self):
        """Test formatting empty port list."""
        ports = []
        result = format_port_list(ports)
        self.assertEqual(result, "")


class TestPortUtilsIntegration(unittest.TestCase):
    """Integration tests for port utility functions."""
    
    def test_parse_and_format_roundtrip(self):
        """Test parsing a port spec and formatting it back."""
        spec = "5060:udp"
        parsed = parse_port_spec(spec)
        formatted = format_port_list(parsed)
        self.assertEqual(formatted, "5060/UDP")
    
    def test_multiple_ports_workflow(self):
        """Test typical workflow with multiple ports."""
        specs = ["5060:udp", "5060:tcp", "8080:tcp"]
        all_ports = []
        for spec in specs:
            all_ports.extend(parse_port_spec(spec))
        
        # Verify all parsed correctly
        self.assertEqual(len(all_ports), 3)
        self.assertEqual(all_ports[0]["port"], 5060)
        self.assertEqual(all_ports[0]["protocol"], "UDP")
        self.assertEqual(all_ports[1]["port"], 5060)
        self.assertEqual(all_ports[1]["protocol"], "TCP")
        self.assertEqual(all_ports[2]["port"], 8080)
        self.assertEqual(all_ports[2]["protocol"], "TCP")
        
        # Format for display
        formatted = format_port_list(all_ports)
        self.assertEqual(formatted, "5060/UDP, 5060/TCP, 8080/TCP")
    
    def test_port_range_workflow(self):
        """Test workflow with port ranges."""
        specs = ["5060-5062:udp", "8080:tcp"]
        all_ports = []
        for spec in specs:
            all_ports.extend(parse_port_spec(spec))
        
        # Verify range was expanded
        self.assertEqual(len(all_ports), 4)  # 3 from range + 1 single
        self.assertEqual(all_ports[0]["port"], 5060)
        self.assertEqual(all_ports[1]["port"], 5061)
        self.assertEqual(all_ports[2]["port"], 5062)
        self.assertEqual(all_ports[3]["port"], 8080)
        
        # Format for display
        formatted = format_port_list(all_ports)
        self.assertIn("5060/UDP", formatted)
        self.assertIn("5061/UDP", formatted)
        self.assertIn("5062/UDP", formatted)
        self.assertIn("8080/TCP", formatted)


if __name__ == '__main__':
    unittest.main()
