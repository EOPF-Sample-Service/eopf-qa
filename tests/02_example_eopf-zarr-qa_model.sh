#!/bin/sh
# Generate and dump Zarr model
# you may format the output by piping through `jq`
# and pipe through `less` to page through output
#
# Note: we also provide tests/05_example_eopf-zarr-qa_diff-model.sh to show how to compare models

zarr_url=https://objects.eodc.eu/e05ab01a9d56408d82ac32d69a5aae2a:202607-s01sewgrm-global/03/products/cpm_v270/S1C_EW_GRDM_1SDV_20260703T191055_20260703T191200_008383_010967_F0F8.zarr

python3 eopf_qa/eopf_zarr_qa.py model --zarr $zarr_url $*
