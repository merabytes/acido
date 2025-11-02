from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import Delegation, VirtualNetwork, Subnet, NetworkProfile, PublicIPAddressSku, NatGatewaySku, SubResource, NatGateway
from acido.azure_utils.ManagedIdentity import ManagedIdentity
from huepy import good, bad, info, bold, green, red, orange

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

    def delete_resources(self, create_ip):
        # Construct the names based on create_ip
        network_profile_name = f"{create_ip}-network-profile"
        cnic_name = f"{create_ip}-cnic"
        ip_config_name = f"{create_ip}-ip-config"
        
        # Delete Network Profile
        delete_network_profile_operation = self._client.network_profiles.begin_delete(
            self.resource_group,
            network_profile_name
        )
        delete_network_profile_result = delete_network_profile_operation.result()
        
        # Logic to delete CNIC and IP config can be added if they are separate resources.
        # In this case, deleting the network profile might already delete associated CNIC and IP configurations.

        return delete_network_profile_result  # Return the result or any necessary information
    
    def get_network_profile(self, resource_name: str) -> NetworkProfile:
        # Construct the network profile name based on create_ip
        network_profile_name = f"{resource_name}-network-profile"
        
        # Get the network profile
        try:
            network_profile = self._client.network_profiles.get(
                self.resource_group,
                network_profile_name
            )
            return network_profile
        except Exception as e:
            print(f"Failed to get network profile: {e}")
            return None
    
    def create_ipv4(self, public_ip_name):
        public_ip_params = {
            'location': 'westeurope',  # Modify this to your preferred location
            'public_ip_allocation_method': 'Static',
            'public_ip_address_version': 'IPv4',
            'sku': PublicIPAddressSku(name='Standard', tier="Regional")
        }
        async_creation = self._client.public_ip_addresses.begin_create_or_update(
            self.resource_group,
            public_ip_name,
            public_ip_params
        )
        public_ip_address = async_creation.result()
        print(good(f"Public IP Address {public_ip_address.id} created successfully."))
        return public_ip_address.id

    def list_ipv4(self):
        ip_addresses_list = self._client.public_ip_addresses.list(self.resource_group)

        ip_addresses_info = [
            {
                'id': ip.id,
                'name': ip.name,
                'ip_address': ip.ip_address,
                'location': ip.location
            }
            for ip in ip_addresses_list
        ]

        return ip_addresses_info
    
    def create_virtual_network(self, vnet_name):
        vnet_params = VirtualNetwork(
            location=self.location,  # Assume `self.location` contains the Azure region
            address_space={
                "address_prefixes": ["10.0.0.0/16"]  # Adjust as needed
            }
        )
        creation_result = self._client.virtual_networks.begin_create_or_update(
            self.resource_group,
            vnet_name,
            vnet_params
        ).result()
        print(good(f"Virtual Network {creation_result.id} created successfully."))
        return creation_result

    def create_subnet(self, vnet_name, subnet_name, ip_address):
        nat_gateway_params = NatGateway(
            sku=NatGatewaySku(name="Standard"),
            location=self.location,  # or your Azure region
            public_ip_addresses=[SubResource(id=ip_address)]
        )
        nat_gateway = self._client.nat_gateways.begin_create_or_update(
            resource_group_name=self.resource_group,
            nat_gateway_name=f'{subnet_name}-nat-gw',
            parameters=nat_gateway_params
        ).result()
        print(good(f"NAT Gateway {nat_gateway.id} created successfully."))
        subnet_params = Subnet(
            address_prefix="10.0.0.0/24", # Adjust as needed
            nat_gateway=nat_gateway,
            delegations=[
                Delegation(
                    name='containerInstanceDelegation',
                    service_name='Microsoft.ContainerInstance/containerGroups'
                )
            ]
        )
        creation_result = self._client.subnets.begin_create_or_update(
            self.resource_group,
            vnet_name,
            subnet_name,
            subnet_params
        ).result()
        print(good(f"Subnet {creation_result.id} created successfully."))
        return creation_result

    def create_network_profile(self, network_profile_name, network_profile_params):
        creation_result = self._client.network_profiles.create_or_update(
            self.resource_group,
            network_profile_name,
            network_profile_params
        )
        return creation_result

