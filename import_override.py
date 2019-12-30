import sys
import os
import imp
import tokenize
import ast
from types import ModuleType, MappingProxyType


class MyPathFinder:

    def __init__(self, sub):
        self.sub = sub

    def find_module(self, *args):
        loader = self.sub.find_module(*args)
        print("find_module", args, "->", loader)
        if loader:
            print(loader.get_filename())
            return MyLoader(loader)

    def _find_spec(self, *args):
        res = self.sub.find_spec(*args)
        print("find_spec", args, "->", res)
        return res


def make_module(modname, fname, src, sysname=None):
    print("make_module", modname)
    tree = ast.parse(src)
#    print(ast.dump(tree))

    shortname = modname.rsplit(".", 1)[-1]
    mod = imp.new_module(shortname)
    globals_dict = mod.__dict__
    globals_dict["__file__"] = fname
    print("newly inited module dict:", globals_dict)

    co = compile(tree, fname, "exec")
    sys.modules[sysname or modname] = mod
    exec(co, globals_dict)
    print(globals_dict.keys())

    return mod


class MyLoader:

    def __init__(self, sub):
        print("MyLoader:", sub)
        self.sub = sub

    def load_module(self, modname):
        mod = self.my_load_module(modname)
        #mod = self.sub.load_module(modname)
        ns = mod.__dict__.copy()
        ns.pop("__builtins__")
        print(modname, ":", ns)
        return mod

    def my_load_module(self, modname):
        mod = None
        print("load_module", modname)
        if modname in sys.modules:
            return sys.modules[modname]

        fname = self.sub.get_filename(modname)
        src = self.sub.get_source(modname)
        mod = make_module(modname, fname, src)

        if fname.endswith("/__init__.py"):
            mod.__path__ = [os.path.dirname(fname)]

        return mod


fname = sys.argv[1]

sys.argv.pop(0)
sys.path[0] = os.path.dirname(os.path.abspath(fname))

with open(fname) as f:
    src = f.read()

sys.meta_path[-1] = MyPathFinder(sys.meta_path[-1])
sys.path_importer_cache.clear()

mod = make_module("__main__", fname, src)
