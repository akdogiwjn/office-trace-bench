# Research scope and interpretation

The frozen suite contains four spreadsheet workloads and three form workloads.
Its purpose is Agent trajectory characterization, tool workload characterization,
and later CPU/OS characterization through fixed tool execution without an LLM.
It is not a spreadsheet accuracy leaderboard, an Office application leaderboard,
an industry-controlled comparison, or a fully open-ended Agent benchmark.
Semantic correctness is an acceptance gate for collecting valid tool workloads.

TLC is a benchmark-generated spreadsheet containing sampled real trip records and
full-population summary tables. It is not a native TLC-published XLSX. Retail and M3
are frozen official statistical tables transcribed without row expansion because
native XLSX downloads were denied. HR is an unmodified cached native occupation-level
OEWS spreadsheet, including all original sheets and aggregate/detail hierarchies.
The cache has partial primary-source corroboration; official byte identity is unknown.
These are different spreadsheet forms, not equivalent observations from four industries.
PDF forms use fixed revisions and reproducible fictional records.

Workbook size, serialized and populated cell counts, sheet layout, formula graph,
charts, styles, merged regions, compression and shared strings are workload properties.
Input complexity is recorded in datasets/xlsx/*/complexity.json and is not injected
into the task prompt. Per-sheet maximum row/column coordinates are not record counts;
style-only cells and empty formatting regions must not be counted as real observations.
There is no common 100k x 16 structural constraint and no artificial size matching.

A CPU/memory/I/O difference between two traces can arise from input complexity,
chosen helper algorithms, library and runtime versions, chart/rendering work, failed
attempts and caching. It cannot establish that an industry is inherently heavier.
Do not infer CPU rankings from Agent wall time or tool-call counts. Later studies
must bind exact trace hashes and execution views, hold runtime and cache conditions
constant where appropriate, repeat measurements, and report input complexity alongside
results. Normalizing by cells or bytes is an optional analysis choice, not proof of
an industry-controlled experiment. This stage runs correctness regressions only.

The full Agent tool chain includes inspection, debugging, failures, rewritten helpers,
retries, process controls, and verification. Final effective execution selects the
successful dependency chain that produces accepted deliverables. Those views answer
different research questions and must have distinct recipe IDs and reported scopes.
LLM inference time is outside future deterministic tool replay. Running a new Agent
session is trace generation, never replay of an existing trace.
