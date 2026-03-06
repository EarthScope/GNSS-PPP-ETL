"""
Configuration-Driven Query Factory
===================================

Loads center configuration YAML files and generates query factories
for downloading GNSS products from various analysis centers.

Usage
-----
    >>> from gnss_ppp_products.resources.config import load_center, QueryFactory
    >>> 
    >>> # Load a center configuration
    >>> wuhan = load_center("wuhan")
    >>> print(wuhan.products)  # Available products
    >>> 
    >>> # Create query factory
    >>> factory = QueryFactory(wuhan)
    >>> result = factory.query("SP3", date(2025, 1, 15), quality="RAP")
    >>> print(result.url)

Configuration Files
-------------------
Configuration files are YAML documents in the `config/` directory:
    - wuhan.yaml: Wuhan University
    - code.yaml: CODE (AIUB Bern)
    - igs.yaml: IGS Combined (via IGN)
    - cddis.yaml: NASA CDDIS
    - gfz.yaml: GFZ Potsdam
    - vmf.yaml: Vienna Mapping Functions
    - ngs.yaml: NOAA NGS
    - esa.yaml: ESA/ESOC
"""

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import yaml


# ---------------------------------------------------------------------------
# Configuration Directory
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).parent


def list_centers() -> List[str]:
    """List all available center configuration files."""
    return [
        f.stem for f in CONFIG_DIR.glob("*.yaml") 
        if not f.name.startswith("_")
    ]


# ---------------------------------------------------------------------------
# Data Classes for Configuration
# ---------------------------------------------------------------------------


@dataclass
class ServerConfig:
    """Server connection configuration."""
    
    id: str
    name: str
    hostname: str
    protocol: Literal["ftp", "ftps", "http", "https"]
    auth_required: bool = False
    notes: str = ""
    
    @property
    def is_ftp(self) -> bool:
        return self.protocol in ("ftp", "ftps")
    
    @property
    def is_http(self) -> bool:
        return self.protocol in ("http", "https")
    
    @property
    def requires_tls(self) -> bool:
        return self.protocol in ("ftps", "https")


@dataclass
class SolutionConfig:
    """Solution type configuration."""
    
    code: str           # OPS, MGX, DEM, etc.
    prefix: str         # Analysis center prefix (WUM, COD, etc.)
    description: str = ""


@dataclass
class DirectoryConfig:
    """Directory pattern configuration."""
    
    pattern: str
    gps_week_based: bool = False
    rapid_pattern: Optional[str] = None
    archive_pattern: Optional[str] = None
    
    def format(
        self,
        year: int,
        doy: int,
        gps_week: Optional[int] = None,
        **kwargs
    ) -> str:
        """Format directory pattern with date values."""
        yy = str(year)[-2:]
        values = {
            "year": year,
            "yy": yy,
            "doy": f"{doy:03d}",
            "gps_week": gps_week,
            **kwargs
        }
        return self.pattern.format(**values)


@dataclass  
class FilenameConfig:
    """Filename pattern configuration."""
    
    template: str
    regex: str
    legacy_template: Optional[str] = None
    archive_template: Optional[str] = None
    
    def format_template(
        self,
        ac: str,
        sol: str,
        qual: str,
        year: int,
        doy: int,
        version: str = "0",
        coverage: str = "01D",
        interval: str = "05M",
        content: str = "ORB",
        ext: str = "SP3",
        **kwargs
    ) -> str:
        """Format filename template."""
        values = {
            "ac": ac,
            "v": version,
            "sol": sol,
            "qual": qual,
            "year": year,
            "doy": f"{doy:03d}",
            "coverage": coverage,
            "interval": interval,
            "content": content,
            "ext": ext,
            **kwargs
        }
        return self.template.format(**values)
    
    def format_regex(
        self,
        ac: str,
        qual: str,
        year: int,
        doy: int,
        **kwargs
    ) -> str:
        """Format regex pattern for file matching."""
        values = {
            "ac": ac,
            "qual": qual,
            "year": year,
            "doy": f"{doy:03d}",
            **kwargs
        }
        return self.regex.format(**values)


