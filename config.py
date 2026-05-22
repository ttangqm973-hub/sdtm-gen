# SDTM GEN Configuration
# Based on real-world SPEC templates from knowledge base

# SPEC Template Column Mapping (12-column standard format)
SPEC_COLUMN_MAP = {
    "VarOrd":     "seq",
    "VarName":    "variable_name",
    "VarLabel":   "variable_label",
    "VarType":    "data_type",
    "VarLen":     "length",
    "VarFormat":  "format",
    "CT/CodeListID": "codelist_name",
    "Core":       "core",
    "Origin":     "origin",
    "Source/Algorithm": "source_algorithm",
    "CRF Pages":  "crf_pages",
    "Algorithm for Programming": "algorithm_text",
}

# Alternative column names (for backward compatibility)
SPEC_COLUMN_ALIASES = {
    "variable_name": ["VarName", "VARIABLE", "Variable", "Variable Name"],
    "variable_label": ["VarLabel", "LABEL", "Label", "Variable Label"],
    "data_type": ["VarType", "TYPE", "Type"],
    "length": ["VarLen", "LENGTH", "Length"],
    "origin": ["Origin", "ORIGIN"],
    "codelist_name": ["CT/CodeListID", "CODELIST", "Codelist", "CodeList"],
    "algorithm_text": ["Algorithm for Programming", "ALGORITHM", "Algorithm"],
}

# SAS Domain Labels
DOMAIN_LABELS = {
    "DM": "Demographics",
    "AE": "Adverse Events",
    "CM": "Concomitant Medications",
    "LB": "Laboratory Test Results",
    "VS": "Vital Signs",
    "EX": "Exposure",
    "MH": "Medical History",
    "EG": "ECG Test Results",
    "PE": "Physical Examination",
    "DS": "Disposition",
    "SV": "Subject Visits",
    "IE": "Inclusion/Exclusion",
    "QS": "Questionnaires",
    "RS": "Disease Response",
    "TR": "Tumor Results",
    "TU": "Tumor Identification",
    "PR": "Procedures",
    "FA": "Findings About",
    "CO": "Comments",
    "DD": "Death Details",
    "DV": "Protocol Deviations",
    "SE": "Subject Elements",
    "SS": "Subject Status",
    "SU": "Subject Units",
    "RELREC": "Related Records",
    "SUPPAE": "Supplemental Qualifiers for AE",
    "SUPPDM": "Supplemental Qualifiers for DM",
    "SUPPCM": "Supplemental Qualifiers for CM",
}

# Supported domains for template generation
SUPPORTED_DOMAINS = [
    "DM", "AE", "CM", "LB", "VS", "EX", "MH", "EG", "PE",
    "DS", "SV", "IE", "QS", "RS", "TR", "TU", "PR", "FA",
    "CO", "DD", "DV", "SE", "SS", "SU", "RELREC",
]

# Macro Library Configuration
MACRO_LIBRARY = {
    "date_processing": ["date", "dtc", "dttm", "imputedt", "iso2sasdt", "maxdtc"],
    "baseline": ["ablfl", "baseflag"],
    "study_day": ["aactdy", "dy"],
    "supp": ["supp", "suppjoin"],
    "analysis": ["var_chg", "param", "add_trtp_trta"],
    "reporting": ["tevents", "tmeans", "tfreq", "tmeans_bds"],
    "utility": ["step", "existx", "fwords06", "coding"],
}

# Standard SAS Keywords
SAS_KEYWORDS = {
    "data", "run", "proc", "quit", "set", "merge", "update", "modify",
    "by", "where", "if", "then", "else", "do", "end", "select", "when",
    "otherwise", "output", "return", "goto", "label", "format", "informat",
    "input", "put", "cards", "datalines", "infile", "file", "keep", "drop",
    "rename", "retain", "length", "attrib", "array", "call", "stop",
    "libname", "filename", "options", "title", "footnote",
}

# SDTM Variable Classes
VARIABLE_CLASSES = {
    "identifier": ["STUDYID", "DOMAIN", "USUBJID", "SUBJID", "SITEID", "INVID"],
    "timing": ["DTC", "DT", "TM", "DY", "STRTPT", "ENRTPT"],
    "topic": ["TERM", "DECOD", "BODSYS", "SOC", "HLT", "LLT"],
    "qualifier": ["STAT", "REASND", "SEV", "SER", "ACN", "OUT"],
}

# Standard header template
SAS_HEADER_TEMPLATE = '''/****************************************************************************************************************
Sponsor Name                 : {sponsor}
Protocol Number              : {protocol}
Program Name                 : {domain}.sas
Location                     : {location}
Platform/SAS Version         : SAS 9.4
Description                  : Create SDTM {domain_label} dataset
Original Author              : {author}
Date                         : {date}
OUTPUT                       : {output}
Remarks                      :
--------------------------------------------------------------------------------
Modification History:

Rev#   Author             Date                Description
---- ----------------  --------------   ---------------------------------------
1      {author}        {date}           Generation
*****************************************************************************************************************/
'''
