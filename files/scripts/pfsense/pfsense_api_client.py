#!/usr/bin/env python3

import datetime
import ipaddress
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import dns.exception
import dns.resolver
import questionary
from loguru import logger
from pydantic import BaseModel, Field, field_validator

# import requests
from requests import Response, Session

import urllib3

urllib3.disable_warnings()

# global constants
LOG_FILE_RETENTION = 3
VERSION = "2024.3.1"
NAME = "pfsense_api_client"

LOGGER_FORMAT = '<level>{message}</level>'

##################
# This api client assumes that the pfsense api has been installed on the endpoint
# ref: https://github.com/jaredhendrickson13/pfsense-api

# See examples here:
# https://github.com/MikeWooster/api-client
# ref: https://github.com/MikeWooster/api-client/blob/master/README.md#extended-example

from apiclient import (
    APIClient,
    HeaderAuthentication,
    JsonResponseHandler,
    JsonRequestFormatter,
)


# from apiclient.exceptions import APIClientError
# from apiclient.request_formatters import BaseRequestFormatter, NoOpRequestFormatter
# from apiclient.response_handlers import BaseResponseHandler, RequestsResponseHandler
# from apiclient.utils.typing import OptionalJsonType, OptionalStr

# from apiclient.exceptions import UnexpectedError
# from apiclient.response import RequestsResponse, Response
# from apiclient.utils.typing import OptionalDict
# from apiclient.request_strategies import RequestStrategy

class PFSenseConfig(BaseModel):
    """This defines the expected config file

        Example config file:
    ```json
    {
            "username" : "me",
            "password" : "mysupersecretpassword",
            "hostname" : "example.com",
            "port" : 8443,
    }
    ```
    """

    username: Optional[str] = None
    password: Optional[str] = None
    port: int = 443
    hostname: str
    mode: str = "local"
    jwt: Optional[str] = None
    client_id: Optional[str] = None
    client_token: Optional[str] = None
    # verify: bool = True
    verify: bool = False
    # verify: Optional[bool]


class APIResponse(BaseModel):
    """standard JSON API response from the pFsense API"""

    status: str
    code: int
    return_code: int = Field(
        ..., title="return", alias="return", description="The return field from the API"
    )
    message: str
    data: Any

    @field_validator("code")
    def validate_code(cls, value: int) -> int:
        """validates it's an integer in the expected list"""
        if value not in [200, 400, 401, 403, 404, 500]:
            raise ValueError(f"Got an invalid status code ({value}).")
        return value


class APIResponseDict(APIResponse):
    """Dict-style JSON API response from the pFsense API"""

    data: Dict[str, Any]


class APIResponseList(APIResponse):
    """List-style JSON API response from the pFsense API"""

    data: List[Any]


# ref: https://github.com/wesinator/pynslookup/tree/master
class DNSresponse:
    """data object for DNS answer
    response_full - full DNS response raw
    answer - DNS answer to the query
    """

    def __init__(self, response_full=[], answer=[]):
        self.response_full = response_full
        self.answer = answer


# ref: https://github.com/wesinator/pynslookup/blob/master/nslookup/nslookup.py
class Nslookup:
    """Object for initializing DNS resolver, with optional specific DNS servers"""

    def __init__(self, dns_servers=[], verbose=True, tcp=False):
        self.dns_resolver = dns.resolver.Resolver()
        self.verbose = verbose

        if tcp:
            print("Warning: using TCP mode with multiple requests will open a new session for each request.\n\
For large number of requests or iterative requests, it may be better to use the granular dnspython dns.query API.",
                  file=sys.stderr)
        self.tcp = tcp

        if dns_servers:
            self.dns_resolver.nameservers = dns_servers

    def base_lookup(self, domain, record_type):
        """Get the DNS record for the given domain and type, handling errors"""
        try:
            answer = self.dns_resolver.resolve(domain, rdtype=record_type, tcp=self.tcp)
            return answer
        except dns.resolver.NXDOMAIN:
            # the domain does not exist so dns resolutions remain empty
            pass
        except dns.resolver.NoAnswer as e:
            # domains existing but not having AAAA records is common
            if self.verbose and record_type != 'AAAA':
                print("Warning:", e, file=sys.stderr)
        except dns.resolver.NoNameservers as e:
            if self.verbose:
                print("Warning:", e, file=sys.stderr)
        except dns.exception.DNSException as e:
            if self.verbose:
                print("Error: DNS exception occurred looking up '{}':".format(domain), e, file=sys.stderr)

    def dns_host_lookup(self, domain, record_type, include_cname=False):
        if record_type in ['A', 'AAAA']:
            dns_answer = self.base_lookup(domain, record_type)
            if dns_answer:
                dns_response = [answer.to_text() for answer in dns_answer.response.answer]
                ips = [ip.address for ip in dns_answer]
                if include_cname:
                    ips += [dns_answer.canonical_name.to_text()]
                return DNSresponse(dns_response, ips)
        else:
            raise ValueError("Expected record_type 'A' or 'AAAA'")

        return DNSresponse()

    def dns_lookup(self, domain, include_cname=False):
        return self.dns_host_lookup(domain, "A", include_cname)

    def dns_lookup6(self, domain, include_cname=False):
        return self.dns_host_lookup(domain, "AAAA", include_cname)

    def dns_lookup_all(self, domain, include_cname=False):
        resp_a = self.dns_lookup(domain, include_cname)
        resp_aaaa = self.dns_lookup6(domain, include_cname)
        return DNSresponse([*resp_a.response_full, *resp_aaaa.response_full], [*resp_a.answer, *resp_aaaa.answer])

    def soa_lookup(self, domain):
        soa_answer = self.base_lookup(domain, "SOA")
        if soa_answer:
            soa_response = [answer.to_text() for answer in soa_answer.response.answer]
            soa = [next(answer.__iter__()).to_text() for answer in soa_answer.response.answer]
            return DNSresponse(soa_response, soa)
        return DNSresponse()


