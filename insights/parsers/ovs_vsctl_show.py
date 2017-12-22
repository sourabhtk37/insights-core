"""
OVSvsctlshow - command ``/usr/bin/ovs-vsctl show``
==================================================

This class parses the output of the ``/usr/bin/ovs-vsctl show`` command.  The
output looks like::

    aa3f16d3-9534-4b74-8e9e-8b0ce94038c5
        Bridge br-int
            fail_mode: secure
            Port br-int
                Interface br-int
                    type: internal
            Port int-br-ctlplane
                Interface int-br-ctlplane
                type: patch
                options: {peer=phy-br-ctlplane}
            Port "tap293d29ec-d1"
                tag: 1
                Interface "tap293d29ec-d1"
                    type: internal
        Bridge br-tun
            fail_mode: secure
            Port "vxlan-aca80118"
                Interface "vxlan-aca80118"
                    type: vxlan
                    options: {df_default="true", in_key=flow, local_ip="172.168.1.26", out_key=flow, remote_ip="172.168.1.24"}
            Port "vxlan-aca80119"
                Interface "vxlan-aca80119"
                    type: vxlan
                    options: {df_default="true", in_key=flow, local_ip="172.168.1.26", out_key=flow, remote_ip="172.168.1.25"}
    ovs_version: "2.3.2"

Examples:
    >>> ovs = shared[OVSvsctlshow]
    >>> ovs.get_ovs_version()
    '2.3.2'
    >>> ovs.get_bridge('br-int')['fail_mode']
    'secure'
    >>> br_tun = ovs.get_bridge('br-tun')
    >>> br_tun['fail_mode']
    'secure'
    >>> len(br_tun['ports'])
    2
    >>> ports = br_tun['ports']
    >>> ports[0]['interface']
    'vxlan-aca80118'
    >>> ports[0]['type']
    'vxlan'
    >>> options = ports[0]['options']
    >>> options['df_default']  # Note no type conversion on this
    'true'
    >>> options['local_ip']
    '172.168.1.26'
    >>> options['out_key']
    'flow'

"""
from .. import Parser, parser
from ..parsers import optlist_to_dict


@parser("ovs-vsctl_show")
class OVSvsctlshow(Parser):
    """
    Parse the ``ovs-vsctl show`` output into a dictionary.
    """

    def parse_content(self, content):
        if len(content) < 3:
            return
        version_line = content[-1]
        self.data = {"uuid": content[0], "bridges": {}, "ovs_version": version_line.split('"')[1]}
        bridge_dict = {}
        port_dict = {}
        for line in content[1:-1]:
            prefix, value = line.strip().split(None, 1)
            if prefix == "Bridge":
                bridge_dict = {"ports": []}
                self.data["bridges"][value] = bridge_dict
            elif prefix == "fail_mode:":
                bridge_dict["fail_mode"] = value
            elif prefix == "Port":
                port_dict = {"port": value.replace('"', "")}
                bridge_dict["ports"].append(port_dict)
            elif prefix in ("tag:", "type:"):
                port_dict[prefix[:-1]] = value
            elif prefix == "Interface":
                port_dict["interface"] = value.replace('"', "")
            elif prefix == "options:":
                port_dict["options"] = optlist_to_dict(
                    value[1:-1], opt_sep=', ', strip_quotes=True
                )

    def get_ovs_version(self):
        return self.data.get("ovs_version")

    def get_bridge(self, bridge_name):
        return self.data["bridges"].get(bridge_name, None)