@dataclass
class ProductConfig:
    """Product configuration."""
    
    id: str
    product_type: str
    server_id: str
    available: bool
    description: str
    qualities: List[str]
    solutions: List[SolutionConfig]
    directory: DirectoryConfig
    filename: FilenameConfig
    intervals: List[str] = field(default_factory=list)
    extensions: List[str] = field(default_factory=list)
    coverage: str = "01D"
    static: bool = False
    notes: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductConfig":
        """Create ProductConfig from YAML dictionary."""
        solutions = [
            SolutionConfig(
                code=s.get("code", "OPS"),
                prefix=s.get("prefix", ""),
                description=s.get("description", "")
            )
            for s in data.get("solutions", [])
        ]
        
        dir_data = data.get("directory", {})
        directory = DirectoryConfig(
            pattern=dir_data.get("pattern", ""),
            gps_week_based=dir_data.get("gps_week_based", False),
            rapid_pattern=dir_data.get("rapid_pattern"),
            archive_pattern=dir_data.get("archive_pattern"),
        )
        
        fn_data = data.get("filename", {})
        filename = FilenameConfig(
            template=fn_data.get("template", ""),
            regex=fn_data.get("regex", ""),
            legacy_template=fn_data.get("legacy_template"),
            archive_template=fn_data.get("archive_template"),
        )
        
        return cls(
            id=data.get("id", ""),
            product_type=data.get("type", ""),
            server_id=data.get("server_id", ""),
            available=data.get("available", False),
            description=data.get("description", ""),
            qualities=data.get("qualities", []),
            solutions=solutions,
            directory=directory,
            filename=filename,
            intervals=data.get("intervals", []),
            extensions=data.get("extensions", []),
            coverage=data.get("coverage", "01D"),
            static=data.get("static", False),
            notes=data.get("notes", ""),
        )


