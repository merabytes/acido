"""
Azure Firewall Manager for DNAT-based port forwarding.

This module provides enterprise-grade firewall capabilities with DNAT (Destination NAT)
support for forwarding traffic from public IPs to private container instances.

Cost: ~$1.25/hour (~$900/month) - Enterprise feature
"""

from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import (
    AzureFirewall, AzureFirewallSku, AzureFirewallSkuName, AzureFirewallSkuTier,
    AzureFirewallIPConfiguration, SubResource, AzureFirewallNatRule,
    AzureFirewallNatRuleCollection, AzureFirewallNetworkRule,
    AzureFirewallApplicationRule, AzureFirewallNetworkRuleProtocol
)
from acido.azure_utils.ManagedIdentity import ManagedIdentity
from huepy import good, bad, orange, info
from azure.core.exceptions import ResourceNotFoundError

__authors__ = "Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)"
__coauthor__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"


class FirewallManager(ManagedIdentity):
    """
    Manages Azure Firewall resources for DNAT-based port forwarding.
    
    Azure Firewall provides enterprise-grade security with:
    - DNAT (Destination NAT) for port forwarding
    - FQDN filtering for outbound traffic
    - Threat intelligence integration
    - High availability
    
    Note: This is an expensive solution (~$900/month). Consider using
    the --bidirectional flag for cost-effective port forwarding (~$13/month).
    """
    
    def __init__(self, resource_group, login: bool = True):
        """
        Initialize FirewallManager.
        
        Args:
            resource_group (str): Azure resource group name
            login (bool): Whether to authenticate with Azure
        """
        self.resource_group = resource_group
        self.location = 'westeurope'
        
        if login:
            credential = self.get_credential()
            subscription = self.extract_subscription(credential)
            self._client = NetworkManagementClient(credential, subscription)
            self.subscription_id = subscription
    
    def create_firewall(self, firewall_name, vnet_name, subnet_name, public_ip_name):
        """
        Create an Azure Firewall in the specified VNet/Subnet.
        
        Azure Firewall requires:
        1. A dedicated subnet named "AzureFirewallSubnet" (minimum /26)
        2. A public IP address (Standard SKU)
        3. VNet for deployment
        
        Args:
            firewall_name (str): Name for the Azure Firewall
            vnet_name (str): Name of the Virtual Network
            subnet_name (str): Name of the firewall subnet (must be "AzureFirewallSubnet")
            public_ip_name (str): Name of the public IP to assign to firewall
            
        Returns:
            AzureFirewall: Created firewall resource
            
        Raises:
            ValueError: If subnet name is not "AzureFirewallSubnet"
        """
        if subnet_name != "AzureFirewallSubnet":
            raise ValueError(
                f"Firewall subnet must be named 'AzureFirewallSubnet', got '{subnet_name}'"
            )
        
        print(info(f"Creating Azure Firewall '{firewall_name}' (this may take 5-10 minutes)..."))
        
        # Get public IP resource
        public_ip = self._client.public_ip_addresses.get(
            self.resource_group, public_ip_name
        )
        
        # Get subnet resource
        subnet = self._client.subnets.get(
            self.resource_group, vnet_name, subnet_name
        )
        
        # Create firewall IP configuration
        ip_config = AzureFirewallIPConfiguration(
            name=f"{firewall_name}-ipconfig",
            subnet=SubResource(id=subnet.id),
            public_ip_address=SubResource(id=public_ip.id)
        )
        
        # Create Azure Firewall
        firewall_params = AzureFirewall(
            location=self.location,
            sku=AzureFirewallSku(
                name=AzureFirewallSkuName.AZFW_VNET,
                tier=AzureFirewallSkuTier.STANDARD
            ),
            ip_configurations=[ip_config],
            nat_rule_collections=[],  # Start with no rules
            network_rule_collections=[],
            application_rule_collections=[],
            tags={
                'purpose': 'port-forwarding',
                'solution': 'Solution-4-Azure-Firewall'
            }
        )
        
        # Deploy firewall (async operation)
        poller = self._client.azure_firewalls.begin_create_or_update(
            self.resource_group,
            firewall_name,
            firewall_params
        )
        
        firewall = poller.result()
        print(good(f"Azure Firewall '{firewall_name}' created successfully"))
        print(info(f"  Public IP: {public_ip.ip_address}"))
        print(orange(f"  Cost: ~$1.25/hour (~$900/month)"))
        
        return firewall
    
    def create_dnat_rule(self, firewall_name, rule_collection_name, rule_name,
                        source_addresses, destination_address, destination_port,
                        translated_address, translated_port, protocol):
        """
        Create a DNAT (Destination NAT) rule to forward traffic to a container.
        
        DNAT rules forward inbound traffic from the firewall's public IP to
        internal private IPs (container instances).
        
        Args:
            firewall_name (str): Name of the Azure Firewall
            rule_collection_name (str): Name for the NAT rule collection
            rule_name (str): Name for the DNAT rule
            source_addresses (list): List of source IP addresses (e.g., ["*"] for any)
            destination_address (str): Firewall public IP address
            destination_port (str): Destination port on firewall (e.g., "5060")
            translated_address (str): Container private IP address
            translated_port (str): Container port (e.g., "5060")
            protocol (str): Protocol - "TCP", "UDP", or "Any"
            
        Returns:
            AzureFirewall: Updated firewall resource
            
        Example:
            # Forward UDP port 5060 from firewall to container
            create_dnat_rule(
                firewall_name="myfw",
                rule_collection_name="voip-rules",
                rule_name="sip-udp",
                source_addresses=["*"],
                destination_address="20.0.0.1",  # Firewall public IP
                destination_port="5060",
                translated_address="10.0.1.4",  # Container private IP
                translated_port="5060",
                protocol="UDP"
            )
        """
        print(info(f"Adding DNAT rule '{rule_name}' to firewall '{firewall_name}'..."))
        
        # Get existing firewall
        firewall = self._client.azure_firewalls.get(
            self.resource_group, firewall_name
        )
        
        # Map protocol string to enum
        protocol_mapping = {
            "TCP": AzureFirewallNetworkRuleProtocol.TCP,
            "UDP": AzureFirewallNetworkRuleProtocol.UDP,
            "ANY": AzureFirewallNetworkRuleProtocol.ANY
        }
        protocol_enum = protocol_mapping.get(protocol.upper())
        if not protocol_enum:
            raise ValueError(f"Invalid protocol: {protocol}. Must be TCP, UDP, or Any")
        
        # Create DNAT rule
        nat_rule = AzureFirewallNatRule(
            name=rule_name,
            description=f"Forward {protocol} port {destination_port} to container",
            source_addresses=source_addresses,
            destination_addresses=[destination_address],
            destination_ports=[destination_port],
            protocols=[protocol_enum],
            translated_address=translated_address,
            translated_port=translated_port
        )
        
        # Check if rule collection exists
        rule_collection = None
        for rc in firewall.nat_rule_collections or []:
            if rc.name == rule_collection_name:
                rule_collection = rc
                break
        
        if rule_collection:
            # Add rule to existing collection
            rule_collection.rules.append(nat_rule)
        else:
            # Create new rule collection
            rule_collection = AzureFirewallNatRuleCollection(
                name=rule_collection_name,
                priority=100,
                action={'type': 'Dnat'},
                rules=[nat_rule]
            )
            
            if firewall.nat_rule_collections is None:
                firewall.nat_rule_collections = []
            firewall.nat_rule_collections.append(rule_collection)
        
        # Update firewall with new rule
        poller = self._client.azure_firewalls.begin_create_or_update(
            self.resource_group,
            firewall_name,
            firewall
        )
        
        updated_firewall = poller.result()
        print(good(f"DNAT rule '{rule_name}' added successfully"))
        print(info(f"  {destination_address}:{destination_port} ({protocol}) → {translated_address}:{translated_port}"))
        
        return updated_firewall
    
    def delete_firewall(self, firewall_name):
        """
        Delete an Azure Firewall.
        
        Args:
            firewall_name (str): Name of the firewall to delete
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            print(info(f"Deleting Azure Firewall '{firewall_name}' (this may take several minutes)..."))
            poller = self._client.azure_firewalls.begin_delete(
                self.resource_group, firewall_name
            )
            poller.result()
            print(good(f"Azure Firewall '{firewall_name}' deleted successfully"))
            return True
        except ResourceNotFoundError:
            print(orange(f"Azure Firewall '{firewall_name}' not found"))
            return False
        except Exception as e:
            print(bad(f"Failed to delete firewall: {e}"))
            return False
    
    def get_firewall(self, firewall_name):
        """
        Get Azure Firewall resource by name.
        
        Args:
            firewall_name (str): Name of the firewall
            
        Returns:
            AzureFirewall: Firewall resource or None if not found
        """
        try:
            return self._client.azure_firewalls.get(
                self.resource_group, firewall_name
            )
        except ResourceNotFoundError:
            return None
    
    def list_firewalls(self):
        """
        List all Azure Firewalls in the resource group.
        
        Returns:
            list: List of dicts with firewall information
        """
        try:
            firewalls = self._client.azure_firewalls.list(self.resource_group)
            result = []
            
            for fw in firewalls:
                # Get public IP from first IP configuration
                public_ip_address = None
                if fw.ip_configurations:
                    ip_config = fw.ip_configurations[0]
                    if ip_config.public_ip_address:
                        # Extract public IP name from ID
                        ip_id = ip_config.public_ip_address.id
                        ip_name = ip_id.split('/')[-1]
                        try:
                            pip = self._client.public_ip_addresses.get(
                                self.resource_group, ip_name
                            )
                            public_ip_address = pip.ip_address
                        except:
                            pass
                
                # Count DNAT rules
                rule_count = 0
                if fw.nat_rule_collections:
                    for collection in fw.nat_rule_collections:
                        if collection.rules:
                            rule_count += len(collection.rules)
                
                result.append({
                    'name': fw.name,
                    'location': fw.location,
                    'public_ip': public_ip_address or 'Unknown',
                    'provisioning_state': fw.provisioning_state,
                    'dnat_rules': rule_count,
                    'sku_tier': fw.sku.tier if fw.sku else 'Unknown'
                })
            
            return result
        except Exception as e:
            print(bad(f"Failed to list firewalls: {e}"))
            return []
    
    def delete_dnat_rule(self, firewall_name, rule_collection_name, rule_name):
        """
        Delete a specific DNAT rule from a firewall.
        
        Args:
            firewall_name (str): Name of the Azure Firewall
            rule_collection_name (str): Name of the NAT rule collection
            rule_name (str): Name of the DNAT rule to delete
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            print(info(f"Deleting DNAT rule '{rule_name}' from firewall '{firewall_name}'..."))
            
            # Get existing firewall
            firewall = self._client.azure_firewalls.get(
                self.resource_group, firewall_name
            )
            
            # Find and remove the rule
            rule_found = False
            if firewall.nat_rule_collections:
                for collection in firewall.nat_rule_collections:
                    if collection.name == rule_collection_name and collection.rules:
                        # Filter out the rule to delete
                        original_count = len(collection.rules)
                        collection.rules = [r for r in collection.rules if r.name != rule_name]
                        
                        if len(collection.rules) < original_count:
                            rule_found = True
                            
                            # If collection is now empty, remove it
                            if not collection.rules:
                                firewall.nat_rule_collections = [
                                    rc for rc in firewall.nat_rule_collections 
                                    if rc.name != rule_collection_name
                                ]
                            break
            
            if not rule_found:
                print(orange(f"DNAT rule '{rule_name}' not found in collection '{rule_collection_name}'"))
                return False
            
            # Update firewall
            poller = self._client.azure_firewalls.begin_create_or_update(
                self.resource_group,
                firewall_name,
                firewall
            )
            poller.result()
            
            print(good(f"DNAT rule '{rule_name}' deleted successfully"))
            return True
            
        except Exception as e:
            print(bad(f"Failed to delete DNAT rule: {e}"))
            return False
