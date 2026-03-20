import datetime
from collections import defaultdict
from itertools import product as iterproduct
import re
from token import OP
import yaml

from pydantic import BaseModel, Field   
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path
from enum import Enum

from gnss_ppp_products.specifications.metadata.metadata_catalog import MetadataCatalog
from gnss_ppp_products.utilities.metadata_funcs import register_computed_fields
from gnss_ppp_products.specifications.local.local import LocalResourceSpec, LocalCollection


def _build_metadata_catalog() -> MetadataCatalog:
    """Build a MetadataCatalog with all computed date fields registered."""
    catalog = MetadataCatalog()
    register_computed_fields(catalog)
    return catalog


def _ensure_datetime(date: datetime.date | datetime.datetime) -> datetime.datetime:
    """Coerce a date to a timezone-aware datetime."""
    if isinstance(date, datetime.date) and not isinstance(date, datetime.datetime):
        return datetime.datetime(date.year, date.month, date.day, tzinfo=datetime.timezone.utc)
    if date.tzinfo is None:
        return date.replace(tzinfo=datetime.timezone.utc)
    return date


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
                resolved_param = default.model_copy(update=param, deep=True)
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
        resolved_parameters = {p.name: p.model_copy(deep=True) for p in format_spec.parameters}
        for param in self.parameters:
            if param.name in resolved_parameters:
                resolved_parameters[param.name] = resolved_parameters[param.name].model_copy(
                    update=param.model_dump(exclude_none=True),deep=True
                )
            else:
                resolved_parameters[param.name] = param

        product = format_spec.model_copy(update={"name": self.name, "parameters": list(resolved_parameters.values())},deep=True)
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
            if product_name == "ORBIT":
                print(product_spec_cat)
            for version_name, version_spec in product_spec_cat.versions.items():
                variants = {}
                for variant_name, product_spec in version_spec.variants.items():
                    product: Product = product_spec.resolve(format_catalog)
                    if hasattr(product, "filename") and hasattr(product.filename, "derive"):
                        product.filename.derive(product.parameters)
                    variants[variant_name] = product
                versions[version_name] = VariantCatalog(name=version_spec.name, variants=variants)
            if product_name in products:
                print(f"Duplicate product name {product_name} found. Overwriting previous entry.")
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


# ═══════════════════════════════════════════════════════════════════
# Resource-Level Models
# ═══════════════════════════════════════════════════════════════════

class Server(BaseModel):
    id: str
    hostname: str
    protocol: Optional[str] = None
    auth_required: Optional[bool] = False
    description: Optional[str] = None

class ResourceProductSpec(BaseModel):
    """A product offering within a resource/center — maps a catalog product to a server with parameter overrides."""
    id: str
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
    products: List[ResourceProductSpec] = []


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

        # Deep-copy filename/directory before mutating to avoid cross-query contamination
        if self.product.filename:
            self.product = self.product.model_copy(deep=True, update={
                "filename": ProductPath(pattern=self.product.filename.pattern.format_map(format_dict))
            })
        self.directory = ProductPath(pattern=self.directory.pattern.format_map(format_dict))
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
                            update={"parameters": merged_params,"name":rp_spec.product_name }, deep=True
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
    result = {p.name: p.model_copy(deep=True) for p in base_params}
    for override in overrides:
        if override.name in result:
            result[override.name] = result[override.name].model_copy(
                update=override.model_dump(exclude_none=True), deep=True
            )
        else:
            result[override.name] = override.model_copy(deep=True)
    return list(result.values())


# ═══════════════════════════════════════════════════════════════════
# ResourceRegistry — flat pool of queries from multiple centers
# ═══════════════════════════════════════════════════════════════════

class ResourceRegistry(BaseModel):
    """Aggregates local and remote ResourceCatalogs with local-first lookup."""

    local_catalogs: List[ResourceCatalog] = []
    remote_catalogs: List[ResourceCatalog] = []

    def add_local(self, catalog: ResourceCatalog) -> None:
        self.local_catalogs.append(catalog)

    def add_remote(self, catalog: ResourceCatalog) -> None:
        self.remote_catalogs.append(catalog)

    @property
    def all_queries(self) -> List[ResourceQuery]:
        return [q for c in self.local_catalogs + self.remote_catalogs for q in c.queries]

    @staticmethod
    def _narrow_queries(queries: List[ResourceQuery], **filters: str) -> List[ResourceQuery]:
        """Filter a flat list of queries by parameter values and product_name."""
        results = []
        for q in queries:
            if "product_name" in filters and q.product.name != filters["product_name"]:
                continue
            param_dict = {p.name: p.value for p in q.product.parameters}
            match = True
            for key, val in filters.items():
                if key == "product_name":
                    continue
                if key in param_dict and param_dict[key] is not None and param_dict[key] != val:
                    match = False
                    break
            if match:
                results.append(q)
        return results

    def narrow(self, **filters: str) -> List[ResourceQuery]:
        return self._narrow_queries(self.all_queries, **filters)

    def search_local(self, **filters: str) -> List[ResourceQuery]:
        """Search only local catalogs."""
        local_queries = [q for c in self.local_catalogs for q in c.queries]
        return self._narrow_queries(local_queries, **filters)

    def search_remote(self, **filters: str) -> List[ResourceQuery]:
        """Search only remote catalogs."""
        remote_queries = [q for c in self.remote_catalogs for q in c.queries]
        return self._narrow_queries(remote_queries, **filters)

    @staticmethod
    def _best_from(candidates: List[ResourceQuery], prefer: Optional[Dict[str, str]] = None) -> Optional[ResourceQuery]:
        if not candidates:
            return None
        if not prefer:
            return candidates[0]
        def score(q: ResourceQuery) -> int:
            param_dict = {p.name: p.value for p in q.product.parameters if p.value}
            return sum(1 for k, v in prefer.items() if param_dict.get(k) == v)
        return max(candidates, key=score)

    def best(self, product_name: str, prefer: Optional[Dict[str, str]] = None) -> Optional[ResourceQuery]:
        """Return the single best query across all catalogs."""
        return self._best_from(self.narrow(product_name=product_name), prefer)

    def best_local(self, product_name: str, prefer: Optional[Dict[str, str]] = None) -> Optional[ResourceQuery]:
        """Return the best local query for a product."""
        return self._best_from(self.search_local(product_name=product_name), prefer)

    def best_remote(self, product_name: str, prefer: Optional[Dict[str, str]] = None) -> Optional[ResourceQuery]:
        """Return the best remote query for a product."""
        return self._best_from(self.search_remote(product_name=product_name), prefer)

    def summary(self) -> str:
        local_q = sum(len(c.queries) for c in self.local_catalogs)
        remote_q = sum(len(c.queries) for c in self.remote_catalogs)
        lines = [f"ResourceRegistry: {len(self.local_catalogs)} local + {len(self.remote_catalogs)} remote catalogs ({local_q} + {remote_q} = {local_q+remote_q} queries)"]
        for cat in self.local_catalogs:
            product_names = sorted(set(q.product.name for q in cat.queries))
            lines.append(f"  LOCAL  [{cat.id}] {cat.name}: {len(cat.queries)} queries ({', '.join(product_names)})")
        for cat in self.remote_catalogs:
            product_names = sorted(set(q.product.name for q in cat.queries))
            lines.append(f"  REMOTE [{cat.id}] {cat.name}: {len(cat.queries)} queries ({', '.join(product_names)})")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# QueryProfile — thin axis-alias config
