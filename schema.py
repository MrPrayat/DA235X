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
        "\n- 'mentions_garage': true/false"
        "\n- 'mentions_källare': true/false"
        "\n- 'mentions_roof': true/false"
        "\n- 'mentions_balcony': true/false"
        "\n- 'mentions_bjälklag': true/false"
        "\n- 'mentions_fasad': true/false"
    ),

    "RenovationNeeds": (
        "An object where each key is a renovation area (e.g., roof, garage, facade, balcony, källare, bjälklag), "
        "and the value is either true (indicating renovation is clearly needed) or false (not mentioned or no issue found)."
    ),

    "AsbestosPresence": (
        "An object with the following keys: \n"
        "- 'Measured': true if explicitly measured or tested, otherwise false\n"
        "- 'presence': true if mentioned, false if explicitly ruled out"
    ),

    "RadonPresence": (
        "An object with the following keys: \n"
        "- 'Measured': true if a numeric radon value is given, otherwise false\n"
        "- 'presence': true if mentioned, false if explicitly ruled out"
    )
}