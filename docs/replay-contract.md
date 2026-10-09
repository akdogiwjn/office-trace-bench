# Trace packs and future recipe compilation

artifacts/suite.json selects one immutable canonical execution trace per formal
dataset. canonical.json binds the original run ID, ATIF and tool-events hashes,
input hashes, task/prompt/manifest/oracle hashes, complete frozen execution source,
Skill and context trees, actual model, runtime image ID, tool versions and verifier
reports. Its artifact_inventory resolves each logical file through the shared
artifacts/objects/sha256/ content-addressed store. Full runs/ directories remain
local and are not the publication interface. Validate with scripts/freeze_suite_index.py
--validate; no model or old sibling repository is needed to validate the evidence.

Canonical trajectory and tool_events are execution evidence, not executable recipes.
segmentation.json keeps all tool calls and heuristic labels; final_effective_selection
is explicitly unset until a dependency review establishes the correct slice. Raw
session JSONL, generated helper files, intermediate configurations/data, final outputs
and filesystem revision objects are retained. No unsuccessful run is promoted.

Artifact capture watches close-write/move events in the task workspace and selected
script/config/text/document/transformed-data extensions under /tmp, plus final workspace inventory. Rewritten
helper versions have distinct content hashes even if the path is reused. Event times
allow alignment with tool timestamps. Tool write/edit arguments also retain content.
This is not syscall read/exec provenance: extremely fast overwrite/delete races,
unsupported temporary-file types or files over the capture limit can leave gaps.
canonical.json reports these gaps; never silently infer that every historical helper
version was recovered. The retained content and command/result chain must be reviewed
before recipe promotion. Intermediate objects are evidence, not executable code to run
blindly during pack validation.

The final TLC v2 run additionally archives temporary workbook revisions through a
passive supplementary observer. Its manifest, start time, observer source hash,
logical /tmp root, file versions and gaps are separately bound in canonical.json.
It started mid-run, so earlier deleted/overwritten unsupported temporary versions
are explicitly not claimed as recovered. Earlier packs retain their narrower
original capture scopes; later compilation must respect each pack's limits.

Future recipe compilation will resolve working directories, symlinks, environment,
input and generated-file revisions, tool arguments/results, process lifetimes, dynamic
session handles, failures and exit codes. The schema is documented at
schemas/replay-recipe-v1.schema.json. Each recipe must select exactly one view:
agent_trajectory_tool_chain or final_effective_tool_execution. Both retain their
canonical parent trace hash and declared inclusions/exclusions. Full-chain adapters
must reproduce tool/process control semantics; logs alone are insufficient.

Preparation restores hash-verified artifacts and the frozen runtime. Execution follows
frozen argv/stdin/env and helper versions; it must not call an LLM, reason again,
regenerate a helper from natural language, download replacement data, or decide new
steps. Compilation itself also has no permission to call an LLM. Recipe validation
will verify dependencies and successful outputs independently before CPU/OS experiments.
No recipe, offline replay image or CPU/OS measurement is produced at this stage.
