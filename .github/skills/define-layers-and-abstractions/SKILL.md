---
name: define-layers-and-abstractions
description: Define clear layers and abstractions in your codebase. Use when user wants to organize code, separate concerns, or mentions "layers", "abstractions", or "separation of concerns".

skills: grill-me, improve-codebase-architecture, write-a-prd
---

# Define Layers and Abstractions

The goal of defining layers and abstractions is to create a clear separation of concerns in your codebase. This makes it easier to understand, maintain, and extend. Identifying intentional boundaries between different parts of the system allows you to manage complexity and reduce coupling.

## Workflow

### 1. Identify Concerns
Start by identifying the different concerns in your codebase. A concern is a specific aspect of the system that has a distinct responsibility. Common concerns include:

- Form handling (e.g., user input, validation)
- Data access (e.g., database interactions)
- Data validation and transformation
- IO (e.g., file handling, network requests)
- Functional logic (e.g., algorithms, domain logic)

Ask: "What are the different responsibilities in this code? Can we group related functionality together?"

Spawn sub-agents to analyze the codebase and identify concerns. Each agent can focus on a specific aspect (e.g., data handling, business logic) to ensure a comprehensive analysis. Write concerns to a shared document for reference in the next steps, in the .blueprint folder.

If code is not yet available, ask user to describe the system and its responsibilities, then identify concerns based on that description. use 'grill-me' skill to ask targeted questions about the system's functionality and responsibilities to uncover concerns.


### 2. Identify/Define application boundaries
Identify the network, filesystem, and user interaction boundaries of the application. These boundaries often correspond to natural layers in the architecture. For example:
- Network boundary: API layer that handles incoming requests and outgoing responses.
- Filesystem boundary: Data access layer that interacts with the file system or database.
- User interaction boundary: Interface layer that manages user input and output.
Ask: "Where does the application interact with the outside world? How can we define clear boundaries for these interactions?"

### 3. Define Layers
Once you have identified the concerns, define layers that correspond to these concerns. Each layer should have a clear responsibility and should interact with other layers through well-defined interfaces. Common layers include:

- **Specification Layer**: Defines the data models, schemas, resource configuration, and specifications for the system.
- **Factory Layer**: Responsible for creating instances of the models defined in the specification layer, often using the specifications to configure the created objects.
- **Service Layer**: Contains the core business logic and operations that manipulate the models created by the factory layer.
- **Interface Layer**: Provides the API or user interface for interacting with the system, often calling into the service layer.

Ask: "How can we group these concerns into layers? What should each layer be responsible for? How do the layers interact with each other?"

If the user has an existing codebase, analyze the code to identify natural boundaries and group related functionality into layers. If the user is designing a new system, use the identified concerns to define layers from the ground up. Use 'improve-codebase-architecture' skill to suggest layer definitions and organization based on best practices and the identified concerns.

### 4. Define Abstractions
Within each horizontal layer, identify abstractions that can hide complexity, encapsulate implementation details, and provide a clear interface for other layers to interact with. For example:
- In the specification layer, you might have abstractions for different types of resources (e.g., `FileResource`, `APIResource`) that share a common interface.
- In the factory layer, you might have a `ResourceFactory` abstraction that can create different types of resources based on the specifications.

Ask: "What are the common patterns or operations within this layer? Can we create abstractions to simplify interactions?"

If the user has an existing codebase, gauge user 'suggestability' to determine how open they are to refactoring and introducing new abstractions. If they are open, analyze the code to identify opportunities for abstraction and suggest specific abstractions that can be introduced. If they are resistant, focus on defining clear interfaces between existing components to improve modularity without requiring significant changes. If the user is designing a new system, use the identified concerns and layers to define abstractions from the outset, ensuring that each layer has clear interfaces and encapsulates complexity effectively. Use 'improve-codebase-architecture' skill to suggest specific abstractions and design patterns that can be applied within each layer to improve modularity and maintainability.

### 5. Define Interfaces
For each layer, define clear interfaces that specify how other layers can interact with it. This includes defining the methods, parameters, and expected behavior. The interfaces should be designed to minimize coupling and maximize flexibility.

Ask: "What methods or operations should this layer expose? What parameters do they take? What should be hidden behind the interface?"

If the user has an existing codebase, analyze the current interactions between components and suggest ways to define clearer interfaces that reduce coupling. If the user is designing a new system, use the identified layers and abstractions to define interfaces from the outset, ensuring that each layer has a clear contract for how it can be used by other layers. Use 'improve-codebase-architecture' skill to suggest specific interface designs and best practices for defining interfaces that promote modularity and maintainability.

### 6. Enforce logical/semantic consistency
Ensure that the defined layers, abstractions, and interfaces are logically and semantically consistent. For example, the specification layer should not depend on the factory layer, and the service layer should not directly interact with the interface layer. Enforce a clear direction of dependencies to maintain a clean architecture.
Ask: "Are my abstractions and their interfaces logically consistent? Do they follow a clear direction of dependencies? Are there any circular dependencies or tight coupling that we can eliminate?"

### 7. Review and Refine
After defining layers, abstractions, and interfaces, review the overall architecture to ensure that it is coherent and that the layers interact in a clear and logical way. Refine the design as needed to improve clarity, reduce coupling, and enhance maintainability. Ask: "Does this architecture make sense? Are the layers well-defined and do they interact in a clear way? Can we simplify or improve any of the layers or interfaces?" 

Write a document summarizing the defined layers, abstractions, and interfaces, along with the rationale for the design decisions. This document can serve as a reference for developers working on the codebase and can be included in a PRD for future development. This should go into the .blueprint folder for reference during implementation.