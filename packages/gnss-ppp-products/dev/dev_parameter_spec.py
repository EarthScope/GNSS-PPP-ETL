from ast import For, pattern
import enum
from fileinput import filename
from itertools import product
from os import name
import re
from token import OP
from unittest.mock import Base
from gnss_ppp_products.specifications.format.spec import FormatVersionSpec
from grpc import server
import yaml
from attr import dataclass

from pydantic import BaseModel, Field   
from typing import List, Optional
from pathlib import Path
from enum import Enum


class _PassthroughDict(dict):
    """Returns '{key}' for any key not in the dict, so unresolved placeholders survive."""

    def __missing__(self, key):
        return f"{{{key}}}"


class DerivationMethod(str, Enum):
    ENUM = "enum"
    COMPUTED = "computed"


class Parameter(BaseModel):
    name: str = Field(..., description="The name of the parameter.")
    value: Optional[str] = Field(None, description="The value of the parameter.")
    pattern: Optional[str] = Field(None, description="A regex pattern to match the parameter value.")
    description: Optional[str] = Field(None, description="A description of the parameter.")
    derivation: Optional[DerivationMethod] = Field(DerivationMethod.ENUM, description="The method used to derive the parameter value.")

class ParameterCatalog:
    def __init__(self, parameters: List[Parameter]):
        self.parameters = {parameter.name: parameter for parameter in parameters}

    def get(self, name: str, default=None) -> Optional[Parameter]:
        return self.parameters.get(name, default)
    
    def __contains__(self, item):
        return item in self.parameters
    
    def __getitem__(self, key):
        return self.parameters[key]

class ProductPath(BaseModel):
    pattern: str = Field( description="A regex pattern to match the product directory.")
    value: Optional[str] = Field(None, description="The value of the product directory.")
    description: Optional[str] = Field(None, description="A description of the product directory.")

    def derive(self, parameters: List[Parameter]) -> None:
        """
        Example
        ----------
        >>> parameters = [
            Parameter(name="SSSS", value=None, pattern="[A-Za-z0-9]{4}"),
            Parameter(name="MONUMENT", value="1"),
            Parameter(name="R", value="R"),
            Parameter(name="CCC", value="001"),
            Parameter(name="S", value="S"),
            Parameter(name="YYYY", value="2024"),
            Parameter(name="DDD", value="150"),
            Parameter(name="HH", value="12"),
            Parameter(name="MM", value="30"),
            Parameter(name="DDU", value="101"),
            Parameter(name="FRU", value="445"),
            Parameter(name="D", value="2")
            ]

        }
        >>> product = ProductPath(
            pattern="{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{FRU}_{D}O.rnx",
            description="The product directory pattern."
            )

        >>> product.derive(parameters)

        >>> product.value  # This will return the derived value based on the pattern and parameters
        
        "[A-Za-z0-9]{4}1R001_S_20241501230_101_445_2O.rnx"

        """
        if self.value is not None:
            return

        for param in parameters:
            # check if the paramter name is in the pattern
            if f"{{{param.name}}}" in self.pattern:
                if param.value is not None:
                    self.pattern = self.pattern.replace(f"{{{param.name}}}", param.value)
                elif param.pattern is not None:
                    self.pattern = self.pattern.replace(f"{{{param.name}}}", param.pattern)

                

        return None

class Product(BaseModel):
    name: str = Field(..., description="The name of the product format.")
    parameters: List[Parameter] = Field(..., description="A list of parameters for the product format.")
    directory: Optional[ProductPath] = Field(default=None, description="The directory where the product format is located.")
    filename: Optional[ProductPath] = Field(default=None, description="The filename pattern for the product format.")


class FormatSpec(BaseModel):
    name:str
    version: Optional[str] = None
    variant: Optional[str] = None
    parameters: Optional[List[dict]] = Field(default_factory=list)
    filename: Optional[str] = None

    def resolve(self, parameter_catalog: ParameterCatalog) -> Product:
        resolved_parameters = {}
        for param in self.parameters:
            # Check if the parameter exists in the parameter catalog. If it does, get it and update the value. If it doesnt simply add the parameter to the resolved parameters.
            name = param["name"]
            default = parameter_catalog.get(name, None)
            if default is not None:
                resolved_param = default.copy(update=param)
            else:
                resolved_param = Parameter(**param)
            resolved_parameters[name] = resolved_param
        
        product = Product(
            name=self.name,
            parameters=list(resolved_parameters.values()),
            filename=ProductPath(pattern=self.filename) if self.filename else None
        )
        
        return product


