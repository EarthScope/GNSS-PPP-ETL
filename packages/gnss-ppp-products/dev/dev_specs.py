parameter_spec_dict = [
    {
        "name": "SSSS",
        "pattern": "[A-Za-z0-9]{4}",
        "description": '4-character station code (e.g., "ALIC", "BRST")',
        "derivation": "enum",
    },
    {
        "name": "MONUMENT",
        "pattern": "[0-9]",
        "description": "1-character monument or marker number",
        "derivation": "enum",
    },
    {
        "name": "R",
        "pattern": "[0-9]{1}",
        "description": "Receiver number (0 if not specified)",
        "derivation": "enum",
    },
    {
        "name": "CCC",
        "pattern": "[A-Za-z0-9]{3}",
        "description": '3-character data center or agency code (e.g., "COD", "IGS", "JPL")',
        "derivation": "enum",
    },
    {
        "name": "SSSMRCCC_",
        "pattern": "[A-Z0-9]{9}_",
        "description": 'Optional station identifier block (e.g., "ALIC00MRC_", "BRST01MRC_")',
        "derivation": "enum",
    },
    {
        "name": "YYYY",
        "pattern": "\\d{4}",
        "description": '4-digit year (e.g., "2024")',
        "derivation": "computed",
    },
    {
        "name": "YY",
        "pattern": "\\d{2}",
        "description": '2-digit year (e.g., "24" for 2024)',
        "derivation": "computed",
    },
    {
        "name": "MONTH",
        "pattern": "\\d{2}",
        "description": "2-digit month (01–12)",
        "derivation": "computed",
    },
    {
        "name": "DAY",
        "pattern": "\\d{2}",
        "description": "2-digit day of month (01–31)",
        "derivation": "computed",
    },
    {
        "name": "DDD",
        "pattern": "\\d{3}",
        "description": "3-digit day of year (001–366)",
        "derivation": "computed",
    },
    {
        "name": "HH",
        "pattern": "\\d{2}",
        "description": "2-digit hour of day (00–23)",
        "derivation": "computed",
    },
    {
        "name": "MM",
        "pattern": "\\d{2}",
        "description": "2-digit minute of hour (00–59)",
        "derivation": "computed",
    },
    {
        "name": "VMFHH",
        "pattern": "H\\d{2}",
        "description": "VMF sub-daily hour tag (H00, H06, H12, H18)",
        "derivation": "enum",
    },
    {"name": "DDU", "pattern": "\\d{2}[DHMS]", "derivation": "enum"},
    {"name": "FRU", "pattern": "\\d{2}[DHMS]", "derivation": "enum"},
    {"name": "LEN", "pattern": "\\d{2}[DHMS]", "derivation": "enum"},
    {"name": "SMP", "pattern": "\\d{2}[DHMS]", "derivation": "enum"},
    {"name": "AAA", "pattern": "[a-zA-Z0-9]{3}", "derivation": "enum"},
    {"name": "V", "pattern": "[0-9]", "derivation": "enum"},
    {"name": "PPP", "pattern": "[A-Z0-9]{3}", "derivation": "enum"},
    {"name": "TTT", "pattern": "[A-Z]{3}", "derivation": "enum"},
    {"name": "CNT", "pattern": "[A-Z]{3}", "derivation": "enum"},
    {"name": "FMT", "pattern": "[A-Z0-9]{3}", "derivation": "enum"},
    {"name": "S", "pattern": "[A-Z]", "derivation": "enum"},
    {"name": "D", "pattern": "[A-Z]", "derivation": "enum"},
    {"name": "T", "pattern": "[a-zA-Z]", "derivation": "enum"},
    {"name": "PRODUCT", "pattern": "[A-Za-z0-9]+", "derivation": "enum"},
    {"name": "RESOLUTION", "pattern": "[0-9x.]+", "derivation": "enum"},
    {
        "name": "GPSWEEK",
        "pattern": "\\d{4}",
        "description": "GPS week number since January 6, 1980",
        "derivation": "computed",
    },
    {"name": "REFFRAME", "pattern": "igs[0-9A-Z]{2}", "derivation": "computed"},
    {
        "name": "INSTRUMENT",
        "pattern": "[A-Z]{3}1B",
        "description": "LEO instrument code with level suffix (e.g., GNV1B, ACC1B)",
        "derivation": "enum",
    },
    {
        "name": "SPACECRAFT",
        "pattern": "[CD]",
        "description": "Spacecraft identifier (C or D for GRACE/GRACE-FO)",
        "derivation": "enum",
    },
    {
        "name": "RELNUM",
        "pattern": "\\d+\\..*",
        "description": "Release/version number followed by file extension",
        "derivation": "enum",
    },
]

