
# upgrade to 2.7.2 from 2.7.0 failed-install: No space left on device

## Problem / Issue

Tried to upgrade from 2.7.0->2.7.2 from the GUI, and it failed with: "install: //boot/efi/efi/boot/INS@XSQmlE: No space left on device"  
My drive is showing 447GB free 6GB used.

Here is a copy and paste from the upgrade log to window:

```shell
Installed packages to be UPGRADED:  
pfSense-boot: 2.7.0 -> 2.7.2 \[pfSense-core\]

Number of packages to be upgraded: 1  
\[1/1\] Upgrading pfSense-boot from 2.7.0 to 2.7.2...  
\[1/1\] Extracting pfSense-boot-2.7.2: .......... done  
Updating the EFI loader  
install: //boot/efi/efi/boot/INS@XSQmlE: No space left on device  
pkg-static: POST-INSTALL script failed  
failed.  
Failed
```

## Solution

If it's a VM, snapshot it before proceeding.

Assuming your EFI partition is `/dev/msdosfs/EFISYS`, this should work. If it's not, substitute in the proper path (e.g. `/dev/gpt/EFISYS` or maybe `/dev/vtbd0p1` for example.)

```shell
$ mkdir -p /boot/efi
$ mount_msdosfs /dev/msdosfs/EFISYS /boot/efi
$ mkdir -p /tmp/efitmp
$ cp -Rp /boot/efi/* /tmp/efitmp
$ umount /boot/efi
$ newfs_msdos -F 32 -c 1 -L EFISYS /dev/msdosfs/EFISYS
$ mount_msdosfs /dev/msdosfs/EFISYS /boot/efi
$ cp -Rp /tmp/efitmp/* /boot/efi/
```

Afterwards you should have an EFI filesystem that is the full size of the partition, which is roughly 200M.

The upgrade should proceed after that.

If it doesn't work, roll back or reinstall. You never saw this post. That torpedo did not self-destruct. You heard it hit the hull. I was never here.

## References

- https://forum.netgate.com/topic/184661/unable-to-upgrade-from-2-7-1-to-2-7-2-unmounting-boot-efi-done-failed/23
- https://forum.netgate.com/post/1140955
- https://forum.netgate.com/topic/185037/upgrade-to-2-7-2-from-2-7-0-failed-install-no-space-left-on-device
- 
