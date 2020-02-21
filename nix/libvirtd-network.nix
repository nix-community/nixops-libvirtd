{ config, lib, pkgs, uuid, name, ... }:

with lib;
with import <nixops/lib.nix> lib;

rec {
    options = {
        type = mkOption {
            default = "nat";
            description = ''
              The type of the libvirt network.
              Either NAT network or isolated network can be specified. Defaults to NAT Network.
            '';
            type = types.enum [ "nat" "isolate" ];
        };

        cidrBlock = mkOption {
            example = "192.168.56.0/24";
            description = ''
              The IPv4 CIDR block for the libvirt network. The following IP addresses are reserved for the network:
              Network     - The first  address in the IP range, e.g. 192.168.56.0   in 192.168.56.0/24
              Gateway     - The second address in the IP range, e.g. 192.168.56.1   in 192.168.56.0/24
              Broadcast   - The last   address in the IP range, e.g. 192.168.56.255 in 192.168.56.0/24
            '';
            type = types.str;
        };

        staticIPs = mkOption {
            default = [];
            description = "The list of machine to IPv4 address bindings for fixing IP address of the machine in the network";
            type = with types; listOf (submodule {
                options = {
                    machine = mkOption {
                        type = either str (resource "machine");
                        apply = x: if builtins.isString x then x else x._name;
                        description = "The name of the machine in the network";
                    };
                    address = mkOption {
                        example = "192.168.56.3";
                        type = str;
                        description = ''
                          The IPv4 address assigned to the machine as static IP.
                          The static IP must be a non-reserved IP address.
                        '';
                    };
                };
            });
        };

        URI = mkOption {
            type = types.str;
            default = "qemu:///system";
            description = ''
              Connection URI.
            '';
        };
    };

    config = {
        _type = "libvirtd-network";
    };
}
