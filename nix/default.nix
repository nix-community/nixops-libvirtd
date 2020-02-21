{
  config_exporters = { optionalAttrs, ... }: [
    (config: { libvirtd = optionalAttrs (config.deployment.targetEnv == "libvirtd") config.deployment.libvirtd; })
  ];
  options = [
    ./libvirtd.nix
  ];
  resources = { evalResources, zipAttrs, resourcesByType, ...}: {
    libvirtdNetworks = evalResources ./libvirtd-network.nix (zipAttrs resourcesByType.libvirtdNetworks or []);
  };
}
