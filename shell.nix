{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    (import ./env.nix { inherit pkgs; })
    pkgs.poetry
    pkgs.pkgconfig
    pkgs.libvirt
  ];
}