format_spec_dict = {
    "RINEX": {
        "name": "RINEX",
        "versions": {
            "2": {
                "name": "2",
                "variants": {
                    "observation": {
                        "name": "RINEX",
                        "version": "2",
                        "variant": "observation",
                        "parameters": [
                            {"name": "SSSS", "description": "4 char station code"},
                            {"name": "DDD", "description": "day of year (001-366)"},
                            {"name": "YY", "description": "2 digit year"},
                            {"name": "T", "description": "file type code"},
                        ],
                        "filename": "{SSSS}{DDD}0.{YY}{T}",
                    },
                    "navigation": {
                        "name": "RINEX",
                        "version": "2",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "DDD"},
                            {"name": "YY"},
                            {"name": "T"},
                        ],
                        "filename": "{SSSS}{DDD}0.{YY}{T}",
                    },
                    "meteorological": {
                        "name": "RINEX",
                        "version": "2",
                        "variant": "meteorological",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "DDD"},
                            {"name": "YY"},
                        ],
                        "filename": "{SSSS}{DDD}0.{YY}m",
                    },
                },
            },
            "3": {
                "name": "3",
                "variants": {
                    "observation": {
                        "name": "RINEX",
                        "version": "3",
                        "variant": "observation",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "MONUMENT"},
                            {"name": "R"},
                            {"name": "CCC"},
                            {"name": "S"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "DDU"},
                            {"name": "FRU"},
                            {"name": "D"},
                        ],
                        "filename": "{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{FRU}_{D}O.rnx",
                    },
                    "navigation": {
                        "name": "RINEX",
                        "version": "3",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "MONUMENT"},
                            {"name": "R"},
                            {"name": "CCC"},
                            {"name": "S"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "DDU"},
                            {"name": "D"},
                        ],
                        "filename": "{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{D}N.rnx",
                    },
                    "meteorological": {
                        "name": "RINEX",
                        "version": "3",
                        "variant": "meteorological",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "MONUMENT"},
                            {"name": "R"},
                            {"name": "CCC"},
                            {"name": "S"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "DDU"},
                            {"name": "D"},
                        ],
                        "filename": "{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{D}M.rnx",
                    },
                },
            },
            "4": {
                "name": "4",
                "variants": {
                    "observation": {
                        "name": "RINEX",
                        "version": "4",
                        "variant": "observation",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "MONUMENT"},
                            {"name": "R"},
                            {"name": "CCC"},
                            {"name": "S"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "DDU"},
                            {"name": "FRU"},
                            {"name": "D"},
                        ],
                        "filename": "{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{FRU}_{D}O.rnx",
                    },
                    "navigation": {
                        "name": "RINEX",
                        "version": "4",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "MONUMENT"},
                            {"name": "R"},
                            {"name": "CCC"},
                            {"name": "S"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "DDU"},
                            {"name": "D"},
                        ],
                        "filename": "{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{D}N.rnx",
                    },
                    "meteorological": {
                        "name": "RINEX",
                        "version": "4",
                        "variant": "meteorological",
                        "parameters": [
                            {"name": "SSSS"},
                            {"name": "MONUMENT"},
                            {"name": "R"},
                            {"name": "CCC"},
                            {"name": "S"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "DDU"},
                            {"name": "D"},
                        ],
                        "filename": "{SSSS}{MONUMENT}{R}{CCC}_{S}_{YYYY}{DDD}{HH}{MM}_{DDU}_{D}M.rnx",
                    },
                },
            },
        },
    },
    "PRODUCT": {
        "name": "PRODUCT",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "AAA"},
                            {"name": "V"},
                            {"name": "PPP"},
                            {"name": "TTT"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "LEN"},
                            {"name": "SMP"},
                            {"name": "CNT"},
                            {"name": "FMT"},
                        ],
                        "filename": "{AAA}{V}{PPP}{TTT}_{YYYY}{DDD}{HH}{MM}_{LEN}_{SMP}_{CNT}.{FMT}.*",
                    },
                    "station": {
                        "name": "PRODUCT",
                        "version": "1",
                        "variant": "station",
                        "parameters": [
                            {"name": "AAA"},
                            {"name": "V"},
                            {"name": "PPP"},
                            {"name": "TTT"},
                            {"name": "YYYY"},
                            {"name": "DDD"},
                            {"name": "HH"},
                            {"name": "MM"},
                            {"name": "LEN"},
                            {"name": "SMP"},
                            {"name": "SSSMRCCC_"},
                            {"name": "CNT"},
                            {"name": "FMT"},
                        ],
                        "filename": "{AAA}{V}{PPP}{TTT}_{YYYY}{DDD}{HH}{MM}_{LEN}_{SMP}_{SSSMRCCC_}_{CNT}.{FMT}.*",
                    },
                },
            },
        },
    },
    "TABLE": {
        "name": "TABLE",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "TABLE",
                        "version": "1",
                        "variant": "default",
                        "parameters": [],
                        "filename": "",
                    },
                },
            },
        },
    },
    "VIENNA_MAPPING_FUNCTIONS": {
        "name": "VIENNA_MAPPING_FUNCTIONS",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "VIENNA_MAPPING_FUNCTIONS",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "PRODUCT"},
                            {"name": "YYYY"},
                            {"name": "MONTH"},
                            {"name": "DAY"},
                            {"name": "VMFHH", "pattern": "H(?:00|06|12|18)"},
                        ],
                        "filename": "{PRODUCT}_{YYYY}{MONTH}{DAY}.{VMFHH}",
                    },
                    "orography": {
                        "name": "VIENNA_MAPPING_FUNCTIONS",
                        "version": "1",
                        "variant": "orography",
                        "parameters": [
                            {
                                "name": "RESOLUTION",
                                "pattern": "\\b(2\\.5x2|1x1|5x5)\\b",
                            }
                        ],
                        "filename": "orography_ell_{RESOLUTION}",
                    },
                },
            },
        },
    },
    "LEO_L1B": {
        "name": "LEO_L1B",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "LEO_L1B",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "INSTRUMENT"},
                            {"name": "YYYY"},
                            {"name": "MONTH"},
                            {"name": "DAY"},
                            {"name": "SPACECRAFT", "pattern": "[CD]"},
                            {"name": "RELNUM", "pattern": "\\d+\\..*"},
                        ],
                        "filename": "{INSTRUMENT}_{YYYY}-{MONTH}-{DAY}_{SPACECRAFT}_{RELNUM}",
                    },
                },
            },
        },
    },
    "ANTENNAE": {
        "name": "ANTENNAE",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "ANTENNAE",
                        "version": "1",
                        "variant": "default",
                        "parameters": [{"name": "REFFRAME"}],
                        "filename": "{REFFRAME}.atx",
                    },
                    "archive": {
                        "name": "ANTENNAE",
                        "version": "1",
                        "variant": "archive",
                        "parameters": [{"name": "REFFRAME"}, {"name": "GPSWEEK"}],
                        "filename": "{REFFRAME}_{GPSWEEK}.atx",
                    },
                },
            },
        },
    },
}