# ═══════════════════════════════════════════════════════════════════

class AxisAlias(BaseModel):
    """Maps a human-friendly axis name to one or more parameter names."""
    alias: str
    parameters: List[str]
    description: Optional[str] = None

class SortPreference(BaseModel):
    """Defines the preferred order for an axis during resolution."""
    axis: str
    order: List[str]

class QueryProfile(BaseModel):
    """Thin query configuration — just axis aliases and sort preferences.
    
    Replaces the 260-line query_config.yaml with a minimal mapping.
    All actual queryable values come from the product/resource specs themselves.
    """
    axes: List[AxisAlias] = []
    sort_preferences: List[SortPreference] = []

    def resolve_axis(self, alias: str) -> List[str]:
        """Map an alias to parameter names."""
        for ax in self.axes:
            if ax.alias == alias:
                return ax.parameters
        return [alias]  # fallback: treat the alias as a direct parameter name

    def get_preference(self, axis: str) -> Optional[List[str]]:
        """Get sort order for a given axis."""
        for sp in self.sort_preferences:
            if sp.axis == axis:
                return sp.order
        return None


# ═══════════════════════════════════════════════════════════════════
# DependencySpec — global + per-dep preference cascade
# ═══════════════════════════════════════════════════════════════════

class DependencyItem(BaseModel):
    """A single dependency: a product + optional per-dep preference overrides."""
    product_name: str
    version: Optional[str] = None
    variant: Optional[str] = None
    required: bool = True
    prefer: Optional[Dict[str, str]] = None  # per-dependency overrides


class ResolvedDependency(BaseModel):
    """The outcome of resolving one dependency item."""
    product_name: str
    required: bool
    source: Optional[str] = None       # "local" | "remote" | None
    catalog_id: Optional[str] = None   # which catalog provided it (e.g., "LOCAL", "WUM")
    query: Optional[ResourceQuery] = None
    prefer_used: Dict[str, str] = {}

    @property
    def found(self) -> bool:
        return self.query is not None

    @property
    def needs_download(self) -> bool:
        return self.source == "remote"


class DependencyResolution(BaseModel):
    """Full resolution result for a DependencySpec."""
    spec_name: str
    items: List[ResolvedDependency] = []

    @property
    def local_hits(self) -> List[ResolvedDependency]:
        return [d for d in self.items if d.source == "local"]

    @property
    def remote_needed(self) -> List[ResolvedDependency]:
        return [d for d in self.items if d.source == "remote"]

    @property
    def missing(self) -> List[ResolvedDependency]:
        return [d for d in self.items if not d.found]

    @property
    def all_found(self) -> bool:
        return all(d.found or not d.required for d in self.items)

    def summary(self) -> str:
        lines = []
        for d in self.items:
            status = "LOCAL" if d.source == "local" else "REMOTE" if d.source == "remote" else "MISSING"
            flag = "✓" if d.found else ("!" if d.required else "—")
            if d.query:
                host = d.query.server.hostname
                lines.append(f"  {flag} {d.product_name:12s} [{status:6s}] {d.catalog_id} @ {host}")
            else:
                req = "REQUIRED" if d.required else "optional"
                lines.append(f"  {flag} {d.product_name:12s} [{status:6s}] — {req}")
        return "\n".join(lines)


class DependencySpec(BaseModel):
    """Dependency specification with global defaults and per-item overrides.
    
    Workflow:
      1. Define dependencies + preferences
      2. resolve() searches LOCAL first
      3. Only queries REMOTE for anything not found locally
    """
    name: str
    description: Optional[str] = None
    global_prefer: Dict[str, str] = {}
    dependencies: List[DependencyItem] = []

    def effective_prefer(self, dep: DependencyItem) -> Dict[str, str]:
        """Merge global preferences with per-dependency overrides."""
        merged = dict(self.global_prefer)
        if dep.prefer:
            merged.update(dep.prefer)
        return merged

    def resolve(self, registry: ResourceRegistry) -> DependencyResolution:
        """Two-phase resolve: local first, remote fallback."""
        resolution = DependencyResolution(spec_name=self.name)

        for dep in self.dependencies:
            prefer = self.effective_prefer(dep)

            # Phase 1: search local
            local_match = registry.best_local(dep.product_name, prefer)
            if local_match:
                # Find which local catalog owns this query
                cat_id = _find_catalog_id(registry.local_catalogs, local_match)
                resolution.items.append(ResolvedDependency(
                    product_name=dep.product_name,
                    required=dep.required,
                    source="local",
                    catalog_id=cat_id,
                    query=local_match,
                    prefer_used=prefer,
                ))
                continue

            # Phase 2: search remote
            remote_match = registry.best_remote(dep.product_name, prefer)
            if remote_match:
                cat_id = _find_catalog_id(registry.remote_catalogs, remote_match)
                resolution.items.append(ResolvedDependency(
                    product_name=dep.product_name,
                    required=dep.required,
                    source="remote",
                    catalog_id=cat_id,
                    query=remote_match,
                    prefer_used=prefer,
                ))
                continue

            # Not found anywhere
            resolution.items.append(ResolvedDependency(
                product_name=dep.product_name,
                required=dep.required,
                prefer_used=prefer,
            ))

        return resolution


