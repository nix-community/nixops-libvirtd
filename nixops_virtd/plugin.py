import os.path
import nixops.plugins


@nixops.plugins.hookimpl
def nixexprs():
    return [os.path.dirname(__file__) + "/nix"]


@nixops.plugins.hookimpl
def load():
    return [
        "nixops_virtd.backends.libvirtd",
    ]
