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
SDK_FILE = 'gnome-46-2404-sdk.snap'

# If there is a modified snapcraft.yaml, delete it before re-generating it
if os.path.exists(f'./{MODIFIED_CONFIG}'):
    os.remove(f'./{MODIFIED_CONFIG}')

if not os.path.exists(f'./{SDK_FILE}'):
    print(f'There is no valid "{SDK_FILE}" file. Aborting.', file=sys.stderr)
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

with open(f'./{MODIFIED_CONFIG}', "w") as config_file:
    config_file.write(yaml.dump(config, Dumper=yaml.Dumper))

os.system('snapcraft clean')
os.system('snapcraft pack -v')
os.remove(f'./{MODIFIED_CONFIG}')
