# GenOps Scaffolds

Scaffold templates define how `/genops-code` generates project structures from LLD designs. Each scaffold represents a tech stack convention — directory layout, build files, and entity stub mappings.

## Available Scaffolds

| Scaffold | Language | Framework | Use Case |
|----------|----------|-----------|----------|
| `go-service` | Go | gin | Microservice with clean architecture |
| `react-vite` | TypeScript | React 19 + Vite | Frontend application |
| `python-fastapi` | Python | FastAPI | REST API service |
| `go-library` | Go | stdlib | Shared Go library |

## Creating a New Scaffold

1. Create directory: `.agents/scaffolds/<scaffold-id>/`
2. Create `STRUCTURE.yaml` defining directories, templates, and entity stubs
3. Create template files for build configs (go.mod, package.json, etc.)
4. Test: add a module to LLD's Project Structure, run `/genops-code`

### STRUCTURE.yaml Schema

```yaml
name: "Human-readable name"
description: "What this scaffold produces"
language: "Language name"
framework: "Framework (optional)"
build: "Build command"
package_manager: "Package manager (optional)"

directories:                           # Created for every module
  - path/to/dir/

templates:                             # Template file → output path
  template.txt: "{module}/output.txt"  # {module} = module name, {entity} = entity name

entity_stubs:                          # Per LLD entity, generate files
  stub_type: "path/to/{entity_lower}.ext"

default_files:                         # Always generated, no entity needed
  - "{module}/path/to/file.ext"
```

### Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{module}` | Module directory name | `user-service` |
| `{module_path}` | Go-style module path | `github.com/project/user-service` |
| `{module_name}` | Human-readable name | `User Service` |
| `{entity}` | Entity name (PascalCase) | `User` |
| `{entity_lower}` | Entity name (lowercase) | `user` |