product_spec_dict = {
    # ── RINEX_OBS ──────────────────────────────────────────────────
    "RINEX_OBS": {
        "name": "RINEX_OBS",
        "versions": {
            "2": {
                "name": "2",
                "variants": {
                    "observation": {
                        "name": "RINEX_OBS",
                        "format": "RINEX",
                        "version": "2",
                        "variant": "observation",
                        "parameters": [
                            {"name": "T", "pattern": "\\b[dot]\\b"},
                        ],
                    },
                },
            },
            "3": {
                "name": "3",
                "variants": {
                    "observation": {
                        "name": "RINEX_OBS",
                        "format": "RINEX",
                        "version": "3",
                        "variant": "observation",
                        "parameters": [
                            {"name": "T", "pattern": "\\b[ONM]\\b"},
                            {"name": "D", "pattern": "\\b[GRECEJSM]\\b"},
                        ],
                    },
                },
            },
            "4": {
                "name": "4",
                "variants": {
                    "observation": {
                        "name": "RINEX_OBS",
                        "format": "RINEX",
                        "version": "4",
                        "variant": "observation",
                        "parameters": [
                            {"name": "T", "pattern": "\\b[ONM]\\b"},
                            {"name": "D", "pattern": "\\b[GRECEJSM]\\b"},
                        ],
                    },
                },
            },
        },
    },
    # ── RINEX_NAV ──────────────────────────────────────────────────
    "RINEX_NAV": {
        "name": "RINEX_NAV",
        "versions": {
            "2": {
                "name": "2",
                "variants": {
                    "navigation": {
                        "name": "RINEX_NAV",
                        "format": "RINEX",
                        "version": "2",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "T", "pattern": "\\b[ngh]\\b"},
                        ],
                    },
                },
            },
            "3": {
                "name": "3",
                "variants": {
                    "navigation": {
                        "name": "RINEX_NAV",
                        "format": "RINEX",
                        "version": "3",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "T", "pattern": "\\b[ON]\\b"},
                            {"name": "D", "pattern": "\\b[GRECEJSM]\\b"},
                        ],
                    },
                },
            },
            "4": {
                "name": "4",
                "variants": {
                    "navigation": {
                        "name": "RINEX_NAV",
                        "format": "RINEX",
                        "version": "4",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "T", "pattern": "\\b[ON]\\b"},
                            {"name": "D", "pattern": "\\b[GRECEJSM]\\b"},
                        ],
                    },
                },
            },
        },
    },
    # ── RINEX_MET ──────────────────────────────────────────────────
    "RINEX_MET": {
        "name": "RINEX_MET",
        "versions": {
            "2": {
                "name": "2",
                "variants": {
                    "meteorological": {
                        "name": "RINEX_MET",
                        "format": "RINEX",
                        "version": "2",
                        "variant": "meteorological",
                        "parameters": [
                            {"name": "T", "value": "m"},
                        ],
                    },
                },
            },
            "3": {
                "name": "3",
                "variants": {
                    "meteorological": {
                        "name": "RINEX_MET",
                        "format": "RINEX",
                        "version": "3",
                        "variant": "meteorological",
                        "parameters": [
                            {"name": "T", "value": "M"},
                            {"name": "D", "pattern": "\\b[GRECEJSM]\\b"},
                        ],
                    },
                },
            },
            "4": {
                "name": "4",
                "variants": {
                    "meteorological": {
                        "name": "RINEX_MET",
                        "format": "RINEX",
                        "version": "4",
                        "variant": "meteorological",
                        "parameters": [
                            {"name": "T", "value": "M"},
                            {"name": "D", "pattern": "\\b[GRECEJSM]\\b"},
                        ],
                    },
                },
            },
        },
    },
    # ── ORBIT ──────────────────────────────────────────────────────
    "ORBIT": {
        "name": "ORBIT",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "ORBIT",
                        "format": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "LEN", "value": "01D"},
                            {"name": "CNT", "value": "ORB"},
                            {"name": "FMT", "value": "SP3"},
                        ],
                    },
                },
            },
        },
    },
    # ── CLOCK ──────────────────────────────────────────────────────
    "CLOCK": {
        "name": "CLOCK",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "CLOCK",
                        "format": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "FMT", "value": "CLK"},
                            {"name": "LEN", "value": "01D"},
                            {"name": "CNT", "value": "CLK"},
                        ],
                    },
                },
            },
        },
    },
    # ── ERP ────────────────────────────────────────────────────────
    "ERP": {
        "name": "ERP",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "ERP",
                        "format": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "FMT", "value": "ERP"},
                            {"name": "LEN", "value": "01D"},
                            {"name": "CNT", "value": "ERP"},
                            {"name": "SMP", "value": "01D"},
                        ],
                    },
                },
            },
        },
    },
    # ── BIA ────────────────────────────────────────────────────────
    "BIA": {
        "name": "BIA",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "BIA",
                        "format": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "FMT", "value": "BIA"},
                            {"name": "LEN", "value": "01D"},
                            {"name": "CNT", "value": "OSB"},
                        ],
                    },
                },
            },
        },
    },
    # ── ATTOBX ─────────────────────────────────────────────────────
    "ATTOBX": {
        "name": "ATTOBX",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "ATTOBX",
                        "format": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "FMT", "value": "OBX"},
                            {"name": "LEN", "value": "01D"},
                            {"name": "CNT", "value": "ATT"},
                            {"name": "SMP", "value": "30S"},
                        ],
                    },
                },
            },
        },
    },
    # ── IONEX ──────────────────────────────────────────────────────
    "IONEX": {
        "name": "IONEX",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "IONEX",
                        "format": "PRODUCT",
                        "version": "1",
                        "variant": "default",
                        "parameters": [
                            {"name": "FMT", "value": "INX"},
                            {"name": "LEN", "value": "01D"},
                            {"name": "CNT", "value": "GIM"},
                        ],
                    },
                },
            },
        },
    },
    # ── RNX3_BRDC ──────────────────────────────────────────────────
    "RNX3_BRDC": {
        "name": "RNX3_BRDC",
        "versions": {
            "3": {
                "name": "3",
                "variants": {
                    "navigation": {
                        "name": "RNX3_BRDC",
                        "format": "RINEX",
                        "version": "3",
                        "variant": "navigation",
                        "parameters": [
                            {"name": "SSSS", "value": "BRDC"},
                            {"name": "DDU", "value": "01D"},
                            {"name": "S", "value": "R"},
                        ],
                    },
                },
            },
        },
    },
    # ── LEAP_SEC ───────────────────────────────────────────────────
    "LEAP_SEC": {
        "name": "LEAP_SEC",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "LEAP_SEC",
                        "format": "TABLE",
                        "version": "1",
                        "variant": "default",
                        "parameters": [],
                        "filename": "leap.sec",
                    },
                },
            },
        },
    },
    # ── SAT_PARAMS ─────────────────────────────────────────────────
    "SAT_PARAMS": {
        "name": "SAT_PARAMS",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "SAT_PARAMS",
                        "format": "TABLE",
                        "version": "1",
                        "variant": "default",
                        "parameters": [],
                        "filename": "sat_parameters",
                    },
                },
            },
        },
    },
    # ── VMF ────────────────────────────────────────────────────────
    "VMF": {
        "name": "VMF",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "VMF",
                        "format": "VIENNA_MAPPING_FUNCTIONS",
                        "version": "1",
                        "variant": "default",
                        "parameters": [],
                    },
                },
            },
        },
    },
    # ── OROGRAPHY ──────────────────────────────────────────────────
    "OROGRAPHY": {
        "name": "OROGRAPHY",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "orography": {
                        "name": "OROGRAPHY",
                        "format": "VIENNA_MAPPING_FUNCTIONS",
                        "version": "1",
                        "variant": "orography",
                        "parameters": [
                            {"name": "RESOLUTION", "value": "5x5"},
                        ],
                    },
                },
            },
        },
    },
    # ── LEO_L1B ────────────────────────────────────────────────────
    "LEO_L1B": {
        "name": "LEO_L1B",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "LEO_L1B",
                        "format": "LEO_L1B",
                        "version": "1",
                        "variant": "default",
                        "parameters": [],
                    },
                },
            },
        },
    },
    # ── ATTATX ─────────────────────────────────────────────────────
    "ATTATX": {
        "name": "ATTATX",
        "versions": {
            "1": {
                "name": "1",
                "variants": {
                    "default": {
                        "name": "ATTATX",
                        "format": "ANTENNAE",
                        "version": "1",
                        "variant": "default",
                        "parameters": [],
                    },
                    "archive": {
                        "name": "ATTATX",
                        "format": "ANTENNAE",
                        "version": "1",
                        "variant": "archive",
                        "parameters": [],
                    },
                },
            },
        },
    },
}