def _find_catalog_id(catalogs: List[ResourceCatalog], query: ResourceQuery) -> Optional[str]:
    """Find which catalog a query belongs to."""
    for cat in catalogs:
        if query in cat.queries:
            return cat.id
    return None


# ═══════════════════════════════════════════════════════════════════
# RemoteResourceFactory
# ═══════════════════════════════════════════════════════════════════

class RemoteResourceFactory:
    """Registry of remote data centers and their resolved catalogs.
    
    Usage::
    
        remote = RemoteResourceFactory(product_catalog)
        remote.register(ResourceSpec(**wum_dict))
        remote.register(ResourceSpec(**igs_dict))
        # or from raw dicts:
        remote.register_dict(code_dict)
    """

    def __init__(self, product_catalog: ProductCatalog) -> None:
        self._product_catalog = product_catalog
        self._catalogs: Dict[str, ResourceCatalog] = {}
        self._specs: Dict[str, ResourceSpec] = {}

    def register(self, spec: ResourceSpec) -> ResourceCatalog:
        self._specs[spec.id] = spec
        cat = ResourceCatalog(resource_spec=spec, product_catalog=self._product_catalog)
        self._catalogs[cat.id] = cat
        return cat

    def register_dict(self, spec_dict: dict) -> ResourceCatalog:
        return self.register(ResourceSpec(**spec_dict))

    def get(self, center_id: str) -> ResourceCatalog:
        return self._catalogs[center_id]

    @property
    def centers(self) -> List[str]:
        return list(self._catalogs.keys())

    @property
    def catalogs(self) -> List[ResourceCatalog]:
        return list(self._catalogs.values())

    @property
    def all_queries(self) -> List[ResourceQuery]:
        return [q for cat in self._catalogs.values() for q in cat.queries]

    @staticmethod
    def match_pinned_query(found: Product, incoming: Product) -> Optional[Product]:
        """Check if a found query matches an incoming product based on pinned parameters."""
        found_params = {p.name: p.value for p in found.parameters if p.value is not None}
        incoming_params = {p.name: p.value for p in incoming.parameters if p.value is not None}
        matching_keys = set(found_params.keys()) & set(incoming_params.keys())
        for key in matching_keys:
            
            found_val = found_params[key]
            incoming_val = incoming_params[key]
            if found_val != incoming_val:
                print(f"Parameter {key} does not match: found={found_val}, incoming={incoming_val}")
                return None
            
        for p in incoming.parameters:
            if p.value is None and p.name in found_params:
                p.value = found_params.get(p.name)
        print(f"DEBUG MATCH")
        return incoming
    
    def resolve_product(self,product:Product,resource_id:str) -> Optional[ResourceQuery]:
        """Resolve a ResourceQuery's product and server for remote access."""
        cat = self._catalogs.get(resource_id)
        if cat is None:
            raise KeyError(f"Resource {resource_id!r} not found in remote catalogs. Known resources: {list(self._catalogs.keys())}")
        query = next((q for q in cat.queries if q.product.name == product.name), None)
        if query is None:
            raise KeyError(f"Product {product.name!r} not found in resource {resource_id!r}. Known products: {set(q.product.name for q in cat.queries)}")
        
        # Deep copy so we never mutate the catalog's original query
        query = query.model_copy(deep=True)
        
        # We need to match incoming product values with query product values.
        matched_product: Optional[Product] = self.match_pinned_query(query.product, product)
        if matched_product is None:
            return None
        
        query.product.filename.derive(product.parameters) if query.product.filename else None
        query.directory.derive(product.parameters)
        return query

# ═══════════════════════════════════════════════════════════════════
# LocalResourceFactory — collections-based (from local_config.yaml)
# ═══════════════════════════════════════════════════════════════════

