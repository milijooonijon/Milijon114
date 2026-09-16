# Milijon App Package
import os
import sys
import importlib.util

_dir = os.path.dirname(os.path.abspath(__file__))
# Ensure modules in app package are always importable even on 9p/overlay caches
for _file in os.listdir(_dir) if hasattr(os, 'listdir') else []:
    pass

for _mod in ['config', 'database', 'harvester', 'proxy_engine', 'generator']:
    _path = os.path.join(_dir, f"{_mod}.py")
    if os.path.exists(_path) and f"app.{_mod}" not in sys.modules:
        try:
            _spec = importlib.util.spec_from_file_location(f"app.{_mod}", _path)
            if _spec and _spec.loader:
                _m = importlib.util.module_from_spec(_spec)
                sys.modules[f"app.{_mod}"] = _m
                _spec.loader.exec_module(_m)
                setattr(sys.modules[__name__], _mod, _m)
        except Exception as _e:
            pass
