# Combined expanded 0.9.0 laboratory dataset

This directory combines two verified sources by copying their manifests and
raw MCP proxy logs. The source datasets remain unchanged.

* `phase9_expanded_20261006`: 720 matched sessions (360 benign, 360 attacks;
  120 attacks per existing inert family), 16,878 MCP wire events.
* `benign_varied_090_expanded_20261006`: 634 benign sessions across 38 tasks,
  task-specific and all-server mounts, and three alternate description styles.
* Combined: 1,354 sessions (994 benign, 360 attack), 31,388 MCP wire events.
* Combined dataset SHA-256: `9ebcbb7d31a2445c6cccba0bbec3385749ded28d8998c103bb439b1f898ad1f2`.
* Composition verification: no problems; source hashes/counts are in
  `composition.json`.

The positive ML label is attack **attempted**. The manifest's attack-success
field describes the simulation's protocol/mock outcome, not real LLM influence.
All data were generated in the isolated Docker lab with the deterministic mock
agent. Raw logs should be treated as immutable.

Feature, model, and result artifacts for the combined experiment are in
`../expanded_20261006_ml/`, `../../models/expanded_20261006/`, and
`../../results/expanded_20261006/`. A separate class-balanced evaluation on
only the paired 720-session source is in `../../results/phase9_expanded_20261006/`.

To reproduce, use the commands documented in `docs/experiments.md` under
`exp_006_expanded_20261006`. Each generator refuses to overwrite a non-empty
output directory; use a fresh tag when repeating the collection.
