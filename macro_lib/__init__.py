# SDTM GEN Macro Library Index
# References macros from knowledge base

MACRO_CATALOG = {
    # Date/Time Processing
    "date": {
        "file": "date.sas",
        "description": "Convert raw date string to ISO 8601 format (YYYY-MM-DD)",
        "usage": "%date(invar=raw_date, outvar=ISO_date)",
        "parameters": {
            "invar": "Input variable containing raw date",
            "outvar": "Output variable for formatted date"
        },
        "category": "date_processing"
    },
    "dtc": {
        "file": "dtc.sas",
        "description": "Parse partial dates with UN/UK handling",
        "usage": "%dtc(var=raw_date, outvar=parsed_date)",
        "category": "date_processing"
    },
    "dttm": {
        "file": "dttm.sas",
        "description": "Create numeric date, time, and datetime variables from DTC suffix",
        "usage": "%dttm(indsn=data, outdsn=data_out)",
        "category": "date_processing"
    },
    "imputedt": {
        "file": "imputedt.sas",
        "description": "Partial date imputation",
        "usage": "%imputedt(dsn=data, var=dtc)",
        "category": "date_processing"
    },
    "iso2sasdt": {
        "file": "iso2sasdt.sas",
        "description": "Convert ISO 8601 date to SAS date",
        "usage": "%iso2sasdt(dsn=data)",
        "category": "date_processing"
    },
    "maxdtc": {
        "file": "maxdtc.sas",
        "description": "Find maximum date from multiple DTC variables",
        "usage": "%maxdtc(dsn=data, vars=var1 var2 var3)",
        "category": "date_processing"
    },

    # Baseline Processing
    "ablfl": {
        "file": "ablfl.sas",
        "description": "Add baseline flag indicators to dataset",
        "usage": "%ablfl(dsn=lb, eval_dt=lbdt, relbas=lbblfl)",
        "parameters": {
            "dsn": "Dataset name",
            "eval_dt": "Evaluation date variable",
            "eval_tm": "Evaluation time variable (optional)",
            "relbas": "Output baseline flag variable"
        },
        "category": "baseline"
    },
    "baseflag": {
        "file": "baseflag.sas",
        "description": "Create baseline flag for BDS datasets",
        "usage": "%baseflag(dsn=vs, byvar=usubjid testcd)",
        "category": "baseline"
    },

    # Study Day
    "aactdy": {
        "file": "aactdy.sas",
        "description": "Calculate actual study day from reference date",
        "usage": "%aactdy(dsn=ae, refdt=rfstdtc, evtdt=aestdtc)",
        "category": "study_day"
    },
    "dy": {
        "file": "DY.sas",
        "description": "Simple study day calculation",
        "usage": "%dy(dsn=data, refdt=rfstdtc)",
        "category": "study_day"
    },

    # SUPP Processing
    "supp": {
        "file": "supp.sas",
        "description": "Create SUPP dataset from parent",
        "usage": "%supp(dsn=parent, vars=var1 var2)",
        "category": "supp"
    },
    "suppjoin": {
        "file": "suppjoin.sas",
        "description": "Join SUPP dataset back to parent",
        "usage": "%suppjoin(parent=ae, supp=suppae)",
        "category": "supp"
    },

    # Analysis
    "var_chg": {
        "file": "var_chg.sas",
        "description": "Calculate change and percent change variables",
        "usage": "%var_chg(dsn=data, fromvar=base, tovar=post)",
        "category": "analysis"
    },
    "param": {
        "file": "param.sas",
        "description": "Create PARAM/PARAMCD variables",
        "usage": "%param(dsn=lb)",
        "category": "analysis"
    },
    "add_trtp_trta": {
        "file": "add_trtp_trta.sas",
        "description": "Add planned/actual treatment variables",
        "usage": "%add_trtp_trta(dsn=adsl)",
        "category": "analysis"
    },

    # Reporting
    "tevents": {
        "file": "Tevents.sas",
        "description": "Event summary tables for AE/CM/PR/MH",
        "usage": "%tevents(MODE=summary, INSET=adae, POP=SAFFL, OUT=result)",
        "category": "reporting"
    },
    "tmeans": {
        "file": "Tmeans.sas",
        "description": "Means procedure results tables",
        "usage": "%tmeans(inset=adsl, pop=ITTFL, nVar=age)",
        "category": "reporting"
    },
    "tfreq": {
        "file": "Tfreq.sas",
        "description": "Frequency tables",
        "usage": "%tfreq(inset=adsl, pop=ITTFL, var=sex, out=result)",
        "category": "reporting"
    },
    "tmeans_bds": {
        "file": "Tmeans_BDS.sas",
        "description": "Lab tests/Vital signs MEANS tables for BDS structure",
        "usage": "%tmeans_bds(inset=adlb, pop=SAFFL)",
        "category": "reporting"
    },

    # Utility
    "step": {
        "file": "step.sas",
        "description": "Stepwise processing control",
        "category": "utility"
    },
    "existx": {
        "file": "existx.sas",
        "description": "Check if dataset/variable exists",
        "category": "utility"
    },
    "char_split_200": {
        "file": "char_split_200.sas",
        "description": "Split character variables >200 chars",
        "usage": "%char_split_200(dsn=data, var=longtext)",
        "category": "utility"
    },
    "coding": {
        "file": "coding.sas",
        "description": "Auto-coding for MedDRA/WHODrug",
        "category": "utility"
    },
}

MACRO_CATEGORIES = {
    "date_processing": "Date/Time Processing",
    "baseline": "Baseline Processing",
    "study_day": "Study Day Calculation",
    "supp": "SUPP Dataset Processing",
    "analysis": "Analysis Variables",
    "reporting": "Reporting Tables",
    "utility": "Utility Functions",
}

def get_macro_info(macro_name: str) -> dict:
    """Get macro information by name."""
    return MACRO_CATALOG.get(macro_name.lower())

def list_macros_by_category(category: str = None) -> list:
    """List all macros, optionally filtered by category."""
    if category:
        return [(k, v) for k, v in MACRO_CATALOG.items() if v.get("category") == category]
    return list(MACRO_CATALOG.items())

def get_required_macros(domain: str) -> list:
    """Get list of required macros for a domain."""
    domain_macro_map = {
        "AE": ["date", "aactdy"],
        "CM": ["date", "aactdy"],
        "LB": ["date", "ablfl", "aactdy"],
        "VS": ["date", "ablfl", "aactdy"],
        "DM": ["date"],
        "EX": ["date", "aactdy"],
        "MH": ["date", "aactdy"],
        "DS": ["date"],
        "SV": ["date"],
    }
    return domain_macro_map.get(domain.upper(), ["date"])
