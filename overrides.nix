{ pkgs }:

self: super: {
  nixops = super.nixops.overridePythonAttrs({ nativeBuildInputs ? [], ... }: {
    format = "pyproject";
    nativeBuildInputs = nativeBuildInputs ++ [ self.poetry ];
  });

  libvirt-python = super.libvirt-python.overridePythonAttrs({ nativeBuildInputs ? [], ... }: {
    format = "pyproject";
    nativeBuildInputs = nativeBuildInputs ++ [ pkgs.pkgconfig ];
    propagatedBuildInputs = [ pkgs.libvirt ];
  });

}