class LocalResourceFactory:
    """Registry of local file-system product archives using collections-based layout.

    Loads a ``LocalResourceSpec`` (from ``local_config.yaml``) plus the
    ``ProductCatalog`` to produce one ``ResourceQuery`` per locally-known
    product type, using the collection's directory template and the catalog's
    filename pattern.

    Usage::

        spec = LocalResourceSpec.from_yaml("local_config.yaml")
        local = LocalResourceFactory(spec, product_catalog, base_dir=Path("/data/gnss"))
    """

    def __init__(
        self,
        local_spec: LocalResourceSpec,
        product_catalog: ProductCatalog,
        parameter_catalog: ParameterCatalog,
        base_dir: Path,
    ) -> None:
        self._local_spec = local_spec
        self._product_catalog = product_catalog
        self._parameter_catalog = parameter_catalog
        self._base_dir = base_dir

        # Build a single local "server"
        self.local_server = Server(
            id="local_disk",
            hostname=str(base_dir) if base_dir else "local",
            protocol="file",
            auth_required=False,
            description="Local product archive",
        )

        # Build spec_name → directory_template map and generate queries per collection
        self._item_to_dir: Dict[str, str] = {}
        self._catalogs: List[ResourceCatalog] = []

        for coll_name, coll in local_spec.collections.items():
            for item in coll.items:
                self._item_to_dir[item] = coll.directory
        
        # Check that all specs in the product catalog have a local directory template
        for prod_name in product_catalog.products.keys():
            if prod_name not in self._item_to_dir:
                raise ValueError(f"Product {prod_name!r} in catalog has no local directory template. Source file: {local_spec.source_file}.")
             


    def resolve_directory(
        self,
        product_name: str,
        date: datetime.date | datetime.datetime,
    ) -> Path:
        """Resolve the local directory for a product spec on a given date."""
        dt = _ensure_datetime(date)
        directory_template = self._item_to_dir.get(product_name)
        if directory_template is None:
            raise KeyError(
                f"Spec {product_name!r} not found in any local collection. "
                f"Known specs: {list(self._item_to_dir.keys())}"
            )
        resolved = self._parameter_catalog.resolve(directory_template, dt, computed_only=True)

        return self._base_dir / Path(resolved)
    
    def resolve_product(self,product:Product,date:datetime.datetime) -> Tuple[Server,ProductPath]:
        """Resolve a ResourceQuery's product and server for local access."""
        dt = _ensure_datetime(date)
        directory_template = self._item_to_dir.get(product.name)
        if directory_template is None:
            raise KeyError(
                f"Spec {product.name!r} not found in any local collection. "
                f"Known specs: {list(self._item_to_dir.keys())}"
            )
        directory_template_pp: ProductPath = ProductPath(pattern=directory_template)
        directory_template_pp.derive(product.parameters)

        

        return self.local_server, directory_template_pp

    def find_local_files(
        self, query: ResourceQuery, date: Optional[datetime.date] = None,
    ) -> List[Path]:
        """Search local disk for files matching a query."""
        dir_pattern = query.directory.pattern
        if date:
            dt = _ensure_datetime(date)
            dir_pattern = self._parameter_catalog.resolve(dir_pattern, dt, computed_only=True)

        if self._base_dir:
            search_dir = self._base_dir / dir_pattern
        else:
            search_dir = Path(query.server.hostname) / dir_pattern

        if not search_dir.exists():
            return []

        file_pattern = query.product.filename.pattern if query.product.filename else None
        if date and file_pattern:
            dt = _ensure_datetime(date)
            file_pattern = self._metadata_catalog.resolve(file_pattern, dt, computed_only=True)

        if file_pattern:
            return sorted(
                p for p in search_dir.iterdir()
                if p.is_file() and re.search(file_pattern, p.name, re.IGNORECASE)
            )
        return sorted(p for p in search_dir.iterdir() if p.is_file())


# ═══════════════════════════════════════════════════════════════════
# ProductQuery — ergonomic progressive narrowing
# ═══════════════════════════════════════════════════════════════════

class _TaggedQuery:
    """A ResourceQuery tagged with its provenance (source type & catalog id).
    
    This wrapper survives derivation operations like for_date() which create
    new ResourceQuery objects, preserving the local/remote and catalog origin.
    """
    __slots__ = ("query", "source_type", "catalog_id")

    def __init__(self, query: ResourceQuery, source_type: str, catalog_id: str):
        self.query = query
        self.source_type = source_type   # "local" or "remote"
        self.catalog_id = catalog_id


