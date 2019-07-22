{ nixopsLibvirtd ? { outPath = ./.; revCount = 0; shortRev = "abcdef"; rev = "HEAD"; }
, nixpkgs ? <nixpkgs>
, officialRelease ? false
}:
let
  pkgs = import nixpkgs {};
  version =  "1.7" + (if officialRelease then "" else "pre${toString nixopsLibvirtd.revCount}_${nixopsLibvirtd.shortRev}");
in
  rec {
    build = pkgs.lib.genAttrs [ "x86_64-linux" "i686-linux" "x86_64-darwin" ] (system:
      with import nixpkgs { inherit system; };
      python2Packages.buildPythonApplication rec {
        name = "nixops-libvirtd";
        src = ./.;
        prePatch = ''
          for i in setup.py; do
            substituteInPlace $i --subst-var-by version ${version}
          done
        '';
        buildInputs = [ python2Packages.nose python2Packages.coverage ];
        propagatedBuildInputs = [ python2Packages.libvirt ];
        doCheck = true;
        postInstall = ''
          mkdir -p $out/share/nix/nixops-libvirtd
          cp -av nix/* $out/share/nix/nixops-libvirtd
        '';
        meta.description = "NixOps libvirtd backend for ${stdenv.system}";
      }
    );
  }
