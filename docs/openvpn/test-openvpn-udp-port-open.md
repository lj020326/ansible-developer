
# Connectivity testing with openvpn

To test if the udp port 1194 is open/listening:

```shell
$ nc -z -v -u 192.168.10.12 1194
Connection to 192.168.10.12 1194 port [udp/openvpn] succeeded!
```

## Reference

- https://www.quora.com/Can-we-Telnet-UDP-port
- 