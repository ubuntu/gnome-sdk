#!/usr/bin/env python3
"""Compare the ABI of the shared libraries shipped in two snaps.

Libraries are paired by SONAME, so that a rename or a path change does
not hide or invent ABI changes; libraries without a SONAME (plugins)
are paired by filename. Every pair is compared with abidiff: changed
symbols or data structures are a failure, while added symbols and new
libraries are only reported. A library that disappears is a failure too.

ABI changes can be allow-listed with libabigail suppression
specifications, stored in '.github/abicheck/'. A file named after the
library relative path applies to that library only, while
'default.abignore' applies to every library.

If any of the snaps ships split debug information (usr/lib/debug), it is
passed to abidiff so that data structure changes can be detected as well.
"""

import os
import re
import subprocess
import sys

ABIDIFF_ERROR = 1
ABIDIFF_USAGE_ERROR = 2
ABIDIFF_ABI_CHANGE = 4
ABIDIFF_ABI_INCOMPATIBLE_CHANGE = 8

SUMMARY_RE = re.compile(
    r'changes summary: (?P<removed>\d+) Removed(?: \(\d+ filtered out\))?'
    r'(?:, (?P<changed>\d+) Changed(?: \(\d+ filtered out\))?)?')
SONAME_RE = re.compile(
    r'\(SONAME\)\s+(?:Shared library|Library soname): \[(.+?)\]')


def read_soname(path):
    try:
        output = subprocess.check_output(['readelf', '-d', path],
                                         stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None
    match = SONAME_RE.search(output.decode(errors='replace'))
    return match.group(1) if match else None


def find_libraries(root):
    """Return {key: {relative path: absolute path}} of the shared objects.

    Libraries are keyed by SONAME so that a rename or a path change does
    not hide or invent ABI changes. Libraries without a SONAME (plugins)
    are keyed by filename.
    """
    libraries = {}
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if not filename.endswith('.so') and '.so.' not in filename:
                continue
            path = os.path.join(dirpath, filename)
            # symlinks point to the real library, which is walked separately
            if os.path.islink(path):
                continue
            # linker scripts (libc.so, libgcc_s.so) and gdb helpers are
            # named like libraries but are not ELF files
            with open(path, 'rb') as binary:
                if binary.read(4) != b'\x7fELF':
                    continue
            soname = read_soname(path) or filename
            relpath = os.path.relpath(path, root)
            libraries.setdefault(soname, {})[relpath] = path
    return libraries


def pair_libraries(old_libraries, new_libraries):
    """Return (pairs, removed, added), where pairs is a list of
    (name, old path, new path) triples."""
    pairs = []
    removed = []
    added = []
    for key in sorted(set(old_libraries) | set(new_libraries)):
        old = old_libraries.get(key, {})
        new = new_libraries.get(key, {})
        for relpath in sorted(set(old) & set(new)):
            pairs.append((relpath, old[relpath], new[relpath]))
        old_rest = sorted(set(old) - set(new))
        new_rest = sorted(set(new) - set(old))
        for old_relpath, new_relpath in zip(old_rest, new_rest):
            pairs.append((new_relpath, old[old_relpath], new[new_relpath]))
        removed += old_rest[len(new_rest):]
        added += new_rest[len(old_rest):]
    return pairs, removed, added


def debug_info_dirs(root):
    """Return the directories where split debug information may be found."""
    path = os.path.join(root, 'usr/lib/debug')
    return [path] if os.path.isdir(path) else []


def suppression_files(name, override_dir):
    """Return the suppression files that allow-list ABI changes of a library.

    A file named after the library relative path applies to that library
    only, while default.abignore applies to every library.
    """
    files = []
    default = os.path.join(override_dir, 'default.abignore')
    if os.path.isfile(default):
        files.append(default)
    library = os.path.join(override_dir, name)
    if os.path.isfile(library):
        files.append(library)
    return files


def only_additions(report):
    """Check whether every summary line reports additions only."""
    for line in report.splitlines():
        match = SUMMARY_RE.search(line)
        if match is None:
            continue
        if match.group('changed') and int(match.group('changed')) > 0:
            return False
        if int(match.group('removed')) > 0:
            return False
    return True


def compare_libraries(old_path, new_path, name, debug_dirs, suppressions):
    # --no-default-suppression keeps the result deterministic and makes
    # the allow-list the only source of suppressions.
    cmd = ['abidiff', '--no-default-suppression']
    for file in suppressions:
        cmd += ['--suppressions', file]
    for dir_opt, dirs in zip(('--debug-info-dir1', '--debug-info-dir2'),
                             debug_dirs):
        for dir in dirs:
            cmd += [dir_opt, dir]
    cmd += [old_path, new_path]

    result = subprocess.run(cmd, capture_output=True, text=True)

    report = result.stdout.strip()
    if result.returncode & (ABIDIFF_ERROR | ABIDIFF_USAGE_ERROR):
        print(f'abidiff failed on {name}:')
        print(result.stdout)
        print(result.stderr)
        return 'error'
    if result.returncode & ABIDIFF_ABI_INCOMPATIBLE_CHANGE:
        # removed symbols or soname change
        print(f'{name} changed:')
        print(report)
        return 'changed'
    if result.returncode & ABIDIFF_ABI_CHANGE:
        if only_additions(report):
            print(f'{name} only added symbols:')
            print(report)
            return 'added'
        print(f'{name} changed:')
        print(report)
        return 'changed'
    if report:
        print(f'{name} only added symbols:')
        print(report)
        return 'added'
    return 'unchanged'


def main():
    if len(sys.argv) != 3:
        print(f'Usage: {sys.argv[0]} <old-snap-root> <new-snap-root>',
              file=sys.stderr)
        return 2

    old_root, new_root = sys.argv[1:]
    # overrides live in '.github/abicheck/' of the repository that owns
    # this script
    override_dir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), '.github', 'abicheck')
    debug_dirs = (debug_info_dirs(old_root), debug_info_dirs(new_root))
    pairs, removed, added = pair_libraries(find_libraries(old_root),
                                           find_libraries(new_root))

    failures = []
    counts = {'unchanged': 0, 'added': 0, 'changed': 0, 'error': 0}
    for name, old_path, new_path in pairs:
        status = compare_libraries(old_path, new_path, name, debug_dirs,
                                   suppression_files(name, override_dir))
        counts[status] += 1
        if status in ('changed', 'error'):
            failures.append(name)

    for name in removed:
        print(f'{name} was removed')
        failures.append(name)
    for name in added:
        print(f'{name} is new')

    print(f'{counts["unchanged"]} libraries unchanged, '
          f'{counts["added"]} with only added symbols, '
          f'{len(added)} new libraries, '
          f'{counts["changed"]} with changed symbols, '
          f'{counts["error"]} abidiff errors, '
          f'{len(removed)} removed libraries')

    for name in failures:
        print(f'::error::{name}')

    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
