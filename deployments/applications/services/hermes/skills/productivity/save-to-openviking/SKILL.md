---
name: save-to-openviking
description: Save a shared link, file, note or voice-message transcript to OpenViking under viking://user/jasper/resources/, picking the folder from the resources map and asking the operator when they named no place.
version: 1.0.0
metadata:
  hermes:
    tags: [openviking, save, bookmark, resources, links, notes, voice]
    category: productivity
---
## When to Use

Whenever the operator asks to save, keep, store, file or bookmark something
(a URL, a file, a typed note, the transcript of a voice message) in
OpenViking or "my knowledge base", with or without naming a place.

## Steps

1. Read the map: `viking_read(uri="viking://user/jasper/resources/.map.md", level="full")`.
   It lists the roots under the resources folder and the rule for each. If
   it does not exist, write the seed map below first with
   `viking_write(uri="viking://user/jasper/resources/.map.md", mode="create", content=<seed map>)`.
2. Work out the kind and the target.
   - A URL: `viking_add_resource(url=<url>, parent=<folder URI>, reason=<one line>)`.
   - A voice message arrives as the gateway's quoted transcript at the top
     of the message. Name a file `YYYY-MM-DD-<short-title>.md` (today's
     date, a few words of title), write the transcript to it with
     `write_file` under /opt/data/tmp, with the date and "Source: Telegram
     voice message" in a header, then
     `viking_add_resource(url=<that path>, parent=<folder URI>, reason=<one line>)`.
   - A typed note goes the same way as a transcript. A file the operator
     sent arrives as a local path: pass that path as `url`.
3. If the operator named a place (for example "to blogs/anthropic"), save
   there without asking, with
   `parent="viking://user/jasper/resources/<place>/"`. If not, propose the
   best-fitting root from the map and a subfolder under it, and ask the
   operator to confirm or name another. Do not save before the answer.
4. `projects/` and `leo/` are written by syncs. Save there only after the
   operator confirms that root by name. A shared blog post goes to
   `blogs/<source>/`, where `<source>` is the site or author, the same
   layout the blog-scraper cron uses.
5. If no map entry fits, do one
   `viking_browse(action="list", path="viking://user/jasper/resources/")`
   before asking. Add any root it finds that the map lacks, with a
   description the operator gives, the same way as step 6.
6. When the operator chooses a new root, ask them for a one-line
   description of it, then append it to the map before the save:
   `viking_write(uri="viking://user/jasper/resources/.map.md", mode="append", content="\n- <root>/: <one-line description> Owner: hand saves.\n")`.
   The content starts with a newline, because append adds text exactly as
   given and the map may not end with one.
   Every root line has a description and an owner. Use owner "hand saves"
   for a root the operator made.
7. If the target name already exists, ask whether to replace it or save
   under a dated name.

`viking_add_resource` returns the saved item's `root_uri`. Trust it and give
it to the operator. Do not check it by hand: no curl, no terminal, no extra
browse or search.

The map holds roots, not every folder. Automated writers only add folders
under roots the map already names, so leave it alone unless step 1, 5 or 6
says to write it.

## Seed map

Write this text, exactly, when the map does not exist:

```markdown
# Resources map
- projects/<repo>/: one per repository, docs/ and .okf/, written by CI ovsync. Owner: ci-openviking-sync. Do not hand-edit.
- leo/: Leo's meeting transcripts, digests and notes, written by leo-consumer. Owner: leo-consumer. Do not hand-edit.
- blogs/<source>/: the daily blog-scraper cron plus posts the operator shares. Owner: blog-scraper and hand saves.
- clips/<slug>/: clips written by ov-clip. Owner: ov-clip.
```
