# NixOps backend for libvirtd

NixOps (formerly known as Charon) is a tool for deploying NixOS
machines in a network or cloud.

* [Manual](https://nixos.org/nixops/manual/)
* [Installation](https://nixos.org/nixops/manual/#chap-installation) / [Hacking](https://nixos.org/nixops/manual/#chap-hacking)
* [Continuous build](http://hydra.nixos.org/jobset/nixops/master#tabs-jobs)
* [Source code](https://github.com/NixOS/nixops)
* [Issue Tracker](https://github.com/NixOS/nixops/issues)

## Quick Start

### Prepare libvirtd

In order to use the libvirtd backend, a couple of manual steps need to be
taken.

*Note:* The libvirtd backend is currently supported only on NixOS.

Configure your host NixOS machine to enable libvirtd daemon,
add your user to libvirtd group and change firewall not to filter DHCP packets.

```nix
virtualisation.libvirtd.enable = true;
users.extraUsers.myuser.extraGroups = [ "libvirtd" ];
networking.firewall.checkReversePath = false;
```

Next we have to make sure our user has access to create images by executing:

```sh
images=/var/lib/libvirt/images
sudo mkdir $images
sudo chgrp libvirtd $images
sudo chmod g+w $images
```

Create the default libvirtd storage pool for root:

```sh
sudo virsh pool-define-as default dir --target $images
sudo virsh pool-autostart default
sudo virsh pool-start default
```

### Deploy the example machine

Create and deploy the trivial example:

```sh
nixops create -d example-libvirtd examples/trivial-virtd.nix
nixops deploy -d example-libvirtd
```

Your new machine doesn't do much by default, but you may connect to it by
running:

```sh
nixops ssh -d example-libvirtd machine
```