class FormatSpecVariantCatalog(BaseModel):
    name:str
    variants : dict[str, FormatSpec]

class FormatSpecVersionCatalog(BaseModel):
    name:str
    versions : dict[str, FormatSpecVariantCatalog]

class FormatSpecCatalog(BaseModel):
    formats: dict[str, FormatSpecVersionCatalog]
    @classmethod
    def from_yaml(cls, path: Path) -> "FormatSpecCatalog":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data.get("formats", {}))

class VariantCatalog(BaseModel):
    name:str
    variants: dict[str, Product]

class VersionCatalog(BaseModel):
    name:str
    versions: dict[str, VariantCatalog]

class FormatCatalog(BaseModel):
    formats: dict[str, VersionCatalog]

    def __init__(self,format_spec_catalog: FormatSpecCatalog, parameter_catalog: ParameterCatalog):
        formats = {}
        for format_name, format_spec_cat in format_spec_catalog.formats.items():
            versions = {}
            for version_name, version_spec in format_spec_cat.versions.items():
                variants = {}
                for variant_name, format_spec in version_spec.variants.items():
                    product = format_spec.resolve(parameter_catalog)
                    variants[variant_name] = product
                versions[version_name] = VariantCatalog(name=version_spec.name, variants=variants)
            formats[format_name] = VersionCatalog(name=format_spec_cat.name, versions=versions)
        super().__init__(formats=formats)


class ProductSpec(BaseModel):
    name:str
    format: str
    version: str 
    variant: str 
    parameters: Optional[List[Parameter]] = Field(default_factory=list)

    def resolve(self, format_catalog: FormatCatalog) -> Product:
        # Get the parent product from the format catalog
        format_spec: Product = format_catalog.formats[self.format].versions[self.version].variants[self.variant]

        # Start with ALL format parameters, then overlay product spec overrides
        resolved_parameters = {p.name: p.model_copy() for p in format_spec.parameters}
        for param in self.parameters:
            if param.name in resolved_parameters:
                resolved_parameters[param.name] = resolved_parameters[param.name].model_copy(
                    update=param.model_dump(exclude_none=True)
                )
            else:
                resolved_parameters[param.name] = param

        product = format_spec.model_copy(update={"name": self.name, "parameters": list(resolved_parameters.values())})
        return product

class ProductSpecVariantCatalog(BaseModel):
    name:str
    variants: dict[str, ProductSpec]

class ProductSpecVersionCatalog(BaseModel):
    name:str
    versions: dict[str, ProductSpecVariantCatalog]

class ProductSpecCatalog(BaseModel):
    products: dict[str, ProductSpecVersionCatalog]

class ProductCatalog(BaseModel):
    products: dict[str, VersionCatalog]

    def __init__(self, product_spec_catalog: ProductSpecCatalog, format_catalog: FormatCatalog):
        products = {}

        for product_name, product_spec_cat in product_spec_catalog.products.items():
            versions = {}
            for version_name, version_spec in product_spec_cat.versions.items():
                variants = {}
                for variant_name, product_spec in version_spec.variants.items():
                    product = product_spec.resolve(format_catalog)
                    variants[variant_name] = product
                versions[version_name] = VariantCatalog(name=version_spec.name, variants=variants)
            products[product_name] = VersionCatalog(name=product_spec_cat.name, versions=versions)
            
        super().__init__(products=products)


# Test

