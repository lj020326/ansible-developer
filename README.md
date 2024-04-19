
# ansible developer - repo for ansible developer to use to stand up developer environment

This is the repo for ansible developers to use for setting up the developer toolchain, including bash environment, python virtualenv, ansible-execution environment build/test scripts/tools, etc.

## Initial setup

### Setup .vault_pass for all ansible encrypt/decryption required for running all local CLI ansible-playbook development/testing

```shell
$ echo "vaultpasswordhere" > ~/.vault_pass
## make sure only readable by the owner
$ chmod 600 ~/.vault_pass
```

### Run the latest install script from shell

For install from public github: 

```shell
$ INSTALL_REMOTE_SCRIPT="https://raw.githubusercontent.com/lj020326/ansible-developer/main/install-ansibledev.sh" && bash -c "$(curl -fsSL ${INSTALL_REMOTE_SCRIPT})"
```

For install from internal/private source:

```shell
$ INSTALL_REMOTE_SCRIPT="https://raw.githubusercontent.com/lj020326/ansible-developer/main/install-ansibledev-pvt.sh" && bash -c "$(curl -fsSL ${INSTALL_REMOTE_SCRIPT})"
```

Or if the repo has already been cloned just use the local install script to do the same:
```shell
$ bash install-ansibledev-local.sh
```

The installer shell script will:
1) create the local developer repo directory under $HOME/repos/ansible
2) clone the repo into the developer's local repo directory at $HOME/repos/ansible/ansible-developer
3) setup/synchronize the developer's bash environment with source bash files located in `files/scripts/bashenv`
4) source the bash env

#### Using msys2 and experiencing issue with git clone issue and `ssh`

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

Reference: https://stackoverflow.com/questions/33942924/how-to-change-home-directory-and-start-directory-on-msys2

### Test environment after installing

```shell
ljohnson@Lees-MBP:[ansible-developer](main)$ . ~/.bashrc
## or alias '.bash' does same
ljohnson@Lees-MBP:[ansible-developer](main)$ .bash
ljohnson@Lees-MBP:[ansible-developer](main)$
ljohnson@Lees-MBP:[ansible-developer](main)$ which python3
~/.pyenv/shims/python3
ljohnson@Lees-MBP:[ansible-developer](main)$ python3 -V
Python 3.11.6
ljohnson@Lees-MBP:[ansible-developer](main)$ 
ljohnson@Lees-MBP:[ansible-developer](main)$ which ansible
~/.pyenv/shims/ansible
ljohnson@Lees-MBP:[ansible-developer](main)$ ansible --version
ansible [core 2.16.2]
  config file = None
  configured module search path = ['/Users/ljohnson/.ansible/plugins/modules', '/usr/share/ansible/plugins/modules']
  ansible python module location = /Users/ljohnson/.pyenv/versions/3.11.6/lib/python3.11/site-packages/ansible
  ansible collection location = /Users/ljohnson/.ansible/collections:/usr/share/ansible/collections
  executable location = /Users/ljohnson/.pyenv/versions/3.11.6/bin/ansible
  python version = 3.11.6 (main, Jan 18 2024, 13:13:46) [Clang 15.0.0 (clang-1500.0.40.1)] (/Users/ljohnson/.pyenv/versions/3.11.6/bin/python3.11)
  jinja version = 3.1.3
  libyaml = True
ljohnson@Lees-MBP:[ansible-developer](main)$ 
ljohnson@Lees-MBP:[ansible-developer](main)$ echo $ANSIBLE_PRIVATE_AUTOMATION_HUB_TOKEN
<sensitive-data-here>
ljohnson@Lees-MBP:[ansible-developer](main)$ 
```

### Check that local copy of `ansible-developer` repo exists