@dataclass
class CenterConfig:
    """Complete center configuration."""
    
    code: str
    name: str
    description: str
    website: str
    servers: List[ServerConfig]
    products: Dict[str, ProductConfig]  # Keyed by product_type
    defaults: Dict[str, Any] = field(default_factory=dict)
    _servers_by_id: Dict[str, ServerConfig] = field(default_factory=dict, repr=False)
    _products_by_id: Dict[str, ProductConfig] = field(default_factory=dict, repr=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CenterConfig":
        """Create CenterConfig from YAML dictionary."""
        center_data = data.get("center", {})
        
        servers = [
            ServerConfig(
                id=s.get("id", s.get("name", "primary")),
                name=s.get("name", "primary"),
                hostname=s.get("hostname", ""),
                protocol=s.get("protocol", "ftp"),
                auth_required=s.get("auth_required", False),
                notes=s.get("notes", ""),
            )
            for s in data.get("servers", [])
        ]
        
        # Products is now a list with id, type, and server_id
        products_list = data.get("products", [])
        products = {}
        products_by_id = {}
        
        for prod_data in products_list:
            prod = ProductConfig.from_dict(prod_data)
            products[prod.product_type] = prod
            products_by_id[prod.id] = prod
        
        servers_by_id = {s.id: s for s in servers}
        
        instance = cls(
            code=center_data.get("code", ""),
            name=center_data.get("name", ""),
            description=center_data.get("description", ""),
            website=center_data.get("website", ""),
            servers=servers,
            products=products,
            defaults=data.get("defaults", {}),
        )
        instance._servers_by_id = servers_by_id
        instance._products_by_id = products_by_id
        return instance
    
    @property
    def primary_server(self) -> Optional[ServerConfig]:
        """Get the primary/first server configuration."""
        return self.servers[0] if self.servers else None
    
    def get_server(self, server_id: str) -> Optional[ServerConfig]:
        """Get a server by its id."""
        return self._servers_by_id.get(server_id)
    
    def get_product_by_id(self, product_id: str) -> Optional[ProductConfig]:
        """Get a product by its id."""
        return self._products_by_id.get(product_id)
    
    def get_server_for_product(self, product: ProductConfig) -> Optional[ServerConfig]:
        """Get the server associated with a product."""
        return self._servers_by_id.get(product.server_id)
    
    def available_products(self) -> List[str]:
        """List all available product types at this center."""
        return [pt for pt, prod in self.products.items() if prod.available]


# ---------------------------------------------------------------------------
# Configuration Loading
# ---------------------------------------------------------------------------


def load_center(name: str) -> CenterConfig:
    """
    Load a center configuration by name.
    
    Parameters
    ----------
    name : str
        Center name (e.g., "wuhan", "code", "igs")
        
    Returns
    -------
    CenterConfig
        Loaded configuration
        
    Raises
    ------
    FileNotFoundError
        If configuration file doesn't exist
    """
    config_file = CONFIG_DIR / f"{name.lower()}.yaml"
    
    if not config_file.exists():
        available = list_centers()
        raise FileNotFoundError(
            f"No configuration found for '{name}'. "
            f"Available centers: {available}"
        )
    
    with open(config_file, "r") as f:
        data = yaml.safe_load(f)
    
    return CenterConfig.from_dict(data)


def load_all_centers() -> Dict[str, CenterConfig]:
    """Load all available center configurations."""
    return {name: load_center(name) for name in list_centers()}


# ---------------------------------------------------------------------------
# Query Factory
# ---------------------------------------------------------------------------


def _date_to_gps_week(date: datetime.date) -> int:
    """Convert date to GPS week number."""
    gps_epoch = datetime.date(1980, 1, 6)
    delta = date - gps_epoch
    return delta.days // 7


def _parse_date(date: datetime.date) -> tuple[int, int]:
    """Convert date to (year, doy)."""
    return date.year, date.timetuple().tm_yday


@dataclass
class QueryResult:
    """Result of a product query."""
    
    server: str
    protocol: str
    directory: str
    filename: str
    regex: str
    url: str
    quality: str
    solution: str
    product: str
    
    @property
    def full_path(self) -> str:
        return f"{self.directory}/{self.filename}"


class QueryFactory:
    """
    Factory for generating product queries from center configuration.
    
    Parameters
    ----------
    config : CenterConfig
        Center configuration loaded from YAML
        
    Examples
    --------
    >>> wuhan = load_center("wuhan")
    >>> factory = QueryFactory(wuhan)
    >>> 
    >>> # Query for SP3 orbit product
    >>> result = factory.query("SP3", date(2025, 1, 15), quality="RAP")
    >>> print(result.url)
    ftp://igs.gnsswhu.cn/pub/whu/phasebias/2025/orbit/WUM0MGXRAP_20250150000_01D_05M_ORB.SP3.gz
    """
    
    def __init__(self, config: CenterConfig):
        self.config = config
    
    def available_products(self) -> List[str]:
        """List available products."""
        return self.config.available_products()
    
    def query(
        self,
        product: str,
        date: datetime.date,
        quality: str = "RAP",
        solution: Optional[str] = None,
        interval: Optional[str] = None,
    ) -> QueryResult:
        """
        Generate a query for a specific product.
        
        Parameters
        ----------
        product : str
            Product type (SP3, CLK, GIM, etc.)
        date : datetime.date
            Date for the product
        quality : str
            Quality level (FIN, RAP, ULT)
        solution : str, optional
            Solution type (OPS, MGX, DEM). If None, uses first available.
        interval : str, optional
            Sampling interval. If None, uses first available.
            
        Returns
        -------
        QueryResult
            Query result with URL and metadata
        """
        if product not in self.config.products:
            raise ValueError(
                f"Product '{product}' not available at {self.config.code}. "
                f"Available: {self.available_products()}"
            )
        
        prod_config = self.config.products[product]
        
        if not prod_config.available:
            raise ValueError(f"Product '{product}' is not available")
        
        if quality not in prod_config.qualities:
            raise ValueError(
                f"Quality '{quality}' not available for {product}. "
                f"Available: {prod_config.qualities}"
            )
        
        # Get solution
        if solution:
            sol_config = next(
                (s for s in prod_config.solutions if s.code == solution),
                None
            )
            if not sol_config:
                raise ValueError(f"Solution '{solution}' not available")
        else:
            sol_config = prod_config.solutions[0]
        
        # Get interval
        if interval is None and prod_config.intervals:
            interval = prod_config.intervals[0]
        
        # Parse date
        year, doy = _parse_date(date)
        gps_week = _date_to_gps_week(date) if prod_config.directory.gps_week_based else None
        
        # Format directory
        directory = prod_config.directory.format(
            year=year,
            doy=doy,
            gps_week=gps_week,
        )
        
        # Format filename
        version = self.config.defaults.get("version", "0")
        coverage = prod_config.coverage
        
        filename = prod_config.filename.format_template(
            ac=sol_config.prefix,
            sol=sol_config.code,
            qual=quality,
            year=year,
            doy=doy,
            version=version,
            coverage=coverage,
            interval=interval or "",
        )
        
        # Format regex
        regex = prod_config.filename.format_regex(
            ac=sol_config.prefix,
            qual=quality,
            year=year,
            doy=doy,
        )
        
        # Get server from product's server_id
        server = self.config.get_server_for_product(prod_config)
        if server is None:
            server = self.config.primary_server
        if server is None:
            raise ValueError(f"No server found for product '{product}'")
        
        # Build URL
        hostname = server.hostname.rstrip("/")
        url = f"{hostname}/{directory.lstrip('/')}{filename}"
        
        return QueryResult(
            server=hostname,
            protocol=server.protocol,
            directory=directory,
            filename=filename,
            regex=regex,
            url=url,
            quality=quality,
            solution=sol_config.code,
            product=product,
        )
    
    def query_regex(
        self,
        product: str,
        date: datetime.date,
        quality: str = "RAP",
    ) -> str:
        """
        Get just the regex pattern for a product query.
        
        Useful for searching local directories or FTP listings.
        """
        result = self.query(product, date, quality)
        return result.regex


# ---------------------------------------------------------------------------
# Module Exports
# ---------------------------------------------------------------------------

__all__ = [
    # Configuration loading
    "load_center",
    "load_all_centers",
    "list_centers",
    "CONFIG_DIR",
    # Data classes
    "CenterConfig",
    "ServerConfig",
    "ProductConfig",
    "SolutionConfig",
    "DirectoryConfig",
    "FilenameConfig",
    # Query factory
    "QueryFactory",
    "QueryResult",
]
