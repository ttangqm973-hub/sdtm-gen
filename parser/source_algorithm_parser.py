"""
Source/Algorithm Parser for SDTM SPEC templates.

Parses the "Source/Algorithm" column from SPEC Variable sheets and the
"Values" sheet from SUPPxx files into structured instructions that drive
SAS code generation.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedAlgorithm:
    """Structured representation of a Source/Algorithm value."""
    raw_text: str
    pattern: str  # direct_assign | conditional | raw_mapping | sdtm_ref | substring | external | complex
    direct_value: Optional[str] = None
    raw_source: Optional[str] = None       # parsed from "raw.AE.AEIN2" → "AEIN2"
    raw_domain: Optional[str] = None        # parsed from "raw.AE.AEIN2" → "AE"
    sdtm_ref: Optional[str] = None          # parsed from "sdtm.DM.USUBJID"
    condition: Optional[str] = None         # the "when/if" clause
    substring_part: Optional[int] = None    # e.g., "2nd 200 chars" → 2
    external_ref: Optional[str] = None      # "See Values Sheet" → "Values Sheet"
    is_templateable: bool = False           # can be handled by deterministic template logic


# Patterns for parsing

# "Set to "VALUE"" or "Set to VARIABLE"
_RE_SET_TO = re.compile(
    r'Set\s+to\s+"([^"]*)"', re.IGNORECASE
)

# "Set to "VALUE" when/if CONDITION", "Set to DOMAIN.VAR", "Set to character/record..."
_RE_SET_TO_COMPLEX = re.compile(
    r'Set\s+to\s+(.+)', re.IGNORECASE
)

# "raw.DOMAIN.VARNAME"
_RE_RAW_SOURCE = re.compile(
    r'raw\.([A-Za-z]+)\.([A-Za-z0-9_]+)', re.IGNORECASE
)

# "sdtm.DOMAIN.VARNAME"
_RE_SDTM_REF = re.compile(
    r'sdtm\.([A-Za-z]+)\.([A-Za-z0-9_]+)', re.IGNORECASE
)

# "DOMAIN.VARNAME" (simple cross-reference, not set to pattern)
_RE_CROSS_REF = re.compile(
    r'^\s*([A-Z]{2,10})\.([A-Za-z0-9_]+)\s*$'
)

# "[DOMAIN.VARNAME]" bracketed cross-reference
_RE_BRACKET_REF = re.compile(
    r'^\s*\[([A-Za-z]{2,10})\.([A-Za-z0-9_]+)\]\s*$'
)

# "raw.DOMAIN" (raw dataset reference without specific variable)
_RE_RAW_DOMAIN = re.compile(
    r'^\s*raw\.([A-Za-z]{2,10})\s*$'
)

# "Xth part of ..." substring extraction
_RE_SUBSTRING = re.compile(
    r'(\d+)(?:st|nd|rd|th)\s+part\s+of\s+the\s+comments?\s+text', re.IGNORECASE
)

# "2nd 200 chars of raw.XX.VAR"
_RE_SUBSTRING_RAW = re.compile(
    r'(\d+)(?:st|nd|rd|th)\s+(\d+)\s*chars?\s+of\s+raw\.([A-Za-z]+)\.([A-Za-z0-9_]+)', re.IGNORECASE
)

# "See Values Sheet" / "See XXX sheet"
_RE_EXTERNAL = re.compile(
    r'See\s+(.+)', re.IGNORECASE
)

# "Based on aCRF..." / "Based on coding..."
_RE_REFERENCE = re.compile(
    r'Based\s+on\s+(.+)', re.IGNORECASE
)

# "Assign as null" / "Assigned from..."
_RE_ASSOCIATED = re.compile(
    r'(Assign|Assigned|Mapping|Convert|From|The)\s+.*', re.IGNORECASE
)


def parse_source_algorithm(text: str) -> ParsedAlgorithm:
    """Parse a Source/Algorithm string into structured instructions."""
    if not text or not text.strip():
        return ParsedAlgorithm(raw_text="", pattern="empty")

    text = text.strip()

    # 1. "Set to "VALUE"" — direct assignment
    set_match = _RE_SET_TO.match(text)
    if set_match:
        result = _parse_set_to(text, set_match)
        if result:
            return result

    # 2. "Set to ..." (complex patterns with conditions)
    set_complex_match = _RE_SET_TO_COMPLEX.match(text)
    if set_complex_match:
        result = _parse_set_to_complex(text)
        if result:
            return result

    # 3. "raw.DOMAIN.VARNAME"
    raw_match = _RE_RAW_SOURCE.match(text)
    if raw_match:
        return ParsedAlgorithm(
            raw_text=text,
            pattern="raw_mapping",
            raw_source=raw_match.group(2),
            raw_domain=raw_match.group(1),
            is_templateable=True,
        )

    # 4. "sdtm.DOMAIN.VARNAME"
    sdtm_match = _RE_SDTM_REF.match(text)
    if sdtm_match:
        is_tmpl = True
        # If the text contains more than just a ref (date calc, conditions), not templateable
        rest = text[sdtm_match.end():].strip()
        if rest and not rest.startswith(';'):
            is_tmpl = False
        return ParsedAlgorithm(
            raw_text=text,
            pattern="sdtm_ref",
            sdtm_ref=f"sdtm.{sdtm_match.group(1)}.{sdtm_match.group(2)}",
            raw_source=sdtm_match.group(2),
            is_templateable=is_tmpl,
        )

    # 5. "DOMAIN.VARNAME" (cross-reference or raw dataset reference)
    cross_match = _RE_CROSS_REF.match(text)
    if cross_match:
        domain = cross_match.group(1).upper()
        if _is_known_domain(domain):
            return ParsedAlgorithm(
                raw_text=text,
                pattern="cross_ref",
                raw_source=cross_match.group(2),
                is_templateable=True,
            )
        else:
            # Raw dataset reference: e.g., SI.SITE, RAND.RANDFA1, CT.CTARM
            return ParsedAlgorithm(
                raw_text=text,
                pattern="raw_dataset_ref",
                raw_source=cross_match.group(2),
                raw_domain=cross_match.group(1).upper(),
                is_templateable=True,
            )

    # 5b. "[DOMAIN.VARNAME]" bracketed cross-reference
    bracket_match = _RE_BRACKET_REF.match(text)
    if bracket_match:
        domain = bracket_match.group(1).upper()
        if _is_known_domain(domain):
            return ParsedAlgorithm(
                raw_text=text,
                pattern="cross_ref",
                raw_source=bracket_match.group(2),
                is_templateable=True,
            )
        else:
            return ParsedAlgorithm(
                raw_text=text,
                pattern="raw_dataset_ref",
                raw_source=bracket_match.group(2),
                raw_domain=bracket_match.group(1).upper(),
                is_templateable=True,
            )

    # 5c. "raw.DOMAIN" (raw dataset without specific variable)
    raw_domain_match = _RE_RAW_DOMAIN.match(text)
    if raw_domain_match:
        return ParsedAlgorithm(
            raw_text=text,
            pattern="raw_domain",
            raw_domain=raw_domain_match.group(1).upper(),
            is_templateable=True,
        )

    # 6. "Xth part of ..." substring extraction patterns
    sub_raw_match = _RE_SUBSTRING_RAW.search(text)
    if sub_raw_match:
        return ParsedAlgorithm(
            raw_text=text,
            pattern="substring_raw",
            raw_source=sub_raw_match.group(4),
            raw_domain=sub_raw_match.group(3),
            substring_part=int(sub_raw_match.group(1)),
            is_templateable=True,
        )
    sub_match = _RE_SUBSTRING.search(text)
    if sub_match:
        return ParsedAlgorithm(
            raw_text=text,
            pattern="substring",
            substring_part=int(sub_match.group(1)),
            is_templateable=False,
        )

    # 7. "See XXX" — external sheet/lookup
    ext_match = _RE_EXTERNAL.match(text)
    if ext_match:
        return ParsedAlgorithm(
            raw_text=text,
            pattern="external",
            external_ref=ext_match.group(1).rstrip('.'),
            is_templateable=False,
        )

    # 8. "Based on ..." — reference documents
    ref_match = _RE_REFERENCE.match(text)
    if ref_match:
        return ParsedAlgorithm(
            raw_text=text,
            pattern="reference",
            external_ref=ref_match.group(1).rstrip('.'),
            is_templateable=False,
        )

    # 9. Date calculation patterns involving sdtm refs
    if 'sdtm.' in text.lower() and ('dtc' in text.lower() or 'date' in text.lower()):
        raw_sources = _RE_SDTM_REF.findall(text)
        return ParsedAlgorithm(
            raw_text=text,
            pattern="date_calculation",
            raw_source=raw_sources[0][1] if raw_sources else None,
            sdtm_ref=f"sdtm.{raw_sources[0][0]}.{raw_sources[0][1]}" if raw_sources else None,
            is_templateable=False,
        )

    # 10. Complex or natural language — mark for AI
    return ParsedAlgorithm(
        raw_text=text,
        pattern="complex",
        is_templateable=False,
    )


def _is_known_domain(domain: str) -> bool:
    """Check if a domain abbreviation is a known SDTM/CDISC domain."""
    return domain.upper() in {
        "DM", "AE", "CM", "LB", "VS", "EX", "MH", "EG", "PE",
        "DS", "SV", "IE", "QS", "CV", "DD", "DV", "EC", "FA",
        "IS", "PC", "PP", "RS", "TR", "TU", "PR", "CO",
        "SE", "SS", "SU", "TI", "TD", "TE", "TA", "TS", "TV",
        "MI", "PF", "XO", "IC", "SCR", "DTH", "SI", "RAND",
        "SUPPAE", "SUPPDM", "SUPPCM",
    }


def _parse_set_to(text: str, set_match) -> Optional[ParsedAlgorithm]:
    """Parse 'Set to "VALUE"' style patterns."""
    value = set_match.group(1)

    # Check for condition after the value
    rest = text[set_match.end():].strip()
    condition = None
    if rest:
        cond_match = re.match(r'(?:when|if|,|；|else|otherwise)\s+(.+)', rest, re.IGNORECASE)
        if cond_match:
            condition = cond_match.group(1).strip()

    # Check if the value itself is a cross-reference
    sdtm_in_value = _RE_SDTM_REF.search(text)
    raw_in_value = _RE_RAW_SOURCE.search(text)

    # Complex date calculations in "Set to" pattern are not templateable
    has_complex_logic = any(kw in text.lower() for kw in ['dtc', 'date part', '-'])

    if sdtm_in_value:
        return ParsedAlgorithm(
            raw_text=text,
            pattern="conditional" if condition else "sdtm_ref",
            direct_value=value,
            sdtm_ref=f"sdtm.{sdtm_in_value.group(1)}.{sdtm_in_value.group(2)}",
            condition=condition,
            is_templateable=not (bool(condition) or has_complex_logic),
        )
    if raw_in_value:
        return ParsedAlgorithm(
            raw_text=text,
            pattern="conditional" if condition else "raw_mapping",
            direct_value=value,
            raw_source=raw_in_value.group(2),
            raw_domain=raw_in_value.group(1),
            condition=condition,
            is_templateable=not bool(condition),
        )

    # Plain "Set to VALUE"
    return ParsedAlgorithm(
        raw_text=text,
        pattern="conditional" if condition else "direct_assign",
        direct_value=value,
        condition=condition,
        is_templateable=not bool(condition),
    )


def _parse_set_to_complex(text: str) -> Optional[ParsedAlgorithm]:
    """Parse complex 'Set to ...' patterns (not simple quoted values)."""
    sdtm_matches = _RE_SDTM_REF.findall(text)
    raw_matches = _RE_RAW_SOURCE.findall(text)

    # Check for conditions and multi-line
    has_condition = bool(re.search(r'\b(?:when|if|；)\b', text, re.IGNORECASE))

    raw_source = raw_matches[0][1] if raw_matches else None
    sdtm_ref = f"sdtm.{sdtm_matches[0][0]}.{sdtm_matches[0][1]}" if sdtm_matches else None

    # "Set to DOMAIN.VARNAME"
    simple_ref = re.match(r'Set\s+to\s+([A-Za-z]+\.[A-Za-z0-9_]+)\s*$', text, re.IGNORECASE)
    if simple_ref:
        parts = simple_ref.group(1).split('.')
        return ParsedAlgorithm(
            raw_text=text,
            pattern="cross_ref",
            raw_source=parts[1],
            raw_domain=parts[0].upper() if parts[0].lower() != 'raw' else None,
            is_templateable=True,
        )

    pattern_type = "conditional" if has_condition else "complex"
    return ParsedAlgorithm(
        raw_text=text,
        pattern=pattern_type,
        raw_source=raw_source,
        sdtm_ref=sdtm_ref,
        is_templateable=False,
    )
