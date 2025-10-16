#!/usr/bin/env bash

SITE_LIST=("pfsense.johnson.int:443")
SITE_LIST+=("diskstation01.johnson.int:5001")
SITE_LIST+=("gitea.admin.dettonville.int:443")
SITE_LIST+=("updates.jenkins.io:443")
SITE_LIST+=("get.jenkins.io:443")
SITE_LIST+=("archives.jenkins.io:443")
SITE_LIST+=("pypi.python.org")
SITE_LIST+=("files.pythonhosted.org")
SITE_LIST+=("bootstrap.pypa.io")
SITE_LIST+=("galaxy.ansible.com")
SITE_LIST+=("repo.maven.apache.org")

install-cacerts.sh "$@" ${SITE_LIST[@]}
