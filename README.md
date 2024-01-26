
# ansible developer - repo for ansible developer to use to stand up developer environment

This is the repo for ansible developers to use for setting up the developer toolchain, including bash environment, python virtualenv, ansible-execution environment build/test scripts/tools, etc.

## Initial setup

### Setup .vault_pass for all ansible encrypt/decryption required for running all local CLI ansible-playbook development/testing

```shell
$ echo "vaultpasswordhere" > ~/.vault_pass
$ git clone 
```

### Run the latest install script from shell

```shell
$ INSTALL_REMOTE_SCRIPT="https://raw.githubusercontent.com/lj020326/ansible-developer/main/install.sh" && bash -c "$(curl -fsSL ${INSTALL_REMOTE_SCRIPT})"
```

### Test environment after installing

```shell
$ ssh ${WORK_USER_ID}@ansutilp1s4${WORK_DOMAIN}
\S
Kernel \r on an \m
Activate the web console with: systemctl enable --now cockpit.socket

Last login: Tue Jan 23 15:25:44 2024 from 172.31.0.191
.bashrc configuring shell env...
.bash_functions configuring shell functions...
.bashrc sourcing .bash_env
.bash_env setting path for LINUX/Other env
.bash_env more PATH env var updates
.bash_env PATH=.:${HOME}/.pyenv/plugins/pyenv-virtualenv/shims:${HOME}/.pyenv/shims:${HOME}/.pyenv/bin:${HOME}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
.bashrc sourcing ~/.bash_secrets
.bashrc setting prompt
.bash_prompt configuring bash prompt...
 setting aliases
.bash_aliases configuring shell aliases...
ljohnson@Lees-MBP:[ansible-developer](main)$
ljohnson@Lees-MBP:[ansible-developer](main)$
ljohnson@Lees-MBP:[ansible-developer](main)$ which python3
~/.pyenv/shims/python3
ljohnson@Lees-MBP:[ansible-developer](main)$ python3 -V
Python 3.9.16
ljohnson@Lees-MBP:[ansible-developer](main)$ 
ljohnson@Lees-MBP:[ansible-developer](main)$ which ansible
~/.pyenv/shims/ansible
ljohnson@Lees-MBP:[ansible-developer](main)$ ansible --version
ansible [core 2.15.8]
  config file = /etc/ansible/ansible.cfg
  configured module search path = ['${HOME}/.ansible/plugins/modules', '/usr/share/ansible/plugins/modules']
  ansible python module location = ${HOME}/.pyenv/versions/3.9.16/lib/python3.9/site-packages/ansible
  ansible collection location = ${HOME}/.ansible/collections:/usr/share/ansible/collections
  executable location = ${HOME}/.pyenv/versions/3.9.16/bin/ansible
  python version = 3.9.16 (main, Jan 23 2024, 13:14:47) [GCC 8.5.0 20210514 (Red Hat 8.5.0-18)] (${HOME}/.pyenv/versions/3.9.16/bin/python3.9)
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
ljohnson@Lees-MBP:[ansible]$ cd ansible-developer/
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
$ git push -u origin develop-[developer-initials-here]
```

### Copy the developer bash environment (Config-as-code in developer-repo in developer-specific branch ) 

The developer bash environment assumes you are working in one of the following platforms/os-environments:
1) MacOS bash
2) Windows msys2/cygwin bash (preference is msys2)
3) Linux bash

```shell
$ cd $PROJECT_DIR
$ git switch "develop-[developer-initials-here]"
$ cp -p files/scripts/bashenv/.bash* ~/ 
```

### Source the bash env

```shell
. ~/.bashrc
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

## Use ansible-setup-env.sh to install ansible with pipenv

ref: https://www.buildahomelab.com/2022/04/26/how-to-install-ansible-with-pipenv-pyenv/

### Brief inventory of aliases / functions available to developer in bash environment

```shell
### ALIASES
cagetpwd ## get ca pwd for user defined in env var $CYBERARK_ACCOUNT_USERNAME
syncbashenv  ## perform rsync from repo/files/scripts/bashenv/.bash* to $HOME/ and copy decrypted .bash_secrets to ~/

