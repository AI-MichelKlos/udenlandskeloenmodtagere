# Udenlandske lønmodtagere i Danmark

Interaktivt dashboard for Danske A-kasser med udvikling og status for udenlandske statsborgere med lønindkomst i Danmark.

## Indhold

Dashboardet viser:

1. Månedlig tidsserie fra 2008 med antal udenlandske lønmodtagere og fuldtidsbeskæftigede.
2. Udenlandske fuldtidsbeskæftigedes andel af alle fuldtidsbeskæftigede lønmodtagere efter bopæl.
3. Top 25 individuelt opgjorte statsborgerskaber.
4. Branchefordeling med andel udenlandsk arbejdskraft.
5. Bopæl i Danmark sammenholdt med pendlere uden registreret dansk bopæl.
6. Fordeling og udvikling efter opholdsgrundlag.
7. Fordeling på de fem regioner efter arbejdssted.
8. Arbejdsmarkedsstatus over tid med andelen, der fortsat er i lønmodtagerbeskæftigelse efter 6, 12, 24, 36, 48 og 60 måneder.

## Datakilder

Primær kilde er Jobindsats.dk API v3 fra Styrelsen for Arbejdsmarked og Rekruttering.

- Udenlandske statsborgere med lønindkomst i Danmark, herunder bopælsstatus, opholdsgrundlag, statsborgerskab, branche og geografi.
- Antal lønmodtagere efter bopæl.
- Beskæftigede udenlandske statsborgeres arbejdsmarkedsstatus over tid.

Målingernes konkrete `table_id`, hierarkier og relevante levels identificeres fra Jobindsats-metadata ved hver kørsel. Hver ny serie har selvstændig kildestatus, så fejl ikke skjules af de øvrige serier.

## Automatisk drift

Workflowet `.github/workflows/update-dashboard.yml`:

- kan startes manuelt med `workflow_dispatch`,
- forsøger ugentlig opdatering mandag formiddag med flere backupforsøg,
- bruger dansk uge som lås, så højst én vellykket fuld opdatering gemmes pr. uge,
- validerer Python, datafil, alle påkrævede kilder og dashboardfiler,
- committer kun data og status, når der er ændringer.

## Metodiske noter

Bopælsstatus følger CPR-registreringen. Geografien i regionsvisningen er arbejdsstedets placering, ikke den ansattes bopæl. Opholdsgrundlag følger den registrerede kategori i Jobindsats. Retentionsmålingen følger beskæftigede udenlandske statsborgere frem i tid og er derfor en kohortemåling, ikke en almindelig tidsserie.
