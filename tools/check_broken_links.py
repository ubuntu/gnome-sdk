#!/usr/bin/env python3

import glob
import os
import sys

def get_package_for_file(filepath):
    print(f"Searching for package that provides {filepath}")
    output = os.popen(f"apt-file search -F {filepath}").read()
    for line in output.splitlines():
        if ": " in line:
            package, _ = line.split(": ", 1)
            if package.find(":") != -1:
                # if the package name contains ":", it's probably an architecture suffix, so remove it
                package = package.split(":")[0]
            return package
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: check_broken_links.py <search_path>")
        return 1
    search_path = sys.argv[1]

    # find broken links for libraries
    broken_links = []

    for filepath in glob.glob(os.path.join(search_path, "**"), recursive=True):
        if not os.path.islink(filepath):
            continue

        basename = os.path.basename(filepath)
        if not ((basename.endswith(".so") or ".so." in basename)):
            continue

        relative_filepath = filepath[len(search_path):]
        if relative_filepath.startswith("/"):
            relative_filepath = relative_filepath[1:]

        target = os.readlink(filepath)
        full_target = target
        if not full_target.startswith("/"):
            full_target = os.path.normpath(os.path.join(os.path.dirname(filepath), full_target))
        if os.path.exists(full_target):
            continue
        relative_target = full_target[len(search_path):]
        if relative_target.startswith("/"):
            relative_target = relative_target[1:]
        broken_links.append((relative_filepath, target, relative_target))

    if not broken_links:
        return 0

    missing_packages = {}
    broken_packages = {}
    for relative_filepath, target, full_target in broken_links:
        full_path = os.path.join('/', relative_filepath)
        full_target_path = os.path.join('/', full_target)
        package = get_package_for_file(full_path)
        if package is None:
            print(f"Can't find which package provides {full_target_path}")
            continue

        missing_package = get_package_for_file(full_target_path)
        if missing_package is None:
            print(f"Broken link: {full_path} -> {full_target_path} (provided by {package})")
            print(f"  Missing package: {full_target_path}")
            if package not in broken_packages:
                broken_packages[package] = []
            broken_packages[package].append(full_target_path)
        else:
            print(f"Broken link: {full_path} -> {full_target_path} (provided by {package}, missing package: {missing_package})")
            missing_packages[missing_package] = False

    if len(missing_packages) != 0:
        print("\n\nMissing packages:")
        for missing_package in missing_packages:
            print(f"  {missing_package}")
        print("\n")

    if len(broken_packages) != 0:
        print("Uneven packages: (not even Core snap contains the needed one to fix them)")
        for uneven_package in broken_packages:
            print(f"  {uneven_package}:")
            for broken_file in broken_packages[uneven_package]:
                print(f"    {broken_file}")
        print("\n\n")

    return 1

if __name__ == "__main__":
    sys.exit(main())