parameter_spec_dict = [
    {
        "name": "SSSS",
        "pattern": "[A-Za-z0-9]{4}",
        "description": '4-character station code (e.g., "ALIC", "BRST")',
        "derivation": "enum",
    },
    {
        "name": "MONUMENT",
        "pattern": "[0-9]",
        "description": "1-character monument or marker number",
        "derivation": "enum",
    },
    {
        "name": "R",
        "pattern": "[0-9]{1}",
        "description": "Receiver number (0 if not specified)",
        "derivation": "enum",
    },
    {
        "name": "CCC",
        "pattern": "[A-Za-z0-9]{3}",
        "description": '3-character data center or agency code (e.g., "COD", "IGS", "JPL")',
        "derivation": "enum",
    },
    {
        "name": "SSSMRCCC_",
        "pattern": "[A-Z0-9]{9}_",
        "description": 'Optional station identifier block (e.g., "ALIC00MRC_", "BRST01MRC_")',
        "derivation": "enum",
    },
    {
        "name": "YYYY",
        "pattern": "\\d{4}",
        "description": '4-digit year (e.g., "2024")',
        "derivation": "computed",
    },
    {
        "name": "YY",
        "pattern": "\\d{2}",
        "description": '2-digit year (e.g., "24" for 2024)',
        "derivation": "computed",
    },
    {
        "name": "MONTH",
        "pattern": "\\d{2}",
        "description": "2-digit month (01–12)",
        "derivation": "computed",
    },
    {
        "name": "DAY",
        "pattern": "\\d{2}",
        "description": "2-digit day of month (01–31)",
        "derivation": "computed",
    },
    {
        "name": "DDD",
        "pattern": "\\d{3}",
        "description": "3-digit day of year (001–366)",
        "derivation": "computed",
    },
    {
        "name": "HH",
        "pattern": "\\d{2}",
        "description": "2-digit hour of day (00–23)",
        "derivation": "computed",
    },
    {
        "name": "MM",
        "pattern": "\\d{2}",
        "description": "2-digit minute of hour (00–59)",
        "derivation": "computed",
    },
    {
        "name": "VMFHH",
        "pattern": "H\\d{2}",
        "description": "VMF sub-daily hour tag (H00, H06, H12, H18)",
        "derivation": "enum",
    },
    {"name": "DDU", "pattern": "\\d{2}[DHMS]", "derivation": "enum"},
    {"name": "FRU", "pattern": "\\d{2}[DHMS]", "derivation": "enum"},
    {"name": "LEN", "pattern": "\\d{2}[DHMS]", "derivation": "enum"},
    {"name": "SMP", "pattern": "\\d{2}[DHMS]", "derivation": "enum"},
    {"name": "AAA", "pattern": "[a-zA-Z0-9]{3}", "derivation": "enum"},
    {"name": "V", "pattern": "[0-9]", "derivation": "enum"},
    {"name": "PPP", "pattern": "[A-Z0-9]{3}", "derivation": "enum"},
    {"name": "TTT", "pattern": "[A-Z]{3}", "derivation": "enum"},
    {"name": "CNT", "pattern": "[A-Z]{3}", "derivation": "enum"},
    {"name": "FMT", "pattern": "[A-Z0-9]{3}", "derivation": "enum"},
    {"name": "S", "pattern": "[A-Z]", "derivation": "enum"},
    {"name": "D", "pattern": "[A-Z]", "derivation": "enum"},
    {"name": "T", "pattern": "[a-zA-Z]", "derivation": "enum"},
    {"name": "PRODUCT", "pattern": "[A-Za-z0-9]+", "derivation": "enum"},
    {"name": "RESOLUTION", "pattern": "[0-9x.]+", "derivation": "enum"},
    {
        "name": "GPSWEEK",
        "pattern": "\\d{4}",
        "description": "GPS week number since January 6, 1980",
        "derivation": "computed",
    },
    {"name": "REFFRAME", "pattern": "igs[0-9A-Z]{2}", "derivation": "computed"},
    {
        "name": "INSTRUMENT",
        "pattern": "[A-Z]{3}1B",
        "description": "LEO instrument code with level suffix (e.g., GNV1B, ACC1B)",
        "derivation": "enum",
    },
    {
        "name": "SPACECRAFT",
        "pattern": "[CD]",
        "description": "Spacecraft identifier (C or D for GRACE/GRACE-FO)",
        "derivation": "enum",
    },
    {
        "name": "RELNUM",
        "pattern": "\\d+\\..*",
        "description": "Release/version number followed by file extension",
        "derivation": "enum",
    },
]

