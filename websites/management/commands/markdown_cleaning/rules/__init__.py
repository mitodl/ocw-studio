import importlib
import pkgutil

for mod_info in pkgutil.walk_packages(__path__, __name__ + "."):
    mod = importlib.import_module(mod_info.name)

    # Emulate `from mod import *`
    try:
        names = mod.__dict__["__all__"]
    except KeyError:
        names = [k for k in mod.__dict__ if not k.startswith("_")]

    globals().update({k: getattr(mod, k) for k in names})
