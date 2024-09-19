#!/usr/bin/env python3

import os
import sys
import yaml

# Ensure that "deb" part depends on all previous parts

config_file = "snapcraft.yaml"
if not os.path.exists(config_file):
    config_file = os.path.join("snap", "snapcraft.yaml")

data = yaml.safe_load(open(config_file, "r"))

parts = {}

for part in data['parts']:
    if part == "debs":
        break
    parts[part] = False

def filldeps(part):
    global data
    global parts
    if 'after' not in data['parts'][part]:
        return

    deps = data['parts'][part]['after']
    for dep in deps:
        parts[dep] = True
        filldeps(dep)

filldeps("debs")
failed = False
for part in parts:
    if parts[part]:
        continue
    print(f"DEBS must depend on {part}")
    failed = True

if failed:
    sys.exit(1)
print("All dependencies are correct")
