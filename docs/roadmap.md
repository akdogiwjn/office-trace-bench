# Frozen suite roadmap

Scope remains XLSX TLC/Retail/Manufacturing/HR and PDF OPM/W-4/SBA 1919.
No extra domain is planned in this phase. The runtime image remains the existing
trace-generation environment; Agent/Skill/ATIF architecture stays in place.

First freeze inputs, actual provenance, shared task contracts, independent semantic
oracles and workbook-complexity metadata. Then independently verify source preservation,
run real Agents, accept successful traces and publish canonical evidence with complete
hash bindings. Test the repository in an independent checkout without a sibling project.
Current evidence and remaining source limitations are in native-input-update-v3.md.

Later, under a separate task, review helper revisions and dependencies, define both
full-tool-chain and final-effective slices, compile recipe-v1 without LLM calls, and
validate recipe execution in the frozen runtime. Only after this gate may offline
replay images and repeated CPU/OS experiments begin. Current suite.json keeps
replay_ready=false; successful trace generation alone never opens that gate.
