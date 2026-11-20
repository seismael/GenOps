"""Zero-dependency JSON Schema Draft-07 validator supporting $ref, combinators, formats, and object/numeric constraints."""

from __future__ import annotations

import decimal
import json
import re
from typing import Any, Dict, List, Optional, Set, Union


class JsonSchemaValidator:
    """
    Zero-dependency JSON Schema Draft-07 validator.
    Supports: $ref (local JSON Pointer #/...), type, required, properties,
    patternProperties, additionalProperties, minProperties, maxProperties,
    dependencies, propertyNames, enum, const, pattern, minLength, maxLength,
    format (date-time, date, email, uri, uuid, ipv4), items (schema or tuple list),
    additionalItems, minItems, maxItems, uniqueItems, contains, minimum, maximum,
    exclusiveMinimum, exclusiveMaximum, multipleOf, allOf, anyOf, oneOf, not,
    if/then/else.
    """

    _FORMAT_VALIDATORS = {
        "date-time": re.compile(
            r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
        ),
        "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
        "email": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
        "uri": re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://[^\s]+$"),
        "uuid": re.compile(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        ),
        "ipv4": re.compile(
            r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
        ),
    }

    @classmethod
    def _resolve_ref(cls, ref: str, root_schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Resolve local JSON Pointer reference ('#/definitions/...') against *root_schema*."""
        if ref == "#":
            return root_schema
        if not ref.startswith("#/"):
            return None
        parts = ref[2:].split("/")
        curr: Any = root_schema
        for raw_part in parts:
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            elif isinstance(curr, list):
                try:
                    curr = curr[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return curr if isinstance(curr, dict) else None

    @classmethod
    def validate(
        cls,
        data: Any,
        schema: Dict[str, Any],
        path: str = "$",
        root_schema: Optional[Dict[str, Any]] = None,
        _seen_refs: Optional[Set[str]] = None,
    ) -> List[str]:
        """Recursively validate *data* against a JSON Schema Draft-07 *schema*."""
        errors: List[str] = []
        if not isinstance(schema, dict):
            return errors
        if root_schema is None:
            root_schema = schema

        # 0. $ref Resolution (RFC 6901 local JSON Pointer)
        if "$ref" in schema and isinstance(schema["$ref"], str):
            ref_uri = schema["$ref"]
            seen = set(_seen_refs) if _seen_refs else set()
            if ref_uri in seen:
                errors.append(f"{path}: cyclic $ref detected: '{ref_uri}'")
                return errors
            target_schema = cls._resolve_ref(ref_uri, root_schema)
            if target_schema is None:
                errors.append(f"{path}: unresolved $ref '{ref_uri}'")
                return errors
            seen.add(ref_uri)
            errors.extend(cls.validate(data, target_schema, path, root_schema, seen))
            sibling_schema = {k: v for k, v in schema.items() if k != "$ref"}
            if not sibling_schema:
                return errors
            schema = sibling_schema

        # 1. Type Validation
        target_type = schema.get("type")
        if target_type:
            type_errors = cls._validate_type(data, target_type, path)
            if type_errors:
                return type_errors

        # 2. Const & Enum Validation
        if "const" in schema:
            expected_const = schema["const"]
            if data != expected_const or (isinstance(data, bool) != isinstance(expected_const, bool)):
                errors.append(f"{path}: value {json.dumps(data)} does not match const {json.dumps(expected_const)}")
        if "enum" in schema:
            matched_enum = any(
                data == item and (isinstance(data, bool) == isinstance(item, bool))
                for item in schema["enum"]
            )
            if not matched_enum:
                errors.append(f"{path}: value {json.dumps(data)} is not one of allowed enum {schema['enum']}")

        # 3. Numeric Constraints
        if isinstance(data, (int, float)) and not isinstance(data, bool):
            if "minimum" in schema and data < schema["minimum"]:
                errors.append(f"{path}: value {data} is less than minimum {schema['minimum']}")
            if "maximum" in schema and data > schema["maximum"]:
                errors.append(f"{path}: value {data} is greater than maximum {schema['maximum']}")
            if "exclusiveMinimum" in schema and data <= schema["exclusiveMinimum"]:
                errors.append(
                    f"{path}: value {data} must be strictly greater than exclusiveMinimum {schema['exclusiveMinimum']}"
                )
            if "exclusiveMaximum" in schema and data >= schema["exclusiveMaximum"]:
                errors.append(
                    f"{path}: value {data} must be strictly less than exclusiveMaximum {schema['exclusiveMaximum']}"
                )
            if "multipleOf" in schema:
                mult = schema["multipleOf"]
                if isinstance(mult, (int, float)) and mult > 0:
                    try:
                        rem = decimal.Decimal(str(data)) % decimal.Decimal(str(mult))
                        if rem != 0:
                            errors.append(f"{path}: value {data} is not a multipleOf {mult}")
                    except (decimal.InvalidOperation, ValueError):
                        if (data / mult) % 1 != 0:
                            errors.append(f"{path}: value {data} is not a multipleOf {mult}")

        # 4. String Constraints
        if isinstance(data, str):
            if "minLength" in schema and len(data) < schema["minLength"]:
                errors.append(f"{path}: string length {len(data)} is less than minLength {schema['minLength']}")
            if "maxLength" in schema and len(data) > schema["maxLength"]:
                errors.append(f"{path}: string length {len(data)} exceeds maxLength {schema['maxLength']}")
            if "pattern" in schema:
                pattern = schema["pattern"]
                try:
                    if not re.search(pattern, data):
                        errors.append(f"{path}: string '{data}' does not match required regex pattern '{pattern}'")
                except re.error as e:
                    errors.append(f"{path}: invalid regex pattern '{pattern}' in schema: {e}")
            if "format" in schema and isinstance(schema["format"], str):
                fmt_name = schema["format"]
                fmt_re = cls._FORMAT_VALIDATORS.get(fmt_name)
                if fmt_re is not None and not fmt_re.match(data):
                    errors.append(f"{path}: string '{data}' is not a valid '{fmt_name}' format")

        # 5. Array Constraints
        if isinstance(data, list):
            if "minItems" in schema and len(data) < schema["minItems"]:
                errors.append(f"{path}: array has {len(data)} items, less than minItems {schema['minItems']}")
            if "maxItems" in schema and len(data) > schema["maxItems"]:
                errors.append(f"{path}: array has {len(data)} items, exceeds maxItems {schema['maxItems']}")
            if schema.get("uniqueItems"):
                seen_items: Set[str] = set()
                for idx, item in enumerate(data):
                    key = json.dumps(item, sort_keys=True)
                    if key in seen_items:
                        errors.append(f"{path}[{idx}]: duplicate item violates uniqueItems")
                        break
                    seen_items.add(key)
            items_schema = schema.get("items")
            if isinstance(items_schema, dict):
                for idx, item in enumerate(data):
                    errors.extend(cls.validate(item, items_schema, f"{path}[{idx}]", root_schema, _seen_refs))
            elif isinstance(items_schema, list):
                for idx, item in enumerate(data):
                    if idx < len(items_schema) and isinstance(items_schema[idx], dict):
                        errors.extend(cls.validate(item, items_schema[idx], f"{path}[{idx}]", root_schema, _seen_refs))
                    elif "additionalItems" in schema:
                        add_items = schema["additionalItems"]
                        if add_items is False:
                            errors.append(
                                f"{path}[{idx}]: additional array items not allowed (tuple length {len(items_schema)})"
                            )
                        elif isinstance(add_items, dict):
                            errors.extend(cls.validate(item, add_items, f"{path}[{idx}]", root_schema, _seen_refs))
            if "contains" in schema and isinstance(schema["contains"], dict):
                if not any(len(cls.validate(item, schema["contains"], path, root_schema, _seen_refs)) == 0 for item in data):
                    errors.append(f"{path}: array does not contain any item matching 'contains' schema")

        # 6. Object Constraints
        if isinstance(data, dict):
            if "minProperties" in schema and len(data) < schema["minProperties"]:
                errors.append(
                    f"{path}: object has {len(data)} properties, less than minProperties {schema['minProperties']}"
                )
            if "maxProperties" in schema and len(data) > schema["maxProperties"]:
                errors.append(
                    f"{path}: object has {len(data)} properties, exceeds maxProperties {schema['maxProperties']}"
                )

            for req in schema.get("required", []):
                if req not in data:
                    errors.append(f"{path}: missing required property '{req}'")

            properties = schema.get("properties", {}) if isinstance(schema.get("properties"), dict) else {}
            for prop_name, prop_schema in properties.items():
                if prop_name in data:
                    errors.extend(
                        cls.validate(data[prop_name], prop_schema, f"{path}.{prop_name}", root_schema, _seen_refs)
                    )

            pattern_props = (
                schema.get("patternProperties", {}) if isinstance(schema.get("patternProperties"), dict) else {}
            )
            matched_by_pattern: Set[str] = set()
            for pat, pat_schema in pattern_props.items():
                try:
                    cre = re.compile(pat)
                except re.error as e:
                    errors.append(f"{path}: invalid patternProperties regex '{pat}': {e}")
                    continue
                for key, val in data.items():
                    if cre.search(key):
                        matched_by_pattern.add(key)
                        if isinstance(pat_schema, dict):
                            errors.extend(cls.validate(val, pat_schema, f"{path}.{key}", root_schema, _seen_refs))

            if "propertyNames" in schema and isinstance(schema["propertyNames"], dict):
                for key in data.keys():
                    errors.extend(
                        cls.validate(key, schema["propertyNames"], f"{path}.<propertyName:{key}>", root_schema, _seen_refs)
                    )

            additional_props = schema.get("additionalProperties")
            allowed_keys = set(properties.keys()) | matched_by_pattern
            if additional_props is False:
                for key in data.keys():
                    if key not in allowed_keys and not key.startswith("$"):
                        errors.append(
                            f"{path}: unexpected additional property '{key}' (additionalProperties is false)"
                        )
            elif isinstance(additional_props, dict):
                for key, val in data.items():
                    if key not in allowed_keys and not key.startswith("$"):
                        errors.extend(cls.validate(val, additional_props, f"{path}.{key}", root_schema, _seen_refs))

            dependencies = schema.get("dependencies", {})
            if isinstance(dependencies, dict):
                for dep_key, dep_target in dependencies.items():
                    if dep_key not in data:
                        continue
                    if isinstance(dep_target, list):
                        for req_dep in dep_target:
                            if req_dep not in data:
                                errors.append(
                                    f"{path}: property '{dep_key}' requires dependent property '{req_dep}'"
                                )
                    elif isinstance(dep_target, dict):
                        errors.extend(cls.validate(data, dep_target, path, root_schema, _seen_refs))

        # 7. Boolean & Conditional Combinators
        if "allOf" in schema and isinstance(schema["allOf"], list):
            for sub in schema["allOf"]:
                errors.extend(cls.validate(data, sub, path, root_schema, _seen_refs))
        if "anyOf" in schema and isinstance(schema["anyOf"], list):
            if not any(len(cls.validate(data, sub, path, root_schema, _seen_refs)) == 0 for sub in schema["anyOf"]):
                errors.append(f"{path}: value does not match any schema in anyOf")
        if "oneOf" in schema and isinstance(schema["oneOf"], list):
            matches = sum(1 for sub in schema["oneOf"] if len(cls.validate(data, sub, path, root_schema, _seen_refs)) == 0)
            if matches != 1:
                errors.append(f"{path}: value matched {matches} schemas in oneOf (expected exactly 1)")
        if "not" in schema and isinstance(schema["not"], dict):
            if len(cls.validate(data, schema["not"], path, root_schema, _seen_refs)) == 0:
                errors.append(f"{path}: value must not match disallowed schema in 'not'")
        if "if" in schema and isinstance(schema["if"], dict):
            cond_ok = len(cls.validate(data, schema["if"], path, root_schema, _seen_refs)) == 0
            if cond_ok and isinstance(schema.get("then"), dict):
                errors.extend(cls.validate(data, schema["then"], path, root_schema, _seen_refs))
            elif not cond_ok and isinstance(schema.get("else"), dict):
                errors.extend(cls.validate(data, schema["else"], path, root_schema, _seen_refs))

        return errors

    @staticmethod
    def _validate_type(data: Any, expected_type: Union[str, List[str]], path: str) -> List[str]:
        type_map = {
            "object": dict,
            "array": list,
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "null": type(None),
        }
        types_to_check = [expected_type] if isinstance(expected_type, str) else expected_type

        is_valid = False
        for t in types_to_check:
            py_type = type_map.get(t)
            if py_type is None:
                continue
            if t == "integer":
                if isinstance(data, int) and not isinstance(data, bool):
                    is_valid = True
                    break
            elif t == "number":
                if isinstance(data, (int, float)) and not isinstance(data, bool):
                    is_valid = True
                    break
            elif isinstance(data, py_type):
                is_valid = True
                break

        if not is_valid:
            actual = "null" if data is None else type(data).__name__
            return [f"{path}: expected type '{expected_type}', got '{actual}'"]
        return []
