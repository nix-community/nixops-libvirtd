{
  description = "NixOps libvirtd backend plugin";

  inputs = {
    nixpkgs = {
      # use temporarily a fork to get libvirtd 7.3
      url = "github:teto/nixpkgs/nixos-unstable";
      # flake = false;
    };
    nixops.url = "github:NixOS/nixops";

    # poetry.url = "github:nix-community/poetry2nix";
    utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, utils, nixpkgs, nixops }:
    utils.lib.eachSystem ["x86_64-linux"] (system: let
      pkgs = import nixpkgs {
        inherit system;
      };

      pyEnv = pkgs.python3.withPackages(ps: [
        nixops.defaultPackage."${system}"
        self.packages.${system}.nixops-libvirtd-plugin
      ]);

    in {
      packages.nixops-libvirtd-plugin = (pkgs.poetry2nix.mkPoetryEnv {
        projectDir = ./.;
        # overrides = pkgs.poetry2nix.overrides.withDefaults overrides;
      });

      # import ./shell.nix { pkgs = nixpkgs.legacyPackages."${system}"; };

      # packages."${system}".nixops-libvirtd = ;
      # nixops-plugged = nixops.withPlugins (ps: [

      defaultPackage = self.packages."${system}".nixops-libvirtd-plugin;
      # defaultPackage = nixops.defaultPackage."${system}".overrideAttrs(oa: {
      #   propagatedBuildInputs = oa.propagatedBuildInputs ++ [
      #     self.packages."${system}".nixops-libvirtd-plugin.propagatedBuildInputs
      #   ];
      # });

      devShell = pkgs.mkShell {
        name = "nixops-libvirtd-shell";
        buildInputs = [
          pyEnv
        ];
      };
  });
}
