# Utility to validate a EOPF Zarr structure
#
import argparse
import json
import logging
import os
import re
import time
import zarr
from utils import check_file_exists
from dataclasses import dataclass
from difflib import SequenceMatcher
from logging import Logger
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from stac_validator.utilities import fetch_and_parse_file
from zarr.core.array import Array
from zarr.core.group import Group
from zarr.storage import ZipStore
##from aiohttp._http_parser import path
#from eopf.product_model.eo_container_validation import _validate_sub_product

EOPF_TOP_ATTR_CATEGORY = ("stac_discovery", "other_metadata", "processing_history")
EOPF_STD_ATTRIBUTES = ['_ARRAY_DIMENSIONS', 'dimensions', 'dtype', 'long_name', 'units', 'valid_min', 'valid_max', 'add_offset', 'scale_factor', 'standard_name']
EOPF_MODELS_BASEPATH = 'models/cpm_v270'

ModelValidationMode = Literal["EXACT", "AT_LEAST", "ANY"]
ValidationAnomalyCategories = Literal["STRUCTURE", "STAC", "MODEL"]

@dataclass
class AnomalyDescriptor:
    category: ValidationAnomalyCategories
    description: str

def append_to_anomalies(
    anomalies_list: list[AnomalyDescriptor],
    category: ValidationAnomalyCategories,
    reason: str,
    logger: Optional[Logger],
) -> None:
    anomalies_list.append(
        AnomalyDescriptor(
            category,
            reason,
        ),
    )
    if logger is not None:
        logger.debug(reason)

def validate_attrs_against_jsonschema(
    eo_object: Dict,
    attrs_jsonschema: Optional[Dict[str, Any]],
    out_anomalies: list[AnomalyDescriptor],
    logger: Optional[Logger],
) -> None:
    if attrs_jsonschema:
        try:
            jsonschema.validate(eo_object.attrs, schema=attrs_jsonschema)
        except ValidationError as e:
            append_to_anomalies(out_anomalies, "MODEL", f"Error validating schema on {e}", logger)


def trimDict(data: Dict, to_remove: List) -> Dict:
    for key in to_remove:
        if key in data:
            data.pop(key)
    return data

def printZarrStructure(node: dict, base: str = '', indent: str = ''): # to STDOUT
    #print(f"{indent}  Info: {node.info}")
    name = node.name.replace(base, '')
    # normalize base name 
    if name[0] == '/':
        name = name[1:]
    if isinstance(node, Group):
        eopf_category = node.metadata.attributes.get('other_metadata',{}).get('eopf_category','group')
        if len(name) > 0:
            print(f"{indent}{name}: {eopf_category}")
        else:
            print(f"{indent}/ {eopf_category}")
        for k in node.keys():
            # recursion
            printZarrStructure(node.get(k), node.name + '/', indent + '    ')
        #
    elif isinstance(node, Array):
        dtype = node.dtype
        shape = str(node.shape).replace(',)',')').replace(', ',',')
        unit = ' ' + str(node.attrs.get('units')) if 'units' in node.attrs else ''
        add_offset = node.attrs.get('add_offset', None)
        scale_factor = node.attrs.get('scale_factor', None)
        scale = ' * ' + str(scale_factor) + ' + ' + str(add_offset) if scale_factor and add_offset else ''
        desc = node.attrs.get('long_name','') 
        print(f"{indent}{name}: {dtype}{shape}{unit}{scale} '{desc}'")
    else:
        print("??? {node}")
    
    for attr in node.attrs:
        value = node.attrs[attr]
        if attr not in EOPF_STD_ATTRIBUTES: 
                #and ( attr == 'standard_name' and name != value ):
            if attr == '_eopf_attrs':
                # remove declared attribute keys
                data = trimDict(value, node.attrs) if not isinstance(node.attrs, str) else value
                # remove known_eopf_attribute_keys
                data = trimDict(data, ['coordinates', 'dimensions', 'short_name', 'fill_value'])
                if len(data) > 0:
                    print(f"{indent}  _eopf_attrs: {data}")
            #elif attr in ['flag_masks', 'flag_meanings', 'flag_values']:
            #    print(f"{indent}  {attr}: {value}")
            elif attr in EOPF_TOP_ATTR_CATEGORY:
                print(f"{indent}  {attr}: json...")
            else:
                print(f"{indent}  {attr}: {value}")

