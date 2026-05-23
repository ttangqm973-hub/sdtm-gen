import re
from parser.column_mapper import ColumnMapper
from parser.source_algorithm_parser import parse_source_algorithm
from ir.models import Variable, DomainIR
from config import DOMAIN_LABELS


class IRBuilder:
    def __init__(self):
        self.mapper = ColumnMapper()

    def build(self, domain: str, rows: list[dict], column_mapping: dict = None) -> DomainIR:
        """Build Domain IR from SPEC rows."""
        if column_mapping is None:
            column_mapping = self.mapper.detect_columns(list(rows[0].keys())) if rows else {}

        variables = []
        for seq, row in enumerate(rows, start=1):
            mapped = self.mapper.map_row(row, column_mapping)
            generation = self._determine_generation(mapped)

            source_algo = str(mapped.get("source_algorithm", "")).strip()
            parsed = parse_source_algorithm(source_algo) if source_algo else None

            variable = Variable(
                seq=seq,
                name=mapped.get("variable_name", ""),
                label=mapped.get("variable_label", ""),
                type=self._safe_type(mapped.get("data_type", "Char")),
                length=mapped.get("length", 8),
                origin=self._safe_origin(mapped.get("origin", "Assigned")),
                generation=generation,
                codelist=mapped.get("codelist_parsed"),
                algorithm=mapped.get("algorithm_text") if mapped.get("algorithm_text") else None,
                source_algorithm=source_algo if source_algo else None,
                raw_source=parsed.raw_source if parsed and parsed.raw_source else None,
                comment=mapped.get("comment"),
            )

            if generation == "ai_required":
                variable.ai_context = self._build_ai_context(mapped, parsed)

            variables.append(variable)

        domain_ir = DomainIR(
            domain=domain.upper(),
            domain_label=DOMAIN_LABELS.get(domain.upper(), domain),
            source_sheet=domain,
            variables=variables,
            template_name=f"{domain.lower()}_standard",
        )

        self._analyze_cross_domain_refs(domain_ir)
        self._detect_macro_refs(domain_ir)

        return domain_ir

    def _determine_generation(self, mapped: dict) -> str:
        """Determine if variable needs template generation or AI assistance."""
        origin = str(mapped.get("origin", "")).strip()
        algorithm = str(mapped.get("algorithm_text", "")).strip()
        source = str(mapped.get("source_algorithm", "")).strip()

        # Parse source_algorithm to determine if template can handle it
        parsed = parse_source_algorithm(source) if source else None

        if origin == "Derived":
            if algorithm or source:
                # If source_algorithm is simple enough for template, return template
                if parsed and parsed.is_templateable:
                    return "template"
                algo_lower = (algorithm + " " + source).lower()
                simple_patterns = [
                    r"concat\s*\(",
                    r"strip\s*\(",
                    r"input\s*\(",
                    r"put\s*\(",
                    r"scan\s*\(",
                    r"substr\s*\(",
                ]
                for pattern in simple_patterns:
                    if re.search(pattern, algo_lower):
                        return "template"
                return "ai_required"
            return "template"

        if origin == "Assigned":
            return "template"

        if origin == "CRF":
            return "template"

        if origin == "Predecessor":
            return "template"

        return "template"

    def _build_ai_context(self, mapped: dict, parsed=None) -> dict:
        """Build AI context for derived variables."""
        algorithm = str(mapped.get("algorithm_text", "")).strip()
        source = str(mapped.get("source_algorithm", "")).strip()
        algo = (algorithm + " " + source).strip()

        if parsed and parsed.pattern in ("direct_assign", "cross_ref"):
            algo = source  # Use only source_algorithm context for simple patterns

        related_vars = []
        var_pattern = re.findall(r'\b([A-Z]{2,}\.)?([A-Z][A-Z0-9_]{1,7})\b', algo)
        for prefix, name in var_pattern:
            if name not in ("IF", "THEN", "ELSE", "AND", "OR", "NOT", "DO", "END", "WHEN"):
                related_vars.append(name)

        related_domains = []
        domain_pattern = re.findall(r'\b(AE|DM|CM|LB|VS|EX|MH|EG|PE|DS|SV|IE|QS|RS|TR|TU|PR|FA|CO)\b', algo.upper())
        related_domains = list(set(domain_pattern))

        logic_type = "conditional_derivation"
        algo_lower = algo.lower()
        if "date" in algo_lower or "dtc" in algo_lower:
            logic_type = "date_derivation"
        elif parsed and parsed.pattern == "cross_ref":
            logic_type = "cross_domain_reference"
        elif parsed and parsed.pattern == "direct_assign":
            logic_type = "direct_assignment"
        elif "merge" in algo_lower or "join" in algo_lower:
            logic_type = "cross_domain_merge"
        elif "sum" in algo_lower or "count" in algo_lower:
            logic_type = "aggregation"

        return {
            "related_vars": list(set(related_vars)),
            "related_domains": related_domains,
            "logic_type": logic_type,
            "algorithm_text": algo,
        }

    def _safe_type(self, raw) -> str:
        """Convert type string to standard form."""
        if not raw:
            return "Char"
        raw_upper = str(raw).strip().upper()
        if raw_upper in ("CHAR", "CHARACTER", "TEXT", "C"):
            return "Char"
        if raw_upper in ("NUM", "NUMERIC", "NUMBER", "INT", "INTEGER", "N"):
            return "Num"
        return "Char"

    def _safe_origin(self, raw) -> str:
        """Normalize origin value to one of the valid SDTM origins."""
        if not raw:
            return "Assigned"
        raw = str(raw).strip()

        # Direct matches
        valid_map = {
            "CRF": "CRF",
            "Assigned": "Assigned",
            "Derived": "Derived",
            "Predecessor": "Predecessor",
        }
        if raw in valid_map:
            return valid_map[raw]

        # Case-insensitive mappings
        raw_lower = raw.lower()
        if raw_lower in ("crf", "edc", "eCRF"):
            return "CRF"
        if raw_lower in ("assigned", "protocol", "sponsor"):
            return "Assigned"
        if raw_lower in ("derived", "calculation"):
            return "Derived"
        if raw_lower in ("predecessor", "previous"):
            return "Predecessor"
        if raw_lower in ("edt", "eDT"):
            return "Assigned"

        return "Assigned"

    def _analyze_cross_domain_refs(self, domain_ir: DomainIR):
        """Analyze cross-domain references."""
        cross_refs = set()
        for var in domain_ir.variables:
            if var.ai_context:
                cross_refs.update(var.ai_context.get("related_domains", []))
        domain_ir.cross_domain_refs = list(cross_refs)

    def _detect_macro_refs(self, domain_ir: DomainIR):
        """Detect required macro references."""
        macro_refs = []
        for var in domain_ir.variables:
            algo = (var.algorithm or "") + " " + (var.source_algorithm or "")
            if "date" in algo.lower() or "dtc" in algo.lower():
                if "date" not in macro_refs:
                    macro_refs.append("date")
            if "dy" in algo.lower() or "study day" in algo.lower():
                if "aactdy" not in macro_refs:
                    macro_refs.append("aactdy")
        domain_ir.macro_refs = macro_refs
