
# How to reset swarm configuration

Simple method to reset the docker configuration including swarm:

Use your OS's package manager to uninstall the Docker package; then

```bash
rm -rf /var/lib/docker
```

That should completely undo all Docker-related things.

## Remove node from existing swarm

```bash
docker node rm --force swarm-node-03
```

## References

- https://stackoverflow.com/questions/62173586/docker-where-is-reset-to-factory-defaults-on-linux
- https://docs.docker.com/reference/cli/docker/node/rm/
- https://docs.docker.com/reference/cli/docker/node/rm/#force
- 