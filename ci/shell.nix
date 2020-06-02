{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {

  buildInputs = [
    (pkgs.poetry2nix.mkPoetryEnv {
      projectDir = ../.;
      overrides = pkgs.poetry2nix.overrides.withDefaults (import ../overrides.nix { inherit pkgs; });
    })
  ];

}
