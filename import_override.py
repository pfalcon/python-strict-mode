import sys
import os
import imp
import tokenize
import ast
from types import ModuleType, MappingProxyType


class MyPathFinder:

    def __init__(self, sub):
        self.sub = sub

    def find_spec(self, fullname, path, target_mod):
        spec = self.sub.find_spec(fullname, path, target_mod)
        print("find_spec", (fullname, path, target_mod), "->", spec)
        if spec.loader:
            spec.loader = MyLoader(spec.loader)
        return spec


def make_module(modname, fname, src, sysname=None):
    print("make_module", modname)
    shortname = modname.rsplit(".", 1)[-1]
    mod = imp.new_module(shortname)
    mod.__file__ = fname
    mod = populate_module(mod, src)
    sys.modules[sysname or modname] = mod
    return mod


def populate_module(mod, src):
    tree = ast.parse(src)
#    print(ast.dump(tree))
    globals_dict = mod.__dict__
    print("newly inited module dict:", globals_dict)

    co = compile(tree, mod.__file__, "exec")
    exec(co, globals_dict)
    print(globals_dict.keys())
    return mod


class MyLoader:

    def __init__(self, sub):
        print("MyLoader:", sub)
        self.sub = sub

    def create_module(self, spec):
        return None

    def exec_module(self, mod):
        print("exec_module", mod)
        src = self.sub.get_source(mod.__name__)
        return populate_module(mod, src)


fname = sys.argv[1]

sys.argv.pop(0)
sys.path[0] = os.path.dirname(os.path.abspath(fname))

with open(fname) as f:
    src = f.read()

sys.meta_path[-1] = MyPathFinder(sys.meta_path[-1])
sys.path_importer_cache.clear()

mod = make_module("__main__", fname, src)
