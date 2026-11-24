#!/usr/bin/env bash

# mount the drive as read/write
mount -rw /

# create a directory for "disabled" extensions
mkdir -p "/Volumes/MAC HD/Library/ExtensionsDisabled"

# view files that exist in your Extensions folder but not the recovery partition
kexts=$(comm -23 \
    <(find "/Volumes/MAC HD/Library/Extensions" -maxdepth 1 -mindepth 1 -exec basename {} \; | sort) \
    <(find "/Library/Extensions" -maxdepth 1 -mindepth 1 -exec basename {} \; | sort))
echo "kexts=${kexts}"

# move "extra" kext files to the "disabled" directory
for kext in $kexts; do
    mv "/Volumes/MAC HD/Library/Extensions/${kext}" "/Volumes/MAC HD/Library/ExtensionsDisabled/${kext}"
done

exit
