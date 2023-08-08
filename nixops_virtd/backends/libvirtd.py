# -*- coding: utf-8 -*-

import copy
import json
import os
import random
import time
from xml.etree import ElementTree

# No type stubs for libvirt
import libvirt  # type: ignore

import nixops.known_hosts
import nixops.util


# to prevent libvirt errors from appearing on screen, see
# https://www.redhat.com/archives/libvirt-users/2017-August/msg00011.html


from nixops.evaluation import eval_network
from nixops.resources import ResourceOptions
from nixops.backends import MachineOptions, MachineDefinition, MachineState
from nixops.plugins.manager import PluginManager
from typing import Optional
from typing import Sequence


class LibvirtdOptions(ResourceOptions):
    URI: str
    baseImage: Optional[str]
    baseImageSize: int
    cmdline: str
    domainType: str
    extraDevicesXML: str
    extraDomainXML: str
    headless: bool
    initrd: str
    kernel: str
    memorySize: int
    networks: Sequence[str]
    storagePool: str
    vcpu: int


class LibvirtMachineOptions(MachineOptions):
    libvirtd: LibvirtdOptions


class LibvirtdDefinition(MachineDefinition):
    """Definition of a trivial machine."""

    config: LibvirtMachineOptions

    @classmethod
    def get_type(cls):
        return "libvirtd"

    def __init__(self, name, config):
        super().__init__(name, config)
        self.vcpu = self.config.libvirtd.vcpu
        self.memory_size = self.config.libvirtd.memorySize
        self.extra_devices = self.config.libvirtd.extraDevicesXML
        self.extra_domain = self.config.libvirtd.extraDomainXML
        self.headless = self.config.libvirtd.headless
        self.domain_type = self.config.libvirtd.domainType
        self.kernel = self.config.libvirtd.kernel
        self.initrd = self.config.libvirtd.initrd
        self.cmdline = self.config.libvirtd.cmdline
        self.storage_pool_name = self.config.libvirtd.storagePool
        self.uri = self.config.libvirtd.URI

        self.networks = list(self.config.libvirtd.networks)
        assert len(self.networks) > 0


