{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {

  buildInputs = [
    (pkgs.poetry2nix.mkPoetryEnv {
      projectDir = ../.;
      overrides = pkgs.poetry2nix.overrides.withDefaults(self: super: {
        # TODO: Add build input poetry to _all_ git deps in poetry2nix
        nixops = super.nixops.overridePythonAttrs(old: {
          buildInputs = old.buildInputs ++ [
            self.poetry
          ];
        });
      });
    })
  ];

}
