# Udenlandske lønmodtagere i Danmark

Interaktivt dashboard for Danske A-kasser med udvikling og status for udenlandske statsborgere med lønindkomst i Danmark.

## Indhold

Dashboardet viser:

1. Månedlig tidsserie fra 2008 med antal udenlandske lønmodtagere og fuldtidsbeskæftigede.
2. Udenlandske fuldtidsbeskæftigedes andel af alle fuldtidsbeskæftigede lønmodtagere efter bopæl.
3. Top 25 individuelt opgjorte statsborgerskaber, mens resten samles som "Øvrige lande".
4. Branchefordeling på den API-gruppering, der bedst matcher 10-grupperingen, med andel udenlandsk arbejdskraft og absolutte tal i tooltip.

## Datakilder

Primær kilde er Jobindsats.dk API v3 fra Styrelsen for Arbejdsmarked og Rekruttering.

- Udenlandske statsborgere med lønindkomst i Danmark, opholdsgrundlag, statsborgerskab og branche.
- Antal lønmodtagere efter bopæl.

Målingernes konkrete `table_id`, hierarkier og relevante levels identificeres automatisk fra Jobindsats-metadata ved hver kørsel. Det reducerer risikoen for, at dashboardet bryder, hvis STAR ændrer tabelkoder eller level-id'er.

## Automatisk drift

Workflowet `.github/workflows/update-dashboard.yml`:

- kan startes manuelt med `workflow_dispatch`,
- forsøger ugentlig opdatering mandag formiddag med flere backupforsøg,
- bruger dansk uge som lås, så højst én vellykket fuld opdatering gemmes pr. uge,
- validerer Python, datafil, kilde-status og dashboardfiler,
- committer kun data og status, når der er ændringer.

## Engangsopsætning

Der er to GitHub-indstillinger, som ikke kan oprettes via den anvendte connector:

1. Opret repository-secretet `API_ADGANG` med dit Jobindsats API-token.
2. Aktivér GitHub Pages for repositoryet med `main` som kilde og `/ (root)` som mappe.

Når det er gjort, kør workflowet manuelt én gang. Den forventede Pages-adresse er:

`https://ai-michelklos.github.io/udenlandskeloenmodtagere/`

## Metodisk note

Den specificerede denominator er målingen "Antal lønmodtagere efter bopæl". Den udenlandske serie kan også omfatte udenlandske statsborgere uden registreret bopæl i Danmark. Dashboardet viser derfor et tydeligt metodeforbehold ved de beregnede andele.

Jobindsats kan desuden samle en del af tredjelandene i en restkategori. Hvis API'et ikke leverer alle nationaliteter enkeltvis, ændres KPI-teksten automatisk til "Individuelt opgjorte nationaliteter" i stedet for at vise et fejlagtigt eksakt antal nationaliteter.