local_resource_spec_dict = {
    "products": {
        "directory": "{YYYY}/{DDD}/products",
        "temporal": "daily",
        "description": "Precise orbit, clock, ERP, bias, and attitude products",
        "specs": ["ORBIT", "CLOCK", "ERP", "BIA", "ATTOBX"],
    },
    "rinex": {
        "directory": "{YYYY}/{DDD}/rinex",
        "temporal": "daily",
        "description": "RINEX observation files for PPP processing",
        "specs": ["RNX3_BRDC", "RINEX_NAV", "RINEX_MET", "RINEX_OBS"],
    },
    "common": {
        "directory": "{YYYY}/{DDD}/common",
        "temporal": "daily",
        "description": "Broadcast navigation, ionosphere maps, and troposphere grids",
        "specs": ["IONEX", "VMF"],
    },
    "table": {
        "directory": "table",
        "temporal": "static",
        "description": "Reference tables, antenna calibrations, and orography grids",
        "specs": ["ATTATX", "LEAP_SEC", "SAT_PARAMS", "OROGRAPHY"],
    },
    "leo": {
        "directory": "{YYYY}/{DDD}/leo",
        "temporal": "daily",
        "description": "LEO satellite Level-1B instrument data (GRACE, GRACE-FO)",
        "specs": ["LEO_L1B"],
    },
}
wuhan_resource_spec_dict = {
    "id": "WUM",
    "name": "Wuhan University GNSS Research Center",
    "website": "http://www.igs.gnsswhu.cn/",
    "servers": [
        {
            "id": "wuhan_ftp",
            "name": "Primary FTP",
            "hostname": "ftp://igs.gnsswhu.cn",
            "protocol": "ftp",
            "auth_required": False,
            "notes": "Primary FTP server, no authentication required",
        }
    ],
    "products": [
        {
            "id": "wuhan_orbit",
            "product_name": "ORBIT",
            "server_id": "wuhan_ftp",
            "available": True,
            "description": "Precise satellite orbits",
            "parameters": [
                {"name": "AAA", "value": "WUM"},
                {"name": "AAA", "value": "WMC"},
                {"name": "TTT", "value": "FIN"},
                {"name": "TTT", "value": "RAP"},
                {"name": "PPP", "value": "MGX"},
                {"name": "PPP", "value": "DEM"},
                {"name": "SMP", "value": "05M"},
                {"name": "SMP", "value": "15M"},
            ],
            "directory": {"pattern": "pub/whu/phasebias/{YYYY}/orbit/"},
        },
        {
            "id": "wuhan_clock",
            "product_name": "CLOCK",
            "server_id": "wuhan_ftp",
            "available": True,
            "description": "Precise satellite and station clocks",
            "parameters": [
                {"name": "AAA", "value": "WUM"},
                {"name": "AAA", "value": "WMC"},
                {"name": "TTT", "value": "FIN"},
                {"name": "TTT", "value": "RAP"},
                {"name": "PPP", "value": "MGX"},
                {"name": "PPP", "value": "DEM"},
                {"name": "SMP", "value": "30S"},
                {"name": "SMP", "value": "05M"},
            ],
            "directory": {"pattern": "pub/whu/phasebias/{YYYY}/clock/"},
        },
    ],
}


