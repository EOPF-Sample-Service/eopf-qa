#!/bin/sh
# Validate a Zarr file

zarr_url=https://objects.eodc.eu/e05ab01a9d56408d82ac32d69a5aae2a:202607-s01sewgrm-global/03/products/cpm_v270/S1C_EW_GRDM_1SDV_20260703T191055_20260703T191200_008383_010967_F0F8.zarr 

python3 eopf_qa/eopf_zarr_qa.py validate --zarr $zarr_url $*
