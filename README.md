[<img src="./static/EOPF-on-bright-baseline.png" width="480">](https://zarr.eopf.copernicus.eu/)

# eopf-qa
EOPF Zarr Product quality checks (draft)

## Stakehoders
ESA, EOPF Developers, Users, Eurac, and EOPF-ZSS internal ingestion workflow
Implemented as a library to be either called during STAC-Item generation or within a JN to check the correctness and completeness of an EOPF-Product

## Goals
* check the STAC item is conform and fits to a TBD best practice (both: within product [optional], and EOPF-ZSS)
  * use existing validators, e.g. pgstac and pystac
* Check that the STAC Assets exist
  * Links: cite-as and license
  * Assets:
    * handle specifics for ProductTypes S1 GRD & SLC, S2 MSI L1C & L2A, S3 OLCI L1 ERR & EFR
    * Expected assets for product type exist (if existing validator does not check this)
    * Expected zarr assets for product type exist
    * Expected zarr assets match EOPF-ZSS library expectations
* Read the Zarr metadata and check that the chunks exist
  Note out-of-scope: checksums [not available] and reading the data to check Zarr contents and datatypes
* Check difference or align with CDSE (possibly with properties to allow or disable variants)
* Proivide properties to disable specific checks to allow validating an ingesting the current state of EOPF products
  * setup tickets in EOPF-CPM and CDSE to foster alignment of EOPF product generation and STAC items
* Agree with EODC on how to report EOPF product errors like missing chunks (within ingestion workflow) to abort publishing and request operator clearance
* library updates after EOPF products evolve.

## Usage examples

### Usage help
```bash
python3 ./eopf_qa/zarr_metadata_qa.py --help
```
Shows:
```
usage: zarr_metadata_qa.py [-h] --zarr ZARR [--schema-map SCHEMA_MAP]
    
EOPF ZARR Validator

options:
  -h, --help            show this help message and exit
  --zarr ZARR           zarr with .zmetadata (either http or file URL)
  --schema-map SCHEMA_MAP
                        schema map in the format 'URL,file'
```

Simlarly for the `eopf_stac_qa.py` tool:
```bash
python3 ./eopf_qa/eopf_stac_qa.py --help
usage: eopf_stac_qa.py [-h] --stac STAC [--expectedStacLinks EXPECTEDSTACLINKS] [--expectedStacAssets EXPECTEDSTACASSETS] [--schema-map SCHEMA_MAP]

EOPF STAC Validator

options:
  -h, --help            show this help message and exit
  --stac STAC           Path to stac json (either http or file URL)
  --expectedStacLinks EXPECTEDSTACLINKS
                        links to check for existance, comma separated
  --expectedStacAssets EXPECTEDSTACASSETS
                        assets to check, comma separated
  --schema-map SCHEMA_MAP
                        schema map in the format 'URL,file'
```


### Validate the a CPM generated Zarr file:
```bash
python3 eopf_qa/zarr_metadata_qa.py --zarr https://objects.eodc.eu:443/e05ab01a9d56408d82ac32d69a5aae2a:202601-s01sewgrm-global/20/products/cpm_v262/S1A_EW_GRDM_1SDH_20260120T122108_20260120T122208_062850_07E274_5E37.zarr --schema-map 'https://stac-extensions.github.io/eopf/v1.2.0/schema.json,local_schemas/eopf-stac-extension/sche ma.json'
```
Reports an error `"'view:off_nadir' is a required property. Error is in properties" for the CPM .zmetadata stac_discovery section.`

### Validate the newest STAC Item directly from the Stac-Catalog:
```bash
python3 eopf_qa/eopf_stac_qa.py --stac <(curl -s 'https://stac.core.eopf.eodc.eu/search?collections=sentinel-2-l1c&sortby=properties.datetime+desc&limit=1' | jq '.fe atures[0]')
```
reports `missing TCI_10m asset file, and an error in the .zmetadata: "Error in STAC: '10' is not of type 'number'. Error is in properties -> gsd"`

### Validate a local STAC item:
```bash
python3 eopf_qa/eopf_stac_qa.py --stac 'tests/sample-data/stac-s2l1c.json'
```
