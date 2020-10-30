import pprint

from spaceone.core.manager import BaseManager
from spaceone.inventory.model.compute import Compute
from spaceone.inventory.model.azure import Azure
from spaceone.inventory.model.os import OS
from spaceone.inventory.model.hardware import Hardware
from spaceone.inventory.model.subscription import Subscription
from spaceone.inventory.model.resource_group import ResourceGroup
from spaceone.inventory.connector.azure_vm_connector import AzureVMConnector


class AzureVmManager(BaseManager):

    def __init__(self, params, azure_vm_connector=None, **kwargs):
        super().__init__(**kwargs)
        self.params = params
        self.azure_vm_connector: AzureVMConnector = azure_vm_connector

    def list_vms(self, resource_group_name):
        return self.azure_vm_connector.list_vms(resource_group_name)

    def get_vm_info(self, vm, resource_group, subscription, network_security_groups, vm_sizes):
        '''
        server_data = {
            "os_type": "LINUX" | "WINDOWS"
            "name": ""
            "ip_addresses": [],
            "primary_ip_address": "",
            "data":  {
                "os": {
                    "os_distro": "",
                    "os_arch": "",
                    "os_details": ""
                },
                "azure": {
                    "boot_diagnostics": "true" | "false",
                    "ultra_ssd_enabled": "true" | "false",
                    "write_accelerator_enabled": "true" | "false",
                    "priority": "Regular" | "Low" | "Spot",
                    "tags": {
                        "Key": "",
                        "Value": ""
                    },
                },
                "hardware": {
                    "core": 0,
                    "memory": 0
                },
                "compute": {
                    "keypair": "",
                    "availability_zone": "",
                    "instance_state": "",
                    "instance_type": "",
                    "launched_at": "datetime",
                    "instance_id": "",
                    "instance_name": "",
                    "security_groups": [
                        {
                            "id": "",
                            "name": "",
                            "display": ""
                        },
                        ...
                    ],
                    "image": "",
                    "account": "",
                    "tags": {
                        "id": ""
                    }
                },
            }
        }
        '''

        resource_group_name = resource_group.name

        vm_dic = self.get_vm_dic(vm)
        os_data = self.get_os_data(vm.storage_profile)
        hardware_data = self.get_hardware_data(vm, vm_sizes)
        azure_data = self.get_azure_data(vm)
        compute_data = self.get_compute_data(vm, resource_group_name, network_security_groups,
                                             subscription)
        resource_group_data = self.get_resource_group_data(resource_group)

        vm_dic.update({
            'data': {
                'os': os_data,
                'hardware': hardware_data,
                'azure': azure_data,
                'compute': compute_data,
                'resource_group': resource_group_data,
            }
        })

        return vm_dic

    def get_vm_dic(self, vm):
        vm_data = {
            'name': vm.name,
            'os_type': self.get_os_type(vm.storage_profile.os_disk),
            'region_code': vm.location
        }
        return vm_data

    def get_os_data(self, vm_storage_profile):
        os_data = {
            'os_distro': self.get_os_distro(self.get_os_type(vm_storage_profile.os_disk),
                                            vm_storage_profile.image_reference.offer),
            'os_details': self.get_os_details(vm_storage_profile.image_reference)
        }
        return OS(os_data, strict=False)

    def get_hardware_data(self, vm, vm_sizes):
        """
        vm_sizes = [
            {
                'location': 'koreacentral',
                'list_sizes': []
            },
        ]
        """
        # caching location info by vm_sizes
        location = vm.location
        size = vm.hardware_profile.vm_size

        if vm_sizes:
            for vm_size in vm_sizes:
                if vm_size.get('location') == location:
                    hardware_data = self.get_vm_hardware_info(vm_size.get('list_sizes'), size)
                    return Hardware(hardware_data, strict=False)

        new_vm_size = {}
        new_vm_size.update({
            'location': location,
            'list_sizes': list(self.azure_vm_connector.list_virtual_machine_sizes(location))
        })

        vm_sizes.append(new_vm_size)
        hardware_data = self.get_vm_hardware_info(new_vm_size.get('list_sizes'), size)

        return Hardware(hardware_data, strict=False)

    def get_compute_data(self, vm, resource_group_name, network_security_groups, subscription_id):
        vm_info = self.azure_vm_connector.get_vm(resource_group_name, vm.name)
        compute_data = {
            'instance_state': self.get_instance_state(vm_info.instance_view.statuses),
            'instance_type': vm.hardware_profile.vm_size,
            'launched_at': self.get_launched_time(vm_info.instance_view.statuses),
            'instance_id': vm.vm_id,
            'instance_name': vm.name,
            'security_groups': self.get_security_groups(vm.network_profile.network_interfaces, network_security_groups),
            'image': self.get_image_detail(vm.location, vm.storage_profile.image_reference, subscription_id),
            'tags': {
                'id': vm.id
            }
        }
        if vm.zones:
            compute_data.update({
                'az': f'{vm.location}-{vm.zones[0]}'
            })

        else:
            compute_data.update({
                'az': vm.location
            })

        # pprint.pprint(compute_data)

        return Compute(compute_data, strict=False)

    def get_azure_data(self, vm):
        azure_data = {
            'boot_diagnostics': vm.diagnostics_profile.boot_diagnostics.enabled,
            'ultra_ssd_enabled': self.get_ultra_ssd_enabled(vm.additional_capabilities),
            'write_accelerator_enabled': vm.storage_profile.os_disk.write_accelerator_enabled,
            'priority': vm.priority,
            'tags': self.get_tags(vm.tags)
        }
        return Azure(azure_data, strict=False)

    def get_vm_size(self, location):
        return self.azure_vm_connector.list_virtual_machine_sizes(location)

    def get_os_distro(self, os_type, offer):
        if offer:
            return self.extract_os_distro(os_type, offer.lower())
        else:
            return os_type.lower()

    @staticmethod
    def get_vm_hardware_info(list_sizes, size):
        result = {}
        for list_size in list_sizes:
            if list_size.name == size:
                result.update({
                    'core': list_size.number_of_cores,
                    'memory': round(float(list_size.memory_in_mb / 1074), 2)
                })
                break

        return result

    @staticmethod
    def get_security_groups(vm_network_interfaces, network_security_groups):
        security_groups = []
        nic_names = []
        for vm_nic in vm_network_interfaces:
            nic_name = vm_nic.id.split('/')[-1]
            nic_names.append(nic_name)

        for nsg in network_security_groups:
            network_interfaces = nsg.network_interfaces
            if network_interfaces:
                for nic in network_interfaces:
                    nic_name2 = nic.id.split('/')[-1]
                    for nic_name in nic_names:
                        if nic_name == nic_name2:
                            nsg_data = {
                                'display': f'{nsg.name} ({nsg.id})',
                                'id': nsg.id,
                                'name': nsg.name
                            }
                            security_groups.append(nsg_data)
                            break
                    break
        if len(security_groups) > 0:
            return security_groups
        return None

    @staticmethod
    def get_launched_time(statuses):
        for status in statuses:
            if status.display_status == 'Provisioning succeeded':
                return status.time.isoformat()

        return None

    @staticmethod
    def get_instance_state(statuses):
        if statuses:
            return statuses[-1].display_status.split(' ')[-1].upper()

        return None

    @staticmethod
    def get_resource_group_data(resource_group):
        resource_group_data = {
            'resource_group_name': resource_group.name,
            'resource_group_id': resource_group.id
        }
        return ResourceGroup(resource_group_data, strict=False)

    @staticmethod
    def get_ultra_ssd_enabled(additional_capabilities):
        if additional_capabilities:
            return additional_capabilities.ultra_ssd_enabled
        else:
            return False

    @staticmethod
    def get_os_type(os_disk):
        return os_disk.os_type.upper()

    @staticmethod
    def extract_os_distro(os_type, offer):
        if os_type == 'LINUX':
            os_map = {
                'suse': 'suse',
                'rhel': 'redhat',
                'centos': 'centos',
                'cent': 'centos',
                'fedora': 'fedora',
                'ubuntu': 'ubuntu',
                'ubuntuserver': 'ubuntu',
                'oracle': 'oraclelinux',
                'oraclelinux': 'oraclelinux',
                'debian': 'debian'
            }

            offer.lower()
            for key in os_map:
                if key in offer:
                    return os_map[key]

            return 'linux'

        elif os_type == 'WINDOWS':
            os_distro_string = None
            offer_splits = offer.split('-')

            version_cmps = ['2016', '2019', '2012']

            for cmp in version_cmps:
                if cmp in offer_splits:
                    os_distro_string = f'win{cmp}'

            if os_distro_string is not None and 'R2_RTM' in offer_splits:
                os_distro_string = f'{os_distro_string}r2'

            if os_distro_string is None:
                os_distro_string = 'windows'

            return os_distro_string

    @staticmethod
    def get_os_details(image_reference):
        if image_reference:
            publisher = image_reference.publisher
            offer = image_reference.offer
            sku = image_reference.sku
            if publisher and offer and sku:
                os_details = f'{publisher}, {offer}, {sku}'
                return os_details

        return None

    @staticmethod
    def get_image_detail(location, image_reference, subscription_id):
        publisher = image_reference.publisher
        offer = image_reference.offer
        sku = image_reference.sku
        version = image_reference.exact_version

        if publisher and offer and sku and version:
            image_detail = f'/Subscriptions/{subscription_id}/Providers/Microsoft.Compute/Locations/{location}' \
                       f'/Publishers/{publisher}/ArtifactTypes/VMImage/Offers/{offer}/Skus/{sku}/Versions/{version}'
            return image_detail

        return None

    @staticmethod
    def match_vm_type(vm_size):
        # TODO: find vm_size_list checking method
        pass

    @staticmethod
    def get_tags(tags):
        tags_result = []
        if tags:
            for k, v in tags.items():
                tag_info = {}
                tag_info.update({'key': k})
                tag_info.update({'value': v})
                tags_result.append(tag_info)

        return tags_result