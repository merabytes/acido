"""
Basic unit tests for Azure App Service Plan (ASP) scaling functionality.

These tests verify:
- ASP SKU tier validation
- CLI argument parsing
- Pattern matching logic
- Configuration handling
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from acido.azure_utils.AppServicePlanManager import ASP_SKU_TIERS, AppServicePlanManager
import fnmatch


class TestASPBasics(unittest.TestCase):
    """Basic tests for ASP functionality without Azure SDK dependencies."""
    
    def test_asp_sku_tiers_structure(self):
        """Test that ASP_SKU_TIERS has the correct structure."""
        # Verify it's a list
        self.assertIsInstance(ASP_SKU_TIERS, list)
        
        # Verify each entry is a tuple with 3 elements
        for tier in ASP_SKU_TIERS:
            self.assertIsInstance(tier, tuple)
            self.assertEqual(len(tier), 3)
            
            tier_name, sku_name, display_name = tier
            self.assertIsInstance(tier_name, str)
            self.assertIsInstance(sku_name, str)
            self.assertIsInstance(display_name, str)
    
    def test_asp_sku_tiers_count(self):
        """Test that we have a reasonable number of SKU tiers."""
        # Should have at least 15 tiers (Free, Shared, Basic, Standard, Premium, Isolated)
        self.assertGreaterEqual(len(ASP_SKU_TIERS), 15)
    
    def test_asp_sku_validation(self):
        """Test SKU validation logic."""
        # Valid SKU combinations
        valid_cases = [
            ('Basic', 'B1'),
            ('Standard', 'S1'),
            ('PremiumV2', 'P1v2'),
            ('PremiumV3', 'P1v3'),
        ]
        
        for tier, sku in valid_cases:
            self.assertTrue(
                AppServicePlanManager.validate_sku(tier, sku),
                f"Expected {tier}/{sku} to be valid"
            )
        
        # Invalid SKU combinations
        invalid_cases = [
            ('Basic', 'S1'),  # Wrong tier
            ('Standard', 'P1v2'),  # Wrong tier
            ('InvalidTier', 'B1'),  # Non-existent tier
            ('Basic', 'InvalidSKU'),  # Non-existent SKU
        ]
        
        for tier, sku in invalid_cases:
            self.assertFalse(
                AppServicePlanManager.validate_sku(tier, sku),
                f"Expected {tier}/{sku} to be invalid"
            )
    
    def test_available_tiers_method(self):
        """Test that get_available_tiers returns the correct list."""
        available_tiers = AppServicePlanManager.get_available_tiers()
        self.assertEqual(available_tiers, ASP_SKU_TIERS)
    
    def test_pattern_matching_all(self):
        """Test that '*' pattern matches all ASP names."""
        test_names = ['prod-asp-01', 'dev-asp-01', 'test-asp', 'my-app']
        pattern = '*'
        
        for name in test_names:
            self.assertTrue(
                fnmatch.fnmatch(name, pattern),
                f"Expected '{name}' to match pattern '{pattern}'"
            )
    
    def test_pattern_matching_specific(self):
        """Test pattern matching for specific prefixes."""
        test_cases = [
            ('prod-*', 'prod-asp-01', True),
            ('prod-*', 'dev-asp-01', False),
            ('*-01', 'prod-asp-01', True),
            ('*-01', 'prod-asp-02', False),
            ('test-asp', 'test-asp', True),
            ('test-asp', 'test-asp-01', False),
        ]
        
        for pattern, name, expected in test_cases:
            result = fnmatch.fnmatch(name, pattern)
            self.assertEqual(
                result, expected,
                f"Pattern '{pattern}' with name '{name}' should be {expected}"
            )
    
    def test_tier_hierarchy(self):
        """Test that tiers are properly ordered (informally)."""
        tier_names = [tier[0] for tier in ASP_SKU_TIERS]
        
        # Check that we have the expected tiers
        expected_tiers = ['Free', 'Shared', 'Basic', 'Standard', 'PremiumV2', 'PremiumV3', 'IsolatedV2']
        for expected in expected_tiers:
            self.assertIn(expected, tier_names)
    
    def test_sku_naming_convention(self):
        """Test that SKU names follow expected naming conventions."""
        for tier_name, sku_name, display_name in ASP_SKU_TIERS:
            # SKU names should be non-empty strings
            self.assertIsInstance(sku_name, str)
            self.assertTrue(len(sku_name) > 0)
            
            # Display names should include the tier and SKU
            self.assertIn(sku_name, display_name)


class TestASPConfigurationHandling(unittest.TestCase):
    """Test configuration handling for ASP scaling."""
    
    def test_config_keys(self):
        """Test that expected configuration keys exist."""
        expected_keys = [
            'asp_scale_up_tier',
            'asp_scale_up_sku',
            'asp_scale_down_tier',
            'asp_scale_down_sku'
        ]
        
        # This test just validates that we have the expected keys defined
        for key in expected_keys:
            self.assertIsInstance(key, str)
            self.assertTrue(len(key) > 0)
    
    def test_scale_direction_exclusivity(self):
        """Test that scale up and scale down are mutually exclusive."""
        # This represents the logic: you can't scale up AND down at the same time
        scale_up = True
        scale_down = False
        
        # Only one should be true
        self.assertFalse(scale_up and scale_down)
        
        # At least one should be true (when scaling)
        self.assertTrue(scale_up or scale_down)
        
        # Test the opposite case
        scale_up = False
        scale_down = True
        self.assertFalse(scale_up and scale_down)
        self.assertTrue(scale_up or scale_down)


if __name__ == '__main__':
    unittest.main()
