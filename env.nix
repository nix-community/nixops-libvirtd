{ pkgs ? import <nixpkgs> {} }:
let
  overrides = import ./overrides.nix { inherit pkgs; };
in pkgs.poetry2nix.mkPoetryEnv {
  projectDir = ./.;
  overrides = pkgs.poetry2nix.overrides.withDefaults overrides;
}
