
# Notes

```shell
docker ps | grep james | awk '{print $1}'
docker exec -ti $(docker ps | grep james | awk '{print $1}') james-cli AddUser ljohnson@dettonville.cloud password123
docker exec -ti $(docker ps | grep james | awk '{print $1}') james-cli ListUsers
docker exec -ti $(docker ps | grep james | awk '{print $1}') james-cli ListDomains
```

Bash into the james container
```shell
docker exec -ti $(docker ps | grep james | awk '{print $1}') /bin/bash
```
