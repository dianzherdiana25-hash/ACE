import importlib, json, sys
CUSTODY = "/workspace/ace-custody-lineage-guard"
sys.path.insert(0, CUSTODY + "/wt-abcv3/code")
sys.path.insert(0, CUSTODY)
mods = {}
for name in ("abc_v3_run", "ace_operational",
             "ace_operational.grid_adapter",
             "ace_operational.grid_generalization",
             "ace_operational.operator_discovery"):
    m = importlib.import_module(name)
    mods[name] = getattr(m, "__file__", None)
ok = all(v is not None and v.startswith(CUSTODY + "/") for v in mods.values())
print(json.dumps({"python": sys.version.split()[0], "modules": mods,
                  "all_under_custody": ok}, indent=1))
