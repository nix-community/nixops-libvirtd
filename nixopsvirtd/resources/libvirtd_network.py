# -*- coding: utf-8 -*-

# Automatic provisioning of Libvirt Virtual Networks.

import os
import ipaddress
import libvirt
from nixops.util import attr_property, logged_exec
from nixops.resources import ResourceDefinition, ResourceState
from nixopsvirtd.backends.libvirtd import LibvirtdDefinition, LibvirtdState

class LibvirtdNetworkDefinition(ResourceDefinition):
    """Definition of the Libvirtd Network"""

    @classmethod
    def get_type(cls):
        return "libvirtd-network"

    @classmethod
    def get_resource_type(cls):
        return "libvirtdNetworks"

    def __init__(self, xml):
        ResourceDefinition.__init__(self, xml)
        self.network_type = xml.find("attrs/attr[@name='type']/string").get("value")
        self.network_cidr = xml.find("attrs/attr[@name='cidrBlock']/string").get("value")

        self.static_ips = { x.find("attr[@name='machine']/string").get("value"):
                            x.find("attr[@name='address']/string").get("value") for x in xml.findall("attrs/attr[@name='staticIPs']/list/attrs") }
        self.static_ips.update({
            x.find("string").get("value"): x.get("name")
            for x in xml.findall("attrs/attr[@name='staticIPs']/attrs/attr")
        })

        self.uri = xml.find("attrs/attr[@name='URI']/string").get("value")

    def show_type(self):
        return "{0} [{1} {2}]".format(self.get_type(), self.network_type, self.network_cidr)

