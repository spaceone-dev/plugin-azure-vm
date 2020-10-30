from spaceone.core.manager import BaseManager
from spaceone.inventory.model.nic import NIC, NICTags
from spaceone.inventory.connector.azure_vm_connector import AzureVMConnector

import pprint


class AzureNICManager(BaseManager):

    def __init__(self, params, azure_vm_connector=None, **kwargs):
        super().__init__(**kwargs)
        self.params = params
        self.azure_vm_connector: AzureVMConnector = azure_vm_connector

    def get_nic_info(self, vm, network_interfaces, public_ip_addresses, virtual_networks):
        '''
        nic_data = {
            "device_index": 0,
            "device": "",
            "nic_type": "",
            "ip_addresses": [],
            "cidr": "",
            "mac_address": "",
            "public_ip_address": "",
            "tags": {
                "nic_id": ""
            }
        }
        '''

        nic_data = []
        index = 0

        vm_network_interfaces = vm.network_profile.network_interfaces
        match_network_interfaces = self.get_network_interfaces(vm_network_interfaces, network_interfaces)

        for vm_nic in match_network_interfaces:
            network_data = {
                'device_index': index,
                'cidr': self.get_nic_cidr(self.get_ip_configurations(vm_nic), virtual_networks),
                'ip_addresses': self.get_nic_ip_addresses(self.get_ip_configurations(vm_nic)),
                'mac_address': vm_nic.mac_address,
                'public_ip_address': self.get_nic_public_ip_addresses(self.get_ip_configurations(vm_nic),
                                                                      public_ip_addresses),
                'tags': self.get_tags(vm_nic)
            }

            # pprint.pprint(network_data)
            index += 1
            nic_data.append(NIC(network_data, strict=False))

        return nic_data

    @staticmethod
    def get_nic_public_ip_addresses(ip_configurations, public_ip_addresses):
        for ip_conf in ip_configurations:
            if ip_conf.public_ip_address:
                ip_name = ip_conf.public_ip_address.id.split('/')[-1]
                for pub_ip in public_ip_addresses:
                    if ip_name == pub_ip.name:
                        return pub_ip.ip_address

        return None

    @staticmethod
    def get_nic_cidr(ip_configurations, virtual_networks):
        if ip_configurations:
            subnet_name = ip_configurations[0].subnet.id.split('/')[-1]
            for vnet in virtual_networks:
                for subnet in vnet.subnets:
                    if subnet_name == subnet.name:
                        return subnet.address_prefix

        return None

    @staticmethod
    def get_nic_ip_addresses(ip_configurations):
        ip_addresses = []
        for ip_conf in ip_configurations:
            ip_addresses.append(ip_conf.private_ip_address)

        if ip_addresses:
            return ip_addresses

        return None

    @staticmethod
    def get_ip_configurations(vm_nic):
        result = []
        for ip in vm_nic.ip_configurations:
            result.append(ip)

        return result

    @staticmethod
    def get_tags(vm_nic):
        tag_info = {}
        tag_info.update({'name': vm_nic.name})
        tag_info.update({'etag': vm_nic.etag})
        tag_info.update({'enable_accelerated_networking': vm_nic.enable_accelerated_networking})
        tag_info.update({'enable_ip_forwarding': vm_nic.enable_ip_forwarding})

        return tag_info

    @staticmethod
    def get_network_interfaces(vm_network_interfaces, network_interfaces):
        result = []
        for vm_nic in vm_network_interfaces:
            for nic in network_interfaces:
                if vm_nic.id.split('/')[-1] == nic.name:
                    result.append(nic)
                    break

        return result