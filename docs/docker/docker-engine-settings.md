
~/.docker/daemon.json:
```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "cgroup-parent": "docker.slice",
  "debug": true,
  "dns": [
    "10.0.0.1"
  ],
  "experimental": false,
  "insecure-registries": [
    "media.johnson.int:5000",
    "admin.dettonville.int:5000"
  ],
  "registry-mirrors": [
    "https://media.johnson.int:5000",
    "https://admin.dettonville.int:5000"
  ]
}
```


You can put your client certificates in `~/.docker/certs.d/<MyRegistry>:<Port>/client.cert` and `~/.docker/certs.d/<MyRegistry>:<Port>/client.key`.

When the Docker for Mac application starts up, it copies the `~/.docker/certs.d` folder on your Mac 
to the `/etc/docker/certs.d` directory on Moby (the Docker for Mac `xhyve` virtual machine).

-   You need to restart Docker for Mac after making any changes to the keychain or to the `~/.docker/certs.d` directory in order for the  
    changes to take effect.
-   The registry cannot be listed as an insecure registry (see [Docker Engine](https://docs.docker.com/desktop/mac/#docker-engine)). 
    Docker for Mac will ignore certificates listed under insecure registries, and will not send client certificates. 
    Commands like docker run that attempt to pull from the registry will produce certificate error messages on the command line, as well as on the registry.


## References

- https://stackoverflow.com/questions/40822912/where-to-add-client-certificates-for-docker-for-mac#51982684
- https://docs.docker.com/desktop/faqs/windowsfaqs/#how-do-i-add-client-certificates
- https://stackoverflow.com/questions/72894189/docker-buildx-build-failing-when-referring-repo-with-tls-certificate-signed-wi
- https://docs.docker.com/desktop/get-started/#add-client-certificates
- 
