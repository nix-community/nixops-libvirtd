{
    resources.libvirtdNetworks.net2 = {
        type = "nat";
        cidrBlock = "172.16.100.0/16";
        staticIPs = [
            {
                machine = "node1";
                address = "172.16.100.12";
            }
            {
                machine = "node2";
                address = "172.16.100.5";
            }
        ];
    };

    node1 = {
        deployment.targetEnv = "libvirtd";
        deployment.libvirtd.imageDir = "/var/lib/libvirt/images";
        deployment.libvirtd.networks = [
            "net2"
            # {
            #     name = "ovsbr0";
            #     type = "bridge";
            #     virtualport = "openvswitch";
            # }
        ];
    };

    node2 = {resources, ...}: {
        deployment.targetEnv = "libvirtd";
        deployment.libvirtd.imageDir = "/var/lib/libvirt/images";
        deployment.libvirtd.networks = [ resources.libvirtdNetworks.net2 ];
    };
}
