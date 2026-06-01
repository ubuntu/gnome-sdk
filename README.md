# GNOME-42-2204 runtime

This snap builds the GNOME-42-2204 runtime from the corresponding GNOME-42-2204-SDK
snap.

By default, it will get the SDK from the store, from the CANDIDATE branch; but it is
possible to use a different SDK (for example, one built locally), by creating a folder
called `base-gnome-sdk`, putting it inside, and launching the
`local-build.py` script. It will create a new, modified `snapcraft.yaml` file in the
project's root, clean the snapcraft build environment, build the new snap, and restore
the `snapcraft.yaml` file. This is useful if you do a change in the SDK and want
to test it, to ensure that everything works as expected and nothing breaks.

If the script finds several `snap` files inside the `base-gnome-sdk` folder, it will
use the most recent one, based on the modification time of the file.

Also, if the build must be done by an external script (like when using Github's CI),
then it is possible to call the `local-build.py` script with the `--prepare-only`
parameter. With it, it will just generate the modified `snapcraft.yaml` file in the
project folder, nothing else.

## Getting the repository

To get the repository, just run:

    git clone -b gnome-42-2204 https://github.com/ubuntu/gnome-sdk.git gnome-42-2204

This branch is used to build [the gnome-42-2204 snap](https://launchpad.net/~desktop-snappers/+snap/gnome-42-2204),
which in turn uses the [the gnome-42-2204-sdk snap](https://launchpad.net/~desktop-snappers/+snap/gnome-42-2204-sdk).
