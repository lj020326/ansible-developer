
# Notes on Putting a Cluster in Retreat Mode in vsphere 7.0

When a datastore is placed in maintenance mode, if the datastore hosts vCLS VMs, you must manually storage vMotion the vCLS VMs to a new location or put the cluster in retreat mode.

This task explains how to put a cluster in retreat mode.

## Procedure

1.  Login to the vSphere Client.
2.  Navigate to the cluster on which vCLS must be deactivated.
3.  Copy the cluster domain ID from the URL of the browser. It should be similar to domain-c(number).
    
    Note: Only copy the numbers to the left of the colon in the URL.
    
4.  Navigate to the vCenter Server Configure tab.
5.  Under Advanced Settings, click the Edit Settings button.
6.  Add a new entry config.vcls.clusters.domain-c(number).enabled. Use the domain ID copied in step 3.
7.  Set the Value to False.
8.  Click Save.

## Results

vCLS monitoring service runs every 30 seconds. Within 1 minute, all the vCLS VMs in the cluster are cleaned up and the Cluster Services health will be set to Degraded. If the cluster has DRS activated, it stops functioning and an additional warning is displayed in the Cluster Summary. DRS is not functional, even if it is activated, until vCLS is reconfigured by removing it from Retreat Mode.

vSphere HA does not perform optimal placement during a host failure scenario. HA depends on DRS for placement recommendations. HA will still power on the VMs but these VMs might be powered on in a less optimal host.

To remove Retreat Mode from the cluster, change the value in step 7 to True.

## References

- https://docs.vmware.com/en/VMware-vSphere/7.0/com.vmware.vsphere.resmgmt.doc/GUID-F98C3C93-875D-4570-852B-37A38878CE0F.html
- https://docs.vmware.com/en/VMware-vSphere/8.0/vsphere-resource-management/GUID-96BD6016-4BE7-4B1C-8269-568D1555B08C.html
- 