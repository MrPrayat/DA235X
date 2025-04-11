FIELDS = [
    "CadastralDesignation",
    "InspectionDate",
    "WaterLeakage",
    "RenovationNeeds",
    "AsbestosPresence",
    "SummaryInsights"
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
        "\n- 'mentions_facade': true/false"
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

    "SummaryInsights": (
        "A short freeform summary in Swedish (1–3 sentences) of the three most important maintenance or renovation actions recommended in the inspection report. "
        "If no major actions are recommended, summarize that as well. The tone should be neutral and helpful."
    )

}