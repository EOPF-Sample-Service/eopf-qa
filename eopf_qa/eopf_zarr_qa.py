# Utility to validate a EOPF Zarr structure
#
import argparse
import json
import re
import zarr
from dataclasses import dataclass
from logging import Logger
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from stac_validator.utilities import fetch_and_parse_file
from zarr.core.array import Array
from zarr.core.group import Group

#known_eopf_attribute_keys = ['coordinates', 'dimensions', 'dtype', 'long_name', 'short_name', 'units', 'flag_masks', 'flag_meanings', 'flag_values']

EOPF_TOP_ATTR_CATEGORY = ("stac_discovery", "other_metadata", "processing_history")
EOPF_STD_ATTRIBUTES = ['_ARRAY_DIMENSIONS', 'dimensions', 'dtype', 'long_name', 'units', 'valid_min', 'valid_max', 'add_offset', 'scale_factor', 'standard_name']
EOPF_MODELS_BASEPATH = 'models'

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

def printStructure(node: dict, base: str = '', indent: str = ''): # to STDOUT
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
            printStructure(node.get(k), node.name + '/', indent + '    ')
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
    
def generateEopfZarrModel(node: Dict, model = {}) -> Dict:
    name = node.name 
    if isinstance(node, Group):
        for k in node.keys():
            # recurse
            generateEopfZarrModel(node.get(k), model)
            
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
    for attr in model.keys():
        value = model[attr]
        type_name = type(value).__name__
        node_type_name = type(node[attr]).__name__ if attr in node else None 
        ##print(f"... checking {attr} ({type_name})")
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

        ##else:
        ##    print(f"    check done.")
    ##var_list: list[str] = validate_product_variables_against_model(product, model, mode, out_anomalies, logger)
    #var_list = []
    #for key in chain.from_iterable(product.items()):
    #    var_list.append(str(key))
    #    print(str(key))
    #for var in product.walk():
    #    if not isinstance(var, EOVariable):
    #        continue
    #    var_list.append(var.path)
    #    if model.variables is not None and var.path in model.variables:
    #        validate_variable(var, model.variables[var.path], mode, out_anomalies, logger)
    #    elif mode == "EXACT":
    #        append_to_anomalies(
    #            out_anomalies,
    #            "MODEL",
    #            f"Variable {var.path} not found in model but is in {product.name}",
    #            logger,
    #        )
    #validate_required_variables_against_model(product, var_list, model, mode, out_anomalies, logger)
    #validate_attrs_against_jsonschema(product, model.attrs_schema, mode, out_anomalies, logger)
    #validate_attrs_against_model(product, model.attrs, mode, out_anomalies, logger)

def validateEopfZarr(node: dict, model = {}, out_anomalies: List[AnomalyDescriptor] = None, logger = None) -> None:
    # check that the product and model have the same product type
    if model.get('product_type_regex', ".*") != ".*":
        if product_type == None:
            msg = "Input product type is unknown"
            append_to_anomalies(out_anomalies, "MODEL", msg, logger)
        elif not re.fullmatch(model.get('product_type_regex'), product_type):
            msg = f"Product type detected {product.product_type} doesn't match {model.product_type_regex}"
            append_to_anomalies(out_anomalies, "MODEL", msg, logger)
    validateZarrModel(product['variables'], model['variables'], anomalies, logger) # TODO

def printValidationResult(anomalies: List[AnomalyDescriptor]):
    if len(anomalies) > 0:
        print("Validation failed")
        for a in anomalies:
            print(f"{a.category} {a.description}")
    else:
        print(f"Validation successful")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='EOPF STAC Validator')
    parser.add_argument('action', choices=['dump', 'model', 'validate'])
    parser.add_argument("--zarr", type=str, help="Path to Zarr file or URL", required=True)
    parser.add_argument("--model", type=str, help="Path to model file", required=False)
    parser.add_argument("-v", "--verbose", type=bool, help="verbose mode", action=argparse.BooleanOptionalAction, required=False, default=False)
    args = parser.parse_args()

    #zarr_url = "https://objects.eodc.eu/e05ab01a9d56408d82ac32d69a5aae2a:202604-s02msil1c-eu/07/products/cpm_v270/S2B_MSIL1C_20260407T125029_N0512_R095_T26TKK_20260407T150815.zarr"
    zarr_url = args.zarr
    
    if args.verbose:
        print(f"Product file: {zarr_url}")

    z = zarr.open(zarr_url)

    # the product type is defined in the Zarr attribute "stac_discovery.properties.product:type"
    product_type = z.attrs["stac_discovery"]["properties"]["product:type"]
    if args.verbose:
        print(f"Product type: {product_type}")

    if args.action == 'dump':
        printStructure(z)
    else:
        vars = generateEopfZarrModel(z)
        if args.action == 'model':
            product = { "product_type_regex": product_type, "variables": vars }
            print(json.dumps(product))
        elif args.action == 'validate':
            model_file = args.model if args.model else EOPF_MODELS_BASEPATH + '/' + product_type + '.json'
            if args.verbose:
                print(f"Loading model: {model_file}")
            model = fetch_and_parse_file(model_file)
            ##print(json.dumps(model))
            product = { "product_type": product_type, "variables": vars }
            anomalies: List[AnomalyDescriptor] = []
            logger = None
            validateEopfZarr(product, model, anomalies, logger) # TODO
            printValidationResult(anomalies)
        else:
            print(f"ERROR: no action specified")
            parser.print_help()
