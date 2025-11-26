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
                        except (ResourceNotFoundError, Exception) as e:
                            # IP might be deleted or inaccessible
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
    
    def create_network_rule(self, firewall_name, rule_collection_name, rule_name,
                           source_addresses, destination_addresses, destination_ports,
                           protocols):
        """
        Create a Network rule to allow outbound traffic from containers.
        
        Network rules control outbound traffic from containers through the firewall.
        
        Args:
            firewall_name (str): Name of the Azure Firewall
            rule_collection_name (str): Name for the Network rule collection
            rule_name (str): Name for the Network rule
            source_addresses (list): List of source IP addresses/CIDRs (e.g., ["10.0.2.0/24"])
            destination_addresses (list): List of destination IP addresses (e.g., ["*"])
            destination_ports (list): List of destination ports (e.g., ["5060", "5061"])
            protocols (list): List of protocols - "TCP", "UDP", "Any", or "ICMP"
            
        Returns:
            AzureFirewall: Updated firewall resource
            
        Example:
            # Allow UDP/TCP traffic from container subnet to any destination
            create_network_rule(
                firewall_name="myfw",
                rule_collection_name="container-outbound",
                rule_name="allow-sip",
                source_addresses=["10.0.2.0/24"],
                destination_addresses=["*"],
                destination_ports=["5060", "5061"],
                protocols=["UDP", "TCP"]
            )
        """
        print(info(f"Adding Network rule '{rule_name}' to firewall '{firewall_name}'..."))
        
        # Get existing firewall
        firewall = self._client.azure_firewalls.get(
            self.resource_group, firewall_name
        )
        
        # Map protocol strings to enums
        protocol_mapping = {
            "TCP": AzureFirewallNetworkRuleProtocol.TCP,
            "UDP": AzureFirewallNetworkRuleProtocol.UDP,
            "ANY": AzureFirewallNetworkRuleProtocol.ANY,
            "ICMP": AzureFirewallNetworkRuleProtocol.ICMP
        }
        protocol_enums = []
        for protocol in protocols:
            protocol_enum = protocol_mapping.get(protocol.upper())
            if not protocol_enum:
                raise ValueError(f"Invalid protocol: {protocol}. Must be TCP, UDP, Any, or ICMP")
            protocol_enums.append(protocol_enum)
        
        # Create Network rule
        from azure.mgmt.network.models import AzureFirewallNetworkRuleCollection
        network_rule = AzureFirewallNetworkRule(
            name=rule_name,
            description=f"Allow {'/'.join(protocols)} traffic from containers",
            source_addresses=source_addresses,
            destination_addresses=destination_addresses,
            destination_ports=destination_ports,
            protocols=protocol_enums
        )
        
        # Check if rule collection exists
        rule_collection = None
        for rc in firewall.network_rule_collections or []:
            if rc.name == rule_collection_name:
                rule_collection = rc
                break
        
        if rule_collection:
            # Add rule to existing collection
            rule_collection.rules.append(network_rule)
        else:
            # Create new rule collection
            rule_collection = AzureFirewallNetworkRuleCollection(
                name=rule_collection_name,
                priority=200,  # Different priority from NAT rules
                action={'type': 'Allow'},
                rules=[network_rule]
            )
            
            if firewall.network_rule_collections is None:
                firewall.network_rule_collections = []
            firewall.network_rule_collections.append(rule_collection)
        
        # Update firewall with new rule
        poller = self._client.azure_firewalls.begin_create_or_update(
            self.resource_group,
            firewall_name,
            firewall
        )
        
        updated_firewall = poller.result()
        print(good(f"Network rule '{rule_name}' added successfully"))
        print(info(f"  Source: {', '.join(source_addresses)} → Destination: {', '.join(destination_addresses)}"))
        print(info(f"  Ports: {', '.join(destination_ports)} ({', '.join(protocols)})"))
        
        return updated_firewall
    
    def create_route_table(self, route_table_name, vnet_name, subnet_name, 
                          firewall_private_ip, location='westeurope'):
        """
        Create a route table to route container traffic through the firewall.
        
        This routes all traffic (0.0.0.0/0) from the container subnet through the
        Azure Firewall's private IP (virtual appliance).
        
        Args:
            route_table_name (str): Name for the route table
            vnet_name (str): Virtual Network name
            subnet_name (str): Subnet name to associate with route table
            firewall_private_ip (str): Private IP address of the firewall (e.g., "10.0.0.4")
            location (str): Azure location (default: westeurope)
            
        Returns:
            RouteTable: Created route table resource
            
        Example:
            create_route_table(
                route_table_name="container-subnet-route",
                vnet_name="firewall-vnet",
                subnet_name="container-ingress-subnet",
                firewall_private_ip="10.0.0.4"
            )
        """
        print(info(f"Creating route table '{route_table_name}' for subnet '{subnet_name}'..."))
        
        from azure.mgmt.network.models import RouteTable, Route
        
        # Create route for all traffic (0.0.0.0/0) to go through firewall
        route = Route(
            name="default-via-firewall",
            address_prefix="0.0.0.0/0",
            next_hop_type="VirtualAppliance",
            next_hop_ip_address=firewall_private_ip
        )
        
        # Create route table with the route
        route_table_params = RouteTable(
            location=location,
            routes=[route],
            tags={
                'purpose': 'firewall-routing',
                'managed-by': 'acido'
            }
        )
        
        # Create the route table
        poller = self._client.route_tables.begin_create_or_update(
            self.resource_group,
            route_table_name,
            route_table_params
        )
        route_table = poller.result()
        print(good(f"Route table '{route_table_name}' created"))
        print(info(f"  Route: 0.0.0.0/0 → {firewall_private_ip} (VirtualAppliance)"))
        
        # Associate route table with subnet
        try:
            print(info(f"Associating route table with subnet '{subnet_name}'..."))
            subnet = self._client.subnets.get(self.resource_group, vnet_name, subnet_name)
            subnet.route_table = SubResource(id=route_table.id)
            
            poller = self._client.subnets.begin_create_or_update(
                self.resource_group,
                vnet_name,
                subnet_name,
                subnet
            )
            poller.result()
            print(good(f"Route table associated with subnet '{subnet_name}'"))
        except Exception as e:
            print(orange(f"Warning: Could not associate route table with subnet: {e}"))
            print(info("You may need to associate it manually"))
        
        return route_table
    
    def get_firewall_private_ip(self, firewall_name):
        """
        Get the private IP address of an Azure Firewall.
        
        Args:
            firewall_name (str): Name of the Azure Firewall
            
        Returns:
            str: Private IP address (e.g., "10.0.0.4") or None if not found
        """
        try:
            firewall = self._client.azure_firewalls.get(
                self.resource_group, firewall_name
            )
            
            if firewall.ip_configurations:
                # Get private IP from first IP configuration
                ip_config = firewall.ip_configurations[0]
                if hasattr(ip_config, 'private_ip_address') and ip_config.private_ip_address:
                    return ip_config.private_ip_address
            
            return None
        except Exception as e:
            print(bad(f"Failed to get firewall private IP: {e}"))
            return None
