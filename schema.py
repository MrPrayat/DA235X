FIELDS = [
    "CadastralDesignation",
    "InspectionDate",
    "WaterLeakage",
    "RenovationNeeds",
    "AsbestosPresence",
    "RadonPresence"
]

FIELD_DEFINITIONS = {
    "CadastralDesignation": "The full legal name of the property, e.g., 'Stockholm Marevik 23'.",
    "InspectionDate": (
        "The year and month when the inspection was conducted, in format YYYY-MM."
    ),
    "WaterLeakage": (
        "An object indicating whether water-related issues were found, and where."
        "\n- 'mentions_garage': true/false/null"
        "\n- 'mentions_källare': true/false/null"
        "\n- 'mentions_roof': true/false/null"
        "\n- 'mentions_balcony': true/false/null"
        "\n- 'mentions_bjälklag': true/false/null"
        "\n- 'mentions_fasad': true/false/null"
    ),
    "RenovationNeeds": (
        "An object where each key is a renovation area (e.g., roof, garage, facade, balcony, källare, bjälklag), "
        "and the value is either true (indicating renovation is clearly needed) or null (not mentioned or no issue found)."
    ),
    "AsbestosPresence": (
        "An object with the following keys: \n"
        "- 'Measured': true if explicitly measured or tested, otherwise false/null\n"
        "- 'presence': true if mentioned, false if explicitly ruled out, null otherwise"
    ),
    "RadonPresence": (
        "An object with the following keys: \n"
        "- 'Measured': true if a numeric radon value is given, otherwise false/null\n"
        "- 'presence': true if mentioned, false if explicitly ruled out, null otherwise\n"
        "- 'level': integer or null (e.g., 170 Bq/m3)"
    )
}
