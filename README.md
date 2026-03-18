# GNOME-SDK

This snap contains the SDK to build Gtk/Gnome-based snaps.

## Setting disk size

This snap requires quite a lot of disk space, so the default value for LXD in
snapcraft may be not enough. To change it, just run:

    lxc storage --project snapcraft device set default size=100GB

This command increases the pool size for virtual disks to 100GB. Thus, the
maximum total size for virtual disks in snapcraft will be of that size.

    lxc profile --project snapcraft device set default root size=25GB

This command increases the maximum disk size for each container to 25GB.

## Clonning the repository

There are several versions of the SDK, so a differen branch is used for each one:

Core22/Gnome-42-2204:

    git clone -b gnome-42-2204-sdk https://github.com/ubuntu/gnome-sdk.git gnome-42-2204-sdk

Core24/Gnome-46-2404:

    git clone -b gnome-46-2404-sdk https://github.com/ubuntu/gnome-sdk.git gnome-46-2404-sdk
