"""Zero-dependency YAML 1.2 core parser supporting block scalars, nested flow collections, anchors/aliases, and null keys."""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Dict, List, Optional, Tuple


def _split_unquoted(text: str, delimiter: str = ",") -> List[str]:
    """Split *text* on *delimiter* outside quotes and nested [] / {} flow collections."""
    parts: List[str] = []
    buf: List[str] = []
    in_quote: Optional[str] = None
    depth_bracket = 0
    depth_brace = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and in_quote == '"' and i + 1 < len(text):
            buf.append(ch)
            buf.append(text[i + 1])
            i += 2
            continue
        if ch in ('"', "'"):
            if in_quote == ch:
                in_quote = None
            elif in_quote is None:
                in_quote = ch
            buf.append(ch)
        elif in_quote is None:
            if ch == "[":
                depth_bracket += 1
                buf.append(ch)
            elif ch == "]" and depth_bracket > 0:
                depth_bracket -= 1
                buf.append(ch)
            elif ch == "{":
                depth_brace += 1
                buf.append(ch)
            elif ch == "}" and depth_brace > 0:
                depth_brace -= 1
                buf.append(ch)
            elif ch == delimiter and depth_bracket == 0 and depth_brace == 0:
                parts.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        else:
            buf.append(ch)
        i += 1
    if buf or parts:
        parts.append("".join(buf))
    return parts


def _unquote_scalar(val: str) -> str:
    """Strip matching outer single or double quotes and unescape double-quoted escapes."""
    if len(val) >= 2 and val.startswith('"') and val.endswith('"'):
        inner = val[1:-1]
        out: List[str] = []
        i = 0
        while i < len(inner):
            if inner[i] == "\\" and i + 1 < len(inner):
                nxt = inner[i + 1]
                if nxt == "n":
                    out.append("\n")
                elif nxt == "t":
                    out.append("\t")
                elif nxt == "r":
                    out.append("\r")
                elif nxt in ('"', "\\", "/"):
                    out.append(nxt)
                else:
                    out.append("\\" + nxt)
                i += 2
                continue
            out.append(inner[i])
            i += 1
        return "".join(out)
    if len(val) >= 2 and val.startswith("'") and val.endswith("'"):
        return val[1:-1].replace("''", "'")
    return val


def _find_unquoted_colon(text: str) -> int:
    """Return index of first YAML mapping colon (':' followed by space or EOL) outside quotes and nested []/{}."""
    in_quote: Optional[str] = None
    depth_bracket = 0
    depth_brace = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and in_quote == '"' and i + 1 < len(text):
            i += 2
            continue
        if ch in ('"', "'"):
            if in_quote == ch:
                in_quote = None
            elif in_quote is None:
                in_quote = ch
        elif in_quote is None:
            if ch == "[":
                depth_bracket += 1
            elif ch == "]" and depth_bracket > 0:
                depth_bracket -= 1
            elif ch == "{":
                depth_brace += 1
            elif ch == "}" and depth_brace > 0:
                depth_brace -= 1
            elif ch == ":" and depth_bracket == 0 and depth_brace == 0:
                if i == len(text) - 1 or text[i + 1].isspace():
                    return i
        i += 1
    return -1


