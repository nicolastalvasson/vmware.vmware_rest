#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = """
module: vcenter_vm_hardware_memory
short_description: Handle resource of type vcenter_vm_hardware_memory
description: Handle resource of type vcenter_vm_hardware_memory
options:
  hot_add_enabled:
    description:
    - 'Flag indicating whether adding memory while the virtual machine is running
      should be enabled. '
    - ' Some guest operating systems may consume more resources or perform less efficiently
      when they run on hardware that supports adding memory while the machine is running. '
    - ' This field may only be modified if the virtual machine is not powered on.'
    - If unset, the value is unchanged.
    type: bool
  size_MiB:
    description:
    - 'New memory size in mebibytes. '
    - ' The supported range of memory sizes is constrained by the configured guest
      operating system and virtual hardware version of the virtual machine. '
    - ' If the virtual machine is running, this value may only be changed if Memory.Info.hot-add-enabled
      is true, and the new memory size must satisfy the constraints specified by Memory.Info.hot-add-increment-size-mib
      and Memory.Info.hot-add-limit-mib.'
    - If unset, the value is unchanged.
    type: int
  state:
    choices:
    - present
    default: present
    description: []
    type: str
  vcenter_hostname:
    description:
    - The hostname or IP address of the vSphere vCenter
    - If the value is not specified in the task, the value of environment variable
      C(VMWARE_HOST) will be used instead.
    required: true
    type: str
  vcenter_password:
    description:
    - The vSphere vCenter username
    - If the value is not specified in the task, the value of environment variable
      C(VMWARE_PASSWORD) will be used instead.
    required: true
    type: str
  vcenter_username:
    description:
    - The vSphere vCenter username
    - If the value is not specified in the task, the value of environment variable
      C(VMWARE_USER) will be used instead.
    required: true
    type: str
  vcenter_validate_certs:
    default: true
    description:
    - Allows connection when SSL certificates are not valid. Set to C(false) when
      certificates are not trusted.
    - If the value is not specified in the task, the value of environment variable
      C(VMWARE_VALIDATE_CERTS) will be used instead.
    type: bool
  vm:
    description:
    - Virtual machine identifier.
    - 'The parameter must be an identifier for the resource type: VirtualMachine.'
    type: str
author:
- Goneri Le Bouder (@goneri) <goneri@lebouder.net>
version_added: 1.0.0
requirements:
- python >= 3.6
- aiohttp
"""

EXAMPLES = """
- name: Collect information about a specific VM
  vcenter_vm_info:
    vm: '{{ search_result.value[0].vm }}'
  register: test_vm1_info
- name: Increase the memory of a VM
  vcenter_vm_hardware_memory:
    vm: '{{ test_vm1_info.id }}'
    size_MiB: 1080
"""

# This structure describes the format of the data expected by the end-points
PAYLOAD_FORMAT = {
    "get": {"query": {}, "body": {}, "path": {"vm": "vm"}},
    "update": {
        "query": {},
        "body": {
            "hot_add_enabled": "spec/hot_add_enabled",
            "size_MiB": "spec/size_MiB",
        },
        "path": {"vm": "vm"},
    },
}

import socket
import json
from ansible.module_utils.basic import env_fallback

try:
    from ansible_collections.cloud.common.plugins.module_utils.turbo.module import (
        AnsibleTurboModule as AnsibleModule,
    )
except ImportError:
    from ansible.module_utils.basic import AnsibleModule
from ansible_collections.vmware.vmware_rest.plugins.module_utils.vmware_rest import (
    build_full_device_list,
    exists,
    gen_args,
    get_device_info,
    get_subdevice_type,
    list_devices,
    open_session,
    prepare_payload,
    update_changed_flag,
)


def prepare_argument_spec():
    argument_spec = {
        "vcenter_hostname": dict(
            type="str", required=True, fallback=(env_fallback, ["VMWARE_HOST"]),
        ),
        "vcenter_username": dict(
            type="str", required=True, fallback=(env_fallback, ["VMWARE_USER"]),
        ),
        "vcenter_password": dict(
            type="str",
            required=True,
            no_log=True,
            fallback=(env_fallback, ["VMWARE_PASSWORD"]),
        ),
        "vcenter_validate_certs": dict(
            type="bool",
            required=False,
            default=True,
            fallback=(env_fallback, ["VMWARE_VALIDATE_CERTS"]),
        ),
    }

    argument_spec["hot_add_enabled"] = {"type": "bool"}
    argument_spec["size_MiB"] = {"type": "int"}
    argument_spec["state"] = {
        "type": "str",
        "choices": ["present"],
        "default": "present",
    }
    argument_spec["vm"] = {"type": "str"}

    return argument_spec


async def main():
    module_args = prepare_argument_spec()
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    session = await open_session(
        vcenter_hostname=module.params["vcenter_hostname"],
        vcenter_username=module.params["vcenter_username"],
        vcenter_password=module.params["vcenter_password"],
    )
    result = await entry_point(module, session)
    module.exit_json(**result)


def build_url(params):

    return (
        "https://{vcenter_hostname}" "/rest/vcenter/vm/{vm}/hardware/memory"
    ).format(**params)


async def entry_point(module, session):
    if module.params["state"] == "present":
        if "_create" in globals():
            operation = "create"
        else:
            operation = "update"
    elif module.params["state"] == "absent":
        operation = "delete"
    else:
        operation = module.params["state"]
    func = globals()[("_" + operation)]
    return await func(module.params, session)


async def _update(params, session):
    payload = payload = prepare_payload(params, PAYLOAD_FORMAT["update"])
    _url = "https://{vcenter_hostname}/rest/vcenter/vm/{vm}/hardware/memory".format(
        **params
    )
    async with session.get(_url) as resp:
        _json = await resp.json()
        for (k, v) in _json["value"].items():
            if (k in payload) and (payload[k] == v):
                del payload[k]
            elif "spec" in payload:
                if (k in payload["spec"]) and (payload["spec"][k] == v):
                    del payload["spec"][k]
        try:
            if payload["spec"]["upgrade_version"] and (
                "upgrade_policy" not in payload["spec"]
            ):
                payload["spec"]["upgrade_policy"] = _json["value"]["upgrade_policy"]
        except KeyError:
            pass
        if (payload == {}) or (payload == {"spec": {}}):
            _json["id"] = params.get("None")
            return await update_changed_flag(_json, resp.status, "get")
    async with session.patch(_url, json=payload) as resp:
        try:
            if resp.headers["Content-Type"] == "application/json":
                _json = await resp.json()
        except KeyError:
            _json = {}
        _json["id"] = params.get("None")
        return await update_changed_flag(_json, resp.status, "update")


if __name__ == "__main__":
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
