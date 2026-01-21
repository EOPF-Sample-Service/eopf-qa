# check that a stac item validates
import json
from stac_validator import stac_validator
from zarr_metadata_qa import zarr_metadata_validate

expectedEopfStacAssets = ["product","zipped_product","product_metadata"]

def stac_validate_local(image_url):
    stac = stac_validator.StacValidate(image_url)#, pydantic=True)#, extensions=True, verbose=True)
    stac.run()

    try:
        stac.message[0]["valid_eopf"] = False
        stac.message[0]["eopf_assets"] = {} 
        assets = stac.stac_content["assets"]
        eopf_assets = {}
        for key in assets:
            asset = assets[key]
            if key in expectedEopfStacAssets:
                zarr_validated = False
                zarrmetadata = {}
                zarrmetadata["type"] = asset["type"]
                zarrmetadata["href"] = asset["href"]
                if asset["type"] == "application/zip":
                    pass # no further validation for ZIPer download endpoint
                elif asset["type"] == "application/json" and asset["href"].endswith(".zmetadata"):
                    # TODO: validate Zarr files
                    messages = zarr_metadata_validate(asset["href"])
                    if messages:
                        #print(messages)
                        zarrmetadata["valid_metadata"] = False
                        zarrmetadata["metadata_errors"] = messages  
                    else:
                        zarr_validated = True
                else:
                    zarr_validated = False
                    
                eopf_assets[key] = zarrmetadata
                #print(key, asset["href"])

                if zarr_validated:
                    stac.message[0]["valid_zarr"] = True
                    pass # TODO
        
        stac.message[0]["eopf_assets"] = eopf_assets 
    
        missing = list(set(expectedEopfStacAssets) - set(eopf_assets.keys()))
        if len(missing) > 0:
            stac.message[0]["eopf_assets_missing"] = missing
        else:
            stac.message[0]["valid_eopf"] = True
    except Exception as ex: 
        print(ex) 
        pass # the error should already be in the message
    #print(json.dumps(stac.stac_content["assets"], indent=4))  

    message = stac.message[0]
    del message["schema"]

    return message

if __name__ == "__main__":
    #jmsg = stac_validate_local("https://stac.core.eopf.eodc.eu/collections/sentinel-1-l1-grd/items/S1A_IW_GRDH_1SDV_20250806T104642_20250806T104711_060414_078274_ED3D")
    jmsg = stac_validate_local("https://stac.core.eopf.eodc.eu/collections/sentinel-1-l1-grd/items/S1A_EW_GRDM_1SDH_20260120T122108_20260120T122208_062850_07E274_5E37")
    #jmsg = stac_validate_local("https://stac.core.eopf.eodc.eu/collections/sentinel-1-l1-slc/items/S1A_IW_SLC__1SDV_20240106T170607_20240106T170635_051989_064848_04A6")
    #jmsg = stac_validate_local("https://stac.core.eopf.eodc.eu/collections/sentinel-2-l1c/items/S2B_MSIL1C_20260113T112329_N0511_R037_T32VKR_20260113T131429")
    #jmsg = stac_validate_local("https://stac.core.eopf.eodc.eu/collections/sentinel-2-l2a/items/S2B_MSIL2A_20250804T185919_N0511_R013_T23XNM_20250804T211910")
    #jmsg = stac_validate_local("https://stac.core.eopf.eodc.eu/collections/sentinel-3-olci-l1-efr/items/S3A_OL_1_EFR____20260112T113833_20260112T114133_20260112T133232_0179_135_023_2340_PS1_O_NR_004")
    
    #print(jmsg)
    print(json.dumps(jmsg, indent=4))

