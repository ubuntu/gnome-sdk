# GNOME-46-2404 runtime

This snap builds the GNOME-46-2404 runtime from the corresponding GNOME-46-2404-SDK
snap.

By default, it will get the SDK from the store, from the CANDIDATE branch; but it is
possible to use a different SDK (for example, one built locally), putting it in the
project root folder, renaming it to `gnome-46-2404-sdk.snap`, and launching the
`local-build.py` script. It will create a new, modified `snapcraft.yaml` file in the,
project's root, clean the snapcraft build environment, build the new snap, and restore
the `snapcraft.yaml` file. This is useful if you do a change in the SDK and want
to test it, to ensure that everything works as expected and nothing breaks.

## Getting the repository

To get the repository, just run:

    git clone -b gnome-46-2404 https://github.com/ubuntu/gnome-sdk.git gnome-46-2404-runtime
