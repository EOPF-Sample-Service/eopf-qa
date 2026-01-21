[<img src="./static/ESA_EOPF_SZS_logo_2025.png">](https://zarr.eopf.copernicus.eu/)

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

