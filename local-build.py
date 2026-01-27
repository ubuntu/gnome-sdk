#!/usr/bin/env python3

# This script builds the gnome runtime snap using a local SDK snap.

import sys
import os
import yaml

def str_presenter(dumper, data):
    """configures yaml for dumping multiline strings
    Ref: https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
    Ensures that the scripts are dumped in the right multiline format """
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter) # to use with safe_dum

BASE_CONFIG = 'snap/snapcraft.yaml'
MODIFIED_CONFIG = 'snapcraft.yaml'
BASE_SNAP_FOLDER = 'base-gnome-sdk'
SDK_FILE = None

# If there is a modified snapcraft.yaml, delete it before re-generating it
if os.path.exists(f'./{MODIFIED_CONFIG}'):
    os.remove(f'./{MODIFIED_CONFIG}')

last_time = None
# get the most recent snap
for f in os.listdir(BASE_SNAP_FOLDER):
    if f.endswith(".snap"):
        fullpath = os.path.join(BASE_SNAP_FOLDER, f)
        now_time = os.path.getmtime(fullpath)
        if (last_time is None) or (now_time > last_time):
            SDK_FILE = fullpath
            last_time = now_time

if SDK_FILE is None:
    print(f'There is no valid SDK file in the {BASE_SNAP_FOLDER} folder. Aborting.', file=sys.stderr)
    sys.exit(1)

with open(f'./{BASE_CONFIG}', "r") as config_file:
    config = yaml.load(config_file, Loader=yaml.Loader)

gnome_part = config['parts']['gnome-sdk']

# remove the stage-snaps entry
del gnome_part['stage-snaps']

version = config['name'].split('-')[1]
gnome_part['build-environment'] = gnome_part.get('build-environment', []) + [
    {'LOCAL_SDK_SNAP': SDK_FILE},
    {'sdk_version': version}
]

try:
    with open(f'./{MODIFIED_CONFIG}', "w") as config_file:
        config_file.write(yaml.dump(config, Dumper=yaml.Dumper))
    if "--prepare-only" not in sys.argv:
        os.system('snapcraft clean')
        os.system('snapcraft pack -v')
finally:
    if "--prepare-only" not in sys.argv:
        os.remove(f'./{MODIFIED_CONFIG}')
