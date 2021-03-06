from spaceone.core.manager import BaseManager
from spaceone.inventory.model.vnet import VNet
from spaceone.inventory.model.subnet import Subnet
from spaceone.inventory.connector.azure_vm_connector import AzureVMConnector


class AzureVNetManager(BaseManager):

    def __init__(self, params, azure_vm_connector=None, **kwargs):
        super().__init__(**kwargs)
        self.params = params
        self.azure_vm_connector: AzureVMConnector = azure_vm_connector

    def get_vnet_subnet_info(self, nic_name, network_interfaces, virtual_networks):
        '''
        vnet_subnet_data = {
            "vnet_data": vnet_data,
            "subnet_data": subnet_data
        }
        '''

        for nic in network_interfaces:
            if nic.name == nic_name:
                vnet_name = nic.ip_configurations[0].subnet.id.split('/')[-3]
                break

        for vnet in virtual_networks:
            if vnet.name == vnet_name:
                return self.get_vnet_info(vnet), self.get_subnet_info(vnet.subnets[0])

        return None

    @staticmethod
    def get_vnet_info(vnet):
        '''
        vnet_data = {
            "vnet_id" = "",
            "vnet_name" = "",
            "cidr" = ""
        }
        '''

        vnet_data = {
            'vnet_id': vnet.id,
            'vnet_name': vnet.name,
            'cidr': vnet.address_space.address_prefixes[0]
        }

        return VNet(vnet_data, strict=False)

    @staticmethod
    def get_subnet_info(subnet):
        '''
        subnet_data = {
            "subnet_name": "",
            "subnet_id": "",
            "cidr": ""
        }
        '''

        subnet_data = {
            'subnet_name': subnet.name,
            'subnet_id': subnet.id,
            'cidr': subnet.address_prefix
        }

        return Subnet(subnet_data, strict=False)
