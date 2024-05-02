#!/usr/bin/env python3

import os
import sys
import subprocess
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import NoteSection
from elftools.elf.enums import ENUM_DT_FLAGS_1
import yaml

basepath = sys.argv[1]
debugroot = sys.argv[2]

files = {}

paths = [basepath]

def describe_e_type(elffile):
    x = elffile.header['e_type']
    if elffile is not None and x == 'ET_DYN':
        try:
            # Detect whether this is a normal SO or a PIE executable
            dynamic = elffile.get_section_by_name('.dynamic')
            for t in dynamic.iter_tags('DT_FLAGS_1'):
                if t.entry.d_val & ENUM_DT_FLAGS_1['DF_1_PIE']:
                    return 'ET_PIE' # executable
        except:
            pass
    return x

def read_elf_type(filepath):
    with open(filepath, "rb") as binary:
        # find the BuildID
        buildId = None
        try:
            elffile = ELFFile(binary)
            ftype = describe_e_type(elffile)
            for sect in elffile.iter_sections():
                if not isinstance(sect, NoteSection):
                    continue
                for note in sect.iter_notes():
                    if  note['n_type'] == 'NT_GNU_BUILD_ID':
                        buildId = note['n_desc']
                        break
        except:
            return None, None
    return ftype, buildId

def generate_version(part_src_dir = None) -> str:
    """Return the latest git tag from PWD or defined part_src_dir.

    The output depends on the use of annotated tags and will return
    something like: '2.28+git.10.abcdef' where '2.28 is the
    tag, '+git' indicates there are commits ahead of the tag, in
    this case it is '10' and the latest commit hash begins with
    'abcdef'. If there are no tags or the revision cannot be
    determined, this will return 0 as the tag and only the commit
    hash of the latest commit.
    """
    if not part_src_dir:
        part_src_dir = Path.cwd()

    encoding = sys.getfilesystemencoding()
    try:
        output = (
            subprocess.check_output(
                ["git", "-C", str(part_src_dir), "describe", "--dirty"],
                stderr=subprocess.DEVNULL,
            )
            .decode(encoding)
            .strip()
        )
    except subprocess.CalledProcessError as err:
        # If we fall into this exception it is because the repo is not
        # tagged at all.
        proc = subprocess.Popen(  # pylint: disable=consider-using-with
            ["git", "-C", str(part_src_dir), "describe", "--dirty", "--always"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            # This most likely means the project we are in is not driven
            # by git.
            raise errors.VCSError(message=stderr.decode(encoding).strip()) from err
        return f"0+git.{stdout.decode(encoding).strip()}"

    match = re.search(
        r"^(?P<tag>[a-zA-Z0-9.+~-]+)-"
        r"(?P<revs_ahead>\d+)-"
        r"g(?P<commit>[0-9a-fA-F]+(?:-dirty)?)$",
        output,
    )

    if not match:
        # This means we have a pure tag
        return output

    tag = match.group("tag")
    revs_ahead = match.group("revs_ahead")
    commit = match.group("commit")

    return f"{tag}+git{revs_ahead}.{commit}"

while len(paths) != 0:
    path = paths[0]
    if (path[-1] == os.path.sep) and (len(path) > 1):
        path = path[:-1]
    paths = paths[1:]
    if path == debugroot:
        continue
    for filename in os.listdir(path):
        fullpath = os.path.join(path, filename)
        if os.path.islink(fullpath):
            continue
        if os.path.isdir(fullpath):
            paths.append(fullpath)
            continue
        if (os.stat(fullpath).st_size == 0):
            continue
        filetype, buildid = read_elf_type(fullpath)
        if (filetype is None) or (buildid is None):
            continue

        debugpath = os.path.join(debugroot, buildid[:2])
        debugname = os.path.join(debugpath, f"{buildid[2:]}.debug")

        print(f"Extracting symbols from {fullpath} into {debugname}")
        try:
            os.makedirs(debugpath)
        except:
            pass
        os.system(f'objcopy --only-keep-debug --compress-debug-sections {fullpath} {debugname}')

        if filetype == 'ET_DYN':
            strip = '--strip-unneeded '
        else:
            strip = '--strip-all'
        print(f"Stripping with {strip} {fullpath}")
        os.system(f"strip {strip} {fullpath}")

config_file = os.path.join(os.environ['CRAFT_PROJECT_DIR'], "snapcraft.yaml")
if not os.path.exists(config_file):
    config_file = os.path.join(os.environ['CRAFT_PROJECT_DIR'], "snap", "snapcraft.yaml")

data = yaml.safe_load(open(config_file, "r"))
version_number = data['version']
if version_number == 'git':
    version_number = generate_version(part_src_dir=os.environ['CRAFT_PROJECT_DIR'])

archive_name = f"{os.environ['SNAPCRAFT_PROJECT_NAME']}_{version_number}_{os.environ['SNAP_ARCH']}.debug"
archive_full_path = os.path.join(os.environ['CRAFT_PROJECT_DIR'], archive_name)
os.system(f"zip -r9 {archive_full_path} {debugroot}")