def generateAttributesModel(node: Dict) -> Dict:
    attrs = {}
    for attr in node.attrs:
        if attr not in ['_ARRAY_DIMENSIONS', '_eopf_attrs']:
            #value = node.attrs[attr];
            #attrs[attr] = value
            # just output an empty model
            attrs[attr] = {} 
    return attrs
    
def fillEopfZarrModel(node: Dict, model = {}, base = '') -> Dict:
    name = str(node.name).replace(base, '')
    if isinstance(node, Group):
        for k in node.keys():
            # recurse
            fillEopfZarrModel(node.get(k), model, base = base)
            
    elif isinstance(node, Array):
        dtype = str(node.dtype)
        dims = node.attrs["_ARRAY_DIMENSIONS"]
        # the eopf_cmp validator does not process "x" and "y" groups
        if not ( len(dims) == 1 and name.endswith("/" + dims[0]) ):
            model[name] = { "dtype": dtype, "dims": dims }

    # the eopf_cmp validator uses "_eopf_attrs" instead of the Zarr Group "attrs" 
    if ("_eopf_attrs" in node.attrs) and len(node.attrs["_eopf_attrs"]) > 0:
        eopf_attrs = {}
        for attr in node.attrs["_eopf_attrs"]:
             eopf_attrs[attr] = {} #{"dont_look_under": False}
        #model[name]["_eopf_attrs"] = eopf_attrs
        # the eopf_cmp validator daclares the use of the "_eopf_attrs" 
        model[name]["attrs"] = eopf_attrs

    return model


def createEopfModelFromZarr(zarr, product_type: str, logger:Logger, base = '') -> Dict:
    product_model = {}
    eopf_category = zarr.metadata.attributes.get('other_metadata',{}).get('eopf_category','group')
    product_model['eopf_category'] = eopf_category
    if eopf_category in ['eocontainer']:
        # process container elements
        product_model['container_type_regex'] = product_type
        sub_containers = {}
        sub_products = {}
        for p in zarr.keys():
            path = base + '/' + p
            component = zarr.get(p)
            # iterate into model with clipped name
            if eopf_category == 'eocontainer' and 'conditions' not in component.keys():
                product_type = getProductType(zarr, logger)
                sub_containers[p] = createEopfModelFromZarr(component, product_type, logger, path)
            else: # 'eoproduct'
                vars = fillEopfZarrModel(component, base = path)
                sub_products[p] = {'product_type_regex': product_type, 'variables':vars, 'attrs':{}}
                ##sub_products[p]['_path'] = path
        product_model['sub_products'] = sub_products
        product_model['sub_containers'] = sub_containers
    else:
        vars = fillEopfZarrModel(z)
        product_model = {"product_type_regex":product_type, "variables":vars}
    ## TODO: create attribute model
    product_model['attrs'] = {}
    ## product_model['attrs']["stac_discovery"] = zarr.attrs["stac_discovery"]
    return product_model