format_spec_dict = {
    "RINEX": {
        "name": "RINEX",
        "versions": {
            "2": {
                "name": "2",
                "variants": {
                    "observation": {
                        "name": "RINEX",
                        "version": "2",
                        "variant": "observation",
                        "parameters": [
                            {"name": "SSSS", "description": "4 char station code"},
                            {"name": "DDD", "description": "day of year (001-366)"},
                            {"name": "YY", "description": "2 digit year"},
                            {"name": "T", "description": "file type code"},
                        ],
                        "filename": "{SSSS}{DDD}0.{YY}{T}",
                    },
                    "navigation": {
                        "name": "RINEX",
                        "version": "2",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "DDD"},
                            {"name": "YY"},
                            {"name": "T"},
                        ],
                        "filename": "{SSSS}{DDD}0.{YY}{T}",
                    },
                    "meteorological": {
                        "name": "RINEX",
                        "version": "2",
                        "variant": "meteorological",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "DDD"},
                            {"name": "YY"},
                        ],
                        "filename": "{SSSS}{DDD}0.{YY}m",
                    },
                },
            },
            "3": {
                "name": "3",
                "variants": {
                    "observation": {
                        "name": "RINEX",
                        "version": "3",
                        "variant": "observation",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "MONUMENT"},
                            {"name": "R"},
                            {"name": "CCC"},
                            {"name": "S"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "DDU"},
                            {"name": "FRU"},
                            {"name": "D"},
                        ],
                        "filename": "{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{FRU}_{D}O.rnx",
                    },
                    "navigation": {
                        "name": "RINEX",
                        "version": "3",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "MONUMENT"},
                            {"name": "R"},
                            {"name": "CCC"},
                            {"name": "S"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "DDU"},
                            {"name": "D"},
                        ],
                        "filename": "{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{D}N.rnx",
                    },
                    "meteorological": {
                        "name": "RINEX",
                        "version": "3",
                        "variant": "meteorological",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "MONUMENT"},
                            {"name": "R"},
                            {"name": "CCC"},
                            {"name": "S"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "DDU"},
                            {"name": "D"},
                        ],
                        "filename": "{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{D}M.rnx",
                    },
                },
            },
            "4": {
                "name": "4",
                "variants": {
                    "observation": {
                        "name": "RINEX",
                        "version": "4",
                        "variant": "observation",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "MONUMENT"},
                            {"name": "R"},
                            {"name": "CCC"},
                            {"name": "S"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "DDU"},
                            {"name": "FRU"},
                            {"name": "D"},
                        ],
                        "filename": "{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{FRU}_{D}O.rnx",
                    },
                    "navigation": {
                        "name": "RINEX",
                        "version": "4",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "MONUMENT"},
                            {"name": "R"},
                            {"name": "CCC"},
                            {"name": "S"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "DDU"},
                            {"name": "D"},
                        ],
                        "filename": "{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{D}N.rnx",
                    },
                    "meteorological": {
                        "name": "RINEX",
                        "version": "4",
                        "variant": "meteorological",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "MONUMENT"},
                            {"name": "R"},
                            {"name": "CCC"},
                            {"name": "S"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "DDU"},
                            {"name": "D"},
                        ],
                        "filename": "{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{D}M.rnx",
                    },
                },
            },
        },
    },
    "PRODUCT": {
        "name": "PRODUCT",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "AAA"},
                            {"name": "V"},
                            {"name": "PPP"},
                            {"name": "TTT"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "LEN"},
                            {"name": "SMP"},
                            {"name": "CNT"},
                            {"name": "FMT"},
                        ],
                        "filename": "{AAA}{V}{PPP}{TTT}_{YYYY}{DDD}{HH}{MM}_{LEN}_{SMP}_{CNT}.{FMT}.*",
                    },
                    "station": {
                        "name": "PRODUCT",
                        "version": "1",
                        "variant": "station",
                        "parameters": [
                            {"name": "AAA"},
                            {"name": "V"},
                            {"name": "PPP"},
                            {"name": "TTT"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "LEN"},
                            {"name": "SMP"},
                            {"name": "SSSMRCCC_"},
                            {"name": "CNT"},
                            {"name": "FMT"},
                        ],
                        "filename": "{AAA}{V}{PPP}{TTT}_{YYYY}{DDD}{HH}{MM}_{LEN}_{SMP}_{SSSMRCCC_}_{CNT}.{FMT}.*",
                    },
                },
            },
        },
    },
    "TABLE": {
        "name": "TABLE",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "TABLE",
                        "version": "1",
                        "variant": "default",
                        "parameters": [],
                        "filename": "",
                    },
                },
            },
        },
    },
    "VIENNA_MAPPING_FUNCTIONS": {
        "name": "VIENNA_MAPPING_FUNCTIONS",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "VIENNA_MAPPING_FUNCTIONS",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "PRODUCT"},
                            {"name": "YYYY"},
                            {"name": "MONTH"},
                            {"name": "DAY"},
                            {"name": "VMFHH", "pattern": "H(?:00|06|12|18)"},
                        ],
                        "filename": "{PRODUCT}_{YYYY}{MONTH}{DAY}.{VMFHH}",
                    },
                    "orography": {
                        "name": "VIENNA_MAPPING_FUNCTIONS",
                        "version": "1",
                        "variant": "orography",
                        "parameters": [
                            {
                                "name": "RESOLUTION",
                                "pattern": "\\b(2\\.5x2|1x1|5x5)\\b",
                            }
                        ],
                        "filename": "orography_ell_{RESOLUTION}",
                    },
                },
            },
        },
    },
    "LEO_L1B": {
        "name": "LEO_L1B",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "LEO_L1B",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "INSTRUMENT"},
                            {"name": "YYYY"},
                            {"name": "MONTH"},
                            {"name": "DAY"},
                            {"name": "SPACECRAFT", "pattern": "[CD]"},
                            {"name": "RELNUM", "pattern": "\\d+\\..*"},
                        ],
                        "filename": "{INSTRUMENT}_{YYYY}-{MONTH}-{DAY}_{SPACECRAFT}_{RELNUM}",
                    },
                },
            },
        },
    },
    "ANTENNAE": {
        "name": "ANTENNAE",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "ANTENNAE",
                        "version": "1",
                        "variant": "default",
                        "parameters": [{"name": "REFFRAME"}],
                        "filename": "{REFFRAME}.atx",
                    },
                    "archive": {
                        "name": "ANTENNAE",
                        "version": "1",
                        "variant": "archive",
                        "parameters": [{"name": "REFFRAME"}, {"name": "GPSWEEK"}],
                        "filename": "{REFFRAME}_{GPSWEEK}.atx",
                    },
                },
            },
        },
    },
}

