{
  description = "NixOps libvirtd backend plugin";

  inputs = {
    nixpkgs = {
      # use temporarily a fork to get libvirtd 7.3
      url = "github:teto/nixpkgs/nixos-unstable";
      # flake = false;
    };

    # poetry.url = "github:nix-community/poetry2nix";
  };

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
  in {

    packages."${system}".nixops-libvirtd = import ./shell.nix { pkgs = nixpkgs.legacyPackages."${system}"; };

    defaultPackage."${system}" = self.packages."${system}".nixops-libvirtd;

  };
}