def validateZarrModel(node: dict, model = {}, 
                      zarr_url: str = '',
                      zarr_path: str = '',
                      out_anomalies: List[AnomalyDescriptor] = None, 
                      logger = None) -> None:
    ## TODO: report anything in node, that is not in model
    # traverse the variables in sync on model and product
    ##logger.info(f"... validating model at {zarr_path}")
    ##print(f"... node.type={type(node).__name__} and reference_model.type={type(model).__name__}")
    for attr in model.keys():
        value = model[attr]
        type_name = type(value).__name__
        ##print(f"... searching {zarr_path} for {attr} ({type_name}) in {type(node).__name__} [{len(value)}]")
        node_type_name = type(node[attr]).__name__ if attr in node.keys() else None 
        if attr in ['dont_look_under', 'required', 'eopf_is_masked', 'eopf_is_scaled', 'eopf_target_dtype']:
            # ignore eopf-cpm specials
            continue
        elif type_name != node_type_name:
            msg = f"    node {zarr_path}/{attr} type ({node_type_name}) differs from model ({type_name})"
            append_to_anomalies(out_anomalies, "MODEL", msg, logger)
        elif type_name != 'str' and not attr in node.keys():
            msg = f"    node missing {attr} from model"
            append_to_anomalies(out_anomalies, "MODEL", msg, logger)
        elif type_name != 'str' and len(value) > 0:
            # relative location of zarr file
            if not attr.startswith("/"):
                zarr_path += '/' + attr

            try:
                if attr.startswith("/") and zarr_url != '':
                    zattrs_file = zarr_url + attr + '/' + '.zattrs'
                    logger.debug(f"... looking for {zattrs_file}")
                    ##print(f"    checking {zattrs_file}")
                    check_file_exists(zattrs_file)
                    ##print(f"    found {zattrs_file}")
            except Exception as e:
                msg = f"    missing '{zattrs_file}'" ## -> {e}"
                append_to_anomalies(out_anomalies, "FILE", msg, logger)
                
            if isinstance(value, Dict):
                ##try:
                ##    if attr.startswith("/"):
                ##        zattrs_file = zarr_url + attr + '/' + '.zgroup'
                ##        check_file_exists(zattrs_file)
                ##        print(f"    found {zattrs_file}")
                ##except Exception as e:
                ##   msg = f"    node {attr} has no '.zgroup' file: {e}"
                ##    append_to_anomalies(out_anomalies, "FILE", msg, logger)
                ##print(f">>> traversing group {attr}")
                ##if checkzarrfiles:
                ##    print(f"... checking {value}")
                # iterate
                validateZarrModel(node[attr], value, zarr_url, zarr_path, out_anomalies, logger)
                ##print(f"<<< traversing group {attr}")
            elif isinstance(value, List):
                ##print(f"... checking attributes {attr}")
                for key in value:
                    if not key in node[attr]:
                        msg = f"    node missing attribute {attr}.{key} from model"
                        ##print(msg)
                        append_to_anomalies(out_anomalies, "MODEL", msg, logger)
        elif type_name == 'str':
            # check the value
            if value == node[attr] or (attr == 'dtype' and 'eopf_is_scaled' in node.keys()):
                msg = f"    node attribute {attr} value {value} matches"
                ##print(msg)
            else:
                msg = f"    node attribute {attr} value {node[attr]} differs from model {value}"
                ##print(msg)
                append_to_anomalies(out_anomalies, "MODEL", msg, logger)