# ref: https://pypi.org/project/api-client/
# @endpoint(base_url="http://testserver")
class Urls:
    gateways = "/api/v1/status/gateway"
    interfaces = "/api/v1/status/interface"
    services_dhcp_leases = "/api/v1/services/dhcpd/lease"
    services_unbound_access_list = "/api/v1/services/unbound/access_list"
    services_unbound_host_override = "/api/v1/services/unbound/host_override"
    services_unbound_host_override_delete = "/api/v1/services/unbound/host_override?id={id}&apply={apply}"
    firewall = "/api/v1/status/log/firewall"
    dhcp_log = "/api/v1/status/log/dhcp"
    config_history_log = "/api/v1/status/log/config_history"
    system_log = "/api/v1/status/log/system"
    openvpn_status = "/api/v1/status/openvpn"
    system_status = "/api/v1/status/system"
    api_version = "/api/v1/system/api/version"
    users = "users"
    user = "users/{id}"
    accounts = "accounts"


class PFSenseAPIClient:
    """ Base """

    def __init__(
            self,
            config_filename: Optional[str] = None
    ):

        if config_filename:
            self.config_filename = Path(os.path.expanduser(config_filename))
            self.config = self.load_config()

        logger.debug("self.config=%s" % self.config)
        self.requests_session = Session()
        self.requests_session.verify = self.config.verify
        # self.requests_session.verify = False

        self.api_client_json = APIClient(
            authentication_method=HeaderAuthentication(token=f"{self.config.client_id} {self.config.client_token}",
                                                       parameter="Authorization",
                                                       scheme=None),
            response_handler=JsonResponseHandler,
            # request_strategy=request_strategy,
            request_formatter=JsonRequestFormatter,
            # request_formatter=JsonRequestFormatter2,
        )
        self.api_client = APIClient(
            authentication_method=HeaderAuthentication(token=f"{self.config.client_id} {self.config.client_token}",
                                                       parameter="Authorization",
                                                       scheme=None),
            # request_strategy=request_strategy,
            response_handler=JsonResponseHandler
        )

        self.api_client_json.set_session(self.requests_session)
        self.api_client.set_session(self.requests_session)

    @property
    def baseurl(self) -> str:
        """ returns the base URL of the host """
        retval = f"https://{self.config.hostname}"
        if self.config.port:
            retval += f":{self.config.port}"
        return retval

    # ref: https://stackoverflow.com/questions/3462784/check-if-a-string-matches-an-ip-address-pattern-in-python
    @staticmethod
    def is_ipv4(host_string) -> bool:
        try:
            ipaddress.IPv4Network(host_string)
            return True
        except ValueError:
            return False

    # ref: https://stackoverflow.com/questions/2805231/how-can-i-do-dns-lookups-in-python-including-referring-to-etc-hosts#2805413
    @staticmethod
    def get_ipv4_by_hostname(hostname) -> List[str]:
        # see `man getent` `/ hosts `
        # see `man getaddrinfo`

        return list(
            i  # raw socket structure
            [4]  # internet protocol info
            [0]  # address
            for i in
            socket.getaddrinfo(
                hostname,
                0  # port, required
            )
            if i[0] is socket.AddressFamily.AF_INET  # ipv4

            # ignore duplicate addresses with other socket types
            and i[1] is socket.SocketKind.SOCK_RAW
        )

    def load_config(self) -> PFSenseConfig:
        """Loads the config from the specified JSON file (see the `PFSenseConfig` class for what fields are required)"""
        if not self.config_filename.exists():
            error = f"Filename {self.config_filename.as_posix()} does not exist."
            raise FileNotFoundError(error)
        with self.config_filename.open(encoding="utf8") as file_handle:
            pfsense_config = PFSenseConfig(
                **json.load(file_handle)
            )

        self.config = pfsense_config
        # self.hostname = pfsense_config.hostname
        # self.port = pfsense_config.port
        # self.mode = pfsense_config.mode or "local"
        # logger.info("config=%s" % config)
        # print("self.config=%s" % self.config)

        return pfsense_config

    def call(
            self,
            url: str,
            method: str = "GET",
            payload: Optional[Any] = None,
            params: Optional[Any] = None,
            **kwargs: Dict[str, Any],
    ) -> Response:
        """mocking type for mypy inheritance"""
        if url.startswith("/"):
            url = f"{self.baseurl}{url}"

        logger.debug("url[final]=%s" % url)
        logger.debug("method=%s" % method)
        logger.debug("payload=%s" % payload)
        logger.debug("params=%s" % params)
        # logger.debug("kwargs[0]=%s" % kwargs)

        # if payload is not None and method == "GET":
        if payload is not None and payload != {}:
            kwargs = payload
            # if method in ["GET", "DELETE"]:
            #     kwargs = payload
            # else:
            #     kwargs["json"] = payload

        # if params is not None and params != {}:
        if params:
            kwargs["params"] = params

        if "headers" not in kwargs:
            kwargs["headers"] = {}

        # ref: https://stackoverflow.com/questions/22758031/how-to-disable-hostname-checking-in-requests-python#22794281
        kwargs["verify"] = self.requests_session.verify

        # if payload is not None and payload != {}:
        #     kwargs = payload
        #     # if method in ["GET", "DELETE"]:
        #     #     kwargs = payload
        #     # else:
        #     #     kwargs = payload
        #
        # # if params is not None:
        # if params is not None and params != {}:
        #     kwargs["params"] = params

        logger.debug("kwargs=%s" % kwargs)

        if method == 'GET':
            return self.api_client_json.get(url, **kwargs)
        elif method == 'POST':
            return self.api_client_json.post(url, **kwargs)
        elif method == 'DELETE':
            return self.api_client.delete(url, **kwargs)

        # return self.session.request(
        #     url=url,
        #     method=method,
        #     allow_redirects=True,
        #     **kwargs,  # type: ignore
        #     )

    def call_api_dict(
            self,
            url: str,
            method: str = "GET",
            payload: Optional[Dict[str, Any]] = None,
    ) -> APIResponse:
        """makes a call, returns the JSON blob as a dict"""
        response = self.call(url, method, payload)
        # print("response=%s" % response)
        # return APIResponse.parse_obj(response)
        return APIResponse.model_validate(response)

    def call_json(
            self,
            url: str,
            method: str = "GET",
            payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """makes a call, returns the JSON blob as a dict"""
        response = self.call(url, method, payload)
        # print("response=%s" % response)
        result: Dict[str, Any] = response
        return result

    def get_gateway_status(
            self, **filterargs: Dict[str, Any]
    ) -> APIResponse:
        """https://github.com/jaredhendrickson13/pfsense-api/blob/master/README.md#1-read-gateway-status"""
        url = Urls.gateways
        return self.call_api_dict(url, payload=filterargs)
        # return self.call(url, payload=filterargs)

    def get_interface_status(
            self, **filterargs: Dict[str, Any]
    ) -> APIResponse:
        """https://github.com/jaredhendrickson13/pfsense-api/blob/master/README.md#1-read-interface-status"""
        url = Urls.interfaces
        return self.call_api_dict(url, payload=filterargs)
        # return self.call(url, payload=filterargs)

    def get_service_unbound_access_list(
            self, **filterargs: Dict[str, Any]
    ) -> APIResponse:
        """https://github.com/jaredhendrickson13/pfsense-api/blob/master/README.md#1-read-interface-status"""
        url = Urls.services_unbound_access_list
        return self.call_api_dict(url, payload=filterargs)
        # return self.call(url, payload=filterargs)

    def __get_service_unbound_host_overrides(
            self, **filterargs: Dict[str, Any]
    ) -> APIResponse:
        """https://github.com/jaredhendrickson13/pfsense-api/blob/master/README.md#1-read-interface-status"""
        url = Urls.services_unbound_host_override
        return self.call_api_dict(url, payload=filterargs)
        # return self.call(url, payload=filterargs)

    def get_configuration_history_status_log(
            self,
            **filterargs: Dict[str, Any],
    ) -> APIResponse:
        """https://github.com/jaredhendrickson13/pfsense-api/blob/master/README.md#1-read-configuration-history-status-log"""
        url = Urls.config_history_log
        return self.call_api_dict(url, payload=filterargs)
        # return self.call(url, payload=filterargs)

    def get_dhcp_status_log(
            self, **filterargs: Dict[str, Any]
    ) -> APIResponse:
        """https://github.com/jaredhendrickson13/pfsense-api/blob/master/README.md#2-read-dhcp-status-log"""
        url = Urls.dhcp_log
        return self.call_api_dict(url, payload=filterargs)

    def get_firewall_status_log(
            self, **filterargs: Dict[str, Any]
    ) -> Response:
        """https://github.com/jaredhendrickson13/pfsense-api/blob/master/README.md#3-read-firewall-status-log"""
        url = Urls.firewall
        return self.call(url, payload=filterargs)

    def get_system_status_log(
            self, **filterargs: Dict[str, Any]
    ) -> Response:
        """https://github.com/jaredhendrickson13/pfsense-api/blob/master/README.md#4-read-system-status-log"""
        url = Urls.system_log
        return self.call(url, payload=filterargs)

    def get_openvpn_status(
            self, **filterargs: Dict[str, Any]
    ) -> Response:
        """https://github.com/jaredhendrickson13/pfsense-api/blob/master/README.md#1-read-openvpn-status"""
        url = Urls.openvpn_status
        return self.call(url, payload=filterargs)

    def get_system_status(
            self, **filterargs: Dict[str, Any]
    ) -> APIResponseDict:
        """https://github.com/jaredhendrickson13/pfsense-api/blob/master/README.md#1-read-system-status"""
        url = Urls.system_status
        # result = APIResponseDict.parse_obj(self.call_json(url, payload=filterargs))
        result = APIResponseDict.model_validate(self.call_json(url, payload=filterargs))
        return result

    def get_system_api_version(self) -> APIResponse:
        """Read the current API version and locate available version updates.

        https://github.com/jaredhendrickson13/pfsense-api#3-read-system-api-version
        """
        url = Urls.api_version
        return self.call_api_dict(url)

    def get_dhcpd_leases(
            self, **filterargs: Dict[str, Any]
    ) -> APIResponse:
        """https://github.com/jaredhendrickson13/pfsense-api/blob/master/README.md#1-read-dhcpd-leases"""
        url = Urls.services_dhcp_leases
        return self.call_api_dict(url, payload=filterargs)

    def add_service_unbound_host_override(
            self, **filterargs: Dict[str, Any]
    ) -> APIResponse:
        url = Urls.services_unbound_host_override
        return self.call_api_dict(url, method="POST", payload=filterargs)

    def delete_service_unbound_host_override(
            self, **filterargs: Dict[str, Any]
    ) -> APIResponse:
        # url = Urls.services_unbound_host_override_delete.format(id=id, apply=apply)
        url = Urls.services_unbound_host_override
        return self.call_api_dict(url, method="DELETE", payload=filterargs)

    @staticmethod
    def dig_host_ip_list(
            hostname: str,
            dns_nameserver: str,
    ) -> List[str]:
        dig_command = "dig +short %s @%s | grep '^[.0-9]*$'" % (hostname, dns_nameserver)

        logger.debug("hostname=%s" % hostname)
        logger.debug("dns_nameserver=%s" % dns_nameserver)

        logger.debug("dig_command=%s" % dig_command)
        a = subprocess.run(dig_command,
                           capture_output=True,
                           text=True,
                           shell=True)
        if a.stderr:
            logger.error("dig error [%s]" % a.stderr)
            return None
        else:
            sortie = a.stdout
            response = str(sortie).split(':')
            # print("response=%s" % response)
            host_list = response[0].strip().split('\n')
            logger.debug("host_list=%s" % host_list)
            return host_list

    def dns_resolve_host_ip_list(
            self,
            hostname: str,
            dns_nameservers: List[str],
    ) -> List[str]:
        # ref: https://stackoverflow.com/questions/50168439/resolve-an-ip-from-a-specific-dns-server-in-python#50177214

        logger.debug("hostname=%s" % hostname)
        logger.debug("dns_nameservers=%s" % dns_nameservers)

        dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)

        dns_nameserver_ip_list = []
        for dns_nameserver in dns_nameservers:
            if self.is_ipv4(dns_nameserver):
                dns_nameserver_ip_list.extend([dns_nameserver])
            else:
                __dns_nameserver_ip_list = self.get_ipv4_by_hostname(dns_nameserver)
                # dns_query = Nslookup()
                dns_query = Nslookup(verbose=True, tcp=True)
                ips_record = dns_query.dns_lookup(dns_nameserver)
                print("ips_record.response_full=%s" % ips_record.response_full)
                print("ips_record.answer=%s" % ips_record.answer)

                soa_record = dns_query.soa_lookup(dns_nameserver)
                print("soa_record.response_full=%s" % soa_record.response_full)
                print("soa_record.answer=%s" % soa_record.answer)

                logger.debug("__dns_nameserver_ip_list=%s" % __dns_nameserver_ip_list)
                dns_nameserver_ip_list.extend(__dns_nameserver_ip_list)

        logger.debug("dns_nameserver_ip_list=%s" % dns_nameserver_ip_list)
        dns.resolver.default_resolver.nameservers = dns_nameserver_ip_list

        host_ip_list = []
        answers = dns.resolver.resolve(qname=hostname, rdtype='PTR')
        for rdata in answers:
            print(rdata)
            host_ip_list.extend(rdata.address)
        return host_ip_list

    def get_service_unbound_host_overrides(
            self, **filterargs: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        service_unbound_host_override_info = self.__get_service_unbound_host_overrides()

        host_override_data: List[Dict[str, str]] = service_unbound_host_override_info.data
        host_override_list = []
        for key, host_override in enumerate(host_override_data):
            host_override_with_id = host_override | dict(id=key)
            host_override_list.append(host_override_with_id)

        return host_override_list

    def get_service_unbound_host_overrides_by_hostname(
            self,
            hostname: str,
    ) -> List[Dict[str, Any]]:
        (host, domain) = hostname.split('.', 1)
        host_override_data: List[Dict[str, str]] = self.get_service_unbound_host_overrides()
        host_override_list = []
        for host_override in host_override_data:
            # logger.debug("key=%s, host_override=%s" % (key, host_override))
            if host.lower() != host_override["host"].lower():
                # logger.debug("Skipping this because host doesn't match: {}", host_override)
                continue
            if domain.lower() != host_override["domain"].lower():
                # logger.debug("Skipping this because domain doesn't match: {}", host_override)
                continue

            host_override_list.append(host_override)

        return host_override_list

    def delete_service_unbound_host_override_by_id(
            self,
            id: str,
            apply: bool = False,
    ) -> List[Dict[str, str]]:

        logger.debug("deleting host override id {}", id)
        host_override_delete = {
            'id': id,
            'apply': apply
        }

        kwargs: Dict[str, Any] = {"params": host_override_delete}

        logger.debug("kwargs=%s" % kwargs)

        host_override_result = self.delete_service_unbound_host_override(**kwargs)
        host_override_result_data: List[Dict[str, str]] = host_override_result.data

        logger.debug(host_override_result_data)
        return host_override_result_data

    def delete_service_unbound_host_override_by_hostname(
            self,
            hostname: str,
            apply: bool = False,
    ) -> None:
        (host, domain) = hostname.split('.', 1)
        host_override_list: List[Dict[str, Any]] = self.get_service_unbound_host_overrides_by_hostname(
            hostname=hostname)

        for host_override in host_override_list:
            logger.debug("host_override=%s" % host_override)

            host_override_id = host_override['id']
            self.delete_service_unbound_host_override_by_id(
                id=host_override_id,
                apply=apply)


def get_client(loglevel: str = None) -> PFSenseAPIClient:
    """ client factory """

    # ref: https://betterstack.com/community/guides/logging/loguru/
    # logger.remove()
    # logger.add(format=LOGGER_FORMAT,
    #            sink=sys.stdout,
    #            level="INFO")

    if loglevel:
        logger.configure(handlers=[{"sink": sys.stdout, "level": loglevel}])
    else:
        # ref: https://github.com/Delgan/loguru/issues/138#issuecomment-1740069619
        # logger.configure(handlers=[{"sink": sys.stdout, "level": "INFO"}])
        logger.configure(handlers=[{"sink": sys.stdout, "level": "INFO"}])

    client = PFSenseAPIClient(
        config_filename="~/.config/pfsense-api.json"
    )
    return client


@click.group()
@click.version_option(version=VERSION, prog_name=NAME)
def cli():
    """ CLI for pFsense """


@cli.command()
def set_loglevel(
    logLevel: str
):
    """ Sets the Log Level

    LOGLEVEL   : log level to set [debug, info, warn, error]
    """

    # ref: https://github.com/Delgan/loguru/issues/138#issuecomment-1740069619
    logger.configure(handlers=[{"sink": sys.stdout, "level": logLevel}])
    # """Log at different severity levels to view based on new loglevel."""
    logger.debug("debug message")
    logger.info("info message")
    logger.warning("warning message")
    logger.error("error message")


@cli.command()
@click.option("--find", "-f", help="Does a wildcard match based on this")
@click.option("--expired", "-e", is_flag=True, default=False, help="Includes expired leases, off by default.")
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
def list_leases(
        find: Optional[str] = None,
        expired: bool = False,
        loglevel: str = None,
) -> None:
    """ lists DHCP leases """
    client = get_client(loglevel)
    lease_info = client.get_dhcpd_leases()

    # print("lease_info=%s" % lease_info)
    lease_data: List[Dict[str, str]] = lease_info.data

    for lease in lease_data:
        if find is not None:
            if find not in str(lease.values()):
                continue
        if not expired and lease['state'] == "expired":
            continue
        lease_message = f"{lease['type']}\t{lease['mac']}\t{lease['ip']}\t{lease.get('hostname', '')}"
        if "descr" in lease and lease["descr"]:
            lease_message += f" ({lease['descr']})"
        if not lease["online"]:
            logger.debug(lease_message)
        else:
            logger.debug(lease_message)
        logger.debug(lease)


@cli.command()
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
def get_system_api_version(
        loglevel: str = None,
) -> None:
    """ lists system api version """
    client = get_client(loglevel)
    api_version_info = client.get_system_api_version()

    logger.debug("api_version_info=%s" % api_version_info)
    api_version_data: Dict[str, str] = api_version_info.data

    logger.info(api_version_data)


@cli.command()
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
def get_system_status(
    loglevel: str = None,
) -> None:
    """ lists system status """
    client = get_client(loglevel)
    system_status_info = client.get_system_status()

    logger.debug("system_status_info=%s" % system_status_info)
    system_status_data: Dict[str, str] = system_status_info.data

    logger.info(system_status_data)


@cli.command()
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
def get_gateway_status(
    loglevel: str = None,
) -> None:
    """ lists gateway leases """
    client = get_client(loglevel)
    gateway_status_info = client.get_gateway_status()

    logger.debug("gateway_status_info=%s" % gateway_status_info)
    gateway_status_data: List[Dict[str, str]] = gateway_status_info.data

    logger.info(gateway_status_data)


@cli.command()
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
def get_interface_status(
    loglevel: str = None,
) -> None:
    """ lists interface status """
    client = get_client(loglevel)
    interface_status_info = client.get_interface_status()

    logger.debug("interface_status_info=%s" % interface_status_info)
    interface_status_data: List[Dict[str, str]] = interface_status_info.data

    logger.info(interface_status_data)


@cli.command()
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
def get_service_unbound_access_list(
    loglevel: str = None,
) -> None:
    """ lists service_unbound_access_list """
    client = get_client(loglevel)
    service_unbound_access_list_info = client.get_service_unbound_access_list()

    logger.debug("service_unbound_access_list_info=%s" % service_unbound_access_list_info)
    service_unbound_access_list_data: List[Dict[str, str]] = service_unbound_access_list_info.data

    logger.info(service_unbound_access_list_data)


@cli.command()
@click.option("--find", "-f", help="Does a wildcard match based on this")
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
def get_service_unbound_host_overrides(
    find: Optional[str] = None,
    loglevel: str = None,
) -> None:
    """ lists service_unbound_host_override """
    client = get_client(loglevel)
    service_unbound_host_override_info = client.get_service_unbound_host_overrides()

    logger.debug("service_unbound_host_override_info=%s" % service_unbound_host_override_info)
    # host_override_data: List[Dict[str, str]] = service_unbound_host_override_info.data
    host_override_data: List[Dict[str, str]] = service_unbound_host_override_info

    for host_override in host_override_data:
        logger.debug("host_override=%s" % host_override)
        if find is not None:
            if find not in str(host_override.values()):
                continue

        linebreak = '=' * 100
        host_override_message = f"{linebreak}"
        host_name = '*'
        if host_override["host"]:
            host_name = host_override["host"]

        # ref: https://stackoverflow.com/questions/8450472/how-to-print-a-string-at-a-fixed-width
        host_override_message += f"\n{'{0: >20}'.format(host_name)}"
        host_override_message += f"\t{'{0: >20}'.format(host_override['domain'])}"
        host_override_message += f"\t{'{0: >15}'.format(host_override['ip'])}"
        if "descr" in host_override and host_override["descr"]:
            host_override_message += f"\t({host_override['descr']})"
        if 'aliases' in host_override and 'item' in host_override["aliases"]:
            host_override_message += f"\nALIASES:"
            for host_alias in host_override["aliases"]["item"]:
                host_override_message += f"\n{'{0: >20}'.format(host_alias['host'])}"
                host_override_message += f"\t{'{0: >20}'.format(host_alias['domain'])}"
                if "descr" in host_alias and host_alias["descr"]:
                    host_override_message += f"\t({host_alias['descr']})"

        logger.info(host_override_message)


@cli.command()
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
@click.argument('hostname')
def get_service_unbound_host_overrides_by_hostname(
    hostname: str,
    loglevel: str = None,
) -> None:
    """ lists service_unbound_host_override """
    client = get_client(loglevel)
    host_override_data: List[Dict[str, str]] = client.get_service_unbound_host_overrides_by_hostname(
        hostname=hostname)

    for host_override in host_override_data:
        logger.debug("host_override=%s" % host_override)

        linebreak = '=' * 100
        host_override_message = f"{linebreak}"
        host_name = '*'
        host_override_id = host_override['id']
        host_name = host_override["host"]

        # ref: https://stackoverflow.com/questions/8450472/how-to-print-a-string-at-a-fixed-width
        host_override_message += f"\n{'{0: >5}'.format(host_override_id)}"
        host_override_message += f"\t{'{0: >20}'.format(host_name)}"
        host_override_message += f"\t{'{0: >20}'.format(host_override['domain'])}"
        host_override_message += f"\t{'{0: >15}'.format(host_override['ip'])}"
        if "descr" in host_override and host_override["descr"]:
            host_override_message += f"\t({host_override['descr']})"
        if 'aliases' in host_override and 'item' in host_override["aliases"]:
            host_override_message += f"\nALIASES:"
            for host_alias in host_override["aliases"]["item"]:
                host_override_message += f"\n{'{0: >20}'.format(host_alias['host'])}"
                host_override_message += f"\t{'{0: >20}'.format(host_alias['domain'])}"
                if "descr" in host_alias and host_alias["descr"]:
                    host_override_message += f"\t({host_alias['descr']})"

        logger.info(host_override_message)


@cli.command()
@click.option("--find", "-f", help="Does a wildcard match based on this")
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
def get_configuration_history_status_log(
        find: Optional[str] = None,
        loglevel: Optional[str] = None
) -> None:
    """ lists configuration history status log """
    client = get_client(loglevel)
    configuration_history_status_info = client.get_configuration_history_status_log()

    logger.debug("configuration_history_status_info=%s" % configuration_history_status_info)
    log_status_data: List[Dict[str, str]] = configuration_history_status_info.data

    for log_item in log_status_data:
        logger.debug("log_item=%s" % log_item)
        if find is not None:
            if find not in str(log_item.values()):
                continue

        # ref: https://stackoverflow.com/questions/9744775/how-to-convert-integer-timestamp-into-a-datetime
        log_time = datetime.datetime.fromtimestamp(log_item['time'] / 1e3)
        # ref: https://stackoverflow.com/questions/3961581/in-python-how-to-display-current-time-in-readable-format
        log_time_string = log_time.strftime("%Y-%m-%d %H:%M:%S")

        log_item_message = f"{log_time_string}"
        if "description" in log_item and log_item["description"]:
            log_item_message += f" ({log_item['description']})"
        logger.info(log_item_message)


# pylint: disable=too-many-branches,invalid-name
@cli.command()
@click.option("--mac", "-m", help="Delete by MAC address")
@click.option("--hostname", "-h", help="Delete by hostname")
@click.option("--ip", "-i", help="Delete by IP Address")
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
def delete_lease(
        mac: Optional[str] = None,
        hostname: Optional[str] = None,
        ip: Optional[str] = None,
        loglevel: str = None,
) -> None:
    """ Delete a DHCP lease, not actually supported by the pFsense API yet... https://github.com/jaredhendrickson13/pfsense-api/issues/212 """
    client = get_client(loglevel)
    lease_info = client.get_dhcpd_leases()
    lease_data: List[Dict[str, str]] = lease_info.data

    if mac:
        logger.debug("Searching for MAC: {}", mac.lower())
    if hostname:
        logger.debug("Searching for hostname: {}", hostname.lower())
    if ip:
        logger.debug("Searching for IP: {}", ip.lower())

    if not (mac or hostname or ip):
        logger.error("Please specify one of MAC/hostname/IP address")
        sys.exit(1)

    for lease in lease_data:
        if mac and "mac" in lease:
            if mac.lower() != lease["mac"].lower():
                logger.debug("Skipping this because MAC doesn't match: {}", lease)
                continue
        if hostname and "hostname" in lease:
            if hostname.lower() != lease["hostname"].lower():
                logger.debug("Skipping this because hostname doesn't match: {}", lease)
                continue
        if ip and "ip" in lease:
            if ip.lower() != lease["ip"].lower():
                logger.debug("Skipping this because IP Address doesn't match: {}", lease)
                continue
        logger.warning("Target:")
        for key, item in lease.items():
            if key != "staticmap_array_index" and str(item).strip() != "":
                logger.info("{:10} {}", key, item)
        if questionary.confirm("Please confirm deletion: ").ask():
            logger.error("Sorry, this isn't supported by the pFsense API yet!")


# pylint: disable=too-many-branches,invalid-name
@cli.command()
@click.option("--overwrite", "-o",
              is_flag=True,
              default=False,
              help="Overwrite existing host entry if found. (Default is to add to existing entry.")
@click.option("--apply", "-a", is_flag=True, default=False, help="Apply changes.")
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
@click.argument('host')
@click.argument('domain')
@click.argument('ip')
def add_service_unbound_host_override(
        host: str,
        domain: str,
        ip: str,
        overwrite: bool,
        apply: bool,
        loglevel: str = None,
) -> None:
    """ Add Unbound Host Override

    HOST    : the host name of the unbound dns override.\n
    DOMAIN  : the domain name of the unbound dns override.\n
    IP      : IPv4 address of unbound dns entry.  May also be a comma delimited list.\n
    APPLY   : boolean to specify if the override should be immediately applied or not.
    """
    client = get_client(loglevel)

    ip_list = []
    if ',' in ip:
        ip_list.append(ip.split(','))
    else:
        ip_list.append([ip])

    hostname = "%s.%s" % (host, domain)
    if overwrite:
        host_override_list = client.get_service_unbound_host_overrides_by_hostname(
            hostname=hostname)

        for host_override in host_override_list:
            host_override_ip_list = host_override['ip']
            logger.debug("overwriting host_override [%s]" % host_override)

            if host_override_ip_list != ip_list:
                host_override_id = host_override['id']
                client.delete_service_unbound_host_override_by_id(
                    id=host_override_id,
                    apply=apply)

    # ref: https://github.com/TimurNurlygayanov/qa_launchpad_weekly_reports/blob/master/testrail_client.py#L203
    # host_override = dict(
    #     host=host,
    #     domain=domain,
    #     ip=ip_list
    # )
    host_override = {
        'host': host,
        'domain': domain,
        'ip': ip_list,
        'apply': apply
    }

    kwargs: Dict[str, Any] = {"data": host_override}

    logger.debug("kwargs=%s" % kwargs)

    host_override_result = client.add_service_unbound_host_override(**kwargs)
    host_override_result_data: List[Dict[str, str]] = host_override_result.data

    logger.info(host_override_result_data)


# pylint: disable=too-many-branches,invalid-name
@cli.command()
@click.option("--apply", "-a", is_flag=True, default=False, help="Apply changes.")
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
@click.argument('host')
@click.argument('domain')
@click.argument('ip')
def delete_service_unbound_host_override(
        host: str,
        domain: str,
        ip: str,
        apply: bool,
        loglevel: str = None,
) -> None:
    """ Delete Unbound Host Override

    HOST    : the host name of the unbound dns override.\n
    DOMAIN  : the domain name of the unbound dns override.\n
    IP      : IPv4 address of unbound dns entry.  May also be a comma delimited list.
    """
    client = get_client(loglevel)
    host_override_data: List[Dict[str, str]] = client.get_service_unbound_host_overrides()
    for host_override in host_override_data:
        logger.debug("host_override=%s" % host_override)

        if host.lower() != host_override["host"].lower():
            logger.debug("Skipping this because host doesn't match: {}", host_override)
            continue
        if domain.lower() != host_override["domain"].lower():
            logger.debug("Skipping this because domain doesn't match: {}", host_override)
            continue
        if ip.lower() != host_override["ip"].lower():
            logger.debug("Skipping this because IP Address doesn't match: {}", host_override)
            continue

        host_override_id = host_override['id']
        logger.warning("Target:")
        logger.info("{:10} {}", host_override_id, host_override)
        if questionary.confirm("Please confirm deletion: ").ask():
            logger.debug("deleting item {}", host_override)
            host_override_result_data: List[Dict[str, str]] = client.delete_service_unbound_host_override_by_id(
                id=host_override_id,
                apply=apply
            )
            # host_override_delete = {
            #     'id': host_override_id,
            #     'apply': apply
            # }
            #
            # # kwargs: Dict[str, Any] = {"data": host_override_delete}
            # kwargs: Dict[str, Any] = {"params": host_override_delete}
            #
            # logger.debug("kwargs=%s" % kwargs)
            #
            # host_override_result = client.delete_service_unbound_host_override(**kwargs)
            # host_override_result_data: List[Dict[str, str]] = host_override_result.data

            logger.info(host_override_result_data)


# pylint: disable=too-many-branches,invalid-name
@cli.command()
@click.option("--apply", "-a", is_flag=True, default=False, help="Apply changes.")
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
@click.argument('hostname')
def delete_service_unbound_host_overrides_by_hostname(
        hostname: str,
        apply: bool,
        loglevel: str = None,
) -> None:
    """ Delete Unbound Host Overrides by hostname

    HOSTNAME        : the hostname to perform the dig resolve.
    """
    client = get_client(loglevel)
    host_override_list = client.get_service_unbound_host_overrides_by_hostname(
        hostname=hostname)

    for host_override in host_override_list:
        logger.debug("host_override=%s" % host_override)
        host_override_id = host_override['id']
        logger.warning("Target:")
        logger.info("{:10} {}", host_override_id, host_override)
        if questionary.confirm("Please confirm deletion: ").ask():
            logger.debug("deleting item {}", host_override)
            host_override_result_data: List[Dict[str, str]] = client.delete_service_unbound_host_override_by_id(
                id=host_override_id,
                apply=apply
            )

            logger.info(host_override_result_data)


# pylint: disable=too-many-branches,invalid-name
@cli.command()
@click.argument('hostname')
@click.argument('dns_nameserver')
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
def dig_host_ip_list(
        hostname: str,
        dns_nameserver: str,
        loglevel: str = None,
) -> None:
    """ Perform dig for hostname using specified dns nameserver

    HOSTNAME        : the hostname to perform the dig resolve.\n
    DNS_NAMESERVER  : the dns server to perform the resolve.\n
    """
    client = get_client(loglevel)
    logger.debug("host_list=%s" % host_list)
    logger.debug("dns_nameserver=%s" % dns_nameserver)
    host_list: List[str] = client.dig_host_ip_list(hostname=hostname, dns_nameserver=dns_nameserver)


# pylint: disable=too-many-branches,invalid-name
@cli.command()
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
@click.argument('hostname')
@click.argument('dns_nameservers')
def dns_resolve_host_ip_list(
        hostname: str,
        dns_nameservers: str,
        loglevel: str = None,
) -> None:
    """ Perform dns resolve for hostname using specified dns nameserver

    HOSTNAME        : the hostname to perform the dig resolve.\n
    DNS_NAMESERVER  : the dns server to perform the resolve.\n
    """
    client = get_client(loglevel)
    # dns_nameserver_list = dns_nameservers.split(',')
    dns_nameserver_list: List[str] = dns_nameservers.split(',')

    host_list: List[str] = client.dns_resolve_host_ip_list(
        hostname=hostname,
        dns_nameservers=dns_nameserver_list
    )

    logger.debug("host_list=%s" % host_list)


# pylint: disable=too-many-branches,invalid-name
@cli.command()
@click.option("--loglevel", "-l", default="INFO", help="Logging level: [DEBUG, INFO, WARN, ERROR]",
              type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR'], case_sensitive=False))
@click.option("--apply", "-a", is_flag=True, default=False, help="Apply changes.")
@click.argument('hostname')
@click.argument('dns_nameserver')
def sync_host_ip_list(
        hostname: str,
        dns_nameserver: str,
        apply: bool,
        loglevel: str = None,
) -> None:
    """ Synchronize host ip list for specified dns nameserver to pfsense unbound with respective host overrides

    HOSTNAME        : the host name of the unbound dns override.\n
    DNS_NAMESERVER  : the dns server to perform the resolve.
    """
    client = get_client(loglevel)
    host_ip_list: List[str] = client.dig_host_ip_list(hostname=hostname, dns_nameserver=dns_nameserver)

    logger.debug("host_ip_list=%s" % host_ip_list)

    ip_list = sorted(host_ip_list)
    logger.debug("ip_list=%s" % ip_list)

    ip_list_string = ','.join(ip_list)
    logger.debug("ip_list_string=%s" % ip_list_string)

    (host, domain) = hostname.split('.', 1)

    host_override_list = client.get_service_unbound_host_overrides_by_hostname(
        hostname=hostname)

    logger.debug("host_override_list=%s" % host_override_list)

    for host_override in host_override_list:
        logger.debug("host_override=%s" % host_override)
        host_override_ip_list = host_override['ip']
        if host_override_ip_list != ip_list_string:
            host_override_id = host_override['id']
            client.delete_service_unbound_host_override_by_id(
                id=host_override_id,
                apply=apply)
        else:
            logger.debug("host_override already exists => [%s]" % host_override)
            return

    host_override = {
        'host': host,
        'domain': domain,
        'ip': ip_list,
        'apply': apply
    }
    kwargs: Dict[str, Any] = {"data": host_override}

    logger.debug("kwargs=%s" % kwargs)

    host_override_result = client.add_service_unbound_host_override(**kwargs)
    host_override_result_data: List[Dict[str, str]] = host_override_result.data

    logger.info(host_override_result_data)


if __name__ == '__main__':
    cli()
