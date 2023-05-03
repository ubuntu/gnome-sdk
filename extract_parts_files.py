#!/usr/bin/env python3

import os
import yaml

"""
    This script extracts API/ABI data from each part and stores it into
    a YAML file to allow to detect API/ABI breakage between versions.

    The YAML file comprises a list of parts, each one with three elements
    (headers, libraries and pkgconfig), and each element contains a list
    of the files for that part.

    This allows to isolate the specific files installed by each part and
    analyze them more easily.
"""

def _resolve_link(path: str) -> str:
    """ given a path, if it is a symlink, will resolve recursively
        until obtaining the final file. """
    while os.path.islink(path):
        newpath = os.readlink(path)
        if newpath[0] != os.sep:
            newpath = os.path.join(os.path.dirname(path), newpath)
        path = newpath
    return path

base_path = os.path.join(os.environ['CRAFT_STAGE'], '..', "parts")
parts = {}
for part_name in os.listdir(base_path):
    full_path = os.path.join(base_path, part_name, "install")
    if not os.path.isdir(full_path):
        continue
    parts[part_name] = {"headers": [], "libraries": [], "pkgconfig": []}
    for root, folders, files in os.walk(full_path):
        for filename in files:
            full_file_path = os.path.join(root, filename)
            relative_file_path = full_file_path.replace(full_path, '')
            if filename.endswith(".so") or (".so." in filename):
                final_path = _resolve_link(full_file_path).replace(full_path, '')
                if final_path not in parts[part_name]["libraries"]:
                    parts[part_name]["libraries"].append(final_path)
            elif filename.endswith(".h") or filename.endswith(".hh"):
                parts[part_name]["headers"].append(relative_file_path)
            elif filename.endswith(".pc"):
                parts[part_name]["pkgconfig"].append(relative_file_path)

output_path = os.path.join(os.environ['CRAFT_PRIME'], 'extra_data')
try:
    os.makedirs(output_path)
except:
    pass
output_path = os.path.join(output_path, 'source_data.yaml')
with open(output_path, "w", encoding='utf-8') as yaml_data:
    yaml.dump(parts, yaml_data, default_flow_style=False)
