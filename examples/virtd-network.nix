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
        deployment.libvirtd.networks = [ "net2" ];
    };

    node2 = {
        deployment.targetEnv = "libvirtd";
        deployment.libvirtd.imageDir = "/var/lib/libvirt/images";
        deployment.libvirtd.networks = [ "net2" ];
    };
}
