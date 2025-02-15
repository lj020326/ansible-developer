
# Notes on how to resolve cert thumbprint mismatch issues on vcenter

To resolve the issue, perform the following steps in the order outlined

-   Log in to the vCenter Server appliance via shell or SSH
-   Create a temporary directory under root

mkdir /certificate

-   Create a copy of the certificate and key from the vpxd-extension store

```shell
/usr/lib/vmware-vmafd/bin/vecs-cli entry getcert --store vpxd-extension --alias vpxd-extension --output /certificate/vpxd-extension.crt    
/usr/lib/vmware-vmafd/bin/vecs-cli entry getkey --store vpxd-extension --alias vpxd-extension --output /certificate/vpxd-extension.key
```

-   Update the service endpoint using the vpxd-extension certificate

```shell
python /usr/lib/vmware-vpx/scripts/updateExtensionCertInVC.py -e com.vmware.vim.eam -c /certificate/vpxd-extension.crt -k /certificate/vpxd-extension.key -s <FQDN> -u Administrator@<SSO Domain> -p <SSO Password>  

python /usr/lib/vmware-vpx/scripts/updateExtensionCertInVC.py -e com.vmware.rbd -c /certificate/vpxd-extension.crt -k /certificate/vpxd-extension.key -s <FQDN> -u Administrator@<SSO Domain> -p <SSO Password>  

python /usr/lib/vmware-vpx/scripts/updateExtensionCertInVC.py -e com.vmware.imagebuilder -c /certificate/vpxd-extension.crt -k /certificate/vpxd-extension.key -s <FQDN> -u Administrator@<SSO Domain> -p <SSO Password>
```

-   Restart the services

```shell
service-control --start vmware-eam  
service-control --start vmware-imagebuilder  
service-control --start vmware-rbd-watchdog
```

To restart all services:

```shell
service-control --stop --all && service-control --start --all
```

## Reference

- https://knowledge.broadcom.com/external/article?legacyId=57379
- https://knowledge.broadcom.com/external/article?legacyId=2112577
- https://knowledge.broadcom.com/external/article?legacyId=80588
- https://knowledge.broadcom.com/external/article/318255
- https://www.reddit.com/r/vmware/comments/117j44q/can_not_delete_orphaned_and_inaccessible_vcls/
- 