product_spec_dict = {
    # ── RINEX_OBS ──────────────────────────────────────────────────
    "RINEX_OBS": {
        "name": "RINEX_OBS",
        "versions": {
            "2": {
                "name": "2",
                "variants": {
                    "observation": {
                        "name": "RINEX_OBS",
                        "format": "RINEX",
                        "version": "2",
                        "variant": "observation",
                        "parameters": [
                            {"name": "T", "pattern": "\\b[dot]\\b"},
                        ],
                    },
                },
            },
            "3": {
                "name": "3",
                "variants": {
                    "observation": {
                        "name": "RINEX_OBS",
                        "format": "RINEX",
                        "version": "3",
                        "variant": "observation",
                        "parameters": [
                            {"name": "T", "pattern": "\\b[ONM]\\b"},
                            {"name": "D", "pattern": "\\b[GRECEJSM]\\b"},
                        ],
                    },
                },
            },
            "4": {
                "name": "4",
                "variants": {
                    "observation": {
                        "name": "RINEX_OBS",
                        "format": "RINEX",
                        "version": "4",
                        "variant": "observation",
                        "parameters": [
                            {"name": "T", "pattern": "\\b[ONM]\\b"},
                            {"name": "D", "pattern": "\\b[GRECEJSM]\\b"},
                        ],
                    },
                },
            },
        },
    },
    # ── RINEX_NAV ──────────────────────────────────────────────────
    "RINEX_NAV": {
        "name": "RINEX_NAV",
        "versions": {
            "2": {
                "name": "2",
                "variants": {
                    "navigation": {
                        "name": "RINEX_NAV",
                        "format": "RINEX",
                        "version": "2",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "T", "pattern": "\\b[ngh]\\b"},
                        ],
                    },
                },
            },
            "3": {
                "name": "3",
                "variants": {
                    "navigation": {
                        "name": "RINEX_NAV",
                        "format": "RINEX",
                        "version": "3",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "T", "pattern": "\\b[ON]\\b"},
                            {"name": "D", "pattern": "\\b[GRECEJSM]\\b"},
                        ],
                    },
                },
            },
            "4": {
                "name": "4",
                "variants": {
                    "navigation": {
                        "name": "RINEX_NAV",
                        "format": "RINEX",
                        "version": "4",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "T", "pattern": "\\b[ON]\\b"},
                            {"name": "D", "pattern": "\\b[GRECEJSM]\\b"},
                        ],
                    },
                },
            },
        },
    },
    # ── RINEX_MET ──────────────────────────────────────────────────
    "RINEX_MET": {
        "name": "RINEX_MET",
        "versions": {
            "2": {
                "name": "2",
                "variants": {
                    "meteorological": {
                        "name": "RINEX_MET",
                        "format": "RINEX",
                        "version": "2",
                        "variant": "meteorological",
                        "parameters": [
                            {"name": "T", "value": "m"},
                        ],
                    },
                },
            },
            "3": {
                "name": "3",
                "variants": {
                    "meteorological": {
                        "name": "RINEX_MET",
                        "format": "RINEX",
                        "version": "3",
                        "variant": "meteorological",
                        "parameters": [
                            {"name": "T", "value": "M"},
                            {"name": "D", "pattern": "\\b[GRECEJSM]\\b"},
                        ],
                    },
                },
            },
            "4": {
                "name": "4",
                "variants": {
                    "meteorological": {
                        "name": "RINEX_MET",
                        "format": "RINEX",
                        "version": "4",
                        "variant": "meteorological",
                        "parameters": [
                            {"name": "T", "value": "M"},
                            {"name": "D", "pattern": "\\b[GRECEJSM]\\b"},
                        ],
                    },
                },
            },
        },
    },
    # ── ORBIT ──────────────────────────────────────────────────────
    "ORBIT": {
        "name": "ORBIT",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "ORBIT",
                        "format": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "LEN", "value": "01D"},
                            {"name": "CNT", "value": "ORB"},
                            {"name": "FMT", "value": "SP3"},
                        ],
                    },
                },
            },
        },
    },
    # ── CLOCK ──────────────────────────────────────────────────────
    "CLOCK": {
        "name": "CLOCK",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "CLOCK",
                        "format": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "FMT", "value": "CLK"},
                            {"name": "LEN", "value": "01D"},
                            {"name": "CNT", "value": "CLK"},
                        ],
                    },
                },
            },
        },
    },
    # ── ERP ────────────────────────────────────────────────────────
    "ERP": {
        "name": "ERP",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "ERP",
                        "format": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "FMT", "value": "ERP"},
                            {"name": "LEN", "value": "01D"},
                            {"name": "CNT", "value": "ERP"},
                            {"name": "SMP", "value": "01D"},
                        ],
                    },
                },
            },
        },
    },
    # ── BIA ────────────────────────────────────────────────────────
    "BIA": {
        "name": "BIA",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "BIA",
                        "format": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "FMT", "value": "BIA"},
                            {"name": "LEN", "value": "01D"},
                            {"name": "CNT", "value": "OSB"},
                        ],
                    },
                },
            },
        },
    },
    # ── ATTOBX ─────────────────────────────────────────────────────
    "ATTOBX": {
        "name": "ATTOBX",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "ATTOBX",
                        "format": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "FMT", "value": "OBX"},
                            {"name": "LEN", "value": "01D"},
                            {"name": "CNT", "value": "ATT"},
                            {"name": "SMP", "value": "30S"},
                        ],
                    },
                },
            },
        },
    },
    # ── IONEX ──────────────────────────────────────────────────────
    "IONEX": {
        "name": "IONEX",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "IONEX",
                        "format": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "FMT", "value": "INX"},
                            {"name": "LEN", "value": "01D"},
                            {"name": "CNT", "value": "GIM"},
                        ],
                    },
                },
            },
        },
    },
    # ── RNX3_BRDC ──────────────────────────────────────────────────
    "RNX3_BRDC": {
        "name": "RNX3_BRDC",
        "versions": {
            "3": {
                "name": "3",
                "variants": {
                    "navigation": {
                        "name": "RNX3_BRDC",
                        "format": "RINEX",
                        "version": "3",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "SSSS", "value": "BRDC"},
                            {"name": "DDU", "value": "01D"},
                            {"name": "S", "value": "R"},
                        ],
                    },
                },
            },
        },
    },
    # ── LEAP_SEC ───────────────────────────────────────────────────
    "LEAP_SEC": {
        "name": "LEAP_SEC",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "LEAP_SEC",
                        "format": "TABLE",
                        "version": "1",
                        "variant": "default",
                        "parameters": [],
                        "filename": "leap.sec",
                    },
                },
            },
        },
    },
    # ── SAT_PARAMS ─────────────────────────────────────────────────
    "SAT_PARAMS": {
        "name": "SAT_PARAMS",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "SAT_PARAMS",
                        "format": "TABLE",
                        "version": "1",
                        "variant": "default",
                        "parameters": [],
                        "filename": "sat_parameters",
                    },
                },
            },
        },
    },
    # ── VMF ────────────────────────────────────────────────────────
    "VMF": {
        "name": "VMF",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "VMF",
                        "format": "VIENNA_MAPPING_FUNCTIONS",
                        "version": "1",
                        "variant": "default",
                        "parameters": [],
                    },
                },
            },
        },
    },
    # ── OROGRAPHY ──────────────────────────────────────────────────
    "OROGRAPHY": {
        "name": "OROGRAPHY",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "orography": {
                        "name": "OROGRAPHY",
                        "format": "VIENNA_MAPPING_FUNCTIONS",
                        "version": "1",
                        "variant": "orography",
                        "parameters": [
                            {"name": "RESOLUTION", "value": "5x5"},
                        ],
                    },
                },
            },
        },
    },
    # ── LEO_L1B ────────────────────────────────────────────────────
    "LEO_L1B": {
        "name": "LEO_L1B",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "LEO_L1B",
                        "format": "LEO_L1B",
                        "version": "1",
                        "variant": "default",
                        "parameters": [],
                    },
                },
            },
        },
    },
    # ── ATTATX ─────────────────────────────────────────────────────
    "ATTATX": {
        "name": "ATTATX",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "ATTATX",
                        "format": "ANTENNAE",
                        "version": "1",
                        "variant": "default",
                        "parameters": [],
                    },
                    "archive": {
                        "name": "ATTATX",
                        "format": "ANTENNAE",
                        "version": "1",
                        "variant": "archive",
                        "parameters": [],
                    },
                },
            },
        },
    },
}

