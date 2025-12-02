from azure.mgmt.web import WebSiteManagementClient
from acido.azure_utils.ManagedIdentity import ManagedIdentity
from huepy import good, bad, info, orange
import fnmatch

__authors__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"

# Valid Azure App Service Plan SKU tiers
# Format: (tier_name, sku_name, display_name)
ASP_SKU_TIERS = [
    # Free and Shared tiers
    ('Free', 'F1', 'Free - F1'),
    ('Shared', 'D1', 'Shared - D1'),
    
    # Basic tier
    ('Basic', 'B1', 'Basic - B1 (1 core, 1.75 GB RAM)'),
    ('Basic', 'B2', 'Basic - B2 (2 cores, 3.5 GB RAM)'),
    ('Basic', 'B3', 'Basic - B3 (4 cores, 7 GB RAM)'),
    
    # Standard tier
    ('Standard', 'S1', 'Standard - S1 (1 core, 1.75 GB RAM)'),
    ('Standard', 'S2', 'Standard - S2 (2 cores, 3.5 GB RAM)'),
    ('Standard', 'S3', 'Standard - S3 (4 cores, 7 GB RAM)'),
    
    # Premium tier (v2)
    ('PremiumV2', 'P1v2', 'Premium v2 - P1v2 (1 core, 3.5 GB RAM)'),
    ('PremiumV2', 'P2v2', 'Premium v2 - P2v2 (2 cores, 7 GB RAM)'),
    ('PremiumV2', 'P3v2', 'Premium v2 - P3v2 (4 cores, 14 GB RAM)'),
    
    # Premium tier (v3)
    ('PremiumV3', 'P1v3', 'Premium v3 - P1v3 (2 cores, 8 GB RAM)'),
    ('PremiumV3', 'P2v3', 'Premium v3 - P2v3 (4 cores, 16 GB RAM)'),
    ('PremiumV3', 'P3v3', 'Premium v3 - P3v3 (8 cores, 32 GB RAM)'),
    
    # Isolated tier (v2)
    ('IsolatedV2', 'I1v2', 'Isolated v2 - I1v2 (2 cores, 8 GB RAM)'),
    ('IsolatedV2', 'I2v2', 'Isolated v2 - I2v2 (4 cores, 16 GB RAM)'),
    ('IsolatedV2', 'I3v2', 'Isolated v2 - I3v2 (8 cores, 32 GB RAM)'),
]


class AppServicePlanManager(ManagedIdentity):
    """Manager for Azure App Service Plans operations."""
    
    def __init__(self, resource_group, login: bool = True):
        """
        Initialize the App Service Plan Manager.
        
        Args:
            resource_group (str): Azure resource group name
            login (bool): Whether to authenticate with Azure
        """
        self.resource_group = resource_group
        self.location = 'westeurope'
        
        if login:
            credential = self.get_credential(scope_keys=("instance",))
            subscription = self.extract_subscription(credential)
            self._client = WebSiteManagementClient(credential, subscription)
            self.subscription_id = subscription
    
    def list_app_service_plans(self, pattern=None):
        """
        List all App Service Plans in the resource group.
        
        Args:
            pattern (str): Optional glob pattern to filter ASP names (e.g., 'prod-*')
        
        Returns:
            list: List of App Service Plan objects
        """
        try:
            all_plans = list(self._client.app_service_plans.list_by_resource_group(self.resource_group))
            
            if pattern and pattern != '*':
                # Filter by pattern
                filtered_plans = [
                    plan for plan in all_plans 
                    if fnmatch.fnmatch(plan.name, pattern)
                ]
                return filtered_plans
            
            return all_plans
        except Exception as e:
            print(bad(f"Error listing App Service Plans: {str(e)}"))
            return []
    
    def get_app_service_plan(self, name):
        """
        Get a specific App Service Plan by name.
        
        Args:
            name (str): Name of the App Service Plan
        
        Returns:
            AppServicePlan object or None if not found
        """
        try:
            plan = self._client.app_service_plans.get(self.resource_group, name)
            return plan
        except Exception as e:
            print(bad(f"Error getting App Service Plan '{name}': {str(e)}"))
            return None
    
    def get_current_sku(self, name):
        """
        Get the current SKU tier of an App Service Plan.
        
        Args:
            name (str): Name of the App Service Plan
        
        Returns:
            tuple: (tier, sku_name) or (None, None) if not found
        """
        plan = self.get_app_service_plan(name)
        if plan and plan.sku:
            return (plan.sku.tier, plan.sku.name)
        return (None, None)
    
    def scale_app_service_plan(self, name, target_tier, target_sku):
        """
        Scale an App Service Plan to a different tier/SKU.
        
        Args:
            name (str): Name of the App Service Plan
            target_tier (str): Target tier (e.g., 'Standard', 'PremiumV2')
            target_sku (str): Target SKU name (e.g., 'S1', 'P1v2')
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            plan = self.get_app_service_plan(name)
            if not plan:
                return False
            
            # Update the SKU
            plan.sku.tier = target_tier
            plan.sku.name = target_sku
            
            # Apply the update
            updated_plan = self._client.app_service_plans.begin_create_or_update(
                self.resource_group,
                name,
                plan
            ).result()
            
            print(good(f"App Service Plan '{name}' scaled to {target_tier}/{target_sku}"))
            return True
            
        except Exception as e:
            print(bad(f"Error scaling App Service Plan '{name}': {str(e)}"))
            return False
    
    def scale_up(self, name, target_tier, target_sku):
        """
        Scale up an App Service Plan.
        
        Args:
            name (str): Name of the App Service Plan
            target_tier (str): Target tier for scale up
            target_sku (str): Target SKU for scale up
        
        Returns:
            bool: True if successful, False otherwise
        """
        current_tier, current_sku = self.get_current_sku(name)
        
        if not current_tier:
            print(bad(f"Could not get current SKU for App Service Plan '{name}'"))
            return False
        
        print(info(f"Scaling up '{name}' from {current_tier}/{current_sku} to {target_tier}/{target_sku}"))
        return self.scale_app_service_plan(name, target_tier, target_sku)
    
    def scale_down(self, name, target_tier, target_sku):
        """
        Scale down an App Service Plan.
        
        Args:
            name (str): Name of the App Service Plan
            target_tier (str): Target tier for scale down
            target_sku (str): Target SKU for scale down
        
        Returns:
            bool: True if successful, False otherwise
        """
        current_tier, current_sku = self.get_current_sku(name)
        
        if not current_tier:
            print(bad(f"Could not get current SKU for App Service Plan '{name}'"))
            return False
        
        print(info(f"Scaling down '{name}' from {current_tier}/{current_sku} to {target_tier}/{target_sku}"))
        return self.scale_app_service_plan(name, target_tier, target_sku)
    
    @staticmethod
    def get_available_tiers():
        """
        Get list of available ASP SKU tiers.
        
        Returns:
            list: List of tuples (tier_name, sku_name, display_name)
        """
        return ASP_SKU_TIERS
    
    @staticmethod
    def validate_sku(tier, sku_name):
        """
        Validate if a tier/SKU combination is valid.
        
        Args:
            tier (str): Tier name
            sku_name (str): SKU name
        
        Returns:
            bool: True if valid, False otherwise
        """
        for t, s, _ in ASP_SKU_TIERS:
            if t == tier and s == sku_name:
                return True
        return False
