# Utility to validate a EOPF Zarr structure
#
import argparse
import json
import pathlib
import re
import zarr
from dataclasses import dataclass
from difflib import SequenceMatcher
from logging import Logger
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from stac_validator.utilities import fetch_and_parse_file
from zarr.core.array import Array
from zarr.core.group import Group
from zarr.storage import ZipStore
##from aiohttp._http_parser import path
#from eopf.product.eo_container_validation import _validate_sub_product

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
        if len(name) > 0:
            print(f"{indent}{name}: ")
        else:
            print(f"{indent}/")
        for k in node.keys():
            # recursion
            printZarrStructure(node.get(k), node.name + '/', indent + '    ')
        #
    elif isinstance(node, Array):
        dtype = node.dtype
        shape = str(node.shape).replace(',)',')').replace(', ',',')
        unit = ' ' + str(node.attrs.get('units')) if 'units' in node.attrs else ''
        add_offset = node.attrs.get('add_offset', '')
        scale_factor = node.attrs.get('scale_factor' '')
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
    
def generateEopfZarrModel(node: Dict, model = {}, base = '') -> Dict:
    name = str(node.name).replace(base, '')
    if isinstance(node, Group):
        for k in node.keys():
            # recurse
            generateEopfZarrModel(node.get(k), model, base = base)
            
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

def validateZarrModel(node: dict, model = {}, out_anomalies: List[AnomalyDescriptor] = None, logger = None) -> None:
    ## TODO: report anything in node, that is not in model
    # traverse the variables in parallel
    ##print(f"... node.type={type(node).__name__} and model.type={type(model).__name__}")
    for attr in model.keys():
        value = model[attr]
        type_name = type(value).__name__
        ##print(f"... searching node for {attr} ({type_name}) in {type(node).__name__}")
        node_type_name = type(node[attr]).__name__ if attr in node.keys() else None 
        if attr in ['dont_look_under', 'required', 'eopf_is_masked', 'eopf_is_scaled', 'eopf_target_dtype']:
            # ignore eopf-cpm specials
            continue
        elif type_name != node_type_name:
            msg = f"    node {attr} type ({node_type_name}) differs from model ({type_name})"
            ##print(msg)
            append_to_anomalies(out_anomalies, "MODEL", msg, logger)
        elif type_name != 'str' and not attr in node.keys():
            msg = f"    node missing {attr} from model"
            ##print(msg)
            append_to_anomalies(out_anomalies, "MODEL", f"node missing {attr} from model", logger)
        elif type_name != 'str' and len(value) > 0:
            if isinstance(value, Dict):
                ##print(f">>> traversing group {attr}")
                # iterate
                validateZarrModel(node[attr], value, out_anomalies, logger)
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
            if value == node[attr] or (attr == 'dtype' and 'eopf_is_scaled' in model['attrs'].keys()):
                msg = f"    node attribute {attr} value {value} matches"
                ##print(msg)
            else:
                msg = f"    node attribute {attr} value {node[attr]} differs from model {value}"
                ##print(msg)
                append_to_anomalies(out_anomalies, "MODEL", msg, logger)


def validateEopfZarr(product: dict, model = {}, out_anomalies: List[AnomalyDescriptor] = None, logger = None) -> None:
    # check that the product and model have the same product type
    product_type = product.get('product_type_regex', product.get('container_type_regex', ".*"))
    print(f"product_type = {product_type }") 
    if product_type != ".*":
        model_type_regex = model.get('product_type_regex', model.get('container_type_regex', ".*"))
        if product_type == None:
            msg = "Input product type is unknown"
            append_to_anomalies(out_anomalies, "MODEL", msg, logger)
        elif not re.fullmatch(model_type_regex, product_type):
            msg = f"Product type detected {product.product_type} doesn't match {model.product_type_regex}"
            append_to_anomalies(out_anomalies, "MODEL", msg, logger)

    # differentiate simple or container product        
    if 'sub_products' in product.keys():
        ##print("product has sub_products") 
        if  'sub_products' in model.keys():
            ##print("model has sub_products") 
            i = 0
            for sub_product_name in product['sub_products'].keys():
                ##print(f"product sub_product name = {sub_product_name}")
                p = product.get('sub_products').get(sub_product_name)
                print(f"product sub_product type = {type(p).__name__}")
                ## use best sub_product_name match
                ##print(f"model sub_product names = {model.get('sub_products').keys()}")
                keys = model.get('sub_products').keys()
                matches = [word for word in keys if SequenceMatcher(None, word, sub_product_name).ratio() > 0.5]
                #best_match = difflib.get_close_matches(sub_product_name, model.get('sub_products').keys())[0] 
                ##print(f"model best matches= {matches}")
                best_match = matches[0]
                ##print(f"model sub_product name best match = {best_match}")
                m = model.get('sub_products').get(best_match)
                ##print(f"model sub_product type = {type(m).__name__}")
                print(f"... validating sub_product {sub_product_name}")
                print(f"...             with model {best_match}")
                validateZarrModel(p, m, anomalies, logger) # TODO
                i += 1
        else:
            msg = f"Product with container does not match model"
            append_to_anomalies(out_anomalies, "MODEL", msg, logger)
    elif 'sub_products' not in model.keys():
        print("product has no sub_products") 
        validateZarrModel(product['variables'], model['variables'], anomalies, logger) # TODO
    else:
        msg = f"Product does not match model container structure"
        append_to_anomalies(out_anomalies, "MODEL", msg, logger)

