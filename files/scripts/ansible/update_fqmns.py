#!/usr/bin/env python3
"""
update_fqmns.py – Convert legacy short Ansible module names to Fully Qualified
Collection Names (FQCNs) with optional task-name linting/normalization.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from argparse import RawTextHelpFormatter
from pathlib import Path

# ---------------------------------------------------------------------------
# Script metadata & logging
# ---------------------------------------------------------------------------
__scriptName__ = os.path.basename(sys.argv[0])
__version__ = "2026.11.17"
__updated__ = "17 November 2026"

log = logging.getLogger(__scriptName__)


def setup_logging(loglevel_str: str = "INFO") -> None:
    """Configure the script logger and apply the requested log level."""
    loglevel = getattr(logging, loglevel_str.upper(), logging.INFO)
    log.setLevel(loglevel)

    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        log.addHandler(handler)
    else:
        log.handlers[0].setLevel(loglevel)


# ---------------------------------------------------------------------------
# Collection module mappings
# ---------------------------------------------------------------------------
COLLECTION_MODULES: dict[str, list[str]] = {
    "ansible.builtin": [
        "add_host",
        "apt",
        "apt_key",
        "apt_repository",
        "assemble",
        "assert",
        "async_status",
        "async_wrapper",
        "blockinfile",
        "command",
        "copy",
        "cron",
        "debconf",
        "debug",
        "dnf",
        "dpkg_selections",
        "expect",
        "fail",
        "fetch",
        "file",
        "find",
        "gather_facts",
        "get_url",
        "getent",
        "git",
        "group",
        "group_by",
        "hostname",
        "import_playbook",
        "import_role",
        "import_tasks",
        "include_role",
        "include_tasks",
        "include_vars",
        "iptables",
        "known_hosts",
        "lineinfile",
        "meta",
        "package",
        "package_facts",
        "pause",
        "ping",
        "pip",
        "raw",
        "reboot",
        "replace",
        "rpm_key",
        "script",
        "service",
        "service_facts",
        "set_fact",
        "set_stats",
        "setup",
        "shell",
        "slurp",
        "stat",
        "subversion",
        "systemd",
        "systemd_service",
        "sysvinit",
        "tempfile",
        "template",
        "unarchive",
        "uri",
        "user",
        "validate_argument_spec",
        "wait_for",
        "wait_for_connection",
        "yum",
        "yum_repository",
    ],
    "ansible.posix": [
        "acl",
        "at",
        "authorized_key",
        "firewalld",
        "firewalld_info",
        "mount",
        "patch",
        "rhel_facts",
        "rhel_rpm_ostree",
        "rpm_ostree_upgrade",
        "seboolean",
        "selinux",
        "synchronize",
        "sysctl",
    ],
    "ansible.windows": [
        "win_acl",
        "win_acl_inheritance",
        "win_certificate_store",
        "win_command",
        "win_copy",
        "win_dns_client",
        "win_domain",
        "win_domain_controller",
        "win_domain_membership",
        "win_dsc",
        "win_environment",
        "win_feature",
        "win_file",
        "win_find",
        "win_get_url",
        "win_group",
        "win_group_membership",
        "win_hostname",
        "win_optional_feature",
        "win_owner",
        "win_package",
        "win_path",
        "win_ping",
        "win_powershell",
        "win_reboot",
        "win_reg_stat",
        "win_regedit",
        "win_service",
        "win_service_info",
        "win_share",
        "win_shell",
        "win_stat",
        "win_tempfile",
        "win_template",
        "win_updates",
        "win_uri",
        "win_user",
        "win_user_right",
        "win_wait_for",
        "win_whoami",
    ],
    "community.general": [
        "psexec",
        "alternatives",
        "ansible_galaxy_install",
        "apache2_mod_proxy",
        "apache2_module",
        "apk",
        "apt_repo",
        "apt_rpm",
        "archive",
        "btrfs_info",
        "btrfs_subvolume",
        "bundler",
        "bzr",
        "capabilities",
        "cargo",
        "cartesian",
        "cloud_init_data_facts",
        "cloudflare_dns",
        "collection_version",
        "consul_kv",
        "counter",
        "cpanm",
        "crc32",
        "cronvar",
        "crypttab",
        "cyberarkpassword",
        "dependent",
        "dict",
        "dict_kv",
        "dig",
        "dnf_config_manager",
        "dnf_versionlock",
        "dnsimple",
        "dnsimple_info",
        "dnsmadeeasy",
        "dnstxt",
        "dpkg_divert",
        "dsv",
        "easy_install",
        "etcd",
        "etcd3",
        "facter",
        "facter_facts",
        "filesize",
        "filesystem",
        "filetree",
        "flattened",
        "from_csv",
        "from_ini",
        "git_config",
        "git_config_info",
        "groupby_as_dict",
        "gunicorn",
        "haproxy",
        "hashids_decode",
        "hashids_encode",
        "homebrew",
        "homebrew_cask",
        "homebrew_tap",
        "homectl",
        "htpasswd",
        "ini_file",
        "interfaces_file",
        "ip_netns",
        "ipbase_info",
        "ipify_facts",
        "ipinfoio_facts",
        "ipmi_boot",
        "ipmi_power",
        "iptables_state",
        "iso_create",
        "iso_customize",
        "iso_extract",
        "java_cert",
        "java_keystore",
        "jboss",
        "jc",
        "jenkins_build",
        "jenkins_build_info",
        "jenkins_job",
        "jenkins_job_info",
        "jenkins_plugin",
        "jenkins_script",
        "json_query",
        "keep_keys",
        "kernel_blacklist",
        "keyring",
        "keyring_info",
        "launchd",
        "ldap_attrs",
        "ldap_entry",
        "ldap_passwd",
        "ldap_search",
        "listen_ports_facts",
        "lists_difference",
        "lists_intersect",
        "lists_mergeby",
        "lists_symmetric_difference",
        "lists_union",
        "lldp",
        "locale_gen",
        "lvg",
        "lvg_rename",
        "lvol",
        "lxc_container",
        "lxca_cmms",
        "lxca_nodes",
        "lxd_container",
        "lxd_profile",
        "lxd_project",
        "macports",
        "mail",
        "make",
        "maven_artifact",
        "merge_variables",
        "mksysb",
        "modprobe",
        "mssql_db",
        "mssql_script",
        "nagios",
        "nmcli",
        "npm",
        "nsupdate",
        "ocapi_command",
        "ocapi_info",
        "oci_vcn",
        "odbc",
        "ohai",
        "open_iscsi",
        "openwrt_init",
        "opkg",
        "osx_defaults",
        "pacman",
        "pacman_key",
        "pam_limits",
        "pamd",
        "parted",
        "pip_package_info",
        "pipx",
        "pipx_info",
        "proxmox",
        "proxmox_disk",
        "proxmox_domain_info",
        "proxmox_group_info",
        "proxmox_kvm",
        "proxmox_nic",
        "proxmox_node_info",
        "proxmox_pool",
        "proxmox_pool_member",
        "proxmox_snap",
        "proxmox_storage_contents_info",
        "proxmox_storage_info",
        "proxmox_tasks_info",
        "proxmox_template",
        "proxmox_user_info",
        "proxmox_vm_info",
        "python_requirements_info",
        "random_mac",
        "random_pet",
        "random_string",
        "random_words",
        "read_csv",
        "redhat_subscription",
        "redis",
        "redis_data",
        "redis_data_incr",
        "redis_data_info",
        "redis_info",
        "remove_keys",
        "replace_keys",
        "rhevm",
        "rhn_channel",
        "rhn_register",
        "rhsm_release",
        "rhsm_repository",
        "sefcontext",
        "selinux_permissive",
        "selogin",
        "seport",
        "shelvefile",
        "shutdown",
        "snap",
        "snmp_facts",
        "ssh_config",
        "sudoers",
        "supervisorctl",
        "syslogger",
        "syspatch",
        "sysrc",
        "sysupgrade",
        "terraform",
        "timezone",
        "to_days",
        "to_hours",
        "to_ini",
        "to_milliseconds",
        "to_minutes",
        "to_months",
        "to_seconds",
        "to_time_unit",
        "to_weeks",
        "to_years",
        "ufw",
        "unicode_normalize",
        "uptimerobot",
        "usb_facts",
        "version_sort",
        "vmadm",
        "wakeonlan",
        "xattr",
        "xenserver_facts",
        "xenserver_guest",
        "xenserver_guest_info",
        "xenserver_guest_powerstate",
        "xfconf",
        "xfconf_info",
        "xfs_quota",
        "xml",
        "yarn",
        "yum_versionlock",
        "zfs",
        "zfs_delegate_admin",
        "zfs_facts",
        "znode",
        "zpool_facts",
        "zypper",
        "zypper_repository",
    ],
    "community.windows": [
        "psexec",
        "win_audit_policy_system",
        "win_audit_rule",
        "win_auto_logon",
        "win_certificate_info",
        "win_computer_description",
        "win_credential",
        "win_data_deduplication",
        "win_defrag",
        "win_dhcp_lease",
        "win_disk_facts",
        "win_disk_image",
        "win_dns_record",
        "win_dns_zone",
        "win_domain_computer",
        "win_domain_group",
        "win_domain_group_membership",
        "win_domain_object_info",
        "win_domain_ou",
        "win_domain_user",
        "win_dotnet_ngen",
        "win_eventlog",
        "win_eventlog_entry",
        "win_feature_info",
        "win_file_compression",
        "win_file_version",
        "win_firewall",
        "win_firewall_rule",
        "win_format",
        "win_hosts",
        "win_hotfix",
        "win_http_proxy",
        "win_iis_virtualdirectory",
        "win_iis_webapplication",
        "win_iis_webapppool",
        "win_iis_webbinding",
        "win_iis_website",
        "win_inet_proxy",
        "win_initialize_disk",
        "win_lineinfile",
        "win_listen_ports_facts",
        "win_mapped_drive",
        "win_msg",
        "win_net_adapter_feature",
        "win_netbios",
        "win_nssm",
        "win_pagefile",
        "win_partition",
        "win_pester",
        "win_power_plan",
        "win_product_facts",
        "win_psexec",
        "win_psmodule",
        "win_psmodule_info",
        "win_psrepository",
        "win_psrepository_copy",
        "win_psrepository_info",
        "win_psscript",
        "win_psscript_info",
        "win_pssession_configuration",
        "win_rabbitmq_plugin",
        "win_rds_cap",
        "win_rds_rap",
        "win_rds_settings",
        "win_region",
        "win_regmerge",
        "win_robocopy",
        "win_route",
        "win_say",
        "win_scheduled_task",
        "win_scheduled_task_stat",
        "win_scoop",
        "win_scoop_bucket",
        "win_security_policy",
        "win_shortcut",
        "win_snmp",
        "win_timezone",
        "win_toast",
        "win_unzip",
        "win_user_profile",
        "win_wait_for_process",
        "win_wakeonlan",
        "win_webpicmd",
        "win_xml",
        "win_zip",
    ],
    "community.docker": [
        "current_container_facts",
        "docker_compose",
        "docker_compose_v2",
        "docker_compose_v2_pull",
        "docker_config",
        "docker_container",
        "docker_container_copy_into",
        "docker_container_exec",
        "docker_container_info",
        "docker_host_info",
        "docker_image",
        "docker_image_build",
        "docker_image_export",
        "docker_image_info",
        "docker_image_load",
        "docker_image_pull",
        "docker_image_push",
        "docker_image_remove",
        "docker_image_tag",
        "docker_login",
        "docker_network",
        "docker_network_info",
        "docker_node",
        "docker_node_info",
        "docker_plugin",
        "docker_prune",
        "docker_secret",
        "docker_stack",
        "docker_stack_info",
        "docker_stack_task_info",
        "docker_swarm",
        "docker_swarm_info",
        "docker_swarm_service",
        "docker_swarm_service_info",
        "docker_volume",
        "docker_volume_info",
    ],
    "openstack.cloud": [
        "current_container_facts",
        "address_scope",
        "auth",
        "baremetal_deploy_template",
        "baremetal_inspect",
        "baremetal_node",
        "baremetal_node_action",
        "baremetal_node_info",
        "baremetal_port",
        "baremetal_port_info",
        "catalog_service",
        "catalog_service_info",
        "coe_cluster",
        "coe_cluster_template",
        "compute_flavor",
        "compute_flavor_access",
        "compute_flavor_info",
        "compute_service_info",
        "config",
        "dns_zone",
        "dns_zone_info",
        "endpoint",
        "federation_idp",
        "federation_idp_info",
        "federation_mapping",
        "federation_mapping_info",
        "floating_ip",
        "floating_ip_info",
        "group_assignment",
        "host_aggregate",
        "identity_domain",
        "identity_domain_info",
        "identity_group",
        "identity_group_info",
        "identity_role",
        "identity_role_info",
        "identity_user",
        "identity_user_info",
        "image",
        "image_info",
        "keypair",
        "keypair_info",
        "keystone_federation_protocol",
        "keystone_federation_protocol_info",
        "lb_health_monitor",
        "lb_listener",
        "lb_member",
        "lb_pool",
        "loadbalancer",
        "network",
        "networks_info",
        "neutron_rbac_policies_info",
        "neutron_rbac_policy",
        "object",
        "object_container",
        "port",
        "port_info",
        "project",
        "project_info",
        "quota",
        "recordset",
        "resource",
        "resources",
        "role_assignment",
        "router",
        "routers_info",
        "security_group",
        "security_group_info",
        "security_group_rule",
        "security_group_rule_info",
        "server",
        "server_action",
        "server_group",
        "server_info",
        "server_metadata",
        "server_volume",
        "stack",
        "stack_info",
        "subnet",
        "subnet_pool",
        "subnets_info",
        "volume",
        "volume_backup",
        "volume_backup_info",
        "volume_info",
        "volume_snapshot",
        "volume_snapshot_info",
        "volume_type",
        "volume_type_access",
        "volume_type_encryption",
        "volume_type_info",
    ],
}


def build_module_patterns(
    collection_modules: dict[str, list[str]],
) -> list[tuple[str, re.Pattern[str]]]:
    """Build compiled regexes matching YAML module keys at task/block indentation."""
    seen_modules: set[str] = set()
    compiled: list[tuple[str, re.Pattern[str]]] = []

    for fqcn_prefix, modules in collection_modules.items():
        unique_mods: list[str] = []
        for mod in modules:
            if mod in seen_modules:
                log.debug(f"Skipping duplicate module '{mod}' already claimed for '{fqcn_prefix}' or an earlier collection.")
                continue
            seen_modules.add(mod)
            unique_mods.append(mod)

        if not unique_mods:
            continue

        log.debug(f"Compiled {len(unique_mods)} unique module(s) for '{fqcn_prefix}'.")
        alternation = "|".join(re.escape(m) for m in sorted(unique_mods, key=len, reverse=True))
        pattern = re.compile(
            rf"^(?P<indent>[ ]*)(?P<dash>-[ ]+)?(?P<mod>{alternation})(?P<colon>:)(?P<rest>[ \t]*.*$)",
            re.MULTILINE,
        )
        compiled.append((fqcn_prefix, pattern))

    return compiled


def apply_optional_task_transforms(
    content: str,
    capitalize_names: bool,
    add_task_names: bool,
) -> str:
    """Apply optional task-name capitalization and shorthand name-generation rules."""
    if capitalize_names:
        log.debug("Applying --capitalize-names transformation.")
        content = re.sub(
            r'^([ ]*-[ ]+name:[ ]+["\'])([a-z])',
            lambda m: f"{m.group(1)}{m.group(2).upper()}",
            content,
            flags=re.MULTILINE,
        )

    if add_task_names:
        log.debug("Applying --add-task-names transformations.")
        # 1. include_tasks / import_tasks
        content = re.sub(
            r"^(?P<indent>[ ]*)-\s+ansible\.builtin\.(?P<inc>include_tasks|import_tasks):\s*(?P<target>.+)$",
            lambda m: (
                f"{m.group('indent')}- name: Run {m.group('target').strip()}\n"
                f"{m.group('indent')}  ansible.builtin.{m.group('inc')}: {m.group('target').strip()}"
            ),
            content,
            flags=re.MULTILINE,
        )

        # 2. debug with var:
        content = re.sub(
            r"^(?P<indent>[ ]*)-\s+ansible\.builtin\.debug:\s*\n(?P<vindent>[ ]*)var:\s*(?P<val>.+)$",
            lambda m: (
                f"{m.group('indent')}- name: Display {m.group('val').strip()}\n"
                f"{m.group('indent')}  ansible.builtin.debug:\n"
                f"{m.group('vindent')}  var: {m.group('val').strip()}"
            ),
            content,
            flags=re.MULTILINE,
        )

        # 3. debug with msg:
        content = re.sub(
            r"^(?P<indent>[ ]*)-\s+ansible\.builtin\.debug:\s*\n(?P<mindent>[ ]*)msg:\s*(?P<rest>.*)$",
            lambda m: (
                f"{m.group('indent')}- name: Display info\n"
                f"{m.group('indent')}  ansible.builtin.debug:\n"
                f"{m.group('mindent')}  msg:{(' ' + m.group('rest')) if m.group('rest').strip() else ''}"
            ),
            content,
            flags=re.MULTILINE,
        )

        # 4. set_fact with a single key: value line
        content = re.sub(
            r"^(?P<indent>[ ]*)-\s+ansible\.builtin\.set_fact:\s*\n(?P<kindent>[ ]*)(?P<key>[A-Za-z0-9_]+):\s*(?P<val>.+)$",
            lambda m: (
                f"{m.group('indent')}- name: Set {m.group('key')}\n"
                f"{m.group('indent')}  ansible.builtin.set_fact:\n"
                f"{m.group('kindent')}  {m.group('key')}: {m.group('val').strip()}"
            ),
            content,
            flags=re.MULTILINE,
        )

    return content


def transform_text(
    content: str,
    patterns: list[tuple[str, re.Pattern[str]]],
    capitalize_names: bool = False,
    add_task_names: bool = False,
) -> str:
    """Transform YAML/Ansible file content to use FQCNs."""
    updated = content
    for fqcn_prefix, pattern in patterns:
        updated = pattern.sub(
            lambda m, prefix=fqcn_prefix: (
                f"{m.group('indent')}{m.group('dash') or ''}{prefix}.{m.group('mod')}{m.group('colon')}{m.group('rest')}"
            ),
            updated,
        )

    return apply_optional_task_transforms(
        updated,
        capitalize_names=capitalize_names,
        add_task_names=add_task_names,
    )


def discover_yaml_files(paths: list[Path]) -> list[Path]:
    """Find YAML files from given file or directory paths."""
    files: list[Path] = []
    for p in paths:
        if not p.exists():
            log.warning(f"Path does not exist: {p}")
            continue
        if p.is_file():
            log.debug(f"Queued file: {p}")
            files.append(p)
        elif p.is_dir():
            for ext in ("*.yml", "*.yaml"):
                matched = list(p.rglob(ext))
                log.debug(f"Found {len(matched)} '{ext}' file(s) under {p}")
                files.extend(matched)
        else:
            log.warning(f"Skipping non-regular path: {p}")
    return sorted(set(files))


def main() -> None:
    prog_usage = f"""
