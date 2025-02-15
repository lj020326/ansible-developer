
# Notes on how to install/use the vcf diagnostic tool

1.  Download the version of VDT compatible with your vCenter version that's attached to this article (see above).
2.  Use the file-moving utility of your choice (WinSCP for example) to copy the entire ZIP directory to /root on the node on which you wish to run it. For being able to open an SCP connection to the vCenter Server Appliance, you need to change the default shell for the root user. Please see [Error when uploading files to vCenter Server Appliance using WinSCP](https://knowledge.broadcom.com/external/article/326317) for more information.
3.  Change your directory to the location of the file, and unpack the zip:
    
    ```shell
    # cd /root/
    # unzip vdt-version_number.zip
    ```
    
4.  Change to the directory that was created by unpacking the zip file.
    
    ```shell
    cd vdt-&lt;version_number&gt;
    ```
    
5.  Run the tool with the command:
    
    ```shell
    python vdt.py
    ```

## References

- https://knowledge.broadcom.com/external/article/344917/using-the-vcf-diagnostic-tool-for-vspher.html
