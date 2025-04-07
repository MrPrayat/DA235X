FIELDS = [
    "CadastralDesignation",
    "PostalAddress",
    "WaterLeakage",
    "InspectionCompany",
    "InspectionDate",
    "LastRenovation",
    "RadonLevels",
    "RenovationNeeds"
]

FIELD_DEFINITIONS = {
    "CadastralDesignation": "The full legal property name (fastighetsbeteckning), including områdesnamn, blocknummer, and enhetsnummer. Example: 'Törnevalla Skäckelstad 2:7'.",
    "PostalAddress": "The full postal address, typically including street name, postal code, and city.",
    "WaterLeakage": "Any mention of water damage, smygläckage, or moisture issues.",
    "InspectionCompany": "The company that performed the inspection (e.g., Anticimex).",
    "InspectionDate": "The date the inspection was performed, format: YYYY-MM-DD.",
    "LastRenovation": "Description or date of the most recent renovation.",
    "RadonLevels": "Measured or described radon levels, or statements about radon presence.",
    "RenovationNeeds": "Indications that renovation is required or recommended.",
}