```shell
ljohnson@Lees-MBP:[ansible-developer](main)$ cd ~/repos/ansible/
ljohnson@Lees-MBP:[ansible]$ ll
total 0
drwxr-xr-x. 3 ljohnson domain users  31 Jan 23 15:35 ./
drwxr-xr-x. 3 ljohnson domain users  21 Jan 23 15:35 ../
drwxr-xr-x. 5 ljohnson domain users 154 Jan 23 15:35 ansible-developer/
ljohnson@Lees-MBP:[ansible]$ cd ~
ljohnson@Lees-MBP:[~]$ cd ~/repos/ansible-developer/
## 'cddev' alias does the same
ljohnson@Lees-MBP:[~]$ cddev
ljohnson@Lees-MBP:[ansible-developer](main)$ 
ljohnson@Lees-MBP:[ansible-developer](main)$ git remote -v
origin	git@github.com:lj020326/ansible-developer.git (fetch)
origin	git@github.com:lj020326/ansible-developer.git (push)
ljohnson@Lees-MBP:[ansible-developer](main)$ 
ljohnson@Lees-MBP:[ansible-developer](main)$ ll
total 28
drwxr-xr-x. 5 ljohnson domain users   154 Jan 23 15:35 ./
drwxr-xr-x. 3 ljohnson domain users    31 Jan 23 15:35 ../
drwxr-xr-x. 2 ljohnson domain users    53 Jan 23 15:35 docs/
drwxr-xr-x. 5 ljohnson domain users    45 Jan 23 15:35 files/
drwxr-xr-x. 8 ljohnson domain users   179 Jan 23 15:35 .git/
-rw-r--r--. 1 ljohnson domain users   334 Jan 23 15:35 .gitignore
lrwxrwxrwx. 1 ljohnson domain users    49 Jan 23 15:35 install-ansibledev-local.sh -> files/scripts/ansible/install-ansibledev-local.sh
-rwxr-xr-x. 1 ljohnson domain users 10091 Jan 23 15:35 install.sh*
-rw-r--r--. 1 ljohnson domain users 10316 Jan 23 15:35 README.md
lrwxrwxrwx. 1 ljohnson domain users    37 Jan 23 15:35 sync-bashenv.sh -> files/scripts/sync-bashenv.sh*
ljohnson@Lees-MBP:[ansible-developer](main)$ 

```

## To enhance/develop the ansible-developer repo

### Clone the dev repo 

```shell
$ git clone git@github.com:lj020326/ansible-developer.git 
$ git checkout -b "develop-[developer-initials-here]"
## make enahncements/modification
$ git add .
$ git commit -m 'enhancements'
$ git push -u origin develop-[developer-initials-here]
```

### Copy the developer bash environment (Config-as-code in developer-repo in developer-specific branch ) 

The developer bash environment assumes you are working in one of the following platforms/os-environments:
1) MacOS bash
2) Windows msys2/cygwin bash (preference is msys2)
3) Linux bash

```shell
ljohnson@Lees-MBP:[ansible-developer](~)$ cddev
ljohnson@Lees-MBP:[ansible-developer](main)$ git switch "develop-[developer-initials-here]"
ljohnson@Lees-MBP:[ansible-developer](develop-lj)$ cp -p files/scripts/bashenv/.bash* ~/ 
```

### Source the bash env

```shell
ljohnson@Lees-MBP:[ansible-developer](main)$ . ~/.bashrc
## or alias '.bash' does same if the ansible-developer env was already loaded 
## and want to reload latest env/alias/function definitions
ljohnson@Lees-MBP:[ansible-developer](main)$ .bash
ljohnson@Lees-MBP:[ansible-developer](main)$
```


### Alias for synchronization/reloading of the developer bash env

Assuming your environment variable `ANSIBLE_DEVELOPER_REPO` is setup as defined in this repo with the corresponding location of this repo at `~/repos/ansible/ansible-developer`, the `syncbashenv` alias will:

1. Performs rsync of git repo developer branch bash environment defintion to the local ~/.bash*
2. un-vaults the ./files/vault/.bash_secrets and rsyncs to ~/.bash_secrets (--vault-password-file "${HOME_DIR}/.vault_pass")
3. re-runs the sourcing of the ~/.bashrc after sync

```shell
$ syncbashenv
```

```
## view syncbashenv definition
$ alias syncbashenv
alias syncbashenv='${ANSIBLE_DEVELOPER_REPO}/sync-bashenv.sh && . ~/.bashrc'
$ 
```

