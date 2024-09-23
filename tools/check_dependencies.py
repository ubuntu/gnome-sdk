#!/usr/bin/env python3

import os
import sys
import yaml

# Ensure that "deb" part depends on all previous parts

config_file = "snapcraft.yaml"
if not os.path.exists(config_file):
    config_file = os.path.join("snap", "snapcraft.yaml")

data = yaml.safe_load(open(config_file, "r"))

exceptions = ['buildenv']

def filldeps(part):
    """ Fill recursively the dependencies of each part """
    global data
    output = []
    if 'after' in data['parts'][part]:
        for dep in data['parts'][part]['after']:
            # it's not a problem to have duplicated dependencies
            output += filldeps(dep)
            output.append(dep)
    return output

dependencies = {}

# get the dependencies for each part
for part in data["parts"]:
    dependencies[part] = filldeps(part)

deb_dependencies = []
for part in data["parts"]:
    if "debs" == part:
        continue
    if "debs" in dependencies[part]:
        # if it depends on debs, it must be after, so don't take it into account
        continue
    if part in exceptions:
        continue
    deb_dependencies.append(part)

failed = False
for dependency in deb_dependencies:
    if dependency not in dependencies["debs"]:
        print(f"DEBS part must be after {dependency}")
        failed = True

if failed:
    sys.exit(1)
print("All dependencies are correct")
