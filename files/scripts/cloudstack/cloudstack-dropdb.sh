#!/usr/bin/env bash

SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"
echo "SCRIPT_DIR=[${SCRIPT_DIR}]"

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/.env"

CSRootPassword="${CSRootPassword:-}"

#/etc/init.d/cloud-management stop
systemctl stop cloudstack-agent
systemctl stop cloudstack-management

mysql -uroot -p"${CSRootPassword}" -e 'drop database cloud' &&
 mysql -uroot -p"${CSRootPassword}" -e 'drop database cloud_usage'
rc="$?"

echo "Finished: dropped cloudstack db"

exit "${rc}"