class SimpleYamlParser:
    """Zero-dependency YAML 1.2 Core parser supporting mappings, sequences, block scalars, flow collections, and anchors."""

    _BLOCK_HEADERS = {"|", "|-", "|+", ">", ">-", ">+"}

    @classmethod
    def _strip_comment(cls, raw_line: str) -> str:
        """Strip trailing # comment outside single/double quotes (handling escaped quotes)."""
        buf: List[str] = []
        in_quote: Optional[str] = None
        i = 0
        while i < len(raw_line):
            ch = raw_line[i]
            if ch == "\\" and in_quote == '"' and i + 1 < len(raw_line):
                buf.append(ch)
                buf.append(raw_line[i + 1])
                i += 2
                continue
            if ch in ('"', "'"):
                if in_quote == ch:
                    in_quote = None
                elif in_quote is None:
                    in_quote = ch
                buf.append(ch)
            elif ch == "#" and in_quote is None and (i == 0 or raw_line[i - 1].isspace()):
                break
            else:
                buf.append(ch)
            i += 1
        return "".join(buf)

    @classmethod
    def _extract_anchor(cls, val: str) -> Tuple[Optional[str], str]:
        """Extract leading &anchor token from a YAML value string if present."""
        s = val.strip()
        if s.startswith("&") and len(s) > 1 and not s.startswith("&&"):
            parts = s.split(None, 1)
            anchor_name = parts[0][1:].strip()
            rest = parts[1].strip() if len(parts) > 1 else ""
            if anchor_name:
                return anchor_name, rest
        return None, s

    @classmethod
    def _line_opens_block_scalar(cls, stripped_content: str) -> bool:
        """Return True if a stripped YAML line ends with a block scalar indicator (|, |-, |+, >, >-, >+)."""
        candidate = stripped_content
        if candidate.startswith("- "):
            candidate = candidate[2:].strip()
        colon_idx = _find_unquoted_colon(candidate) if not candidate.startswith(("{", "[")) else -1
        if colon_idx != -1:
            val_part = candidate[colon_idx + 1:].strip()
        else:
            val_part = candidate
        _, rest = cls._extract_anchor(val_part)
        return rest in cls._BLOCK_HEADERS

    @classmethod
    def _tokenize_lines(cls, text: str) -> List[Tuple[int, str, str]]:
        """Tokenize YAML into (indent, stripped_line, raw_line) preserving block scalar raw lines and blanks."""
        entries: List[Tuple[int, str, str]] = []
        block_parent_indent: Optional[int] = None

        for raw_line in text.splitlines():
            if block_parent_indent is not None:
                if not raw_line.strip():
                    entries.append((-1, "", ""))
                    continue
                raw_indent = len(raw_line) - len(raw_line.lstrip(" "))
                if raw_indent > block_parent_indent:
                    entries.append((raw_indent, raw_line[raw_indent:], raw_line))
                    continue
                block_parent_indent = None

            line_no_comment = cls._strip_comment(raw_line)
            stripped_r = line_no_comment.rstrip()
            if not stripped_r:
                continue
            indent = len(stripped_r) - len(stripped_r.lstrip(" "))
            content = stripped_r.strip()
            entries.append((indent, content, stripped_r))
            if cls._line_opens_block_scalar(content):
                block_parent_indent = indent

        # Drop any trailing blank lines at EOF that were not followed by block content
        while entries and entries[-1][0] == -1:
            entries.pop()
        return entries

    @classmethod
    def _consume_block_scalar(
        cls,
        lines: List[Tuple[int, str, str]],
        idx: int,
        parent_indent: int,
        indicator: str,
    ) -> Tuple[str, int]:
        """Consume indented block scalar lines starting at *idx* and apply YAML 1.2 folding and chomping."""
        collected: List[Tuple[int, str]] = []
        while idx < len(lines):
            ind, _, raw = lines[idx]
            if ind == -1:
                collected.append((-1, ""))
                idx += 1
            elif ind > parent_indent:
                collected.append((ind, raw))
                idx += 1
            else:
                break

        trailing_blanks = 0
        while collected and collected[-1][0] == -1:
            collected.pop()
            trailing_blanks += 1

        non_blank_indents = [ind for ind, _ in collected if ind >= 0]
        if not non_blank_indents:
            if indicator.endswith("+") and trailing_blanks > 0:
                return "\n" * trailing_blanks, idx
            return "", idx

        min_indent = min(non_blank_indents)
        dedented: List[Tuple[bool, str]] = []
        for ind, raw in collected:
            if ind == -1:
                dedented.append((False, ""))
            else:
                text_line = raw[min_indent:] if len(raw) >= min_indent else ""
                dedented.append((ind > min_indent, text_line))

        if indicator.startswith("|"):
            body = "\n".join(line for _, line in dedented)
        else:
            # Folded '>' block scalar per YAML 1.2: fold single newlines between normal lines into spaces
            out_chunks: List[str] = []
            para_buf: List[str] = []

            def _flush_para() -> None:
                if para_buf:
                    out_chunks.append(" ".join(para_buf))
                    para_buf.clear()

            for is_more_indented, line in dedented:
                if line == "":
                    _flush_para()
                    out_chunks.append("")
                elif is_more_indented:
                    _flush_para()
                    out_chunks.append(line)
                else:
                    para_buf.append(line)
            _flush_para()

            # Reconstruct folded text: blank line items become paragraph breaks
            rebuilt: List[str] = []
            i = 0
            while i < len(out_chunks):
                if out_chunks[i] == "":
                    blank_run = 0
                    while i < len(out_chunks) and out_chunks[i] == "":
                        blank_run += 1
                        i += 1
                    rebuilt.append("\n" * blank_run)
                else:
                    if rebuilt and not rebuilt[-1].endswith("\n"):
                        rebuilt.append("\n")
                    rebuilt.append(out_chunks[i])
                    i += 1
            body = "".join(rebuilt)

        if indicator.endswith("-"):
            return body, idx
        if indicator.endswith("+"):
            return body + "\n" + ("\n" * trailing_blanks), idx
        return body + "\n", idx

    @classmethod
    def parse(cls, text: str) -> Any:
        entries = cls._tokenize_lines(text)
        if not entries:
            return {}
        anchors: Dict[str, Any] = {}
        res, _ = cls._parse_node(entries, 0, entries[0][0], anchors)
        return res if res is not None else {}

    @classmethod
    def _parse_node(
        cls,
        lines: List[Tuple[int, str, str]],
        idx: int,
        current_indent: int,
        anchors: Dict[str, Any],
    ) -> Tuple[Any, int]:
        while idx < len(lines) and lines[idx][0] == -1:
            idx += 1
        if idx >= len(lines):
            return None, idx
        indent, line, _ = lines[idx]
        if line == "-" or line.startswith("- "):
            return cls._parse_seq(lines, idx, indent, anchors)
        return cls._parse_map(lines, idx, indent, anchors)

    @classmethod
    def _resolve_value_or_block(
        cls,
        raw_val: str,
        lines: List[Tuple[int, str, str]],
        idx: int,
        key_indent: int,
        anchors: Dict[str, Any],
    ) -> Tuple[Any, int]:
        """Parse an inline value, block scalar, or indented child node, registering any &anchor."""
        anchor_name, rest = cls._extract_anchor(raw_val)
        if rest in cls._BLOCK_HEADERS:
            val, next_idx = cls._consume_block_scalar(lines, idx + 1, key_indent, rest)
            if anchor_name:
                anchors[anchor_name] = val
            return val, next_idx

        if rest:
            val = cls._parse_scalar(rest, anchors)
            if anchor_name:
                anchors[anchor_name] = copy.deepcopy(val)
            return val, idx + 1

        next_idx = idx + 1
        while next_idx < len(lines) and lines[next_idx][0] == -1:
            next_idx += 1
        if next_idx < len(lines) and lines[next_idx][0] > key_indent:
            sub_res, next_idx = cls._parse_node(lines, next_idx, lines[next_idx][0], anchors)
            if anchor_name:
                anchors[anchor_name] = copy.deepcopy(sub_res)
            return sub_res, next_idx

        val = None
        if anchor_name:
            anchors[anchor_name] = None
        return val, idx + 1

    @staticmethod
    def _apply_merge_key(target: Dict[str, Any], merge_val: Any) -> None:
        """Apply YAML << merge key from a mapping or list of mappings without clobbering existing keys."""
        if isinstance(merge_val, dict):
            for mk, mv in merge_val.items():
                if mk not in target:
                    target[mk] = copy.deepcopy(mv)
        elif isinstance(merge_val, list):
            for item in merge_val:
                if isinstance(item, dict):
                    for mk, mv in item.items():
                        if mk not in target:
                            target[mk] = copy.deepcopy(mv)

    @classmethod
    def _parse_seq(
        cls,
        lines: List[Tuple[int, str, str]],
        idx: int,
        current_indent: int,
        anchors: Dict[str, Any],
    ) -> Tuple[List[Any], int]:
        res: List[Any] = []
        while idx < len(lines):
            if lines[idx][0] == -1:
                idx += 1
                continue
            indent, line, raw = lines[idx]
            if indent < current_indent:
                break
            if indent == current_indent and (line == "-" or line.startswith("- ")):
                item_str = line[2:].strip() if line.startswith("- ") else ""
                if item_str == "-" or item_str.startswith("- "):
                    nested_lines = list(lines)
                    nested_indent = indent + 2
                    nested_lines[idx] = (nested_indent, item_str, raw)
                    sub_res, idx = cls._parse_seq(nested_lines, idx, nested_indent, anchors)
                    res.append(sub_res)
                    continue

                colon_idx = _find_unquoted_colon(item_str) if not item_str.startswith(("{", "[")) else -1
                if colon_idx != -1:
                    k = _unquote_scalar(item_str[:colon_idx].strip())
                    v = item_str[colon_idx + 1:].strip()
                    item_dict: Dict[str, Any] = {}
                    parsed_v, idx = cls._resolve_value_or_block(v, lines, idx, indent, anchors)
                    if k == "<<":
                        cls._apply_merge_key(item_dict, parsed_v)
                    else:
                        item_dict[k] = parsed_v

                    while idx < len(lines):
                        if lines[idx][0] == -1:
                            idx += 1
                            continue
                        s_ind, s_line, _ = lines[idx]
                        if s_ind <= current_indent:
                            break
                        if s_line == "-" or s_line.startswith("- "):
                            break
                        s_colon = _find_unquoted_colon(s_line)
                        if s_colon != -1:
                            sk = _unquote_scalar(s_line[:s_colon].strip())
                            sv = s_line[s_colon + 1:].strip()
                            sub_val, idx = cls._resolve_value_or_block(sv, lines, idx, s_ind, anchors)
                            if sk == "<<":
                                cls._apply_merge_key(item_dict, sub_val)
                            else:
                                item_dict[sk] = sub_val
                        else:
                            idx += 1
                    res.append(item_dict)
                else:
                    parsed_item, idx = cls._resolve_value_or_block(item_str, lines, idx, indent, anchors)
                    res.append(parsed_item)
            else:
                break
        return res, idx

    @classmethod
    def _parse_map(
        cls,
        lines: List[Tuple[int, str, str]],
        idx: int,
        current_indent: int,
        anchors: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], int]:
        res: Dict[str, Any] = {}
        while idx < len(lines):
            if lines[idx][0] == -1:
                idx += 1
                continue
            indent, line, _ = lines[idx]
            if indent < current_indent:
                break
            if indent == current_indent:
                colon_idx = _find_unquoted_colon(line)
                if colon_idx != -1:
                    k = _unquote_scalar(line[:colon_idx].strip())
                    v = line[colon_idx + 1:].strip()
                    parsed_v, idx = cls._resolve_value_or_block(v, lines, idx, indent, anchors)
                    if k == "<<":
                        cls._apply_merge_key(res, parsed_v)
                    else:
                        res[k] = parsed_v
                else:
                    idx += 1
            else:
                break
        return res, idx

    @classmethod
    def _parse_scalar(cls, val: str, anchors: Optional[Dict[str, Any]] = None) -> Any:
        val = val.strip()
        if not val:
            return ""
        if anchors is None:
            anchors = {}

        anchor_name, rest = cls._extract_anchor(val)
        if anchor_name:
            parsed_val = cls._parse_scalar(rest, anchors) if rest else None
            anchors[anchor_name] = copy.deepcopy(parsed_val)
            return parsed_val

        if val in cls._BLOCK_HEADERS or val.startswith(("| ", "> ")):
            raise ValueError(f"unexpected inline block scalar '{val}'")
        if val.startswith("!"):
            raise ValueError(f"unsupported YAML custom tag '{val}'")
        if val.startswith("*"):
            alias = val[1:].strip()
            if alias not in anchors:
                raise ValueError(f"undefined YAML alias '*{alias}'")
            return copy.deepcopy(anchors[alias])

        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                return []
            return [cls._parse_scalar(x, anchors) for x in _split_unquoted(inner, ",") if x.strip()]

        if val.startswith("{") and val.endswith("}"):
            inner = val[1:-1].strip()
            if not inner:
                return {}
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                parsed_map: Dict[str, Any] = {}
                for part in _split_unquoted(inner, ","):
                    part = part.strip()
                    if not part:
                        continue
                    c_idx = _find_unquoted_colon(part)
                    if c_idx == -1:
                        raise ValueError(f"malformed YAML inline mapping '{val}'")
                    mk = _unquote_scalar(part[:c_idx].strip())
                    mv = part[c_idx + 1:].strip()
                    parsed_val = cls._parse_scalar(mv, anchors) if mv else None
                    if mk == "<<":
                        cls._apply_merge_key(parsed_map, parsed_val)
                    else:
                        parsed_map[mk] = parsed_val
                return parsed_map

        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            return _unquote_scalar(val)
        if val.lower() == "true":
            return True
        if val.lower() == "false":
            return False
        if val.lower() in ("null", "~"):
            return None
        if re.match(r"^-?\d+$", val):
            return int(val)
        if re.match(r"^-?\d+\.\d+$", val):
            return float(val)
        return val