def printValidationResult(anomalies: List[AnomalyDescriptor]):
    if len(anomalies) > 0:
        print("ERROR: validation failed")
        for a in anomalies:
            print(f"{a.category} {a.description}")
    else:
        print(f"INFO: validation successful")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='EOPF STAC Validator')
    parser.add_argument('action', choices=['dump', 'model', 'validate'])
    parser.add_argument("--zarr", type=str, help="Path to Zarr file or URL", required=True)
    parser.add_argument("--model", type=str, help="Path to model file or directory", required=False)
    parser.add_argument("-v", "--verbose", type=bool, help="verbose mode", action=argparse.BooleanOptionalAction, required=False, default=False)
    args = parser.parse_args()

    #zarr_url = "https://objects.eodc.eu/e05ab01a9d56408d82ac32d69a5aae2a:202604-s02msil1c-eu/07/products/cpm_v270/S2B_MSIL1C_20260407T125029_N0512_R095_T26TKK_20260407T150815.zarr"
    zarr_url = args.zarr
    
    if args.verbose:
        print(f"Product file: {zarr_url}")

    if pathlib.Path(zarr_url).suffix == '.zip':
        z = zarr.open(ZipStore(zarr_url))
    else:
        z = zarr.open(zarr_url)

    # the product type is defined in the Zarr attribute "stac_discovery.properties.product:type"
    try:
        product_type = z.attrs["stac_discovery"]["properties"]["product:type"]
        if args.verbose:
            print(f"Product type: {product_type}")
    except Exception as e:
        print(f"Failed to extract product type {e}")
        product_type = "UNKNOWN"

    if args.action == 'dump':
        printZarrStructure(z)
    else:
        if 'conditions' not in z.keys():
            # process container elements 
            sub_products = {}
            product = { "container_type_regex": product_type, "sub_products": sub_products}
            ## TODO: create attribute model
            product['attrs'] = {}
            ## TODO: check if our Zarr products have sub_containers
            product['sub_containers'] = {}
            for p in z.keys():
                product_type = z.attrs["stac_discovery"]["properties"]["product:type"]
                component = z.get(p)
                # iterate into model with clipped name
                vars = generateEopfZarrModel(component, base = p + '/')
                sub_products[p] = { "product_type_regex": product_type, "variables": vars, "attrs": {} }
        else:
            vars = generateEopfZarrModel(z)
            product = { "product_type_regex": product_type, "variables": vars }
            ## TODO: create attribute model
            product['attrs'] = {}

        if args.action == 'model':
            print(json.dumps(product))
        elif args.action == 'validate':
            if args.model:
                model_path = pathlib.Path(args.model)
                if model_path.is_dir():
                    model_file = args.model + '/' + product_type + '.json'
                elif model_path.exists():
                    model_file = args.model
                else:
                    print(f"ERROR: path to '{args.model}' not found")
                    exit(1)
            else:
                model_file = EOPF_MODELS_BASEPATH + '/' + product_type + '.json'
            if args.verbose:
                print(f"Loading model: {model_file}")
            model = fetch_and_parse_file(model_file)
            if args.verbose:
                print(json.dumps(model))

            logger = None
            anomalies: List[AnomalyDescriptor] = []
            validateEopfZarr(product, model, anomalies, logger) # TODO
            printValidationResult(anomalies)
        else:
            print(f"ERROR: no action specified")
            parser.print_help()
