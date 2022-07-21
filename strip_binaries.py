#!/usr/bin/env python3

import os
import sys
import subprocess

basepath = sys.argv[1]

files = {}

paths = [basepath]

# def read_retval(command):
#     pr = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     retval = pr.returncode
#     if retval != 0:
#         data = None
#     else:
#         data = pr.stdout.decode('utf8')
#     return retval, data

while len(paths) != 0:
    path = paths[0]
    paths = paths[1:]
    for filename in os.listdir(path):
        fullpath = os.path.join(path, filename)
        if os.path.islink(fullpath):
            continue
        if os.path.isdir(fullpath):
            paths.append(fullpath)
            continue
        if (os.stat(fullpath).st_size == 0):
            continue
        with open(fullpath, "rb") as f:
            data = f.read(4)
            if data == b"\x7fELF":
                os.system(f"strip --strip-unneeded {fullpath}")

        # this code is for deduplicating files using hard links
        # but the gain is too little
        #
        # retval, data = read_retval(['md5sum', fullpath])
        # if (retval != 0):
        #     print(f"Failed to get md5sum of {fullpath}")
        #     continue
        # md5 = data.split(" ")[0].strip()
        # if md5 not in files:
        #     files[md5] = [fullpath]
        #     continue
        # found = False
        # for otherfiles in files[md5]:
        #     retval, data = read_retval(['cmp', fullpath, otherfiles])
        #     if retval == 0:
        #         found = True
        #         os.unlink(fullpath)
        #         print(f"Linking {fullpath} to {otherfiles}")
        #         os.system(f"ln {otherfiles} {fullpath}")
        #         break
        # if not found:
        #     files[md5].append(fullpath)

