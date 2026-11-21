#!/usr/bin/env python3
"""
pfSense Backup Migration Tool
Migrates configuration from a source pfSense file onto a target baseline configuration,
preserving system/hardware preferences specified in the target baseline.
"""

import os
import sys
import copy
import argparse
from argparse import RawTextHelpFormatter
import logging
import logging.handlers
import xml.etree.ElementTree as ET

__scriptName__ = os.path.basename(sys.argv[0])
__version__ = '2026.9.18'
__updated__ = '18 September 2026'

progname = __scriptName__.split(".")[0]

log = logging.getLogger(__scriptName__)


def setup_logging(loglevel_str="INFO"):
    """Sets up the script logger and applies the requested logging level."""
    loglevel = getattr(logging, loglevel_str.upper(), logging.INFO)
    log.setLevel(loglevel)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        log.addHandler(handler)
    else:
        log.handlers[0].setLevel(loglevel)


def migrate_pfsense_config(source_xml_path, target_xml_path, output_xml_path, interface_mapping=None):
    if interface_mapping is None:
        # Default mapping based on analyzed configs (igc0 -> igc0, igc1 -> igc1)
        interface_mapping = {
            'igc0': 'igc0',
            'igc1': 'igc1'
        }

    log.info(f"Loading source config: {source_xml_path}")
    source_tree = ET.parse(source_xml_path)
    source_root = source_tree.getroot()

    log.info(f"Loading target baseline config: {target_xml_path}")
    target_tree = ET.parse(target_xml_path)
    target_root = target_tree.getroot()

    # Create working copy of source configuration
    migrated_root = copy.deepcopy(source_root)

    # 1. Update physical interface assignments based on mapping table
    log.info("Updating interface mappings...")
    interfaces_node = migrated_root.find('interfaces')
    if interfaces_node is not None:
        for iface in interfaces_node:
            if_tag = iface.find('if')
            if if_tag is not None and if_tag.text in interface_mapping:
                old_if = if_tag.text
                new_if = interface_mapping[old_if]
                if_tag.text = new_if
                log.info(f"  - Interface '{iface.tag}': {old_if} -> {new_if}")

    # 2. Synchronize hardware and device-specific system preferences from target
    log.info("Syncing hardware/system options from target baseline...")
    target_system = target_root.find('system')
    migrated_system = migrated_root.find('system')

    # List of hardware/system tags that should always default to target baseline settings
    hardware_override_tags = [
        'primaryconsole',
        'serialspeed',
        'crypto_hardware',
        'hwpstate',
        'hwpstate_control_level',
        'hwpstate_epp',
        'pkg_repo_conf_path'
    ]

    if target_system is not None and migrated_system is not None:
        for tag in hardware_override_tags:
            target_node = target_system.find(tag)
            migrated_node = migrated_system.find(tag)

            if target_node is not None:
                if migrated_node is None:
                    migrated_node = ET.SubElement(migrated_system, tag)
                migrated_node.text = target_node.text
                log.info(f"  - Applied target hardware setting: <{tag}> = '{target_node.text}'")
            elif migrated_node is not None:
                migrated_system.remove(migrated_node)
                log.info(f"  - Removed source hardware setting absent in target: <{tag}>")

    # 3. Save output XML file
    migrated_tree = ET.ElementTree(migrated_root)
    ET.indent(migrated_tree, space="\t", level=0)
    migrated_tree.write(output_xml_path, encoding='utf-8', xml_declaration=True)
    log.info(f"Migrated config successfully written to: {output_xml_path}")


def verify_step(output_path):
    """Verify generated XML structural integrity and output primary hardware tags."""
    try:
        tree = ET.parse(output_path)
        root = tree.getroot()
        console = root.find('system/primaryconsole')
        crypto = root.find('system/crypto_hardware')
        console_val = console.text if console is not None else "Not set"
        crypto_val = crypto.text if crypto is not None else "Not set"

        # Display formatted verification details directly to stdout
        print("\n[Verification Summary]")
        print(f"  File:             {output_path}")
        print(f"  Status:           Valid XML (root: <{root.tag}>)")
        print(f"  primaryconsole:  {console_val}")
        print(f"  crypto_hardware: {crypto_val}\n")
    except Exception as e:
        log.error(f"Verification Failed: Error validating generated XML: {e}")


def main():
    prog_usage = f"""
Examples of use:
  {__scriptName__} source.xml target.xml
  {__scriptName__} source.xml target.xml migrated_out.xml
  {__scriptName__} -L DEBUG source.xml target.xml
  {__scriptName__} --version
"""

    parser = argparse.ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description="pfSense Backup Migration Tool\nMigrates existing configuration settings onto a new hardware target baseline.",
        epilog=prog_usage
    )

    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__} ({__updated__})")
    parser.add_argument("-L", "--loglevel", choices=['DEBUG', 'INFO', 'WARN', 'ERROR'], default='INFO',
                        help="Set log level (default: INFO)")

    parser.add_argument('src_file', help="Source pfSense configuration XML file (original/existing configuration)")
    parser.add_argument('target_file', help="Target pfSense configuration XML file (baseline)")
    parser.add_argument('out_file', nargs='?', default="migrated_config_pfsense.xml",
                        help="Optional: Output XML file path (default: migrated_config_pfsense.xml)")

    args = parser.parse_args()

    setup_logging(args.loglevel)

    log.debug("Started migration run")
    log.debug(f"src_file={args.src_file}, target_file={args.target_file}, out_file={args.out_file}")

    if not os.path.exists(args.src_file):
        log.error(f"Source file not found: {args.src_file}")
        sys.exit(1)

    if not os.path.exists(args.target_file):
        log.error(f"Target file not found: {args.target_file}")
        sys.exit(1)

    custom_interface_mapping = {
        'igc0': 'igc0',
        'igc1': 'igc1'
    }

    try:
        migrate_pfsense_config(args.src_file, args.target_file, args.out_file, custom_interface_mapping)
        verify_step(args.out_file)
    except Exception as e:
        log.error(f"Migration failed: {e}")
        sys.exit(1)

    log.debug("Finished migration run successfully")


if __name__ == '__main__':
    main()