class ProductQuery:
    """Progressive narrowing query over the combined local + remote product space.
    
    Usage::
    
        pq = ProductQuery(
            remote_factory=remote,
            local_factory=local,
            query_profile=profile,
        )
        
        # Narrow by date (resolves YYYY, DDD, GPSWEEK, etc.)
        pq = pq.for_date(datetime.date(2024, 6, 15))
        
        # Narrow by product, center, solution
        orbits = pq.for_product("ORBIT").narrow(center="WUM", solution="FIN")
        
        # Local first, remote fallback
        local_hits = orbits.local_only()
        if not local_hits:
            remote_hits = orbits.remote_only()
    """

    def __init__(
        self,
        *,
        remote_factory: RemoteResourceFactory,
        local_factory: LocalResourceFactory,
        metadata_catalog: Optional[MetadataCatalog] = None,
        query_profile: Optional[QueryProfile] = None,
        _tagged: Optional[List[_TaggedQuery]] = None,
        _pinned: Optional[Dict[str, str]] = None,
        _date: Optional[datetime.date] = None,
    ):
        self._remote_factory = remote_factory
        self._local_factory = local_factory
        self._metadata_catalog = metadata_catalog or _build_metadata_catalog()
        self._query_profile = query_profile or QueryProfile()
        self._date = _date
        self._pinned: Dict[str, str] = dict(_pinned) if _pinned else {}

        if _tagged is not None:
            self._tagged = _tagged
        else:
            self._tagged = self._build_tagged()

    def _build_tagged(self) -> List[_TaggedQuery]:
        tagged: List[_TaggedQuery] = []
        for cat in self._local_factory.catalogs:
            for q in cat.queries:
                tagged.append(_TaggedQuery(q, "local", cat.id))
        for cat in self._remote_factory.catalogs:
            for q in cat.queries:
                tagged.append(_TaggedQuery(q, "remote", cat.id))
        return tagged

    # ── Derivation (immutable chaining) ──────────────────────────

    def _derive(
        self,
        tagged: Optional[List[_TaggedQuery]] = None,
        pinned: Optional[Dict[str, str]] = None,
        date: Optional[datetime.date] = None,
    ) -> "ProductQuery":
        return ProductQuery(
            remote_factory=self._remote_factory,
            local_factory=self._local_factory,
            metadata_catalog=self._metadata_catalog,
            query_profile=self._query_profile,
            _tagged=tagged if tagged is not None else list(self._tagged),
            _pinned=pinned if pinned is not None else dict(self._pinned),
            _date=date if date is not None else self._date,
        )

    # ── Narrowing ────────────────────────────────────────────────

    def for_date(self, date: datetime.date | datetime.datetime) -> "ProductQuery":
        """Pin computed parameters to a date and resolve templates
        using MetadataCatalog.resolve()."""
        dt = _ensure_datetime(date)
        mc = self._metadata_catalog
        # Collect the names of computed fields so we can prune needed_parameters
        computed_names = {name for name in mc._fields if mc._fields[name].compute is not None}
        new_tagged = []
        for tq in self._tagged:
            q = tq.query
            new_dir_pattern = mc.resolve(q.directory.pattern, dt, computed_only=True)
            new_dir = ProductPath(pattern=new_dir_pattern)
            new_filename = None
            if q.product.filename:
                new_filename = ProductPath(
                    pattern=mc.resolve(q.product.filename.pattern, dt, computed_only=True)
                )
            new_product = q.product.model_copy(
                update={"filename": new_filename} if new_filename else {},deep=True
            )
            new_q = ResourceQuery(
                product=new_product,
                server=q.server,
                directory=new_dir,
                needed_parameters=[
                    p for p in q.needed_parameters
                    if p.name not in computed_names
                ],
            )
            new_tagged.append(_TaggedQuery(new_q, tq.source_type, tq.catalog_id))
        # Build pinned dict from the resolved computed values
        pinned_date = {}
        for name in computed_names:
            field = mc._fields[name]
            if field.compute:
                pinned_date[name] = field.compute(dt)
        new_pinned = {**self._pinned, **pinned_date}
        return self._derive(tagged=new_tagged, pinned=new_pinned, date=date)

    def for_product(self, product_name: str) -> "ProductQuery":
        """Keep only queries for this product."""
        filtered = [tq for tq in self._tagged if tq.query.product.name == product_name]
        new_pinned = {**self._pinned, "product": product_name}
        return self._derive(tagged=filtered, pinned=new_pinned)

    def narrow(self, **axis_values: str) -> "ProductQuery":
        """Narrow by axis aliases or direct parameter names.
        
        Examples::
        
            pq.narrow(center="WUM")         # alias → AAA
            pq.narrow(solution="FIN")       # alias → TTT
            pq.narrow(AAA="WUM", TTT="FIN") # direct param names
        """
        param_filters: Dict[str, str] = {}
        for key, val in axis_values.items():
            param_names = self._query_profile.resolve_axis(key)
            for pn in param_names:
                param_filters[pn] = val

        filtered = self._tagged
        for param_name, param_value in param_filters.items():
            filtered = [
                tq for tq in filtered
                if _query_matches_param(tq.query, param_name, param_value)
            ]
        new_pinned = {**self._pinned, **axis_values}
        return self._derive(tagged=filtered, pinned=new_pinned)

    def local_only(self) -> "ProductQuery":
        """Keep only queries from local catalogs."""
        filtered = [tq for tq in self._tagged if tq.source_type == "local"]
        return self._derive(tagged=filtered, pinned={**self._pinned, "source": "local"})

    def remote_only(self) -> "ProductQuery":
        """Keep only queries from remote catalogs."""
        filtered = [tq for tq in self._tagged if tq.source_type == "remote"]
        return self._derive(tagged=filtered, pinned={**self._pinned, "source": "remote"})

    def from_center(self, *center_ids: str) -> "ProductQuery":
        """Keep only queries from specific centers (by catalog id)."""
        allowed = set(c.upper() for c in center_ids)
        filtered = [tq for tq in self._tagged if tq.catalog_id.upper() in allowed]
        return self._derive(tagged=filtered)

    # ── Resolution ───────────────────────────────────────────────

    def best(self, prefer: Optional[Dict[str, str]] = None) -> Optional[_TaggedQuery]:
        """Return the single best match, scored by preference dict."""
        if not self._tagged:
            return None
        if not prefer:
            return self._sort_by_preference()[0] if self._tagged else None
        def score(tq: _TaggedQuery) -> int:
            pd = {p.name: p.value for p in tq.query.product.parameters if p.value}
            return sum(1 for k, v in prefer.items() if pd.get(k) == v)
        return max(self._tagged, key=score)

    def _sort_by_preference(self) -> List[_TaggedQuery]:
        """Sort results using query profile sort preferences."""
        if not self._query_profile.sort_preferences:
            return list(self._tagged)
        def sort_key(tq: _TaggedQuery) -> Tuple:
            pd = {p.name: p.value for p in tq.query.product.parameters if p.value}
            scores = []
            for sp in self._query_profile.sort_preferences:
                val = pd.get(sp.axis, "")
                try:
                    scores.append(sp.order.index(val))
                except ValueError:
                    scores.append(len(sp.order))
            return tuple(scores)
        return sorted(self._tagged, key=sort_key)

    # ── Discovery helpers ────────────────────────────────────────

    def _unique_param_values(self, param_name: str) -> List[str]:
        vals = set()
        for tq in self._tagged:
            for p in tq.query.product.parameters:
                if p.name == param_name and p.value:
                    vals.add(p.value)
        return sorted(vals)

    def products(self) -> List[str]:
        return sorted(set(tq.query.product.name for tq in self._tagged))

    def centers(self) -> List[str]:
        return self._unique_param_values("AAA")

    def solutions(self) -> List[str]:
        return self._unique_param_values("TTT")

    def campaigns(self) -> List[str]:
        return self._unique_param_values("PPP")

    def samplings(self) -> List[str]:
        return self._unique_param_values("SMP")

    def sources(self) -> List[str]:
        """List all catalog IDs that own current results."""
        return sorted(set(tq.catalog_id for tq in self._tagged))

    def axes_summary(self) -> Dict[str, List[str]]:
        return {
            "product": self.products(),
            "center": self.centers(),
            "solution": self.solutions(),
            "campaign": self.campaigns(),
            "sampling": self.samplings(),
            "source": self.sources(),
        }

    # ── Local file search ────────────────────────────────────────

    def find_local_files(self) -> List[Dict]:
        """For each local result, search disk for matching files."""
        found = []
        for tq in self._tagged:
            if tq.source_type != "local":
                continue
            files = self._local_factory.find_local_files(tq.query, self._date)
            if files:
                found.append({"query": tq.query, "catalog": tq.catalog_id, "files": files})
        return found

    # ── Display ──────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._tagged)

    @property
    def results(self) -> List[ResourceQuery]:
        return [tq.query for tq in self._tagged]

    @property
    def tagged_results(self) -> List[_TaggedQuery]:
        return list(self._tagged)

    def __len__(self) -> int:
        return len(self._tagged)

    def __iter__(self):
        return iter(tq.query for tq in self._tagged)

    def __bool__(self) -> bool:
        return len(self._tagged) > 0

    def __repr__(self) -> str:
        pinned = ", ".join(f"{k}={v}" for k, v in self._pinned.items())
        return f"<ProductQuery({pinned or 'all'}): {self.count} results>"

    def table(self) -> str:
        """Tabular view of current results."""
        lines = [
            f"{'product':<12s} {'source':<8s} {'server':<35s} "
            f"{'AAA':<5s} {'TTT':<5s} {'PPP':<5s} {'SMP':<5s} "
            f"{'file_template':<55s}"
        ]
        lines.append("─" * len(lines[0]))
        for tq in self._tagged:
            q = tq.query
            pd = {p.name: (p.value or "*") for p in q.product.parameters}
            src = f"{'L' if tq.source_type == 'local' else 'R'}:{tq.catalog_id}"
            tmpl = q.product.filename.pattern[:55] if q.product.filename else "(none)"
            lines.append(
                f"{q.product.name:<12s} {src:<8s} {q.server.hostname[:35]:<35s} "
                f"{pd.get('AAA',''):<5s} {pd.get('TTT',''):<5s} "
                f"{pd.get('PPP',''):<5s} {pd.get('SMP',''):<5s} "
                f"{tmpl}"
            )
        return "\n".join(lines)


