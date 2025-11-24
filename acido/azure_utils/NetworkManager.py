from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import (
    Delegation, VirtualNetwork, Subnet, PublicIPAddressSku,
    NatGatewaySku, SubResource, NatGateway
)
from acido.azure_utils.ManagedIdentity import ManagedIdentity
from huepy import good

__authors__ = "Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)"
__coauthor__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"

class NetworkManager(ManagedIdentity):
    def __init__(self, resource_group, login: bool = True, user_assigned: str = None, ip_address: str = None):
        self.resource_group = resource_group
        self.location = 'westeurope'
        self.ip_address = ip_address
        if login:
            credential = self.get_credential()
            subscription = self.extract_subscription(credential)
            self._client = NetworkManagementClient(credential, subscription)
            self.subscription_id = subscription

    def create_ipv4(self, public_ip_name, with_nat_stack=False):
        """
        Create a public IP address, optionally tagged with NAT stack indicator.
        
        Args:
            public_ip_name (str): Name for the public IP
            with_nat_stack (bool): Whether this IP is part of a NAT Gateway stack
        
        Returns:
            str: Public IP resource ID
        """
        tags = {'has_nat_stack': 'true' if with_nat_stack else 'false'}
        
        params = {
            'location': self.location,
            'public_ip_allocation_method': 'Static',
            'public_ip_address_version': 'IPv4',
            'sku': PublicIPAddressSku(name='Standard', tier="Regional"),
            'tags': tags
        }
        pip = self._client.public_ip_addresses.begin_create_or_update(
            self.resource_group, public_ip_name, params
        ).result()
        print(good(f"Public IP Address {pip.id} created successfully."))
        return pip.id

    def list_ipv4(self):
        """
        List all public IP addresses with NAT stack indicator.
        
        Returns:
            list: List of dicts with IP information including has_nat_stack tag
        """
        ips = self._client.public_ip_addresses.list(self.resource_group)
        result = []
        for ip in ips:
            has_nat_stack = False
            if ip.tags and ip.tags.get('has_nat_stack') == 'true':
                has_nat_stack = True
            result.append({
                'id': ip.id,
                'name': ip.name,
                'ip_address': ip.ip_address,
                'location': ip.location,
                'has_nat_stack': has_nat_stack
            })
        return result

    def create_virtual_network(self, vnet_name, cidr="10.0.0.0/16"):
        vnet = self._client.virtual_networks.begin_create_or_update(
            self.resource_group, vnet_name,
            VirtualNetwork(location=self.location, address_space={"address_prefixes": [cidr]})
        ).result()
        print(good(f"Virtual Network {vnet.id} created successfully."))
        return vnet

    def create_subnet(self, vnet_name, subnet_name, public_ip_id, subnet_cidr="10.0.1.0/24"):
        # NAT GW with PIP for egress
        nat = self._client.nat_gateways.begin_create_or_update(
            resource_group_name=self.resource_group,
            nat_gateway_name=f'{subnet_name}-nat-gw',
            parameters=NatGateway(
                sku=NatGatewaySku(name="Standard"),
                location=self.location,
                public_ip_addresses=[SubResource(id=public_ip_id)]
            )
        ).result()
        print(good(f"NAT Gateway {nat.id} created successfully."))

        subnet = self._client.subnets.begin_create_or_update(
            self.resource_group, vnet_name, subnet_name,
            Subnet(
                address_prefix=subnet_cidr,
                nat_gateway=SubResource(id=nat.id),
                delegations=[Delegation(
                    name='containerInstanceDelegation',
                    service_name='Microsoft.ContainerInstance/containerGroups'
                )]
            )
        ).result()
        print(good(f"Subnet {subnet.id} created successfully."))
        return subnet

    def delete_stack(self, public_ip_name, vnet_name, subnet_name):
        """
        Delete in order: NAT GW -> Subnet -> VNet -> Public IP.
        (Requires that no container groups are using the subnet).
        """
        # Subnet
        try:
            print(good(f"Deleting Subnet: {subnet_name}..."))
            self._client.subnets.begin_delete(
                self.resource_group, vnet_name, subnet_name
            ).result()
            print(good(f"Subnet {subnet_name} deleted successfully."))
        except Exception as e:
            print(good(f"Subnet {subnet_name} not found or already deleted."))
        

        # NAT Gateway
        nat_gw_name = f'{subnet_name}-nat-gw'
        try:
            print(good(f"Deleting NAT Gateway: {nat_gw_name}..."))
            self._client.nat_gateways.begin_delete(
                self.resource_group, nat_gw_name
            ).result()
            print(good(f"NAT Gateway {nat_gw_name} deleted successfully."))
        except Exception as e:
            print(good(f"NAT Gateway {nat_gw_name} not found or already deleted."))
        
        # VNet
        try:
            print(good(f"Deleting Virtual Network: {vnet_name}..."))
            self._client.virtual_networks.begin_delete(
                self.resource_group, vnet_name
            ).result()
            print(good(f"Virtual Network {vnet_name} deleted successfully."))
        except Exception as e:
            print(good(f"Virtual Network {vnet_name} not found or already deleted."))
        
        # Public IP
        try:
            print(good(f"Deleting Public IP: {public_ip_name}..."))
            self._client.public_ip_addresses.begin_delete(
                self.resource_group, public_ip_name
            ).result()
            print(good(f"Public IP {public_ip_name} deleted successfully."))
        except Exception as e:
            print(good(f"Public IP {public_ip_name} not found or already deleted."))
        
        return True

    def get_public_ip(self, name):
        """
        Get public IP resource by name.
        
        Args:
            name (str): Name of the public IP resource
        
        Returns:
            PublicIPAddress: Azure public IP resource object
            
        Raises:
            ResourceNotFoundError: If public IP doesn't exist
        """
        return self._client.public_ip_addresses.get(
            self.resource_group, name
        )

    def delete_public_ip_only(self, public_ip_name):
        """
        Delete only the public IP without deleting NAT Gateway stack.
        Used for standalone IPs (has_nat_stack=false).
        
        Args:
            public_ip_name (str): Name of the public IP to delete
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            print(good(f"Deleting Public IP: {public_ip_name}..."))
            self._client.public_ip_addresses.begin_delete(
                self.resource_group, public_ip_name
            ).result()
            print(good(f"Public IP {public_ip_name} deleted successfully."))
            return True
        except Exception as e:
            print(good(f"Public IP {public_ip_name} not found or already deleted: {e}"))
            return False