def validateEopfZarr(product_model: dict, 
                     reference_model = {}, 
                     out_anomalies: List[AnomalyDescriptor] = None, 
                     logger = None) -> None:
    # check that the product_model and model have the same product_model type
    product_type = product_model.get('product_type_regex', product_model.get('container_type_regex', ".*"))
    ##print(f"product_type = {product_type }") 
    if product_type != ".*":
        model_type_regex = reference_model.get('product_type_regex', reference_model.get('container_type_regex', ".*"))
        if product_type == None:
            msg = "Input product type is unknown"
            append_to_anomalies(out_anomalies, "MODEL", msg, logger)
        elif not re.fullmatch(model_type_regex, product_type):
            msg = f"Product type {product_type} doesn't match {model_type_regex}"
            append_to_anomalies(out_anomalies, "MODEL", msg, logger)

    # differentiate simple or container product_model        
    if 'sub_containers' in product_model.keys() and len(product_model['sub_containers']) > 0:
        logger.info(f"product_model has sub_containers") 
        if  'sub_containers' in reference_model.keys():
            ##print("model has sub_containers") 
            for sub_container_name in product_model['sub_containers'].keys():
                logger.info(f"product_model sub_container name = {sub_container_name}")
                p = product_model.get('sub_containers').get(sub_container_name)
                m = reference_model.get('sub_containers').get(sub_container_name)
                ##print(f"model sub_container type = {type(m).__name__}")
                logger.info(f"... validating sub_containers {sub_container_name}")
                if product_model.get('path'):
                    p['path'] = product_model['path'] + '/' + sub_container_name
                validateEopfZarr(p, m, anomalies, logger) # TODO
        else:
            msg = f"Product with sub_containers does not match model"
            append_to_anomalies(out_anomalies, "MODEL", msg, logger)

    if 'sub_products' in product_model.keys():
        logger.info("product_model has sub_products") 
        if  'sub_products' in reference_model.keys():
            ##print("model has sub_products") 
            for sub_product_name in product_model['sub_products'].keys():
                logger.debug(f"product_model sub_product name = {sub_product_name}")
                p = product_model.get('sub_products').get(sub_product_name)
                ##print(f"product_model sub_product type = {type(p).__name__}")
                ## use best sub_product_name match
                keys = reference_model.get('sub_products').keys()
                logger.debug(f"model sub_products= {keys}")
                matches = [word for word in keys if SequenceMatcher(None, word, sub_product_name).ratio() > 0.5]
                #best_match = difflib.get_close_matches(sub_product_name, model.get('sub_products').keys())[0] 
                logger.debug(f"model matches= {matches}")
                best_match = matches[0]
                ##logger.debug(f"model sub_product name best match = {best_match}")
                m = reference_model.get('sub_products').get(best_match)
                ##print(f"model sub_product type = {type(m).__name__}")
                logger.info(f"... validating sub_product {sub_product_name}")
                ##print(f"...             with model {best_match}")
                if product_model.get('path'):
                    zarr_url = product_model['path'] + '/' + sub_product_name
                else:
                    zarr_url = ''
                validateZarrModel(p['variables'], m['variables'], zarr_url, '', anomalies, logger) # TODO
        else:
            msg = f"Product with sub_products does not match model"
            append_to_anomalies(out_anomalies, "MODEL", msg, logger)
    elif 'sub_products' not in reference_model.keys():
        logger.debug("product_model has no sub_products") 
        validateZarrModel(product_model['variables'], reference_model['variables'], product_model.get('path', ''), '', anomalies, logger) # TODO
    else:
        msg = f"Product does not match model container structure"
        append_to_anomalies(out_anomalies, "MODEL", msg, logger)


def getProductType(zarr, logger:Logger):
    # the product_model type is defined in the Zarr attribute "stac_discovery.properties.product:type"
    try:
        product_type = zarr.attrs["stac_discovery"]["properties"]["product:type"]
    except Exception as e:
        logger.error(f"Failed to extract product type {e}")
        product_type = None
    return product_type


def loadReferenceModel(product_type, modelPath = None, logger:Logger = None):
    if modelPath:
        model_path = Path(modelPath)
        if model_path.is_dir():
            model_file = modelPath + '/' + product_type + '.json'
        elif model_path.exists():
            model_file = modelPath
        else:
            if logger:
                logger.error(f"ERROR: path to '{args.model}' not found")
            exit(1)
    else:
        relative = os.path.dirname(__file__) + '/../' + EOPF_MODELS_BASEPATH + '/' + str(product_type) + '.json'
        model_file = str(Path(relative).resolve())
        
    model = fetch_and_parse_file(model_file)

    if logger:
        logger.info(f"model {model_file}")
    
    return model


def printValidationResult(anomalies: List[AnomalyDescriptor], logger:Logger) -> int:
    if len(anomalies) > 0:
        logger.info(f"validation results:")
        limit = 10 if (logger.getEffectiveLevel() >= logging.INFO) else 1000
        count = 1
        for a in anomalies:
            logger.error(f"{a.category} {a.description}")
            count += 1
            if count > limit:
                logger.warning(f"... and {len(anomalies) - count} more validation errors (use --verbose to see them all)")
                break
        logger.error("validation failed")
        ##print(f"logger.getEffectiveLevel()={logger.getEffectiveLevel()} limit={logging.INFO} imposes {limit}")
        return(1)
    else:
        logger.info(f"validation successful")
        return(0)


