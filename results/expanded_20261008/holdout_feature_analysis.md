# Why unseen attack families are missed (family holdout, feature evidence)

| Training set | Held-out family | Model | Recall | Top features (importance) |
|---|---|---|---:|---|
| 180 | poisoned_tool | Random Forest | 0.43 | `max_desc_param_ratio` 0.18, `desc_len_std` 0.17, `desc_len_mean` 0.08 |
| 180 | poisoned_tool | XGBoost | 0.80 | `desc_len_std` 1.00, `max_desc_param_ratio` 0.00, `max_directive_density` 0.00 |
| 180 | sampling_injection | Random Forest | 0.00 | `tool_name_mentions` 0.11, `desc_len_std` 0.10, `desc_len_mean` 0.10 |
| 180 | sampling_injection | XGBoost | 0.00 | `desc_len_mean` 0.41, `tool_name_mentions` 0.35, `size_max` 0.17 |
| 720 | poisoned_tool | Random Forest | 0.42 | `max_desc_param_ratio` 0.20, `desc_len_std` 0.17, `desc_len_mean` 0.08 |
| 720 | poisoned_tool | XGBoost | 0.80 | `desc_len_std` 1.00, `max_desc_param_ratio` 0.00, `max_directive_density` 0.00 |
| 720 | sampling_injection | Random Forest | 0.00 | `tool_name_mentions` 0.12, `desc_len_mean` 0.11, `desc_len_std` 0.10 |
| 720 | sampling_injection | XGBoost | 0.00 | `desc_len_mean` 0.45, `tool_name_mentions` 0.38, `size_max` 0.16 |
| 1354 | poisoned_tool | Random Forest | 0.00 | `max_desc_param_ratio` 0.15, `desc_len_std` 0.13, `tools_call_req_size_mean` 0.08 |
| 1354 | poisoned_tool | XGBoost | 0.00 | `max_desc_param_ratio` 0.81, `size_std` 0.18, `tools_call_req_size_mean` 0.01 |
| 1354 | sampling_injection | Random Forest | 0.00 | `tool_name_mentions` 0.17, `desc_len_std` 0.10, `metadata_text_len_max` 0.10 |
| 1354 | sampling_injection | XGBoost | 0.00 | `tool_name_mentions` 0.77, `desc_len_max` 0.21, `desc_len_std` 0.01 |

| Training set | Feature | Benign max | Poisoned median | Poisoned above benign max |
|---|---|---:|---:|---:|
| 180 | `desc_len_std` | 34.7 | 52.5 | 80% |
| 180 | `desc_len_max` | 172.0 | 212.0 | 80% |
| 180 | `directive_word_count` | 2.0 | 5.0 | 100% |
| 180 | `model_address_count` | 0.0 | 4.0 | 100% |
| 720 | `desc_len_std` | 34.7 | 52.5 | 80% |
| 720 | `desc_len_max` | 172.0 | 212.0 | 80% |
| 720 | `directive_word_count` | 2.0 | 5.0 | 100% |
| 720 | `model_address_count` | 0.0 | 4.0 | 100% |
| 1354 | `desc_len_std` | 79.2 | 52.5 | 25% |
| 1354 | `desc_len_max` | 231.0 | 212.0 | 40% |
| 1354 | `directive_word_count` | 5.0 | 5.0 | 20% |
| 1354 | `model_address_count` | 5.0 | 4.0 | 0% |

Median `server_initiated_request_count` per group: 180 sessions: {'benign': 0.0, 'poisoned_tool': 0.0, 'sampling_injection': 1.0, 'shadowing': 0.0}; 720 sessions: {'benign': 0.0, 'poisoned_tool': 0.0, 'sampling_injection': 1.0, 'shadowing': 0.0}; 1354 sessions: {'benign': 0.0, 'poisoned_tool': 0.0, 'sampling_injection': 1.0, 'shadowing': 0.0}
