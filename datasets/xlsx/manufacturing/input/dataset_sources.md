# manufacturing benchmark inputs

Official publisher: U.S. Census Bureau; frozen data obtained from FRED.
Source: https://fred.stlouisfed.org/graph/fredgraph.csv?id=AMTMVS,AMTMNO,AMTMUO,AMTMTI&cosd=2023-01-01&coed=2024-12-31

Only January 2023–December 2024 observations are selected from the downloaded history.
Raw_Data contains 100,000 SYNTHETIC workload shards, not observed establishments or transactions.
Integer-dollar partition: each observed amount split across deterministic synthetic shards; source totals preserved. Each source million-dollar observation is converted to dollars.
National total; six explicitly synthetic benchmark segments, not industry estimates. Never sum overlapping national/subsector totals.
Retail totals cover ONLY the six selected categories, not all U.S. retail. Manufacturing stock measures are shown for the latest month, not summed as annual flows.
Read template_manifest.json for provenance and dataset_manifest.json for required KPI references and scenario assumptions.
Preserve all existing sheets, raw rows, formulas, source values and both existing charts.
