# Layers, dependencies


## Specification Layer

### Meta Data Specification
The metadata specification outlines individual meta-data strings that are required to perform remote and local queries by dynamic path and filename generation

ex: MetaDataCatalog.interpolate(f"{YYYY}_{DDD}.file") -> "2024_001.file"

### Format Specification
The format specification outlines the conventions used to 'name' product files.

### Product Specification
The product specification outlines a list of products avaialable to query from local/remote resources and define task dependencies

### Local resource Specification
The local resource specification outlines how to store and locate a specific product in a local file system

### Remote resource specification
The remote resource specification outlines a collection of server configurations and products available to query from an analysis center or other entity.

### Query specification
The query specification outlines the parameters, products, and resource to find and store a given product and its parameters. 

### Dependency specification
The dependency specification outlines the products needed to perform a GNSS related task and the local/remote resources to locate said product.


## Catalog-Factory-Engine layer

This layer is where specifications are loaded into python objects and validated against their dependencies. The dependency relations are as follows:

metadata spec -> metadata catalog

checks: 
1. make sure the file formatting is correct

format spec -> format catalog

checks: 
1. make sure the file formatting is correct

[format catalog, metadata catalog] -> product catalog

checks: 
1. make sure the file formatting is correct
2. make sure we can find all the metadata and format references listed in the product catalog and that our product variants can 'build'


[metadata catalog, product catalog] -> local resource factory

checks: 
1. make sure the file formatting is correct
2. make sure our product references can be found in the product catalog
3. make sure our metadata references can be found in the metadata catalog



[metadata catalog, product catalog] -> remote resource factory

checks: 
1. make sure the file formatting is correct
2. make sure our product references can be found in the product catalog
3. make sure our metadata references can be found in the metadata catalog


[metadata catalog, product catalog,] -> query engine

checks: 
1. make sure the file formatting is correct
2. make sure our product references can be found in the product catalog
3. make sure our metadata references can be found in the metadata catalog


[query spec, product catalog,remote resource factory] -> task dependency catalog

checks: 
1. make sure the file formatting is correct
2. make sure our product references can be found in the product catalog
3. make sure our remote resource refernces can be found in the remote resource factory



## Environment layer

The environment layer is where outputs from the Catalog-Factory-Engine layer meet to perform tasks. Here we can define our set of specification files, test remote resource availablility, and interface with external applications via the SDK.
