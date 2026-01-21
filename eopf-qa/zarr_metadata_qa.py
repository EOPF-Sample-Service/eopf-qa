# check that zarr metadata is complete and .zgroup, .zarray and .zattrs files exist

import json
import os
import requests
import urllib
from stac_validator.utilities import fetch_and_parse_file
from stac_validator import stac_validator
#from stac_validator.utilites import fetch_and_parse_file

schema_map_local = {"https://stac-extensions.github.io/eopf/v1.2.0/schema.json": "../local_schemas/eopf-stac-extension/schema.json"}

def __init__():
    # see warning in https://docs.python.org/3/library/urllib.request.html#module-urllib.request for mac
    os.environ["no_proxy"] = "*"

def _check_file_exists(url):
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
    except urllib.request.HTTPError:
        return False

def print_json(json_data):
    print(json.dumps(json_data, indent=4))

def _zattrs_validate(zattrs):
    return False

def _zarray_validate(zarray):
    return False

def _zgroup_validate(zd):
    return False

def zarr_metadata_validate(zurl, check_files=True, check_stack=True):
    result = []
    jmsg = {}
    try:
        if not zurl.endswith('/.zmetadata'):
            zurl += '/.zmetadata'
        zmd = fetch_and_parse_file(zurl)
        #print(json.dumps(zmd, indent=4))
        ## TODO: check other metadata content
        try:
            stac_item = zmd['metadata']['.zattrs']['stac_discovery']
            print(json.dumps(stac_item, indent=4))
            stac = stac_validator.StacValidate(schema_map = schema_map_local)
            stac.validate_dict(stac_item)
            #print(stac.message)
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
    # test code
    #url = "https://objects.eodc.eu:443/e05ab01a9d56408d82ac32d69a5aae2a:202508-s02msil1c/04/products/cpm_v256/S2B_MSIL1C_20250804T222529_N0511_R015_T05WPU_20250804T224050.zarr"
    #url = "https://objects.eodc.eu:443/e05ab01a9d56408d82ac32d69a5aae2a:202508-s01siwgrh/06/products/cpm_v256/S1A_IW_GRDH_1SDV_20250806T104642_20250806T104711_060414_078274_ED3D.zarr"
    url = "https://objects.eodc.eu:443/e05ab01a9d56408d82ac32d69a5aae2a:202601-s01sewgrm-global/20/products/cpm_v262/S1A_EW_GRDM_1SDH_20260120T122108_20260120T122208_062850_07E274_5E37.zarr"
    result, jmsg = zarr_metadata_validate(url)
    #print(url, result)
    print(json.dumps(jmsg, indent=4))