def _query_matches_param(q: ResourceQuery, param_name: str, param_value: str) -> bool:
    """Check if a query has a parameter matching the given name/value.
    If the param has no value (unresolved), it passes the filter."""
    for p in q.product.parameters:
        if p.name == param_name:
            if p.value is None:
                return True  # unresolved — don't filter out
            return p.value.upper() == param_value.upper()
    return True  # param not on this product — don't filter out


# ═══════════════════════════════════════════════════════════════════
# Test Data — Additional Centers
# ═══════════════════════════════════════════════════════════════════

igs_resource_spec_dict = {
    "id": "IGS",
    "name": "International GNSS Service",
    "website": "https://igs.org/",
    "servers": [
        {
            "id": "igs_cddis_ftp",
            "hostname": "ftps://gdc.cddis.eosdis.nasa.gov",
            "protocol": "ftps",
            "auth_required": True,
            "description": "CDDIS archive (NASA Earthdata login required)",
        }
    ],
    "products": [
        {
            "id": "igs_orbit",
            "product_name": "ORBIT",
            "server_id": "igs_cddis_ftp",
            "available": True,
            "description": "IGS combined final orbits",
            "parameters": [
                {"name": "AAA", "value": ["IGS","WUM"]},
                {"name": "TTT", "value": ["FIN","RAP"]},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "15M"},
            ],
            "directory": {"pattern": "pub/gnss/products/{GPSWEEK}/"},
        },
        {
            "id": "igs_clock",
            "product_name": "CLOCK",
            "server_id": "igs_cddis_ftp",
            "available": True,
            "description": "IGS combined final clocks",
            "parameters": [
                {"name": "AAA", "value": "IGS"},
                {"name": "TTT", "value": "FIN"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "30S"},
            ],
            "directory": {"pattern": "pub/gnss/products/{GPSWEEK}/"},
        },
        {
            "id": "igs_erp",
            "product_name": "ERP",
            "server_id": "igs_cddis_ftp",
            "available": True,
            "description": "IGS combined Earth rotation parameters",
            "parameters": [
                {"name": "AAA", "value": "IGS"},
                {"name": "TTT", "value": "FIN"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "01D"},
            ],
            "directory": {"pattern": "pub/gnss/products/{GPSWEEK}/"},
        },
        {
            "id": "igs_attatx",
            "product_name": "ATTATX",
            "server_id": "igs_cddis_ftp",
            "available": True,
            "description": "IGS antenna phase center model",
            "parameters": [
                {"name": "REFFRAME", "value": "igs20"},
            ],
            "directory": {"pattern": "pub/gnss/products/"},
        },
    ],
}

code_resource_spec_dict = {
    "id": "COD",
    "name": "Center for Orbit Determination in Europe",
    "website": "http://www.aiub.unibe.ch/",
    "servers": [
        {
            "id": "code_ftp",
            "hostname": "ftp://ftp.aiub.unibe.ch",
            "protocol": "ftp",
            "auth_required": False,
            "description": "CODE FTP server at University of Bern",
        }
    ],
    "products": [
        {
            "id": "code_orbit",
            "product_name": "ORBIT",
            "server_id": "code_ftp",
            "available": True,
            "description": "CODE precise orbits",
            "parameters": [
                {"name": "AAA", "value": "COD"},
                {"name": "TTT", "value": "FIN"},
                {"name": "TTT", "value": "RAP"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "05M"},
            ],
            "directory": {"pattern": "CODE/{YYYY}/"},
        },
        {
            "id": "code_clock",
            "product_name": "CLOCK",
            "server_id": "code_ftp",
            "available": True,
            "description": "CODE precise clocks",
            "parameters": [
                {"name": "AAA", "value": "COD"},
                {"name": "TTT", "value": "FIN"},
                {"name": "TTT", "value": "RAP"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "30S"},
                {"name": "SMP", "value": "05M"},
            ],
            "directory": {"pattern": "CODE/{YYYY}/"},
        },
        {
            "id": "code_bia",
            "product_name": "BIA",
            "server_id": "code_ftp",
            "available": True,
            "description": "CODE observation-specific biases",
            "parameters": [
                {"name": "AAA", "value": "COD"},
                {"name": "TTT", "value": "FIN"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "01D"},
            ],
            "directory": {"pattern": "CODE/{YYYY}/"},
        },
        {
            "id": "code_ionex",
            "product_name": "IONEX",
            "server_id": "code_ftp",
            "available": True,
            "description": "CODE global ionosphere maps",
            "parameters": [
                {"name": "AAA", "value": "COD"},
                {"name": "TTT", "value": "FIN"},
                {"name": "TTT", "value": "RAP"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "02H"},
            ],
            "directory": {"pattern": "CODE/{YYYY}/"},
        },
    ],
}

# Local storage specification — loaded from production local_config.yaml
LOCAL_CONFIG_PATH = Path(__file__).resolve().parent.parent / "src" / "gnss_ppp_products" / "configs" / "local" / "local_config.yaml"


# ═══════════════════════════════════════════════════════════════════
# Query Profile Data
# ═══════════════════════════════════════════════════════════════════

