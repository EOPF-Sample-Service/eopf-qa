#!/bin/sh
# Run the EOPF-QA Zarr validator against an old model to demonstrate an error
# Add '--model models/cpm_v270' to succeed validation when using expected model

#zarr_url=https://objects.eodc.eu/e05ab01a9d56408d82ac32d69a5aae2a:202606-s03olcefr-eu/29/products/cpm_v270/S3A_OL_1_EFR____20260629T135535_20260629T135835_20260629T155811_0179_141_110_1800_PS1_O_NR_004.zarr
zarr_url=https://objects.eodc.eu/e05ab01a9d56408d82ac32d69a5aae2a:202607-s01sewgrm-global/03/products/cpm_v270/S1C_EW_GRDM_1SDV_20260703T191055_20260703T191200_008383_010967_F0F8.zarr


python3 eopf_qa/eopf_zarr_qa.py validate --model models/cpm_v280 --zarr $zarr_url -v $*
