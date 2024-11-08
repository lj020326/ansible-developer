
# sshd notes

## How to display active/run-time sshd config information

To display active/run-time sshd config information:

```shell
$ sshd -T
$ sshd -T | grep -i kexalgorithms
$ sshd -T | grep -i hostkeyalgorithms
$ sshd -T | grep -i ciphers
```

Can also validate the config from the client:

```shell
$ ssh -G administrator@vcontrol01.johnson.int | grep -i kexalgorithms
$ ssh -G administrator@vcontrol01.johnson.int | grep -i hostkeyalgorithms
$ ssh -G administrator@vcontrol01.johnson.int | grep -i ciphers
```


ref: https://serverfault.com/questions/717129/how-to-show-the-host-configured-default-ssh-configuration

## How to resolve 'Server does not support diffie-hellman-group1-sha1 for keyexchange'

When attempt to ssh connect the response is:

```
ssh: Server does not support diffie-hellman-group1-sha1 for keyexchange
```

Here is the solution:

1.  Enable the correct Kex:

```
sudo nano /etc/ssh/sshd_config
```

append with these lines to ensure correct digest:

```
KexAlgorithms diffie-hellman-group1-sha1,curve25519-sha256@libssh.org,ecdh-sha2-nistp256,ecdh-sha2-nistp384,ecdh-sha2-nistp521,diffie-hellman-group-exchange-sha256,diffie-hellman-group14-sha1
Ciphers 3des-cbc,blowfish-cbc,aes128-cbc,aes128-ctr,aes256-ctr
```

Regenerate all keys:

```
ssh-keygen -A
```

[reference](https://www.howtoforge.com/community/threads/enable-diffie-hellman-group1-sha1-on-jessie.70764/)

and then restart ssh service:

```
sudo service ssh restart
```

After these steps you would need to update your local known_hosts file, as the SSH key has changed. Say, your Digital Ocean droplet IP is 255.255.222.211.

Locate it in ~.ssh/known_hosts and remove the line that begins with this 255.255.222.111.

**In a new shell window test you can connect to your instance!**

Next time you log in you will be asked to add the host to known hosts again.

ref: https://www.digitalocean.com/community/questions/server-does-not-support-diffie-hellman-group1-sha1-for-keyexchange

## How to resolve slow connection

If slow to connect to ssh:

Try the following possible solutions:
1) Set 'UseDNS' to NO in sshd_config and restarting the sshd server.
   ref: https://serverfault.com/questions/432479/ssh-very-slow-when-connecting-from-external


## How to set up SSH Agent on msys2

Fetch our ssh-agent.sh script and wire it up to work with your new MSYS2 install with the following multi-line command:

```
curl -OL https://github.com/OULibraries/msys2-setup/raw/master/ssh-agent.sh && \
chmod +x ssh-agent.sh && \
mv ssh-agent.sh /etc/profile.d/
```

This script checks to make sure that the ssh-agent key manager is running and has access to your keys when you open a new MSYS2 shell. Once you've installed it, quit and restart MSYS2. You should get asked to enter your the passphrase required to uncock the key that you just created, after which your key will be available to ssh.

### [](https://github.com/OULibraries/msys2-setup/blob/master/02-ssh.md#set-up-your-ssh-key-at-github)

How to cleanup duplicate host keys on server and client:
	ref: https://unix.stackexchange.com/questions/338535/how-to-clear-duplicated-entries-in-ssh-known-hosts-and-authorized-keys-files

	on server:
		sort ~/.ssh/authorized_keys | uniq > ~/.ssh/authorized_keys.uniq
		## then replace the old file with the new one:
		mv ~/.ssh/authorized_keys{.uniq,}

	on client:
		sort ~/.ssh/known_hosts | uniq > ~/.ssh/known_hosts.uniq
		## then replace the old file with the new one:
		mv ~/.ssh/known_hosts{.uniq,}

	Another option where host has multiple keys:

	```
	cat known_hosts | cut -f1 -d' ' | sort | uniq -c | \ 
	sed '/^ *1 /d' | awk '{print $2}' | while read line; do \
	ssh-keygen -R $line; ssh-keyscan $line; \
	done
	```


How to run ssh proxy to access private server:


	ssh -L 8888:192.168.1.254:80 administrator@admin01.dettonville.int


	ref: https://www.howtogeek.com/168145/how-to-use-ssh-tunneling/

	Local Port Forwarding: Make Remote Resources Accessible on Your Local System

	Local port forwarding allows you to access local network resources that aren’t exposed to the Internet. 
	For example, let's say you want to access a database server at your office from your home. 

	To use local forwarding, connect to the SSH server normally, but also supply the -L argument. The syntax is:

		ssh -L local_port:remote_address:remote_port username@server.com
	
	For example, lets say the database server at your office is located at 192.168.1.111 on the office network. 
	You have access to the offices SSH server at ssh.youroffice.com, and your user account on the SSH server is bob . 
	In that case, your command would look like this:

		ssh -L 8888:192.168.1.111:1234 bob@ssh.youroffice.com

	After running that command, youd be able to access the database server at port 8888 at localhost. 
	So, if the database server offered web access, you could plug http://localhost:8888 into your web browser to access it. 



	ref: https://www.systutorials.com/proxy-using-ssh-tunnel/
		
	We can access a sshd server sshd_server and we want to use it as a socks5 proxy server. 
	It is simple by using ssh:

		ssh -D 8080 username@sshd_server

	or, to allow remote hosts to use the socks5 proxy too,

		ssh -g -D 8080 username@sshd_server
	

	To scp/ssh through jump server:

		https://www.golinuxcloud.com/ssh-proxy/