Where `ANSIBLE_DEVELOPER_REPO` is set on the `~/.bash_env` as

```shell
...
ANSIBLE_DEVELOPER_REPO=$HOME/repos/ansible/ansible-developer
...
```

### Edit the files/git/ config files to specify developer ssh key configs as needed

This is used for all git ssh related aliases/functions

## Use ansible-setup-env.sh to install ansible with pyenv

ref: https://www.buildahomelab.com/2022/04/26/how-to-install-ansible-with-pipenv-pyenv/

### Brief inventory of aliases / functions available to developer in bash environment

```shell
### ALIASES
cagetpwd ## get ca pwd for user defined in env var $CYBERARK_ACCOUNT_USERNAME
syncbashenv  ## perform rsync from repo/files/scripts/bashenv/.bash* to $HOME/ and copy encrypted .bash_secrets to ~/

getsitecertinfo ## pass the site endpoint to get site ssl cert info (e.g., 'getsitecertinfo somesite.example.com 443') 

ll
la
lld
lll

cdrepos
cddocs
cdtechdocs

cddocker
cdjenkins
cdnode
cdpython
cdansible
cddc
cddev
cdkube
cdmeteor
cdreact
cdjava
cdcpp
cdblog
cdk8s
cdkolla
cdpyutils

.bash
.k8sh

gitpullsub
gitmergesub
gitresetsub
gitgetcomment
gitgetrequestid
gitpullrebase
gitmerge
gitmergemain
gitpulltheirs
gitlog
gitgraph
gitgraphall
gitrebase
gitrewind
gitcleanupoldlocal
gitaddorigin
gitsetupstream

sshtestd1s1
sshtestd2s1
sshtestd3s1
sshtestd1s4
sshtestd2s4
sshtestd3s4
sshatrnextd1s4
sshatrup1s4
sshntpq1s1
sshntpq1s4
sshawxtest
sshawxprod
sshawxp1s1
sshawxp1s4
sshawxp2s1
sshawxp2s4

mountwork
unmountwork

vaultdecrypt
vaultencrypt

venv ## create local venv in directory $pwd/.venv
.venv ## source local venv in directory $pwd/.venv

### FUNCTIONS
blastit  ## git pull && git add . && git commit -m "$(getgitcomment)" && git push
cagetaccountpwd
certinfo
change-commit-msg
create-git-project
dockerbash
explodeansibletest
get-certs
get-largest-docker-image-sizes

getbranchhist
getgitcomment ## create a git comment prefixed with getgitrequestid() result and based on the changes 
getgitrequestid ## extract git comment prefix based on regex of branch

gitbranchdelete
gitcommitpush
gitmergebranch
gitpull
gitpullrebase
gitpush
gitreinitrepo
gitremovecached
gitsetupstream
gitshowupstream
gitupdatesub
sshpacker
sshpackerwork
sshpackerwork

```

## Alias / Function

### `blastit` function -- maybe a better name would be `git_pacp` ;)

This is wrapper for `git pull && git add . && git commit -m "$(getgitcomment)" && git push`

```shell
[ansible-developer](main)$ blastit
From github.com:lj020326/ansible-developer
 * branch            main       -> FETCH_HEAD
Already up to date.
Staging changes:
Committing changes:
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
Everything up-to-date
[ansible-developer](main)$

```

### `syncbashenv` function

