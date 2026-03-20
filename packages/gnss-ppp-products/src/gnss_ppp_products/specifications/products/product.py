"""Core product models — ProductPath, Product, and catalog hierarchies."""

from typing import List, Optional

from pydantic import BaseModel, Field

from gnss_ppp_products.specifications.parameters.parameter import Parameter


class ProductPath(BaseModel):
    """A template pattern with ``{NAME}``-style placeholders, resolved via :meth:`derive`."""
    pattern: str = Field(description="A template pattern with {NAME}-style placeholders.")
    value: Optional[str] = Field(None, description="The resolved value after derivation.")
    description: Optional[str] = Field(None, description="A description of the product path.")

    def derive(self, parameters: List[Parameter]) -> None:
        """Replace ``{PARAM}`` placeholders in *pattern* with parameter values."""
        if self.value is not None:
            return

        for param in parameters:
            if f"{{{param.name}}}" in self.pattern:
                if param.value is not None:
                    self.pattern = self.pattern.replace(f"{{{param.name}}}", param.value)

        return None


class Product(BaseModel):
    """A resolved product with its parameters and file/directory templates."""
    name: str = Field(..., description="The name of the product.")
    parameters: List[Parameter] = Field(..., description="A list of parameters for the product.")
    directory: Optional[ProductPath] = Field(default=None, description="The directory where the product is located.")
    filename: Optional[ProductPath] = Field(default=None, description="The filename pattern for the product.")


class VariantCatalog(BaseModel):
    """Named collection of product variants."""
    name: str
    variants: dict[str, Product]


class VersionCatalog(BaseModel):
    """Named collection of product versions, each containing variants."""
    name: str
    versions: dict[str, VariantCatalog]
