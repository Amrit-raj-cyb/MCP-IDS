# Incomplete Phase 9 capture — do not use

This directory contains the preserved output of an initial 56-session
generation attempt. All sessions completed at the agent level, but dataset
verification correctly rejected the capture: multiple six-server sessions
were missing proxy shutdown lifecycle events. The raw JSONL and manifest have
been retained unchanged for diagnosis.

Use the verified dataset in `data/phase9_verified/` instead. The Phase 9
generator now selects task-sized matched scenarios whose proxy lifecycle
records pass verification. Six-server `all_servers` scenarios remain a known
limitation until their proxy shutdown behavior is fixed.