```shell
[ansible-developer](main)$ syncbashenv
**********************************
*** installing bashrc         ****
**********************************
==> SCRIPT_DIR=/Users/ljohnson/repos/ansible/ansible-developer
==> SCRIPT_BASE_DIR=/Users/ljohnson/repos/ansible/ansible-developer/files/scripts
==> BASHENV_DIR=/Users/ljohnson/repos/ansible/ansible-developer/files/scripts/bashenv
==> HOME=/Users/ljohnson
==> PROJECT_DIR=/Users/ljohnson/repos/ansible/ansible-developer
==> PRIVATE_DIR=/Users/ljohnson/repos/ansible/ansible-developer/files/private/env
From bitbucket.org:lj020326/ansible-developer
 * branch            main       -> FETCH_HEAD
Already up to date.
==> rsync -arv --update --exclude=.idea --exclude=.git --exclude=venv --exclude=save --backup --backup-dir=/Users/ljohnson/.bash-backups /Users/ljohnson/repos/ansible/ansible-developer/files/scripts/bashenv/ /Users/ljohnson/
sending incremental file list

sent 201 bytes  received 12 bytes  426.00 bytes/sec
total size is 54,748  speedup is 257.03
==> rsync private env scripts
sending incremental file list

sent 303 bytes  received 19 bytes  644.00 bytes/sec
total size is 57,904  speedup is 179.83
==> rsync private env configs
sending incremental file list

sent 72 bytes  received 12 bytes  168.00 bytes/sec
total size is 177  speedup is 2.11
==> rsync private env git configs
sending incremental file list

sent 83 bytes  received 12 bytes  190.00 bytes/sec
total size is 1,646  speedup is 17.33
==> rsync env scripts
sending incremental file list

sent 115 bytes  received 22 bytes  274.00 bytes/sec
total size is 66,253  speedup is 483.60
sending incremental file list

sent 86 bytes  received 19 bytes  210.00 bytes/sec
total size is 216  speedup is 2.06
sending incremental file list

sent 163 bytes  received 22 bytes  370.00 bytes/sec
total size is 65,260  speedup is 352.76
==> deploying secrets /Users/ljohnson/repos/ansible/ansible-developer/files/private/vault/bashenv/.bash_secrets
sending incremental file list

sent 72 bytes  received 19 bytes  182.00 bytes/sec
total size is 32,365  speedup is 355.66
.bashrc configuring shell env...
.bashrc PLATFORM=[DARWIN]
.bashrc setting functions
.bash_functions configuring shell functions...
.bashrc sourcing .bash_env
.bash_env setting path for DARWIN env
.bash_env more PATH env var updates
.bash_env PATH=.:/Users/ljohnson/.local/bin:/Users/ljohnson/bin:/usr/local/Cellar/pyenv-virtualenv/1.2.1/shims:/Users/ljohnson/.pyenv/shims:/usr/local/opt/coreutils/libexec/gnubin:/usr/local/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Applications/Visual Studio Code.app/Contents/Resources/app/bin:/opt/podman/bin
.bashrc sourcing .bash_path
.bashrc sourcing ~/.bash_secrets
.bashrc setting prompt
.bash_prompt configuring bash prompt...
 setting aliases
.bash_aliases configuring shell aliases...
.bash_aliases setting aliases for DARWIN env
[ansible-developer](main)$ 
```

### `cagetpwd` function to get cyberark password using api

```shell
[ansible-developer](main)$ cagetpwd
CA_ACCOUNT_PWD=",sdkjfh;kewl4j<"
```

The alias/function definition above assumes/requires the developer to have configured the following env vars in the vaulted file at './files/private/vault/bashenv/.bash_secrets':
```shell
export CYBERARK_API_ENDPOINT="cyberarkpas.example.int"
export CYBERARK_API_BASE_URL="https://${CYBERARK_API_ENDPOINT}"
export CYBERARK_API_USERNAME="ca-user-account"
export CYBERARK_API_PASSWORD="ca-password"
## e.g., 'leej'
export CYBERARK_ACCOUNT_USERNAME="ca-user-safe-account-name"
```

### ssh aliases

The following alias definitions assume that the developer has already added the necessary ssh public key to the target linux host user ssh authorized  keys configuration file at '${HOME}/.ssh/authorized_keys':

```shell
[ansible-developer](main)$ sshtestd1s1
Last login: Sun Oct 22 15:35:57 2023 from 172.31.0.190
DEV  [ljohnson@testlinuxd1s1 ~]$ 
DEV  [ljohnson@testlinuxd1s1 ~]$ exit

[ansible-developer](main)$ sshtestd1s4
Activate the web console with: systemctl enable --now cockpit.socket

Last login: Fri Oct 27 15:00:19 2023 from 172.21.1.76
[ljohnson@testlinuxd1s4 ~]$ 
DEV  [ljohnson@testlinuxd1s1 ~]$ exit
[ansible-developer](main)$ 

```
