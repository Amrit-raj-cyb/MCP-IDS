# Using a real LLM (Claude API): setup, cost, and when to use it

## 1. Do you need it at all?

**Not for most of the project.** The mock brain is free, offline and
reproducible, and it generates the main dataset. The IDS learns from MCP
*traffic*, and the mock produces real MCP traffic.

You need a real model for **one research question**: *does a given injection
actually change an AI model's behaviour?* That's the `attack_succeeded` field
(Phases 6–8). It's also useful to compare mock and real-model benign
traffic, to check that the mock isn't unrealistic.

Suggested plan:
| Data | Brain | Sessions | Cost |
|---|---|---|---|
| Main training/test dataset | mock | hundreds–thousands | $0 |
| Attack-success study + realism check | Claude | ~50–200 | a few dollars (see §3) |

## 2. Setup (Windows, PowerShell)

1. **Create an API account** in the Claude Console: <https://platform.claude.com>
   (formerly console.anthropic.com). The API is billed **separately** from
   claude.ai chat subscriptions; a Claude Pro plan does not include API usage.
2. **Add credit** under *Billing*. It's prepaid, so a small top-up is enough
   for this project.
3. **Set a spend limit** under *Limits* (e.g. $5–10/month) so a bug in a loop
   can't run up a bill.
4. **Create an API key** under *API Keys* (name it e.g. `mcp-ids-lab`). It
   starts with `sk-ant-` and is shown **once**; copy it.
5. **Give it to the program as an environment variable**, for the current
   terminal only (safest):
   ```powershell
   $env:ANTHROPIC_API_KEY = "<paste your key here>"
   ```
   Or permanently for your Windows user (open a new terminal afterwards):
   ```powershell
   setx ANTHROPIC_API_KEY "<paste your key here>"
   ```
6. **Choose a model** (optional, default `claude-opus-5-5`):
   ```powershell
   $env:LLM_MODEL = "claude-haiku-4-5"     # cheapest
   ```
7. **Run one session** and check the printed usage line:
   ```powershell
   .venv\Scripts\python -m agent.driver --task fs_summarize_notes --llm claude
   ```
   Expected ending:
   ```
   llm usage  : 3 API call(s), 5210 in / 840 out tokens, est. cost ~$0.0xx (claude-...)
   wire log   : data\raw\sessions\<id>   (view: python -m proxy.reader latest)
   ```
8. **Optional live test** (one real call):
   ```powershell
   $env:RUN_LIVE_LLM = "1"; .venv\Scripts\python -m pytest tests/test_agent.py -k live -v
   ```

### Key safety rules
* Never put the key in code, in `.env.example`, in Git, in screenshots for
  your report, or in a chat. The project reads it **only** from the
  environment, never from files.
* If it leaks, delete it in the Console (*API Keys*) and create a new one.
* Real-model runs need internet, so they run from your normal terminal, **not**
  inside the Docker lab (whose network is offline by design).

## 3. How much does it cost?

### How API pricing works
You pay per **token** (roughly ¾ of a word), with separate prices for
**input** (everything sent to the model) and **output** (everything it
writes, including hidden reasoning).

The important detail for agents: **the API is stateless, so every step
re-sends the whole conversation.** The system prompt, the tool descriptions
and all earlier tool results go back in on every call. A 4-step session pays
for the early messages 4 times. So input tokens grow with every step, and
large tool results (big files, web pages) are what make sessions expensive.

### Prices (USD per million tokens, list price, Sept 2026; check the pricing page)
| Model | Input | Output | Notes |
|---|---|---|---|
| `claude-opus-5-5` (default) | $4 | $20 | Most capable; always reasons before answering |
| `claude-sonnet-5-5` | $2 | $10 | Good balance |
| `claude-haiku-4-5` | $1 | $5 | Cheapest, fastest; no reasoning by default |

### Estimate for this lab
A filesystem task is about 2–4 API calls with small tool results. A rough
estimate is **~4–8k input tokens and ~0.5–2k output tokens per session**.
Opus and Sonnet produce more output because of their reasoning; Haiku less.

| Model | ≈ per session | ≈ 100 sessions | ≈ 200 sessions |
|---|---|---|---|
| Opus 5.5 | $0.03–0.07 | $3–7 | $6–14 |
| Sonnet 5.5 | $0.015–0.035 | $1.50–3.50 | $3–7 |
| Haiku 4.5 | $0.005–0.01 | $0.50–1 | $1–2 |

**These are estimates, not measurements.** Run one session first; the driver
prints the real token counts and an estimated cost from the table above
(`agent/llm.py: PRICES_PER_MTOK`). Your Console's *Usage* page shows the
actual billed amount. Web-fetch tasks (Phase 4) return longer text, so expect
them to cost more.

### Ways to keep it cheap
* Use the mock for everything except the attack-success study.
* Start with `claude-haiku-4-5`, and use a stronger model only for the final
  comparison.
* `LLM_EFFORT=low` reduces reasoning tokens on Opus/Sonnet (not used on Haiku).
* Keep `--max-steps` low (default 12) so a confused model can't loop.

## 4. Research note: the model is a variable
Different models resist injections differently. A strong model may ignore a
poisoned tool description that a smaller model obeys. That's why we record
`attack_attempted` (the malicious metadata was on the wire) separately from
`attack_succeeded` (this model followed it), and why the IDS is trained on
**attempts**. Always report which model and effort produced a given result.

## 5. How the code adapts to the model
`agent/llm.py: ClaudeLLM.request_kwargs()` sends only what each model supports:
| Feature | Opus 5.5 / Sonnet 5.5 | Haiku 4.5 |
|---|---|---|
| `output_config.effort` | sent | omitted (would be rejected) |
| Refusal fallback (`fallbacks="default"`) | sent | omitted |
| Reasoning | always on (adaptive) | off |
