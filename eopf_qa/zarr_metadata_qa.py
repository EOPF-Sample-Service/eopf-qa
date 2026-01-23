# check that zarr metadata is complete and .zgroup, .zarray and .zattrs files exist
import argparse
import json
import os
import re
import requests
import urllib
from stac_validator.utilities import fetch_and_parse_file
from stac_validator import stac_validator
#from stac_validator.utilites import fetch_and_parse_file

def __init__():
    # see warning in https://docs.python.org/3/library/urllib.request.html#module-urllib.request for mac
    os.environ["no_proxy"] = "*"

def check_file_exists(url):
    """
    Checks that a given URL is reachable.
    :param url: a URL
    :rtype: bool
    """
    request = urllib.request.Request(url)
    request.get_method = lambda: 'HEAD'

    try:
        urllib.request.urlopen(request)
        return True
    except urllib.request.HTTPError as err:
        #print(err)
        return False

def print_json(json_data):
    print(json.dumps(json_data, indent=4))

#def _zattrs_validate(zattrs):
#    return False
#
#def _zarray_validate(zarray):
#    return False
#
#def _zgroup_validate(zd):
#    return False

# check that all EOPF assets exist
def eopf_check_assets(assets, baseurl = ""):
    assets_messages = {}
    eopf_assets = {}
    asset_missing = False
    for key in assets:
        asset = assets[key]
        href = asset["href"]
        if not href.startswith("http"):
            if href.startswith("/"):
                href = baseurl + href
            else:
                href = baseurl + "/" + href
        if not href.endswith("/.zattrs"):
            if not href.endswith("/"):
                href += "/"
            href += ".zattrs"

        found = check_file_exists(href)
        eopf_assets[ asset["href"] ] = found
        asset_missing |= not found
    
    assets_messages["eopf_assets"] = eopf_assets
    assets_messages["eopf_assets_all_accessible"] = not asset_missing

    return assets_messages

def zarr_metadata_validate(zurl, schema_map, check_files=True, check_stack=True):
    result = []
    message = {}
    try:
        baseurl = re.sub("/?.zmetadata$", "", zurl)
        zmd = fetch_and_parse_file(baseurl + '/.zmetadata')
        #print_json(zmd)
        ## TODO: check other metadata content
        try:
            stac_item = zmd['metadata']['.zattrs']['stac_discovery']
            #print_json(stac_item)
            stac = stac_validator.StacValidate(schema_map = schema_map)
            stac.validate_dict(stac_item)
            #print(stac.message)
            
            # TODO: check all assets point to real files
            try:
                assets = stac.stac_content["assets"]
                asset_messages = eopf_check_assets(assets, baseurl)
                stac.message[0].update(asset_messages)
            except Exception as ex: 
                print(ex) 
            
            message = stac.message[0]
            del message["schema"]

            if not stac.message[0]["valid_stac"]:
                result.append('Error in STAC: ' + stac.message[0]["error_message"])
        except Exception as e:
            result.append("Error parsing STAC item: " + str(e))
        ## TODO: iterate over all zarray elements
        ## ...
    except (ValueError, requests.exceptions.RequestException) as e:
        result.append("Error reading .zmetadata: " + str(e))
    return result, message

def _print_result(url, result):
    println('Validation result:', url)
    if len(result) == 0:
        println("Success!")
    else:
        print(*result, sep='\n')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='EOPF ZARR Validator')
    parser.add_argument("--zarr", type=str, help="zarr with .zmetadata (either http or file URL)", required=True)
    parser.add_argument("--schema-map", type=str, help="schema map in the format 'URL,file'", required=False)
    args = parser.parse_args()

    # test code
    #url = "https://objects.eodc.eu:443/e05ab01a9d56408d82ac32d69a5aae2a:202601-s02msil1c-eu/20/products/cpm_v262/S2B_MSIL1C_20260120T125339_N0511_R138_T27VXL_20260120T130450.zarr"
    #url = "https://objects.eodc.eu:443/e05ab01a9d56408d82ac32d69a5aae2a:202601-s01sewgrm-global/20/products/cpm_v262/S1A_EW_GRDM_1SDH_20260120T122108_20260120T122208_062850_07E274_5E37.zarr"

    if args.schema_map:
        s = args.schema_map.split(',')
        # convert into dict by zipping "slice with keys" and "slice with values" together
        schema_map_local = dict( zip(s[::2], s[1::2]) )
    else:
        schema_map_local = {"https://stac-extensions.github.io/eopf/v1.2.0/schema.json": "local_schemas/eopf-stac-extension/schema.json"}

    # run the validator
    result, jmsg = zarr_metadata_validate(args.zarr, schema_map=schema_map_local)
    #print(url, result)
    print_json(jmsg)

