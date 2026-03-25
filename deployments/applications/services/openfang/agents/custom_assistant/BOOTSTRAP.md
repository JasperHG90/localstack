# First-Run Bootstrap

On each new conversation, the KV-loading constraint in AGENTS.md handles session hydration automatically.

If `user:name` is NOT found in the loaded KV entries, this is a new user. Follow this protocol:

1. **Greet** — Introduce yourself briefly.
2. **Discover** — Ask the user's name and what they'd like help with.
3. **Store** — Call `memex_kv_write` with key `user:name` and another with key `user:first_interaction` set to today's date.
4. **Serve** — If the user included a request in their first message, handle it immediately.

After bootstrap, this protocol is complete. Focus entirely on the user's needs.
