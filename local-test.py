#!/usr/bin/env python3

import os
import sys
import time
import yaml

vm_name = 'local-test'
# Ubuntu version name
vm_version = 'noble'
# Memory in GB
vm_memory = 16
# number of cores assigned to the VM
vm_cpu_cores = 2
# disk space for the VM in GB
vm_disk_space = 10

def run_command_inside(command):
    print(f'Running {command}')
    os.system(f'multipass exec {vm_name} -- {command}')

def create_vm():
    print('Creating VM')
    # first, delete any old VM
    os.system(f'multipass delete {vm_name}')
    os.system(f'multipass purge')
    time.sleep(2)
    os.system(f'multipass launch {vm_version} -n {vm_name} -m {vm_memory}G -c {vm_cpu_cores} -d {vm_disk_space}G')
    run_command_inside('sudo apt update')
    run_command_inside('sudo apt dist-upgrade -y')
    run_command_inside('mkdir -p /home/ubuntu/basedir')
    os.system(f'multipass stop {vm_name}')
    os.system(f'multipass mount -t native . {vm_name}:/home/ubuntu/basedir')
    os.system(f'multipass start {vm_name}')


if (len(sys.argv) != 2):
    print('Usage:')
    print('    local-test init      Initializes the VM and exits')
    print('    local-text SNAP-NAME Tests the specified snap')
    sys.exit(-1)

if (sys.argv[1] == 'init'):
    create_vm()
    print('System created')
    sys.exit(0)

# load YAML test file

snapName = sys.argv[1]

with open('./.github/workflows/build.yml', 'r') as testFile:
    testData = yaml.load(testFile, yaml.CLoader)

job = testData['jobs']['testing']
snapList = job['strategy']['matrix']['snapname']
snapParams = job['strategy']['matrix']['include']

if snapName not in snapList:
    print(f'Error: the snap "{snapName}" is not in the test list')
    sys.exit(-1)

params = {}
for param in snapParams:
    if param['snapname'] == snapName:
        params = param
        break

correspondences = {
    'snapname': 'TEST_SNAPNAME',
    'waittext': 'TEST_WAITTEXT',
    'commandname': 'TEST_COMMAND_NAME',
    'enablex11': 'TEST_DO_ENABLE_X11',
    'separated': 'TEST_DO_SEPARATED',
    'timeout': 'TEST_TIMEOUT',
    'connections': 'TEST_IFACE_CONNECTIONS'
}

test_script_path = './test.sh'

with open(test_script_path, "w") as test_script:
    test_script.write('#!/bin/bash\n\n')

    for step in job['steps']:
        if 'run' not in step:
            continue
        if step['name'] == 'Test application':
            continue
        for line in step['run'].split('\n'):
            if line.find('steps.download-snap.outputs.download-path') != -1:
                continue
            test_script.write(line + '\n')
        test_script.write('\n')
    for param in correspondences:
        if param in params:
            test_script.write(f'export {correspondences[param]}="{params[param]}"\n')
        else:
            test_script.write(f'export {correspondences[param]}=""\n')
    test_script.write(f'./.github/workflows/test_script.sh\n')
    test_script.write(f'cp -a ~/snap/yarf/common/yarf-outdir .')

os.chmod(test_script_path, 0o755)
run_command_inside(test_script_path)