igs_resource_spec_dict = {
    "id": "IGS",
    "name": "International GNSS Service",
    "website": "https://igs.org/",
    "servers": [
        {
            "id": "igs_cddis_ftp",
            "hostname": "ftps://gdc.cddis.eosdis.nasa.gov",
            "protocol": "ftps",
            "auth_required": True,
            "description": "CDDIS archive (NASA Earthdata login required)",
        }
    ],
    "products": [
        {
            "id": "igs_orbit",
            "product_name": "ORBIT",
            "server_id": "igs_cddis_ftp",
            "available": True,
            "description": "IGS combined final orbits",
            "parameters": [
                {"name": "AAA", "value": "IGS"},
                {"name": "TTT", "value": "FIN"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "15M"},
            ],
            "directory": {"pattern": "pub/gnss/products/{GPSWEEK}/"},
        },
        {
            "id": "igs_clock",
            "product_name": "CLOCK",
            "server_id": "igs_cddis_ftp",
            "available": True,
            "description": "IGS combined final clocks",
            "parameters": [
                {"name": "AAA", "value": "IGS"},
                {"name": "TTT", "value": "FIN"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "30S"},
            ],
            "directory": {"pattern": "pub/gnss/products/{GPSWEEK}/"},
        },
        {
            "id": "igs_erp",
            "product_name": "ERP",
            "server_id": "igs_cddis_ftp",
            "available": True,
            "description": "IGS combined Earth rotation parameters",
            "parameters": [
                {"name": "AAA", "value": "IGS"},
                {"name": "TTT", "value": "FIN"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "01D"},
            ],
            "directory": {"pattern": "pub/gnss/products/{GPSWEEK}/"},
        },
        {
            "id": "igs_attatx",
            "product_name": "ATTATX",
            "server_id": "igs_cddis_ftp",
            "available": True,
            "description": "IGS antenna phase center model",
            "parameters": [
                {"name": "REFFRAME", "value": "igs20"},
            ],
            "directory": {"pattern": "pub/gnss/products/"},
        },
    ],
}

