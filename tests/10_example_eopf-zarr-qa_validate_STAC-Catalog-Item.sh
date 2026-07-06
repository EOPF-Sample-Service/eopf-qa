#!/bin/bash -v

echo "Validate the newest STAC Item directly from the Stac-Catalog:"

python3 eopf_qa/eopf_stac_qa.py --stac <(curl -s 'https://stac.core.eopf.eodc.eu/search?collections=sentinel-2-l1c&sortby=properties.datetime+desc&limit=1' | jq '.features[0]')
