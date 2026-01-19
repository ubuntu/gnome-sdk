#!/bin/bash

set -eux -o pipefail

export TEST_COMMAND_NAME="${TEST_COMMAND_NAME:-snap run ${TEST_SNAPNAME}}"
# default value for TEST_TIMEOUT: 20 seconds
export TEST_TIMEOUT=${TEST_TIMEOUT:-20}

echo Testing ${TEST_SNAPNAME} with $TEST_COMMAND_NAME and waiting for ${TEST_WAITTEXT}
rm -rf ./testRobot
mkdir ./testRobot

TEST_ROBOT_FILE=./testRobot/app.robot
cat > $TEST_ROBOT_FILE <<EOF
*** Settings ***
Resource        kvm.resource
Library         Process

*** Tasks ***
Do test
EOF
if [[ "${TEST_DO_SEPARATED}" == "true" ]]; then
    for entry in ${TEST_WAITTEXT}; do
    echo "  Match Text    ${entry}    ${TEST_TIMEOUT}" >> ${TEST_ROBOT_FILE}
    export TEST_TIMEOUT=""
    done
    echo "  Sleep    5" >> ${TEST_ROBOT_FILE}
    for entry in ${TEST_WAITTEXT}; do
    echo "  Match Text    ${entry}" >> ${TEST_ROBOT_FILE}
    done
else
    cat >> $TEST_ROBOT_FILE <<EOF
    Match Text    ${TEST_WAITTEXT}    ${TEST_TIMEOUT}
    Sleep    5
    Match Text    ${TEST_WAITTEXT}
EOF
fi
cat >> $TEST_ROBOT_FILE <<EOF
    Keys Combo    Alt_L    F4
    [Teardown]    Run Keyword    Log Screenshot
EOF

echo "Test robot file:"
cat ${TEST_ROBOT_FILE}
sudo snap install ${TEST_SNAPNAME} || echo Snap already installed
# This is needed because the gnome runtime has been installed manually with --dangerous
sudo snap connect ${TEST_SNAPNAME}:gnome-46-2404 gnome-46-2404:gnome-46-2404
for plug in ${TEST_IFACE_CONNECTIONS}; do
    sudo snap connect ${TEST_SNAPNAME}:${plug}
done
sudo /usr/lib/snapd/snap-discard-ns ${TEST_SNAPNAME}
echo Current connections:
snap connections ${TEST_SNAPNAME}
echo

MYUID=$(id -u)
export WAYLAND_DISPLAY=/run/user/${MYUID}/wayland-0
export MIR_SERVER_ADD_WAYLAND_EXTENSIONS=zwlr_screencopy_manager_v1:zwlr_virtual_pointer_manager_v1
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${MYUID}/bus
export LANG=en_US.UTF-8
export XDG_CONFIG_DIRS=/etc/xdg/xdg-ubuntu:/etc/xdg
export XDG_MENU_PREFIX=gnome-
export XDG_SESSION_DESKTOP=ubuntu
export XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=ubuntu:GNOME
export XDG_SESSION_CLASS=user
export XDG_RUNTIME_DIR=/run/user/${MYUID}
export XDG_DATA_DIRS=/usr/share/ubuntu:/usr/share/gnome:/usr/local/share/:/usr/share/:/var/lib/snapd/desktop
export GNOME_SHELL_SESSION_MODE=ubuntu
export GNOME_SETUP_DISPLAY=:1

# use only GTK portal, since mutter isn't running
sudo sed -i -e 's/gnome;gtk;/gtk;/g' /usr/share/xdg-desktop-portal/gnome-portals.conf

# this must be defined after launching the demo server; if not, it won't launch
unset DISPLAY
export ENABLE_X11_PROP=""
if [[ "${TEST_DO_ENABLE_X11}" == "true" ]]; then
    export ENABLE_X11_PROP="--enable-x11=true"
fi

# required to work in a no-DRM environment
export XWAYLAND_NO_GLAMOR=1
mir-test-tools.demo-server --platform-display-libs mir:virtual --virtual-output 1920x1080 ${ENABLE_X11_PROP} &  MIR_PID=$! # starts the demo Mir compositor

counter=0
until wayland-info > /dev/null || (( ${counter} > 30 )); do
    echo waiting for mir server...
    sleep 1
    counter=$((counter+1))
done

if [[ "${TEST_DO_ENABLE_X11}" == "true" ]]; then
    export DISPLAY=:0
    counter=0
    until (( ${counter} > 30 )); do
        timeout 2 xclock || EXIT_CODE=$?
        # 124 is "timeout"
        if (( "EXIT_CODE" == "124" )); then
            # end loop if timed out
            echo XWayland available
            counter=50
        else
            echo Waiting for XWayland to be available
            sleep 1
        fi
        counter=$((counter+1))
    done
    unset WAYLAND_DISPLAY
    export XDG_SESSION_TYPE=x11
fi

echo Launching ${TEST_COMMAND_NAME}
${TEST_COMMAND_NAME} & command_pid=$!

echo Launching YARF
YARF_RETERR=0
APP_RETERR=0
MIR_RETERR=0
yarf --platform Mir ./testRobot || YARF_RETERR=$?

echo Journal
journalctl --user --no-pager

echo Waiting for application to die
# wait up to 10 seconds for the snap to finish.
timeout 10 tail --pid=${command_pid} -f /dev/null || /bin/true

echo killing MIR server
# kill DBus and MIR and wait for it to fully finish.
kill $MIR_PID
wait $MIR_PID

echo Cleaning up
# remove user data, just in case
rm -rf ~/snap/${TEST_SNAPNAME}
sudo snap remove ${TEST_SNAPNAME} || echo Failed to remove the snap
rm -rf ./testRobot
# only fail after cleanup
exit ${YARF_RETERR}