query_profile_dict = {
    "axes": [
        {"alias": "center", "parameters": ["AAA"], "description": "Analysis center code"},
        {"alias": "solution", "parameters": ["TTT"], "description": "Solution type (FIN, RAP, ULT)"},
        {"alias": "campaign", "parameters": ["PPP"], "description": "Campaign/constellation (OPS, MGX, DEM)"},
        {"alias": "sampling", "parameters": ["SMP"], "description": "Sampling interval"},
        {"alias": "date", "parameters": ["YYYY", "DDD", "HH", "MM"], "description": "Date parameters"},
        {"alias": "station", "parameters": ["SSSS", "MONUMENT", "R", "CCC"], "description": "Station identifiers"},
    ],
    "sort_preferences": [
        {"axis": "TTT", "order": ["FIN", "RAP", "ULT"]},
        {"axis": "SMP", "order": ["30S", "05M", "15M", "01D"]},
    ],
}


# ═══════════════════════════════════════════════════════════════════
# Dependency Spec Data
# ═══════════════════════════════════════════════════════════════════

dependency_spec_dict = {
    "name": "pride_ppp_static",
    "description": "Dependencies for PRIDE-PPP static processing",
    "global_prefer": {
        "AAA": "WUM",
        "TTT": "FIN",
        "PPP": "MGX",
        "SMP": "05M",
    },
    "dependencies": [
        {"product_name": "ORBIT", "required": True},
        {"product_name": "CLOCK", "required": True, "prefer": {"SMP": "30S"}},
        {"product_name": "ERP", "required": True, "prefer": {"AAA": "IGS", "PPP": "OPS"}},
        {"product_name": "BIA", "required": False, "prefer": {"AAA": "COD", "PPP": "OPS"}},
        {"product_name": "IONEX", "required": False, "prefer": {"AAA": "COD", "PPP": "OPS"}},
        {"product_name": "ATTATX", "required": True},
    ],
}


