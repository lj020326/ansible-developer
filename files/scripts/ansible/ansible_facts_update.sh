#!/usr/bin/env bash

echo "1. Convert Standard Facts (Direct Translation)"
## contains  to match "ansible_" only when it's at the start of a line, preceded by whitespace, OR a parenthesis
sed -i -E "s/(^| |\()ansible_(hostname|fqdn|distribution_release|distribution_version|distribution_major_version|distribution|os_family|pkg_mgr|architecture|kernel|processor_vcpus|all_ipv6_addresses|all_ipv4_addresses|default_ipv4_address|default_ipv6|default_ipv4|virtualization_type|processor_nproc|processor_cores|userspace_architecture|memtotal_mb|product_serial|product_name|service_mgr|system_vendor|system|virtualization_role|port|nodename|pip_interpreter|python_version)(?!:)/\1ansible_facts['\2']/g" **/*
sed -i -E "s/(^| |\()ansible_facts['(default_ipv6|default_ipv4)']\.([a-z0-9_]+)/\1ansible_facts['\2']['\3']/g" **/*

echo "2. Convert hostvar referenced ansible facts (Indirect Translation)"
sed -i -E "s/hostvars[(\S+)]['ansible_([a-z0-9_]+)']/hostvars[\1]['ansible_facts']['\2']/g" **/*
sed -i -E "s/hostvars[(\S+)]\.ansible_([a-z0-9_]+)/hostvars[\1]['ansible_facts']['\2']/g" **/*

echo "3. The Nested Facts (Date and Time)"
# Converts ansible_date_time.iso8601 -> ansible_facts['date_time']['iso8601']
sed -i -E "s/(^| |\()ansible_date_time\.([a-zA-Z0-9_]+)/\1ansible_facts['date_time']['\2']/g" **/*

echo "4. Complex Nested Hardware Facts (Devices/Mounts)"
# Converts ansible_devices.sda -> ansible_facts['devices']['sda']
sed -i -E "s/(^| |\()ansible_(all_ipv4_addresses|devices|mounts|interfaces|processor\*|processor)\.([a-z0-9_]+)/\1ansible_facts['\2']['\3']/g" **/*
sed -i -E "s/(^| |\()ansible_(all_ipv4_addresses|devices|mounts|interfaces|processor\*|processor)/\1ansible_facts['\2']/g" **/*
