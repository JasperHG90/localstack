# Tools

Use your Memex skill tools to store and retrieve knowledge. These are provided directly — just call them like any other tool. Prefer searching Memex before asking the user for information they may have previously stored.

## Memex Tools by Category

### Search & Discovery
| Tool | When to use |
|------|------------|
| `memex_note_search` | Targeted document lookup. Run in parallel with `memex_memory_search`. |
| `memex_memory_search` | Broad/exploratory queries across extracted facts. Run in parallel with `memex_note_search`. |
| `memex_note_find` | Know (part of) the note title. Lightweight fuzzy match. |
| `memex_entity_search` | "What relates to X?", relationship/landscape queries. |
| `memex_entity_related` | Co-occurring entities — fastest relationship mapping. |
| `memex_entity_mentions` | Source facts mentioning an entity. |

### Reading Notes
| Tool | When to use |
|------|------------|
| `memex_note_metadata` | Check total_tokens and has_assets BEFORE reading. Skip after `memex_note_search`. |
| `memex_note_view` | Read full note — ONLY when total_tokens < 500. |
| `memex_note_page_index` | Get TOC for large notes. Then drill into sections with `memex_note_node`. |
| `memex_note_node` | Read specific sections by node ID from page-index. |
| `memex_note_list_assets` | Check when has_assets: true. ALWAYS check before reproducing diagrams. |

### Browsing
| Tool | When to use |
|------|------------|
| `memex_note_list` | List notes with optional date filters. |
| `memex_note_recent` | Browse recent notes. NOT for discovery — use search. |
| `memex_list_vaults` | List all vaults with note counts. |

### Writing
| Tool | When to use |
|------|------------|
| `memex_note_add` | Save a note. Use background=true. Keep concise (300 token max). |
| `memex_kv_write` | Store structured facts/preferences. Default to `app:openfang:custom_assistant:` namespace. |
| `memex_kv_get` | Exact key lookup. |
| `memex_kv_list` | List all KV entries. Use at session start. |
| `memex_kv_search` | Fuzzy semantic search over stored facts. |

## Other tool protocols

- `file_read` BEFORE `file_write` — always understand what exists.
- `web_search` for current info, `web_fetch` for specific URLs.
- `browser_*` for interactive sites that need clicks/forms.

## Error handling

- If a Memex tool returns an error, check the message. Common causes: server unreachable, invalid note/entity ID, network timeout.
- If Memex is unreachable, inform the user and continue with non-Memex tasks. Do not retry more than once.
- If search returns no results, broaden the query or switch strategies. Do not say nothing was found until you have tried at least two approaches.