code_resource_spec_dict = {
    "id": "COD",
    "name": "Center for Orbit Determination in Europe",
    "website": "http://www.aiub.unibe.ch/",
    "servers": [
        {
            "id": "code_ftp",
            "hostname": "ftp://ftp.aiub.unibe.ch",
            "protocol": "ftp",
            "auth_required": False,
            "description": "CODE FTP server at University of Bern",
        }
    ],
    "products": [
        {
            "id": "code_orbit",
            "product_name": "ORBIT",
            "server_id": "code_ftp",
            "available": True,
            "description": "CODE precise orbits",
            "parameters": [
                {"name": "AAA", "value": "COD"},
                {"name": "TTT", "value": "FIN"},
                {"name": "TTT", "value": "RAP"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "05M"},
            ],
            "directory": {"pattern": "CODE/{YYYY}/"},
        },
        {
            "id": "code_clock",
            "product_name": "CLOCK",
            "server_id": "code_ftp",
            "available": True,
            "description": "CODE precise clocks",
            "parameters": [
                {"name": "AAA", "value": "COD"},
                {"name": "TTT", "value": "FIN"},
                {"name": "TTT", "value": "RAP"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "30S"},
                {"name": "SMP", "value": "05M"},
            ],
            "directory": {"pattern": "CODE/{YYYY}/"},
        },
        {
            "id": "code_bia",
            "product_name": "BIA",
            "server_id": "code_ftp",
            "available": True,
            "description": "CODE observation-specific biases",
            "parameters": [
                {"name": "AAA", "value": "COD"},
                {"name": "TTT", "value": "FIN"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "01D"},
            ],
            "directory": {"pattern": "CODE/{YYYY}/"},
        },
        {
            "id": "code_ionex",
            "product_name": "IONEX",
            "server_id": "code_ftp",
            "available": True,
            "description": "CODE global ionosphere maps",
            "parameters": [
                {"name": "AAA", "value": "COD"},
                {"name": "TTT", "value": "FIN"},
                {"name": "TTT", "value": "RAP"},
                {"name": "PPP", "value": "OPS"},
                {"name": "SMP", "value": "02H"},
            ],
            "directory": {"pattern": "CODE/{YYYY}/"},
        },
    ],
}
