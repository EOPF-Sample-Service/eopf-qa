import json
import logging
import datetime

import os
import xarray as xr

# This function helps us to retrieve and visualise the names
# for each of the stored groups inside a .zarr product. 
# As an output, it will print a general overview of elements inside the zarr.
def print_gen_structure(node, indent=""):
    print(f"{indent}{node.name}")     #allows us access each node
    for child_name, child_node in node.children.items(): #loops inside the selected nodes to extract naming
        print_gen_structure(child_node, indent + "  ") # prints the name of the selected nodes

stac = 'https://stac.core.eopf.eodc.eu/collections/sentinel-2-l2a/items/S2A_MSIL2A_20250729T084731_N0511_R107_T33KVQ_20250729T122727'

url = 'https://objects.eodc.eu:443/e05ab01a9d56408d82ac32d69a5aae2a:202507-s02msil2a/29/products/cpm_v256/S2A_MSIL2A_20250729T084731_N0511_R107_T33KVQ_20250729T122727.zarr'
s2l2a_zarr_sample= xr.open_datatree(url,
    engine="eopf-zarr", # storage format
    op_mode="native", # no analysis mode
    chunks={}, # allows to open the default chunking
)

print("Zarr Sentinel 2 L2A Structure")
print_gen_structure(s2l2a_zarr_sample.root) 
print("-" * 30)

# Retrieving the reflectance groups:
# s2l2a_zarr_sample["measurements/reflectance"] # Run it yourself for an inteactive overview

# STAC metadata style:
print(list(s2l2a_zarr_sample.attrs["stac_discovery"].keys()))


# retrieve specific information by diving deep into the stac_discovery metadata, such as:
print('Date of Item Creation: ', s2l2a_zarr_sample.attrs['stac_discovery']['properties']['created'])
print('Item Bounding Box    : ', s2l2a_zarr_sample.attrs['stac_discovery']['bbox'])
print('Item ESPG            : ', s2l2a_zarr_sample.attrs['stac_discovery']['properties']['proj:epsg'])
print('Sentinel Platform    : ', s2l2a_zarr_sample.attrs['stac_discovery']['properties']['platform'])
print('Item Processing Level: ', s2l2a_zarr_sample.attrs['stac_discovery']['properties']['processing:level'])

# and from other_metadata, we are able to retrieve the information specific to the instrument variables.
# Complementing metadata:
print(list(s2l2a_zarr_sample.attrs["other_metadata"].keys()))
