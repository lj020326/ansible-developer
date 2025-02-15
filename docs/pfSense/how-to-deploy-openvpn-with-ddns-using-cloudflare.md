October 7, 2023

This article will show you how to set up DDNS and OpenVPN on pfSense with Cloudflare. DDNS will keep your domain name up-to-date with your WAN IP address, and OpenVPN will allow you to securely connect to your home network from anywhere in the world.

**Prerequisites**

-   A pfSense firewall or router
-   A domain name or IP address for your VPN server
-   A valid SSL/TLS certificate for your VPN server

**Steps:**

1.  **Create a domain name on Cloudflare**

First, you'll need to create a domain name on Cloudflare. You can do this through the Cloudflare website or CLI tool.

2.  **Set up Cloudflare DDNS on pfSense**

Setting up Cloudflare DDNS on pfSense is simple. Just follow these steps:

-   In the pfSense web interface, go to **Services** \> **Dynamic DNS** \> **Cloudflare**.
-   In the **Cloudflare API Token** field, enter your Cloudflare API token. You can generate an API token on the Cloudflare website.
-   In the **Domain** field, enter your Cloudflare domain name.
-   In the **Record Type** field, select **A**.
-   In the **IP Address** field, enter your WAN IP address.
-   Click **Save**.

3.  **Create an OpenVPN configuration on pfSense**

Creating an OpenVPN configuration on pfSense is also simple. Just follow these steps:

-   In the pfSense web interface, go to **VPN** \> **OpenVPN** \> **Clients**.
-   Click **Create**.
-   In the **Name** field, enter a name for your OpenVPN client.
-   In the **Remote Site** field, enter the IP address or domain name of your OpenVPN server.
-   In the **Protocol** field, select **UDP** or **TCP**.
-   In the **Port** field, enter the port number of your OpenVPN server.
-   In the **TLS** field, select **Enable** to enable TLS encryption.
-   In the **CA Certificate** field, upload the CA certificate from your OpenVPN server.
-   In the **Client Certificate** field, upload the client certificate from your OpenVPN client.
-   In the **Client Key** field, enter the client key from your OpenVPN client.
-   Click **Save**.

4.  **Configure OpenVPN on your OpenVPN client**

To connect to your OpenVPN server, you'll need to configure OpenVPN on your OpenVPN client. For detailed instructions on how to configure OpenVPN on your client, please refer to your OpenVPN client documentation.

5.  **Test your OpenVPN connection**

To test your OpenVPN connection, try connecting to your OpenVPN server from your OpenVPN client. If the connection is successful, you will be able to access your local network resources.

**Additional tips:**

-   You can use Cloudflare's DNS servers to resolve your DDNS domain name. This will save you from having to specify your WAN IP address in your OpenVPN configuration.
-   If you're using the UDP protocol with OpenVPN, you may need to open port 1194 on your firewall.
-   If you're using the TCP protocol with OpenVPN, you may need to open port 443 on your firewall.

**Conclusion:**

By following these steps, you can easily set up DDNS and OpenVPN on pfSense with Cloudflare. This will allow you to securely connect to your home network from anywhere in the world.

## Reference

- https://www.ikoolcore.com/blogs/knowledge/how-to-deploy-openvpn-on-pfsense
- 