class LibvirtdState(MachineState[LibvirtdDefinition]):
    private_ipv4 = nixops.util.attr_property("privateIpv4", None)
    client_public_key = nixops.util.attr_property("libvirtd.clientPublicKey", None)
    client_private_key = nixops.util.attr_property("libvirtd.clientPrivateKey", None)
    primary_net = nixops.util.attr_property("libvirtd.primaryNet", None)
    primary_mac = nixops.util.attr_property("libvirtd.primaryMAC", None)
    domain_xml = nixops.util.attr_property("libvirtd.domainXML", None)
    disk_path = nixops.util.attr_property("libvirtd.diskPath", None)
    storage_volume_name = nixops.util.attr_property("libvirtd.storageVolume", None)
    storage_pool_name = nixops.util.attr_property("libvirtd.storagePool", None)
    vcpu = nixops.util.attr_property("libvirtd.vcpu", None)

    # older deployments may not have a libvirtd.URI attribute in the state file
    # using qemu:///system in such case
    uri = nixops.util.attr_property("libvirtd.URI", "qemu:///system")

    @classmethod
    def get_type(cls):
        return "libvirtd"

    def __init__(self, depl, name, id):
        MachineState.__init__(self, depl, name, id)
        self._conn = None
        self._dom = None
        self._pool = None
        self._vol = None

    @property
    def conn(self):
        if self._conn is None:
            self.logger.log("Connecting to {}...".format(self.uri))
            try:
                self._conn = libvirt.open(self.uri)
            except libvirt.libvirtError as error:
                self.logger.error(error.get_error_message())
                if error.get_error_code() == libvirt.VIR_ERR_NO_CONNECT:
                    # this error code usually means "no connection driver available for qemu:///..."
                    self.logger.error(
                        "make sure qemu-system-x86_64 is installed on the target host"
                    )
                raise Exception(
                    "Failed to connect to the hypervisor at {}".format(self.uri)
                )
        return self._conn

    @property
    def dom(self):
        if self._dom is None:
            try:
                self._dom = self.conn.lookupByName(self._vm_id())
            except Exception as e:
                self.log("Warning: %s" % e)
        return self._dom

    @property
    def pool(self):
        if self._pool is None:
            self._pool = self.conn.storagePoolLookupByName(self.storage_pool_name)
        return self._pool

    @property
    def vol(self):
        if self._vol is None:
            self._vol = self.pool.storageVolLookupByName(self.storage_volume_name)
        return self._vol

    def get_console_output(self):
        import sys

        return self._logged_exec(
            ["virsh", "-c", self.uri, "console", self.vm_id.decode()], stdin=sys.stdin
        )

    def get_ssh_private_key_file(self):
        return self._ssh_private_key_file or self.write_ssh_private_key(
            self.client_private_key
        )

    def get_ssh_flags(self, *args, **kwargs):
        super_flags = super(LibvirtdState, self).get_ssh_flags(*args, **kwargs)
        return super_flags + [
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-i",
            self.get_ssh_private_key_file(),
        ]

    def get_physical_spec(self):
        return {
            ("users", "extraUsers", "root", "openssh", "authorizedKeys", "keys"): [
                self.client_public_key
            ]
        }

    def address_to(self, m):
        if isinstance(m, LibvirtdState):
            return m.private_ipv4
        return MachineState.address_to(self, m)

    def _vm_id(self):
        return "nixops-{0}-{1}".format(self.depl.uuid, self.name)

    def _generate_primary_mac(self):
        mac = [
            0x52,
            0x54,
            0x00,
            random.randint(0x00, 0x7F),
            random.randint(0x00, 0xFF),
            random.randint(0x00, 0xFF),
        ]
        self.primary_mac = ":".join(["%02x" % x for x in mac])

    def create(self, defn, check, allow_reboot, allow_recreate):
        assert isinstance(defn, LibvirtdDefinition)
        self.set_common_state(defn)
        self.primary_net = defn.networks[0]
        self.storage_pool_name = defn.storage_pool_name
        self.uri = defn.uri

        # required for virConnectGetDomainCapabilities()
        # https://libvirt.org/formatdomaincaps.html
        if self.conn.getLibVersion() < 1002007:
            raise Exception("libvirt 1.2.7 or newer is required at the target host")

        if not self.primary_mac:
            self._generate_primary_mac()

        if not self.client_public_key:
            (
                self.client_private_key,
                self.client_public_key,
            ) = nixops.util.create_key_pair()

        if self.storage_volume_name is None:
            self._prepare_storage_volume()
            self.storage_volume_name = self.vol.name()

        self.domain_xml = self._make_domain_xml(defn)

        if self.vm_id is None:
            # By using "define" we ensure that the domain is
            # "persistent", as opposed to "transient" (i.e. removed on reboot).
            self._dom = self.conn.defineXML(self.domain_xml)
            if self._dom is None:
                self.log("Failed to register domain XML with the hypervisor")
                return False

            self.vm_id = self._vm_id()

        self.start()
        return True

    def _prepare_storage_volume(self):
        self.logger.log("preparing disk image...")
        newEnv = copy.deepcopy(os.environ)
        newEnv["NIXOPS_LIBVIRTD_PUBKEY"] = self.client_public_key

        temp_image_path = nixops.evaluation.eval(
            networkExpr=self.depl.network_expr,
            uuid=self.depl.uuid,
            deploymentName=self.depl.name or "",
            checkConfigurationOptions=False,
            attr="nodes.{0}.config.deployment.libvirtd.baseImage".format(self.name),
            pluginNixExprs=PluginManager.nixexprs(),
            build=True
        )

        temp_disk_path = os.path.join(temp_image_path, "nixos.qcow2")

        self.logger.log("uploading disk image...")
        image_info = self._get_image_info(temp_disk_path)
        self._vol = self._create_volume(
            image_info["virtual-size"], image_info["file-length"]
        )
        self._upload_volume(temp_disk_path, image_info["file-length"])

    def _get_image_info(self, filename):
        output = self._logged_exec(
            ["qemu-img", "info", "--output", "json", filename], capture_stdout=True
        )

        info = json.loads(output)
        info["file-length"] = os.stat(filename).st_size

        return info

    def _create_volume(self, virtual_size, file_length):
        xml = """
        <volume>
          <name>{name}</name>
          <capacity>{virtual_size}</capacity>
          <allocation>{file_length}</allocation>
          <target>
            <format type="qcow2"/>
          </target>
        </volume>
        """.format(
            name="{}.qcow2".format(self._vm_id()),
            virtual_size=virtual_size,
            file_length=file_length,
        )
        vol = self.pool.createXML(xml)
        self._vol = vol
        return vol

    def _upload_volume(self, filename, file_length):
        stream = self.conn.newStream()
        self.vol.upload(stream, offset=0, length=file_length)

        def read_file(stream, nbytes, f):
            return f.read(nbytes)

        with open(filename, "rb") as f:
            stream.sendAll(read_file, f)
            stream.finish()

    def _get_qemu_executable(self):
        domaincaps_xml = self.conn.getDomainCapabilities(
            emulatorbin=None,
            arch="x86_64",
            machine=None,
            virttype="kvm",
        )
        domaincaps = ElementTree.fromstring(domaincaps_xml)
        return domaincaps.find("./path").text.strip()

    def _make_domain_xml(self, defn):
        qemu = self._get_qemu_executable()

        def maybe_mac(n):
            if n == self.primary_net:
                return '<mac address="' + self.primary_mac + '" />'
            else:
                return ""

        def iface(n):
            return "\n".join(
                [
                    '    <interface type="network">',
                    maybe_mac(n),
                    '      <source network="{0}"/>',
                    "    </interface>",
                ]
            ).format(n)

        def _make_os(defn):
            return [
                "<os>",
                '    <type arch="x86_64">hvm</type>',
                "    <kernel>%s</kernel>" % defn.kernel,
                "    <initrd>%s</initrd>" % defn.initrd if len(defn.kernel) > 0 else "",
                "    <cmdline>%s</cmdline>" % defn.cmdline
                if len(defn.kernel) > 0
                else "",
                "</os>",
            ]

        domain_fmt = "\n".join(
            [
                '<domain type="{5}">',
                "  <name>{0}</name>",
                '  <memory unit="MiB">{1}</memory>',
                "  <vcpu>{4}</vcpu>",
                "\n".join(_make_os(defn)),
                "  <devices>",
                "    <emulator>{2}</emulator>",
                '    <disk type="file" device="disk">',
                '      <driver name="qemu" type="qcow2"/>',
                '      <source file="{3}"/>',
                '      <target dev="hda"/>',
                "    </disk>",
                "\n".join([iface(n) for n in defn.networks]),
                '    <graphics type="vnc" port="-1" autoport="yes"/>'
                if not defn.headless
                else "",
                '    <input type="keyboard" bus="usb"/>',
                '    <input type="mouse" bus="usb"/>',
                defn.extra_devices,
                "  </devices>",
                defn.extra_domain,
                "</domain>",
            ]
        )

        return domain_fmt.format(
            self._vm_id(),
            defn.memory_size,
            qemu,
            self.vol.path(),
            defn.vcpu,
            defn.domain_type,
        )

    def _parse_ip(self):
        """
        return an ip v4
        """
        # alternative is VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE if qemu agent is available
        ifaces = self.dom.interfaceAddresses(
            libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE, 0
        )
        if ifaces is None:
            self.log("Failed to get domain interfaces")
            return

        for (name, val) in ifaces.items():
            if val["addrs"]:
                for ipaddr in val["addrs"]:
                    return ipaddr["addr"]

    def _wait_for_ip(self, prev_time):
        self.log_start("waiting for IP address to appear in DHCP leases...")
        while True:
            ip = self._parse_ip()
            if ip:
                self.private_ipv4 = ip
                break
            time.sleep(1)
            self.log_continue(".")
        self.log_end(" " + self.private_ipv4)

    def _is_running(self):
        try:
            return self.dom.isActive()
        except libvirt.libvirtError:
            self.log("Domain %s is not running" % self.vm_id)
        return False

    def start(self):
        assert self.vm_id
        assert self.domain_xml
        assert self.primary_net
        if self._is_running():
            self.log("connecting...")
            self.private_ipv4 = self._parse_ip()
        else:
            self.log("starting...")
            self.dom.create()
            self._wait_for_ip(0)

    def get_ssh_name(self):
        self.private_ipv4 = self._parse_ip()
        return self.private_ipv4

    def stop(self):
        assert self.vm_id
        if self._is_running():
            self.log_start("shutting down... ")
            if self.dom.destroy() != 0:
                self.log("Failed destroying machine")
        else:
            self.log("not running")
        self.state = self.STOPPED

    def destroy(self, wipe=False):
        self.log_start("destroying... ")

        if self.vm_id is not None:
            self.stop()
            if self.dom.undefine() != 0:
                self.log("Failed undefining domain")
                return False

        if self.disk_path and os.path.exists(self.disk_path):
            # the deployment was created by an older NixOps version that did
            # not use the libvirtd API for uploading disk images
            os.unlink(self.disk_path)

        if self.storage_volume_name is not None:
            self.vol.delete()

        return True
