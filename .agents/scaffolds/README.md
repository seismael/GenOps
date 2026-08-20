# GenOps Scaffolds

Scaffold templates define how `/genops-code` generates project structures from LLD designs. Each scaffold represents a tech stack convention — directory layout, build files, and entity stub mappings.

## Available Scaffolds

| Scaffold | Language | Framework | Use Case |
|----------|----------|-----------|----------|
| `go-service` | Go | gin | Microservice with clean architecture |
| `python-fastapi` | Python | FastAPI | Async REST API service |
| `react-vite` | TypeScript | React 19 + Vite | Modern frontend SPA |
| `rust-service` | Rust | Actix Web / Tokio | High-throughput async microservice |
| `node-service` | TypeScript | Express / Vitest | Node.js backend service |
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

### Supported Template Variables & Casing Transforms

| Variable | Transform | Example (`User Account`) |
|----------|-----------|--------------------------|
| `{module}` | Raw module identifier | `user-account` |
| `{module_name}` | Human-readable title | `User Account` |
| `{module_path}` | Go-style import path | `github.com/project/user-account` |
| `{module_kebab}` | Lowercase hyphenated | `user-account` |
| `{module_snake}` | Lowercase underscored | `user_account` |
| `{module_camel}` | camelCase | `userAccount` |
| `{module_pascal}` | PascalCase | `UserAccount` |
| `{module_lower}` | Lowercase continuous | `useraccount` |
| `{entity}` / `{Entity}` | PascalCase | `UserAccount` |
| `{entity_name}` | Human-readable title | `User Account` |
| `{entity_lower}` | Lowercase continuous | `useraccount` |
| `{entity_kebab}` | Lowercase hyphenated | `user-account` |
| `{entity_snake}` | Lowercase underscored | `user_account` |
| `{entity_camel}` | camelCase | `userAccount` |
| `{entity_screaming_snake}` | UPPERCASE underscored | `USER_ACCOUNT` |
