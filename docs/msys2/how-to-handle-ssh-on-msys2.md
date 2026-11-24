
# Using msys2 and `ssh`

## Resolve issue with git clone issue and `ssh`

This is a known issue since ssh uses the msys default user home path and is not sourcing from the windows %USERPROFILE% path.
The [msys2 ssh issue with solution is noted here](https://stackoverflow.com/questions/33942924/how-to-change-home-directory-and-start-directory-on-msys2).

The HOME environment is set correct to the windows %USERPROFILE% path:
```shell
ljohnson@ljlaptop:[~]$ env | grep -i userprofile
USERPROFILE=C:\Users\ljohnson
ljohnson@ljlaptop:[~]$ env | grep -i home
...
HOME=/c/Users/ljohnson
...
ljohnson@ljlaptop:[~]$ INSTALL_REMOTE_SCRIPT="https://raw.githubusercontent.com/lj020326/ansible-developer/main/install-ansibledev-pvt.sh" && bash -c "$(curl -fsSL ${INSTALL_REMOTE_SCRIPT})"
...
==> Downloading and installing ansible-developer repo...
git@bitbucket.org: Permission denied (publickey).
fatal: Could not read from remote repository.

Please make sure you have the correct access rights
and the repository exists.
Failed during: /usr/bin/git fetch --force origin
```

The solution is to enable the msys2 shell to be set to source using the windows user path.
Configure the MSYS2 shell to use your windows home folder by editing `/etc/nsswitch.conf`.

/etc/nsswitch.conf:
```
...
#db_home: cygwin desc
db_home: windows cygwin desc
...
```

## References

- https://stackoverflow.com/questions/33942924/how-to-change-home-directory-and-start-directory-on-msys2
