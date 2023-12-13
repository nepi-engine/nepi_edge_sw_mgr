#!/bin/bash

# Leverage licenseheaders Python module to update license headers
# Requires licenseheaders is on PATH or PYTHONPATH (e.g., pip3 install licenseheaders) 
# and the NEPI source header license text template file is passed in as first argument
# to this script

TEMPLATE_FILE=$1
TARGET_DIR='.'
EXCLUSIONS='*generate_license_headers.sh*'
OWNER='Numurus, LLC <https://www.numurus.com>'
PROJECT='nepi_edge_sw_manager'
PROJECT_URL='https://github.com/numurus-nepi/nepi_edge_sw_mgr'

# Create a dummy Python file to generate the LICENSE file
touch ${TARGET_DIR}/license_dummy.py

# Generate headers
python3 -m licenseheaders -t ${TEMPLATE_FILE} -d ${TARGET_DIR} -x ${EXCLUSIONS} -o "${OWNER}" -n ${PROJECT} -u ${PROJECT_URL} -cy

# Remove leading '#' to generate the LICENSE file
sed -i -e 's/^#//g' ${TARGET_DIR}/license_dummy.py
mv ${TARGET_DIR}/license_dummy.py LICENSE

