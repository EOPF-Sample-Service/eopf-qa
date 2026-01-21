# check that a stac item validates
import argparse
import json
from stac_validator import stac_validator
from zarr_metadata_qa import zarr_metadata_validate, check_file_exists

expectedStacLinks = ["collection","parent","root","self","cite-as","license"]
expectedStacAssets = ["product","zipped_product","product_metadata","test"]

def stac_validate_links(links):
    link_messages = {}
    found_links = []
    for link in links:
        #print(json.dumps(link, indent=4))
        if link["rel"] in expectedStacLinks:
            found_links.append(link["rel"])
            link_messages[link["rel"]] = link["href"]
    
    missing = list(set(expectedStacLinks) - set(link_messages.keys()))
    if len(missing) > 0:
        link_messages["stac_links_missing"] = missing
    
    return link_messages

def stac_validate_assets(assets):
    assets_messages = {}
    assets_messages["valid_eopf"] = False
    try:
        baseurl = assets["product"]["href"] + "/"
        assets_messages["eopf_assets_baseurl"] = baseurl
    except:
        baseurl = "" 
    assets_messages["eopf_assets"] = {}
    asset_missing = False
    eopf_found_assets = {}
    for key in assets:
        asset = assets[key]
        zarrmetadata = {}
        zarrmetadata["type"] = asset["type"]
        zarrmetadata["href"] = asset["href"].replace(baseurl,"")
        if key in expectedStacAssets:
            if asset["type"] == "application/zip":
                pass # no further validation for ZIPer download endpoint
            elif asset["type"] == "application/json" and asset["href"].endswith(".zmetadata"):
                # TODO: make deep-check optional
                messages,jmsg = zarr_metadata_validate(asset["href"])
                if messages:
                    #print(messages)
                    zarrmetadata["valid_metadata"] = False
                    zarrmetadata["eopf_stac_metadata_errors"] = messages
                

        elif asset["type"] == "application/vnd+zarr":
            href = asset["href"]
            if not href.endswith("/.zattrs"):
                href += "/.zattrs"
            #print(href)
            found = check_file_exists(href)
            zarrmetadata["accessible"] = found
            asset_missing |= not found
        else:
            zarrmetadata["unchecked"]: True

        eopf_found_assets[key] = zarrmetadata
    
    assets_messages["eopf_assets"] = eopf_found_assets 
    assets_messages["eopf_assets_all_accessible"] = not asset_missing

    missing = list(set(expectedStacAssets) - set(eopf_found_assets.keys()))
    if len(missing) > 0:
        eopf_found_assets["eopf_assets_missing"] = missing
    
    return assets_messages


def stac_validate_local(image_url):
    stac = stac_validator.StacValidate(image_url)#, pydantic=True)#, extensions=True, verbose=True)
    stac.run()

    # check links
    try:
        links = stac.stac_content["links"]
        link_messages = stac_validate_links(links)
        stac.message[0]["stac_links"] = link_messages
    except Exception as ex: 
        print(ex) 
        pass # the error should already be in the message

    # check assets
    try:
        assets = stac.stac_content["assets"]
        asset_messages = stac_validate_assets(assets)
        stac.message[0].update(asset_messages)
    except Exception as ex: 
        print(ex) 
        pass # the error should already be in the message
    #print(json.dumps(stac.stac_content["assets"], indent=4))  

    message = stac.message[0]
    del message["schema"]

    return message

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='EOPF STAC Validator')
    parser.add_argument("--stac", type=str, help="Path to stac json (either http or file URL)", required=True)
    parser.add_argument("--expectedStacLinks", type=str, help="links to check for existance, comma separated", required=False)
    parser.add_argument("--expectedStacAssets", type=str, help="assets to check, comma separated", required=False)
    args = parser.parse_args()

    #jmsg = stac_validate_local("https://stac.core.eopf.eodc.eu/collections/sentinel-1-l1-grd/items/S1A_IW_GRDH_1SDV_20250806T104642_20250806T104711_060414_078274_ED3D")
    jmsg = stac_validate_local("https://stac.core.eopf.eodc.eu/collections/sentinel-1-l1-grd/items/S1A_EW_GRDM_1SDH_20260120T122108_20260120T122208_062850_07E274_5E37")
    #jmsg = stac_validate_local("https://stac.core.eopf.eodc.eu/collections/sentinel-1-l1-slc/items/S1A_IW_SLC__1SDV_20240106T170607_20240106T170635_051989_064848_04A6")
    #jmsg = stac_validate_local("https://stac.core.eopf.eodc.eu/collections/sentinel-2-l1c/items/S2B_MSIL1C_20260113T112329_N0511_R037_T32VKR_20260113T131429")
    ##jmsg = stac_validate_local("https://stac.core.eopf.eodc.eu/collections/sentinel-2-l2a/items/S2B_MSIL2A_20250804T185919_N0511_R013_T23XNM_20250804T211910")
    #jmsg = stac_validate_local("https://stac.core.eopf.eodc.eu/collections/sentinel-3-olci-l1-efr/items/S3A_OL_1_EFR____20260112T113833_20260112T114133_20260112T133232_0179_135_023_2340_PS1_O_NR_004")
    
    if args.expectedStacLinks:
        expectedStacLinks = args.expectedStacLinks.split(",")
    if args.expectedStacAssets:
        expectedStacAssets = args.expectedStacAssets.split(",")
    
    # run the validator
    jmsg = stac_validate_local(args.stac)
    #print(jmsg)
    print(json.dumps(jmsg, indent=4))

