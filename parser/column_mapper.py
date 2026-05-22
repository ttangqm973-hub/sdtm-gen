import re
from config import SPEC_COLUMN_MAP, SPEC_COLUMN_ALIASES


class ColumnMapper:
    def __init__(self):
        self.column_map = SPEC_COLUMN_MAP
        self.aliases = SPEC_COLUMN_ALIASES

    def detect_columns(self, headers: list) -> dict:
        """Detect and map SPEC columns to IR fields."""
        mapping = {}
        header_lower = {str(h).strip().lower(): h for h in headers if h}

        for ir_field, aliases in self.aliases.items():
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower in header_lower:
                    mapping[header_lower[alias_lower]] = ir_field
                    break

        for spec_col, ir_field in self.column_map.items():
            spec_lower = spec_col.lower()
            if spec_lower in header_lower and ir_field not in mapping.values():
                mapping[header_lower[spec_lower]] = ir_field

        return mapping

    def map_row(self, row: dict, column_mapping: dict = None) -> dict:
        """Map a SPEC row to IR fields."""
        if column_mapping is None:
            column_mapping = self._build_default_mapping(row)

        result = {}
        for header, ir_field in column_mapping.items():
            value = row.get(header, "")
            result[ir_field] = value

        if "codelist_name" in result:
            result["codelist_parsed"] = self._parse_codelist(result.get("codelist_name", ""))

        if "length" in result:
            result["length"] = self._parse_length(result.get("length", "8"))

        return result

    def _build_default_mapping(self, row: dict) -> dict:
        """Build mapping from available row keys."""
        mapping = {}
        row_keys_lower = {k.lower(): k for k in row.keys()}

        for ir_field, aliases in self.aliases.items():
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower in row_keys_lower:
                    mapping[row_keys_lower[alias_lower]] = ir_field
                    break

        return mapping

    def _parse_codelist(self, raw: str) -> dict | None:
        """Parse codelist string into dictionary."""
        if not raw or not str(raw).strip():
            return None
        raw = str(raw).strip()

        items = re.split(r'[;,]', raw)
        result = {}
        for item in items:
            item = item.strip()
            if not item:
                continue
            if "=" in item:
                key, val = item.split("=", 1)
                result[key.strip()] = val.strip()
            elif item:
                result[item] = item

        return result if result else None

    def _parse_length(self, raw: str) -> int:
        """Parse length value, handling ~ASDATA and other special values."""
        if not raw:
            return 8
        raw = str(raw).strip()
        if raw.startswith("~") or raw.upper() in ("ASDATA", "DEFAULT"):
            return 8
        try:
            return int(float(raw))
        except (ValueError, TypeError):
            return 8