# ═══════════════════════════════════════════════════════════════════
#  BUILD — Assemble the full pipeline
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  ProductQuery — Ergonomic Local-First Query API")
    print("=" * 70)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 1: Build the shared product catalog
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    PARAMETER_CATALOG = ParameterCatalog(parameters=[Parameter(**p) for p in parameter_spec_dict])
    FORMAT_CATALOG = FormatCatalog(
        format_spec_catalog=FormatSpecCatalog(formats=format_spec_dict),
        parameter_catalog=PARAMETER_CATALOG,
    )
    PRODUCT_CATALOG = ProductCatalog(
        product_spec_catalog=ProductSpecCatalog(products=product_spec_dict),
        format_catalog=FORMAT_CATALOG,
    )
    print(f"\n[1] Product catalog: {len(PRODUCT_CATALOG.products)} products")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 2: Build factories
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    METADATA_CATALOG = _build_metadata_catalog()
    print(f"    Metadata fields: {list(METADATA_CATALOG._fields.keys())}")

    remote = RemoteResourceFactory(PRODUCT_CATALOG)
    remote.register_dict(resource_spec_dict)
    remote.register_dict(igs_resource_spec_dict)
    remote.register_dict(code_resource_spec_dict)

    LOCAL_SPEC = LocalResourceSpec.from_yaml(str(LOCAL_CONFIG_PATH))
    local = LocalResourceFactory(LOCAL_SPEC, PRODUCT_CATALOG, METADATA_CATALOG)

    profile = QueryProfile(**query_profile_dict)

    print(f"\n[2] Factories:")
    print(f"    Remote centers: {remote.centers} ({len(remote.all_queries)} queries)")
    print(f"    Local collections: {list(local.collections.keys())} ({len(local.all_queries)} queries)")
    for coll_name, coll in local.collections.items():
        print(f"      {coll_name:12s}: {coll.directory:30s} → {coll.specs}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 3: Create the ProductQuery
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    pq = ProductQuery(
        remote_factory=remote,
        local_factory=local,
        metadata_catalog=METADATA_CATALOG,
        query_profile=profile,
    )
    print(f"\n[3] {pq}")
    print(f"    Products:  {pq.products()}")
    print(f"    Centers:   {pq.centers()}")
    print(f"    Solutions: {pq.solutions()}")
    print(f"    Campaigns: {pq.campaigns()}")
    print(f"    Sources:   {pq.sources()}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 4: Pin to a date
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    DATE = datetime.date(2024, 6, 15)
    pq_dated = pq.for_date(DATE)
  
    """
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 5: Narrow to ORBIT product
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    orbits = pq_dated.for_product("ORBIT")
    print(f"\n[5] ORBIT queries: {orbits}")
    print(f"    Centers:   {orbits.centers()}")
    print(f"    Solutions: {orbits.solutions()}")
    print(f"    Sources:   {orbits.sources()}")
    print(orbits.table())

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 6: Narrow by axis aliases
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    wum_fin = orbits.narrow(center="WUM", solution="FIN")
    print(f"\n[6] ORBIT center=WUM solution=FIN: {wum_fin}")
    print(wum_fin.table())

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 7: Local vs remote
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n[7] Local-first resolution for each product:")
    for prod_name in pq_dated.products():
        prod_q = pq_dated.for_product(prod_name)
        local_q = prod_q.local_only()
        remote_q = prod_q.remote_only()
        if local_q.count > 0:
            tq = local_q.best()
            center = next((p.value for p in tq.query.product.parameters if p.name == "AAA"), "—")
            print(f"    {prod_name:12s} → LOCAL  ({local_q.count} hits, best: {center} @ {tq.query.server.hostname})")
        elif remote_q.count > 0:
            tq = remote_q.best()
            center = next((p.value for p in tq.query.product.parameters if p.name == "AAA"), "—")
            print(f"    {prod_name:12s} → REMOTE ({remote_q.count} hits, best: {center} @ {tq.query.server.hostname})")
        else:
            print(f"    {prod_name:12s} → NOT FOUND")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 8: Dependency resolution via ProductQuery
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    dep_spec = DependencySpec(**dependency_spec_dict)
    print(f"\n[8] Dependency resolution — '{dep_spec.name}':")
    print(f"    Global prefer: {dep_spec.global_prefer}")

    # Build a registry from the factories for DependencySpec.resolve()
    registry = ResourceRegistry()
    for cat in local.catalogs:
        registry.add_local(cat)
    for cat in remote.catalogs:
        registry.add_remote(cat)

    resolution = dep_spec.resolve(registry)
    print(resolution.summary())
    print(f"\n    Local: {len(resolution.local_hits)}  Remote: {len(resolution.remote_needed)}  Missing: {len(resolution.missing)}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 9: from_center narrowing
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    cod_only = pq_dated.from_center("COD")
    print(f"\n[9] Queries from COD only: {cod_only}")
    print(cod_only.table())

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 10: Full axes summary
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n[10] Full axes summary:")
    for axis, vals in pq_dated.axes_summary().items():
        print(f"    {axis:12s}: {vals}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage 11: Local download + discovery round-trip
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    import tempfile, shutil

    DATE = datetime.date(2025, 1,1)
    dt = _ensure_datetime(DATE)
    mc = METADATA_CATALOG

    print(f"\n[11] Local download + discovery round-trip (date={DATE})")

    # 11a — Create a temp directory to act as the local product archive
    tmp_root = Path(tempfile.mkdtemp(prefix="gnss_local_"))
    print(f"     Temp local dir: {tmp_root}")

    # 11b — Pick a few remote queries to "download"
    #        Use the dated ProductQuery to get fully-resolved filenames
    download_targets = []
    for prod_name in ["ORBIT", "CLOCK", "ERP"]:
        prod_q = pq_dated.for_product(prod_name).remote_only()
        tq = prod_q.best(prefer={"AAA": "WUM", "TTT": "FIN", "PPP": "MGX", "SMP": "05M"})
        if tq:
            download_targets.append(tq)

    print(f"     Selected {len(download_targets)} remote queries to 'download':")
    for tq in download_targets:
        q = tq.query
        pd = {p.name: p.value for p in q.product.parameters if p.value}
        print(f"       {q.product.name:8s}  {pd.get('AAA','?')}/{pd.get('TTT','?')}/{pd.get('PPP','?')}  "
              f"dir={q.directory.pattern}  file={q.product.filename.pattern if q.product.filename else '?'}")

    # 11c — Simulate downloading: create the directory structure and placeholder files
    #        Use the LOCAL_SPEC collections layout to place files in the right directory
    downloaded_files = []
    for tq in download_targets:
        q = tq.query
        # Resolve the directory template from the local spec for this product type
        dir_template = local._spec_to_dir.get(q.product.name)
        if dir_template is None:
            print(f"     ⚠ No local collection for {q.product.name}, skipping")
            continue
        resolved_dir = mc.resolve(dir_template, dt, computed_only=True)
        actual_dir = tmp_root / resolved_dir
        actual_dir.mkdir(parents=True, exist_ok=True)

        # Resolve filename: replace remaining {X} placeholders with defaults,
        # then strip trailing regex wildcard (.*) to get a concrete name
        if q.product.filename:
            fname = q.product.filename.pattern
            # Replace any remaining {X} placeholders (e.g. {V}) with "0"
            fname = re.sub(r'\{[A-Za-z]+\}', '0', fname)
            if fname.endswith(".*"):
                fname = fname[:-2] + ".gz"
            local_file = actual_dir / fname
            local_file.write_text(f"# placeholder for {q.product.name}\n")
            downloaded_files.append(local_file)
            print(f"     ✓ Created: {local_file.relative_to(tmp_root)}")

    # 11d — Build a new LocalResourceFactory pointing at tmp_root
    #        Reuses the same LOCAL_SPEC (collections layout) but with a different base_dir
    local2 = LocalResourceFactory(LOCAL_SPEC, PRODUCT_CATALOG, METADATA_CATALOG, base_dir=tmp_root)

    print(f"\n     Local factory (post-download): {[c.id for c in local2.catalogs]} "
          f"({len(local2.all_queries)} queries)")

    # 11e — Build a fresh ProductQuery that includes the new local factory
    pq2 = ProductQuery(
        remote_factory=remote,
        local_factory=local2,
        metadata_catalog=METADATA_CATALOG,
        query_profile=profile,
    )
    pq2_dated = pq2.for_date(DATE)

    # 11f — Search for downloaded files via ProductQuery
    print(f"\n     Searching for downloaded files via ProductQuery.find_local_files():")
    found = pq2_dated.find_local_files()
    for hit in found:
        q = hit["query"]
        files = hit["files"]
        print(f"       {q.product.name:8s} → {len(files)} file(s)")
        for f in files:
            print(f"         {f.relative_to(tmp_root)}")

    # 11g — Also test direct LocalResourceFactory.find_local_files() per query
    print(f"\n     Direct LocalResourceFactory.find_local_files() per query:")
    for tq in pq2_dated.local_only().tagged_results:
        q = tq.query
        files = local2.find_local_files(q, DATE)
        status = f"{len(files)} file(s)" if files else "no files"
        print(f"       {q.product.name:8s} ({tq.catalog_id}) → {status}")
        for f in files:
            print(f"         {f.name}")

    # 11h — Verify: all downloaded files were found
    all_found_paths = set()
    for hit in found:
        all_found_paths.update(hit["files"])
    all_downloaded = set(downloaded_files)
    missed = all_downloaded - all_found_paths
    extra = all_found_paths - all_downloaded

    print(f"\n     Verification:")
    print(f"       Downloaded:  {len(all_downloaded)} files")
    print(f"       Found:       {len(all_found_paths)} files")
    if missed:
        print(f"       ✗ MISSED:    {[f.name for f in missed]}")
    if extra:
        print(f"       (extra):     {[f.name for f in extra]}")
    if not missed:
        print(f"       ✓ All downloaded files discovered successfully!")

    # 11i — Cleanup
    shutil.rmtree(tmp_root)
    print(f"     Cleaned up {tmp_root}")

    print("\n" + "=" * 70)
    print("  Done.")
    print("=" * 70)
"""
