FIELDS = [
    "CadastralDesignation",
    "InspectionDate",
    "MoistureDamage",
    "RenovationNeeds",
    "AsbestosPresence",
    "SummaryInsights"
]

FIELD_DEFINITIONS = {
    "CadastralDesignation": "The full legal name of the property, e.g., 'Stockholm Marevik 23'.\n"
    "If the name is not found, set to false",

    "InspectionDate": (
        "The year and month when the inspection was conducted, in format YYYY-MM.\n"
        "If the date is not found, set to false.\n"
    ),

    "MoistureDamage": (
        "An object indicating whether water-related issues were found in specific structural locations."
        "\nSet a field to true only if moi is clearly mentioned in that location."
        "\nOtherwise, set to false."
        "\n- 'mentions_garage': true/false"
        "\n- 'mentions_källare': true/false"
        "\n- 'mentions_roof': true/false"
        "\n- 'mentions_balcony': true/false"
        "\n- 'mentions_bjälklag': true/false"
        "\n- 'mentions_facade': true/false"
    ),

    "RenovationNeeds": (
        "An object where each key is a structural area (e.g., roof, garage, facade, balcony, källare, bjälklag)."
        "\nSet to true only if the report clearly recommends or plans renovation work for that area."
        "\nSet to false otherwise."
    ),

    "AsbestosPresence": (
        "An object with the following keys: \n"
        "- 'Measured': true if explicitly measured or tested, otherwise false\n"
        "- 'presence': true if mentioned to be present in the facility, false if explicitly ruled out or not mentioned"
    ),

    "SummaryInsights": (
        "A short freeform summary in Swedish (1–3 sentences) describing the most important issues and recommended actions.\n"
        "This should capture the high-level impression from the inspection report."
    )
} 
