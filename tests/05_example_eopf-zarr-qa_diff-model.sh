#!/bin/bash
# Compare eopf_zarr_qa.py generated model with a reference

zarr_product=https://objects.eodc.eu/e05ab01a9d56408d82ac32d69a5aae2a:202509-s01siwocn-eu/21/products/cpm_v256/S1C_IW_OCN__2SDH_20250921T194014_20250921T194043_004227_008634_1302.zarr
reference_model=models/cpm_v280/S01SIWOCN.json
awk_merge_lists='/: \[/ {line=$0; stripnl=1; next} (stripnl) {gsub(/ /, "", $0); line = line$0} /]/ {print line; stripnl=0; line=""; next} (!stripnl) {print $0}'
sed_merge_dicts='s/[{]\f[ \t]*}/{}/g'

diff -ywW 200 <(python3 eopf_qa/eopf_zarr_qa.py model --zarr $zarr_product | jq -S . | awk "$awk_merge_lists") \
              <(cat $reference_model |  jq -S . | egrep -v '"dont_look_under":|"required":' | jq -S . | awk "$awk_merge_lists" \
                | egrep -v 'stac_discovery|other_metadata|processing_history' | tr '\n' '\f' | sed -e "$sed_merge_dicts" | tr '\f' '\n')
