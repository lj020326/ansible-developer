#!/usr/bin/env python3

# ref: https://stackoverflow.com/questions/1087227/validate-ssl-certificates-with-python
import pycurl
import ssl


def get_executable_name() -> str:
    from sys import executable
    from pathlib import Path
    return Path(executable).name


def get_script_name() -> str:
    from sys import argv
    return argv[0]


class SSLValidater:
    def __init__(self, endpoint_host="example.com", endpoint_port=443):
        self.endpoint_host = endpoint_host
        self.endpoint_port = endpoint_port
        self.endpoint_url = "https://%s:%s/" % (endpoint_host, endpoint_port)
        self.openssl_cafile = ssl.get_default_verify_paths().openssl_cafile
        self.curl = pycurl.Curl()

    def connect_to_endpoint(self):
        self.curl.setopt(pycurl.CAINFO, self.openssl_cafile)
        self.curl.setopt(pycurl.SSL_VERIFYPEER, 1)
        self.curl.setopt(pycurl.SSL_VERIFYHOST, 2)
        self.curl.setopt(pycurl.URL, self.endpoint_url)
        self.curl.perform()


if __name__ == "__main__":
    from sys import argv

    execname = get_executable_name()
    scriptname = get_script_name()
    argv = argv[1:]
    
    params = {
        "endpoint_host": ["--host", "-H"],
        "endpoint_port": ["--port", "-P"]
    }
    
    if "--help" in argv or "-h" in argv:
        print(f"({scriptname}) is a very simple python curl based ssl validator.")
        print()
        print("\033[1mArguments:")
        print("[Long/Short]; Purpose; Default")
        print("[--endpoint_host/-H]; SSL endpoint host; example.int, 192.168.1.8, etc")
        print("[--endpoint_port/-P]; SSL endpoint port; 443, 8443, etc")
        print("\033[0m")
        print(f"Example: {execname} {scriptname} -H google.com --port 443")
        print(f"On Unix-like systems, this script can be ran via the Shebang: {scriptname} -H 10.0.1.10 -P 443")
        exit(1)

    args = {
        "endpoint_host": "example.com",
        "endpoint_port": "443",
    }

    sslValidater = SSLValidater(endpoint_host=endpoint_host, endpoint_port=endpoint_port)
    sslValidater.connect_to_endpoint()