class LibvirtdNetworkState(ResourceState):
    """State of the Libvirtd Network"""

    network_name  = attr_property("libvirtd.network_name", None)
    network_type  = attr_property("libvirtd.network_type", None)
    network_cidr  = attr_property("libvirtd.network_cidr", None)
    static_ips    = attr_property("libvirtd.static_ips", {}, "json")

    uri = attr_property("libvirtd.URI", "qemu:///system")

    @classmethod
    def get_type(cls):
        return "libvirtd-network"

    def __init__(self, depl, name, id):
        ResourceState.__init__(self, depl, name, id)
        self._conn = None
        self._net = None

    def show_type(self):
        s = super(LibvirtdNetworkState, self).show_type()
        if self.state == self.UP: s = "{0} [{1}]".format(s, self.network_type)
        return s

    @property
    def resource_id(self):
        return self.network_name

    @property
    def public_ipv4(self):
        return self.network_cidr if self.state == self.UP else None;

    nix_name = "libvirtdNetworks"

    @property
    def full_name(self):
        return "Libvirtd network '{}'".format(self.name)

    @property
    def conn(self):
        if self._conn is None:
            self.logger.log('Connecting to {}...'.format(self.uri))
            try:
                self._conn = libvirt.open(self.uri)
            except libvirt.libvirtError as error:
                self.logger.error(error.get_error_message())
                if error.get_error_code() == libvirt.VIR_ERR_NO_CONNECT:
                    # this error code usually means "no connection driver available for qemu:///..."
                    self.logger.error('make sure qemu-system-x86_64 is installed on the target host')
                raise Exception('Failed to connect to the hypervisor at {}'.format(self.uri))
        return self._conn

    @property
    def net(self):
        if self._net is None:
            try:
                self._net = self.conn.networkLookupByName(self.name)
            except Exception as e:
                self.log("Warning: %s" % e)
        return self._net

    def create(self, defn, check, allow_reboot, allow_recreate):
        assert isinstance(defn, LibvirtdNetworkDefinition)

        if check: self.check()

        subnet = ipaddress.ip_network(unicode(defn.network_cidr), strict=False)

        if self.state != self.UP:
            self.log("creating {}...".format(self.full_name))
            self.network_type = defn.network_type
            self.network_cidr = defn.network_cidr
            self.static_ips   = defn.static_ips
            self.uri          = defn.uri

            self._net = self.conn.networkDefineXML('''
              <network>
                <name>{name}</name>
                {maybeForward}
                <ip address="{gateway}" netmask="{netmask}">
                  <dhcp>
                    <range start="{lowerip}" end="{upperip}"/>
                    {dhcpHosts}
                  </dhcp>
                </ip>
              </network>
            '''.format(
                name=self.name,
                maybeForward='<forward mode="nat"/>' if defn.network_type == "nat" else "",
                gateway=subnet[1],
                netmask=subnet.netmask,
                lowerip=subnet[2],
                upperip=subnet[-2],
                dhcpHosts="".join("<host name='{name}' ip='{ip}'/>".format(
                    name=machine,
                    ip=address,
                ) for machine, address in defn.static_ips.iteritems())
            ))

            self.net.create()
            self.net.setAutostart(1)
            self.network_name = self.net.bridgeName()
            self.state = self.UP
            return

        if self._need_update(defn, allow_reboot, allow_recreate):
            self.log("updating {}...".format(self.full_name))

            if self.network_type != defn.network_type:
                self.conn.networkUpdate(
                    libvirt.VIR_NETWORK_UPDATE_COMMAND_ADD if defn.network_type == "nat" else libvirt.VIR_NETWORK_UPDATE_COMMAND_DELETE,
                    libvirt.VIR_NETWORK_SECTION_FORWARD,
                    -1,
                    '<forward mode="nat"/>'
                )
                self.network_type = defn.network_type

            if self.static_ips != defn.static_ips:
                # Remove obsolete
                for machine, address in self.static_ips.iteritems():
                    if not defn.static_ips.get(machine):
                        self.net.update(
                            libvirt.VIR_NETWORK_UPDATE_COMMAND_DELETE,
                            libvirt.VIR_NETWORK_SECTION_IP_DHCP_HOST,
                            -1,
                            "<host name='{name}' ip='{ip}'/>".format(
                                name=machine,
                                ip=address,
                            )
                        )

                # Add or update existings
                for machine, address in defn.static_ips.iteritems():
                    mstate = self.depl.resources.get(machine)
                    mdefn  = self.depl.definitions.get(machine)
                    if isinstance(mstate, LibvirtdState) and isinstance(mdefn, LibvirtdDefinition):
                        for net in mdefn.config["libvirtd"]["networks"]:
                            if net == defn.name or (net.get("_name", net.get("name")) == defn.name and net.get("type") == defn.network_type):
                                try:
                                    if ipaddress.ip_address(unicode(address)) not in subnet:
                                        raise Exception("cannot assign a static IP out of the network CIDR")
                                    self.net.update(
                                        libvirt.VIR_NETWORK_UPDATE_COMMAND_MODIFY if self.static_ips.get(machine) else libvirt.VIR_NETWORK_UPDATE_COMMAND_ADD_LAST,
                                        libvirt.VIR_NETWORK_SECTION_IP_DHCP_HOST,
                                        -1,
                                        "<host name='{name}' ip='{ip}'/>".format(
                                            name=machine,
                                            ip=address,
                                        )
                                    )
                                except Exception as e:
                                    print(e)
                                    self.warn("Cannot assign static IP '{0}' to machine '{1}' in subnet '{2}'".format(address, machine, defn.network_cidr))
                        break;
                    else:
                        self.warn("Cannot assign static IP '{0}' to non-attached machine '{1}'".format(address, machine))
                else:
                    self.warn("Cannot assign static IP '{0}' to non-existent machine '{1}'".format(address, machine))

                self.static_ips = defn.static_ips

    def _need_update(self, defn, allow_reboot, allow_recreate):
        if self.uri != defn.uri:
            self.warn("Change of the connection URI from {0} to {1} is not supported; skipping".format(self.uri, defn.uri))
            return False

        if self.network_cidr != defn.network_cidr:
            self.warn("Change of the network CIDR from {0} to {1} is not supported; skipping".format(self.network_cidr, defn.network_cidr))
            return False

        if self.network_type == defn.network_type and self.static_ips == defn.static_ips: # no changes
            return False

        if self.network_type != defn.network_type and not allow_reboot:
            self.warn("change of the network type requires reboot; skipping")
            return False

        # checkme: the state of the attached machine should also be considered
        if any(defn.static_ips.get(machine) != address for machine, address in self.static_ips.iteritems()) and not allow_reboot:
            self.warn("change of existing bindings for static IPs requires reboot; skipping")
            return False

        return True

    def destroy(self, wipe=False):
        if self.state != self.UP or not self.net: return True
        if not self.depl.logger.confirm("are you sure you want to destroy {}?".format(self.full_name)):
            return False

        self.log("destroying {}...".format(self.full_name))

        self.net.destroy()
        self.net.undefine()

        return True

    def _check(self):
        if self.net:
            if self.network_name != self.net.bridgeName():
               self.network_name = self.net.bridgeName()
            return super(LibvirtdNetworkState, self)._check()

        with self.depl._db:
            self.network_name = None
            self.state = self.MISSING

        return False