if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.WARN,
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    action_help='''\
    inspect   to print the structure of the contents of a Zarr file
    model     to generate and dump Zarr model
    validate  to validate a Zarr file'''
    example_help='''example:
    python3 eopf_qa/eopf_zarr_qa.py validate --zarr path_to_your_zarr_file.zarr
    '''
    
    parser = argparse.ArgumentParser(description='EOPF Zarr Model Validator', epilog=example_help, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('action', choices=['inspect', 'model', 'validate'], help=action_help)
    parser.add_argument("--zarr", type=str, help="path to Zarr file (may be zip) or URL", required=True)
    parser.add_argument("--model", type=str, help="path to model file or directory", required=False)
    parser.add_argument("-s", "--skipzarrfilecheck", help="skip Zarr .attrs file checks", action='store_true', required=False, default=False)
    parser.add_argument("-v", "--verbose",  help="verbose mode, multiple -v increments mode 0:WARN 1:INFO 2:DEBUG", action='count', required=False, default=0)
    parser.add_argument("-q", "--quiet", help="do not print result, only exit code > 0 on error", action='store_true', required=False, default=False)
    args = parser.parse_args()

    #zarr_url = "https://objects.eodc.eu/e05ab01a9d56408d82ac32d69a5aae2a:202604-s02msil1c-eu/07/products/cpm_v270/S2B_MSIL1C_20260407T125029_N0512_R095_T26TKK_20260407T150815.zarr"
    zarr_url = args.zarr
    # convert to URL
    ##if not zarr_url.startswith("http") and not zarr_url.startswith("s3:"):
    ##    # translate to absolute path
    ##    zarr_url = Path(zarr_url).resolve().as_uri()

    logger = logging.getLogger()
    
    # lazy load the Zarr file 
    if Path(zarr_url).suffix == '.zip':
        stream = ZipStore(zarr_url)
    else:
        stream = zarr_url
    try:
        z = zarr.open_group(stream, mode='r', use_consolidated=True)
    except Exception as e:
        logger.error(e)
        exit(1)

    if args.verbose == 1:
        logger.setLevel(logging.INFO)
    elif args.verbose > 1:
        logger.setLevel(logging.DEBUG)

    # the product_model type is defined in the Zarr attribute "stac_discovery.properties.product:type"
    product_type = getProductType(z, logger)

    if args.action == 'inspect':
        logger.info(f"inspecting structure of {zarr_url}")
        try:
            ##print(f"{z.name} {str(z.metadata)[0:250]}\n{z.info}" ) ## debug code
            printZarrStructure(z)
        except Exception as e:
            logger.error(e)
            exit(1)
    else:
        product_model = createEopfModelFromZarr(z, product_type, logger)

        if args.action == 'model':
            logger.info(f"dumping model for {zarr_url}")
            print(json.dumps(product_model))
        elif args.action == 'validate':
            logger.info(f"validating {zarr_url}")

            if args.skipzarrfilecheck:
                if not args.quiet:
                    logger.warning(f"skipping Zarr .attrs file checks")
            else:
                # will use this path to validate the accessibility of the zarr groups and attr files
                product_model['path'] = zarr_url if zarr_url.startswith('http') else Path(zarr_url).resolve().as_uri() 

            try:
                reference_model = loadReferenceModel(product_type, args.model, logger)
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                exit(1)

            anomalies: List[AnomalyDescriptor] = []
            validateEopfZarr(product_model, reference_model, anomalies, logger) # TODO
            # ensure final result is displayed
            if args.quiet == True:
                result = 1 if len(anomalies) > 0 else 0
            else:
                ##print(f"{logger.getEffectiveLevel()} >= {logging.INFO}")
                if len(anomalies) == 0:
                    # ensure success log is shown
                    logger.setLevel(logging.DEBUG)
                result = printValidationResult(anomalies, logger)
            exit(result)
        else:
            logger.error(f"ERROR: no action specified")
            parser.print_help()