How to store public ssh key in openldap:

	http://pig.made-it.com/ldap-openssh.html#29273


How to use password in commandline with ssh:

	ref: https://serverfault.com/questions/241588/how-to-automate-ssh-login-with-password

	sudo apt-get install sshpass
	sshpass -p your_password ssh user@hostname

How to install sshpass on macOS:

	## https://bitsanddragons.wordpress.com/2021/05/27/avoid-typing-ssh-passwords-with-sshpass-on-macos/
	## https://gist.github.com/arunoda/7790979
	
	brew install hudochenkov/sshpass/sshpass
	
	
To turn off strict host key checking:

	https://askubuntu.com/questions/87449/how-to-disable-strict-host-key-checking-in-ssh

	ssh -o StrictHostKeyChecking=no yourHardenedHost.com

How to use password in commandline with ansible ssh:

	ref: https://stackoverflow.com/a/51966833/2791368

	instead of using the connection ssh like below,

		$ansible-playbook -i hosts -v -b -c ssh --ask-pass myplaybook.yml

	you can use

		$ansible-playbook -i hosts -v -b -c paramiko --ask-pass myplaybook.yml

	Yet another way is to set it as a playbook option, 

		connection: paramiko_ssh

Useful symptom / resolutions checklist:

	https://support.ehelp.edu.au/support/solutions/articles/6000149723-troubleshooting-ssh-access-to-a-nectar-instance
	https://www.tecmint.com/enable-debugging-mode-in-ssh/

	To enable verbose:

		ssh -v admin@192.168.56.10

	Next, you can enable additional (level 2 and 3) verbosity for even more debugging messages as shown.

		ssh -vv admin@c192.168.56.10
		ssh -vvv admin@c192.168.56.10

Reset ssh key:

	```
	SSH_HOST=ubuntu.johnson.local
	echo $SSH_HOST
	ssh-keygen -R $SSH_HOST ; ssh-keyscan -H $SSH_HOST
	```

	Example:

	```
	Lee@LJLAPTOP:[ansible-datacenter](master)$ ssh-keygen -R 192.168.0.221
	# Host 192.168.0.221 found: line 85
	/home/Lee/.ssh/known_hosts updated.
	Original contents retained as /home/Lee/.ssh/known_hosts.old
	
	Lee@LJLAPTOP:[ansible-datacenter](master)$ ssh-keyscan -H 192.168.0.221
	|1|Ys9s03+muLyE9nyw8BDSGv/ZBtA=|Lytm5odOP/IljfyWjZe8ij3lDc0= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIP1l49xh08lYFjeHS/72FbZix1uRGODH+RKUSfQwtQ9s
	# 192.168.0.221:22 SSH-2.0-OpenSSH_8.2p1 Ubuntu-4
	|1|LF/H9G/EuUzOqPLcplamo59KI4o=|hPwiMAiGOm7xxbJpUI8mtk1sCYE= ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDHiCx84qnjrHIPxr5p1Ub6t+wH2HUVZ0qJVneMErNczW+t0+JTgQDBZJsGrBGd5obr8CteRJCoTg4g49pc4wjU/C0gSE9MObZ7BQ4jYYVwxjIa7IWBj1sRFQlqYUB8M6Q3yHdvVIH3Lv4hTxTzyoyuWSgvgAvq+1TFz17ya7iHOwL0Y00KM02jk1LfY4oOczxAE64vIG3NlStxACfrUpllBdVBCol25+3mHba4KARMS/ftsuUKolYsKRcFs/K+z4tBrZ7CjTrRw06XapacEoHxTi8QiXlL6fkqw4H2i5iF5gObY36f95y24uuJE6xeFWUh5r53uuGnbXC1G4skozuz2ax2xBaK8vLrn4qYtreCGA00SGBi8DiklNyCU/pMRaG9HWbDO140xc/ht70pGiFtP7rh+73Gb5j0whvCpjHvJkmoDaOIPi2CLtBEfPsU+sE/utfBBl6YLT3DuJCxOD3A/VAjr/3Nskpln4oL1w0dzLHScksDgdwLaFnxFlPgbp0=
	# 192.168.0.221:22 SSH-2.0-OpenSSH_8.2p1 Ubuntu-4
	|1|mv/TJXFVrsb1a7zeHWaJcxPlFyA=|szZ223+ZHhUgguO/yQyvmvE+ty8= ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBHSWGSxXQsTXOTg6DnFdwrbYBeH/YptKpOTaSYINv9sopurOklx7lt5XaC4CN5vrMjtyQUbbcWnwTPiJsEZZDe4=
	# 192.168.0.221:22 SSH-2.0-OpenSSH_8.2p1 Ubuntu-4
	# 192.168.0.221:22 SSH-2.0-OpenSSH_8.2p1 Ubuntu-4
	Lee@LJLAPTOP:[ansible-datacenter](master)$
	```

