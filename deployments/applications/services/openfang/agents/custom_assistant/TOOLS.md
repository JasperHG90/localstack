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
| `memex_entity_view` | Get details for specific entities (batch — pass array of names/UUIDs). |
| `memex_entity_related` | Co-occurring entities — fastest relationship mapping. |
| `memex_entity_mentions` | Source facts mentioning an entity. |

### Reading Notes
| Tool | When to use |
|------|------------|
| `memex_note_metadata` | Check total_tokens and has_assets BEFORE reading. Batch — pass array of note IDs. Skip after `memex_note_search`. |
| `memex_note_view` | Read full note — ONLY when total_tokens < 500. |
| `memex_note_page_index` | Get TOC for large notes. Batch — pass array of note IDs. |
| `memex_note_node` | Read sections by node ID. Batch — pass array of node IDs. |
| `memex_note_list_assets` | Check when has_assets: true. ALWAYS check before reproducing diagrams. |
| `memex_get_resource` | Download assets by path. Batch — pass array of paths. |
| `memex_memory_view` | Inspect memory units by ID. Includes contradiction/supersession context. Batch. |
| `memex_get_lineage` | Trace provenance of any memory entity. Pass entity_type + entity_id. Direction: upstream (source docs), downstream (derived knowledge), or both. |

### Browsing
| Tool | When to use |
|------|------------|
| `memex_note_list` | List notes with optional date filters. |
| `memex_note_recent` | Browse recent notes. NOT for discovery — use search. |
| `memex_list_vaults` | List all vaults with note counts. |

### Writing & Lifecycle
| Tool | When to use |
|------|------------|
| `memex_note_add` | Save a note. Use `background: true`. Pass the vault from session bootstrap if one is configured. |
| `memex_note_rename` | Rename a note (updates title everywhere). |
| `memex_note_template_list` | List available templates with slugs and descriptions. |
| `memex_note_template_get` | Get a template's markdown content by slug. Use it to structure `memex_note_add` content. |
| `memex_note_template_register` | Register a new template. Pass slug, name, description, and template (markdown with YAML frontmatter). |
| `memex_kv_write` | Store structured facts/preferences. Default to `app:openfang:custom_assistant:` namespace. |
| `memex_kv_get` | Exact key lookup. |
| `memex_kv_list` | List all KV entries. Use at session start. |
| `memex_kv_search` | Fuzzy semantic search over stored facts. |

### Writing notes — protocol

1. **Vault**: Use the vault resolved during session bootstrap. If none was configured, omit to use the default.
2. **Template-first** — before ANY `memex_note_add` call:
   a. Call `memex_note_template_list` to see available templates.
   b. Pick the best-matching template. If one fits, call `memex_note_template_get` to retrieve it, fill in placeholders, and pass as `content`.
   c. If NO template fits the note you're about to save, call `memex_note_template_register` to create a reusable template first, then use it. Do not fall back to an unstructured "Quick note".
3. **Author**: ALWAYS set `created_by: custom_assistant` in the YAML frontmatter. Never leave it as a placeholder like `[Author name]`.
4. **Content**: Write complete, well-structured markdown with YAML frontmatter (`title`, `description`, `tags`, `created_by`).
5. **Size**: Background notes (auto-capture) ~300 tokens. User-requested notes can be as long as needed.
6. **Background**: `background: true` for auto-capture, `background: false` for user-requested notes.

## Other tool protocols

- `file_read` BEFORE `file_write` — always understand what exists.
- `web_search` for current info, `web_fetch` for specific URLs.
- `browser_*` for interactive sites that need clicks/forms.

## Error handling

- If a Memex tool returns an error, check the message. Common causes: server unreachable, invalid note/entity ID, network timeout.
- If Memex is unreachable, inform the user and continue with non-Memex tasks. Do not retry more than once.
- If search returns no results, broaden the query or switch strategies. Do not say nothing was found until you have tried at least two approaches.
