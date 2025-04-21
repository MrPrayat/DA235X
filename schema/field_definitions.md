# 📑 Field Definitions

This document outlines the fields we extract from Swedish housing inspection reports, their meaning, expected JSON format, and explicit boolean semantics for key object‑type fields.

---

## Fields and Descriptions

### `CadastralDesignation`

The full legal name of the property, e.g., “Stockholm Marevik 23”.

### `InspectionDate`

The date the inspection was conducted, in format **YYYY-MM** (year and month only).

### `MoistureDamage`

Object indicating whether water‑related issues appear in specific locations.

**Keys:**

- `mentions_garage`
- `mentions_källare`
- `mentions_roof`
- `mentions_balcony`
- `mentions_bjälklag`
- `mentions_fasad`

**Boolean semantics:**

- **Default**: all keys are `false` unless evidence is found.
- Set a location key to `true` only if the report explicitly mentions water damage, leaks, moisture ingress, or similar terms in that area.
- Leave `false` if the area is not mentioned or explicitly described as dry/without issues.

### `RenovationNeeds`

Object indicating whether renovation work is needed in each area.

**Keys:**

- `roof`
- `garage`
- `facade`
- `balcony`
- `källare`
- `bjälklag`

**Boolean semantics:**

- **Default**: all keys are `false` unless a clear need is stated.
- Set to `true` only when the text contains direct statements like “bör åtgärdas”, “i dåligt skick”, “slitage”, or scheduled/planned renovation for that area.
- If the area is mentioned but noted as in good order, or is not mentioned, keep `false`.

### `AsbestosPresence`

Object describing asbestos mentions.

- `Measured`: `true` if a measurement or test for asbestos is explicitly described; otherwise `false`.
- `presence`: `true` if asbestos is mentioned anywhere; `false` if no mention.

### `SummaryInsights`

Free‑text summary (1–2 sentences) of the most important actionable renovation items.\
Set to `null` if no clear actions are described.

---

## Example Output

```json
{
  "pdf_id": "1234567",
  "model_output": {
    "CadastralDesignation": "Stockholm Marevik 23",
    "InspectionDate": "2021-05",
    "MoistureDamage": {
      "mentions_garage": false,
      "mentions_källare": true,
      "mentions_roof": false,
      "mentions_balcony": false,
      "mentions_bjälklag": false,
      "mentions_fasad": true
    },
    "RenovationNeeds": {
      "roof": false,
      "garage": true,
      "facade": true,
      "balcony": false,
      "källare": false,
      "bjälklag": false
    },
    "AsbestosPresence": {
      "Measured": false,
      "presence": false
    },
    "SummaryInsights": "Inga större åtgärder krävs för fasad och garage."
  },
  "ground_truth": {
    ...
  }
}
```