'''

Build the parameter catalog, format catalog, and product catalog from the above specifications. This will be used for validation and parsing of filenames in the GNSS PPP ETL pipeline.

'''

PARAMETER_CATALOG = ParameterCatalog(parameters=[Parameter(**p) for p in parameter_spec_dict])
format_spec_catalog = FormatSpecCatalog(formats = format_spec_dict)
FORMAT_CATALOG = FormatCatalog(format_spec_catalog=format_spec_catalog, parameter_catalog=PARAMETER_CATALOG)
product_spec_catalog = ProductSpecCatalog(products=product_spec_dict)
PRODUCT_CATALOG = ProductCatalog(product_spec_catalog=product_spec_catalog, format_catalog=FORMAT_CATALOG)


class Server(BaseModel):
    id: str
    hostname: str
    protocol: Optional[str] = None
    auth_required: Optional[bool] = False
    description: Optional[str] = None

class ProductSpec(BaseModel):
    id:str
    server_id: str
    available: bool = True
    product_name: str
    product_version: Optional[List[str] | str] = None
    description: Optional[str] = None
    parameters: List[Parameter]
    directory: ProductPath


class ResourceSpec(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    website: Optional[str] = None
    servers: List[Server] = []
    products: List[ProductSpec] = []


resource_spec_dict = {
    "id": "WUM",
    "name": "Wuhan University GNSS Research Center",
    "website": "http://www.igs.gnsswhu.cn/",
    "servers": [
        {
            "id": "wuhan_ftp",
            "name": "Primary FTP",
            "hostname": "ftp://igs.gnsswhu.cn",
            "protocol": "ftp",
            "auth_required": False,
            "notes": "Primary FTP server, no authentication required",
        }
    ],
    "products": [
        {
            "id": "wuhan_orbit",
            "product_name": "ORBIT",
            "server_id": "wuhan_ftp",
            "available": True,
            "description": "Precise satellite orbits",
            "parameters": [
                {"name": "AAA", "value": "WUM"},
                {"name": "AAA", "value": "WMC"},
                {"name": "TTT", "value": "FIN"},
                {"name": "TTT", "value": "RAP"},
                {"name": "PPP", "value": "MGX"},
                {"name": "PPP", "value": "DEM"},
                {"name": "SMP", "value": "05M"},
                {"name": "SMP", "value": "15M"},
            ],
            "directory": {"pattern": "pub/whu/phasebias/{YYYY}/orbit/"},
        },
        {
            "id": "wuhan_clock",
            "product_name": "CLOCK",
            "server_id": "wuhan_ftp",
            "available": True,
            "description": "Precise satellite and station clocks",
            "parameters": [
                {"name": "AAA", "value": "WUM"},
                {"name": "AAA", "value": "WMC"},
                {"name": "TTT", "value": "FIN"},
                {"name": "TTT", "value": "RAP"},
                {"name": "PPP", "value": "MGX"},
                {"name": "PPP", "value": "DEM"},
                {"name": "SMP", "value": "30S"},
                {"name": "SMP", "value": "05M"},
            ],
            "directory": {"pattern": "pub/whu/phasebias/{YYYY}/clock/"},
        },
    ],
}

resource_spec = ResourceSpec(**resource_spec_dict)


class ResourceQuery(BaseModel):
    """A single concrete query target — one combination of parameter values."""

    product: Product  # base product with parameters pinned
    server: Server  # which server to fetch from
    directory: ProductPath  # resolved directory template
    needed_parameters: List[Parameter] = []  # parameters that were needed to resolve the product at the server level (e.g., for directory resolution) and thus must be provided by the caller

    def resolve(self) -> 'ResourceQuery':

        to_keep = [p for p in self.product.parameters if p.value is None]
        to_update = {p.name: p for p in self.product.parameters if p.value is not None}
        format_dict = _PassthroughDict({k: p.value for k,p in to_update.items()})
        self.product.filename.pattern = self.product.filename.pattern.format_map(format_dict)
        self.directory.pattern = self.directory.pattern.format_map(format_dict)
        self.needed_parameters = to_keep
        return self

class ResourceCatalog(BaseModel):
    """Resolves a ResourceSpec against a ProductCatalog into queryable products."""

    id: str
    name: str
    description: Optional[str] = None
    website: Optional[str] = None
    servers: List[Server]
    queries: List[ResourceQuery]

    def __init__(self, resource_spec: ResourceSpec, product_catalog: ProductCatalog):
        queries = []
        for rp_spec in resource_spec.products:
            if not rp_spec.available:
                continue

            # 1. Look up base product(s) from catalog
            version_catalog = product_catalog.products.get(rp_spec.product_name)
            if version_catalog is None:
                continue

            # Determine which versions to query
            versions = rp_spec.product_version or list(version_catalog.versions.keys())
            if isinstance(versions, str):
                versions = [versions]

            # 2. Group multi-valued parameters: {name: [Parameter, ...]}
            param_groups: dict[str, list[Parameter]] = {}
            for p in rp_spec.parameters:
                param_groups.setdefault(p.name, []).append(p)

            # 3. Cartesian product of parameter groups
            combos = _cartesian_product(param_groups)

            # 4. Resolve server
            server = next(s for s in resource_spec.servers if s.id == rp_spec.server_id)

            # 5. For each version × variant × combo → one ResourceQuery
            for ver_key in versions:
                variant_catalog = version_catalog.versions.get(ver_key)
                if variant_catalog is None:
                    continue
                for variant_name, base_product in variant_catalog.variants.items():
                    for combo in combos:
                        # Overlay combo parameter values onto the base product
                        merged_params = _merge_parameters(
                            base_product.parameters, combo
                        )
                        pinned_product = base_product.model_copy(
                            update={"parameters": merged_params,"name":rp_spec.product_name }
                        )
                        queries.append(
                            ResourceQuery(
                                product=pinned_product,
                                server=server,
                                directory=rp_spec.directory,
                            ).resolve()
                        )

        super().__init__(
            id=resource_spec.id,
            name=resource_spec.name,
            description=resource_spec.description,
            website=resource_spec.website,
            servers=resource_spec.servers,
            queries=queries,
        )


def _cartesian_product(
    param_groups: dict[str, list[Parameter]],
) -> list[list[Parameter]]:
    """Expand {name: [vals...]} into list of combinations, one Parameter per name."""
    from itertools import product as iterproduct

    names = list(param_groups.keys())
    if not names:
        return [[]]
    value_lists = [param_groups[n] for n in names]
    return [list(combo) for combo in iterproduct(*value_lists)]


def _merge_parameters(
    base_params: List[Parameter],
    overrides: List[Parameter],
) -> List[Parameter]:
    """Return base params with overrides applied (by name)."""
    result = {p.name: p.model_copy() for p in base_params}
    for override in overrides:
        if override.name in result:
            result[override.name] = result[override.name].model_copy(
                update=override.model_dump(exclude_none=True)
            )
        else:
            result[override.name] = override.model_copy()
    return list(result.values())


RESOURCE_CATALOG = ResourceCatalog(resource_spec=resource_spec, product_catalog=PRODUCT_CATALOG)

print(RESOURCE_CATALOG.queries[0].model_dump_json(indent=2))