getsitecertinfo

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
blastit  ## git pull && git add . && git commit -m getgitcomment() && git push origin CURRENT_BRANCH
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

### `blastit` function -- maybe a better name would be `git_pacp` :)

This is basically a `git pull && git add . && git commit -m "${PREGENERATED_COMMIT_MSG}" && git push`

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
SCRIPT_DIR=[/Users/ljohnson/repos/ansible/ansible-datacenter/files/scripts/bashenv]
HOME_DIR=[/Users/ljohnson]
PROJECT_DIR=[/Users/ljohnson/repos/ansible/ansible-datacenter]
FROM=[/Users/ljohnson/repos/ansible/ansible-datacenter/files/scripts/bashenv/.bash*]
SECRETS_DIR=[/Users/ljohnson/repos/ansible/ansible-datacenter/files/private/env]
rsync -arv --update --exclude=.idea --exclude=.git --exclude=venv --exclude=save --backup --backup-dir=/Users/ljohnson/.bash-backups /Users/ljohnson/repos/ansible/ansible-datacenter/files/scripts/bashenv/.bash* /Users/ljohnson/
sending incremental file list

sent 149 bytes  received 12 bytes  322.00 bytes/sec
total size is 54,872  speedup is 340.82
rsync env scripts
sending incremental file list
ansible-test-integration.sh
install_worksite_cacerts.sh
mount-sshfs-work.sh
sync-dns-hosts-to-pfsense.sh
sync-sshfs-work.sh
unmount-sshfs-work.sh

sent 26,725 bytes  received 130 bytes  53,710.00 bytes/sec
total size is 26,216  speedup is 0.98
sending incremental file list
setup-ssh-key-identities.sh

sent 1,776 bytes  received 35 bytes  3,622.00 bytes/sec
total size is 1,646  speedup is 0.91
sending incremental file list

sent 222 bytes  received 19 bytes  482.00 bytes/sec
total size is 8,220  speedup is 34.11
sending incremental file list

sent 838 bytes  received 85 bytes  1,846.00 bytes/sec
total size is 78,948  speedup is 85.53
sending incremental file list

sent 111 bytes  received 22 bytes  266.00 bytes/sec
total size is 66,315  speedup is 498.61
deploying secrets /Users/ljohnson/repos/ansible/ansible-datacenter/files/private/env/.bash_secrets
ansible-vault decrypt /Users/ljohnson/repos/ansible/ansible-datacenter/files/private/env/.bash_secrets --output /Users/ljohnson/.bash_secrets --vault-password-file /Users/ljohnson/.vault_pass
Decryption successful
.bashrc configuring shell env...
platform=[DARWIN]
setting functions
.bash_functions configuring shell functions...
.bashrc sourcing .bash_env
.bash_env PYUTILS_DIR=[/Users/ljohnson/repos/python/pyutils]
.bash_env setting path for DARWIN env
-bash: python: command not found
python_version=[3]
PYTHON_HOME=[/usr/local/bin]
.bash_env more PATH env var updates
.bashrc sourcing .bash_secrets
.bashrc setting prompt
.bash_prompt configuring bash prompt...
.bash_prompt setting aliases
.bash_aliases configuring shell aliases...
.bash_aliases setting aliases for DARWIN env
sync /Users/ljohnson/repos/ansible/ansible-datacenter/files/private/env/git/git-ssh-config.ini to ~/.ssh/config
current ssh key identities
The agent has no identities.
remove ssh key identities
All identities removed.
sync /Users/ljohnson/repos/ansible/ansible-datacenter/files/private/env/git/.gitconfig.home.ini to /Users/ljohnson/.gitconfig
sync /Users/ljohnson/repos/ansible/ansible-datacenter/files/private/env/git/.gitconfig.work.ini to /Users/ljohnson/repos/work/.gitconfig
[ansible-developer](main)$ 
```

### `cagetpwd` function to get cyberark password using api

```shell
[ansible-developer](main)$ cagetpwd
CA_ACCOUNT_PWD=",sdkjfh;kewl4j<"
```

### ssh aliases

These assumes that the developer has already added their ssh public key to the linux hosts `~/.ssh/authorized_keys` 

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