Examples of use:

  # Dry-run preview across playbooks and roles (default)
  {__scriptName__} playbooks/ roles/

  # Apply FQCN conversions and capitalize task names
  {__scriptName__} tasks/*.yml --apply --capitalize-names

  # Apply FQCNs and generate missing task names for include/debug/set_fact
  {__scriptName__} roles/my_role/tasks/ --apply --add-task-names

  # Run with verbose debug logging
  {__scriptName__} -L DEBUG playbooks/site.yml
"""

    parser = argparse.ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description=(
            "Mass-convert short Ansible module calls to Fully Qualified Collection Names (FQCNs)\n"
            "across YAML playbooks, roles, and task files, with optional task-name cleanup."
        ),
        epilog=prog_usage,
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__} ({__updated__})",
    )
    parser.add_argument(
        "-L", "--loglevel",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        default="INFO",
        help="Set log level (default: INFO)",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Ansible YAML files or directories (e.g., playbooks/, roles/, tasks/)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to files (default is dry-run mode)",
    )
    parser.add_argument(
        "--capitalize-names",
        action="store_true",
        help="Capitalize the first lowercase letter of quoted task '- name:' values",
    )
    parser.add_argument(
        "--add-task-names",
        action="store_true",
        help="Add default '- name:' entries to include_tasks, import_tasks, debug, and set_fact tasks",
    )

    args = parser.parse_args()
    setup_logging(args.loglevel)

    log.debug(f"Started {__scriptName__} run (apply={args.apply})")

    files = discover_yaml_files(args.paths)
    if not files:
        log.error("No YAML files found to process.")
        sys.exit(1)

    log.info(f"Scanning {len(files)} YAML file(s)...")
    patterns = build_module_patterns(COLLECTION_MODULES)
    changed_count = 0

    for file_path in files:
        try:
            original = file_path.read_text(encoding="utf-8")
        except Exception as e:
            log.error(f"Failed to read {file_path}: {e}")
            sys.exit(1)

        updated = transform_text(
            original,
            patterns=patterns,
            capitalize_names=args.capitalize_names,
            add_task_names=args.add_task_names,
        )

        if updated != original:
            changed_count += 1
            if args.apply:
                try:
                    file_path.write_text(updated, encoding="utf-8")
                    log.info(f"Updated: {file_path}")
                except Exception as e:
                    log.error(f"Failed to write {file_path}: {e}")
                    sys.exit(1)
            else:
                log.info(f"Would update: {file_path}")
        else:
            log.debug(f"No changes needed: {file_path}")

    if not args.apply:
        log.info(
            f"Dry run complete: {changed_count} file(s) would be modified. "
            "Pass --apply to write changes."
        )
    else:
        log.info(f"Done: {changed_count} file(s) updated.")

    log.debug(f"Finished {__scriptName__} run successfully")


if __name__ == "__main__":
    main()
