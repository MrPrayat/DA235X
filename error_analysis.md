# Error Triage – baseline_v1 (2025-04-22)

## Problematiska fält
- RenovationNeeds
- InspectionDate
- CadastralDesignation

### CadastralDesignation
- [3626545]: Klassas som bilaga pga står "bilaga till besiktningsprotokoll"
- [3651738]: Klassas som bilaga pga står "bilaga till besiktningsprotokoll"
- [3652255]: Väldigt annorlunda layout, står dock under 'beteckning' och är 'Floåsen 13:57' så syntaxen är ej avvikande"

### InspectionDate
- [3626545]: Klassas som bilaga pga står "bilaga till besiktningsprotokoll"
- [3651738]: Klassas som bilaga pga står "bilaga till besiktningsprotokoll"
- [3654249]: Vet ej varför men den säger 2024-12 ist för 2024-11, det är en bilaga som sätter detta datum av någon anledning.

### RenovationNeeds.facade
- [3626545]: Klassas som bilaga pga står "bilaga till besiktningsprotokoll"
- [3651738]: Klassas som bilaga pga står "bilaga till besiktningsprotokoll"

## Generella observationer
- Av någon anledning så finns problem med cadastraldesignation och inspectionDate som sett bra ut tidigare. Misstänker något fel vid refactoring, ska utreda.
