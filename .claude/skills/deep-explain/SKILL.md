---
name: deep-explain
description: Teach the user a new codebase, technology, framework, or system by walking through it from high-level architecture down to implementation details using a paginated, layered approach. Use this skill whenever the user wants to understand how something works, needs onboarding onto a new technology, asks you to explain a system end-to-end, or says things like "walk me through", "explain how X works", "I need to learn X", "teach me", or "help me understand". Also use when the user shares documentation and asks to be taught from it.
---

# Deep Explain

Teach complex systems by walking down a "ladder of abstraction" — start at the highest conceptual level and descend layer by layer into implementation details. Each level is paginated: the user controls pacing and can pause to ask questions, dive deeper into a subtopic, or get quizzed.

## Why this approach works

People don't learn systems by reading source code top-to-bottom. They build mental models in layers: first the shape, then the moving parts, then the wiring. Dumping everything at once overwhelms. Drip-feeding without structure leaves gaps. The ladder gives structure *and* user control.

## Procedure

### Phase 1: Gather material

Before teaching, you need to understand the system yourself. Depending on what the user gives you:

- **A URL or documentation site**: Fetch and read the docs systematically. Build a sitemap first, then read key pages (architecture, getting started, core concepts) before detail pages.
- **A codebase**: Explore the directory structure, read README/architecture docs, identify entry points, trace key data flows.
- **A topic you already know**: Draw on your training knowledge but verify specifics if the user provides sources.
- **A paper or PDF**: Read it fully before explaining.

Don't start teaching until you have enough material to plan the full ladder. Incomplete understanding leads to shallow or wrong explanations.

### Phase 2: Plan the ladder

Design 5-7 levels of increasing depth. The exact levels depend on the subject, but a typical structure:

| Level | Scope | Token budget | Example |
|-------|-------|-------------|---------|
| 1 | 30-second mental model | 300-500 | "Kubernetes runs containers across machines" |
| 2 | Major subsystems | 800-1200 | "There are 5 subsystems: scheduler, API server, ..." |
| 3 | How subsystems connect | 800-1200 | "When you deploy a pod, the API server writes to etcd, the scheduler picks a node, ..." |
| 4 | One subsystem in detail | 1000-1500 | "The scheduler scores nodes using predicates and priorities..." |
| 5 | Implementation mechanics | 1000-1500 | "The scoring loop in scheduler.go iterates..." |
| 6 | Edge cases and gotchas | 800-1200 | "When a node goes NotReady, the taint manager..." |
| 7 | Integration/advanced | 800-1200 | "CRDs extend the API server by..." |

Don't share this plan with the user. The levels should feel like a natural conversation, not a syllabus.

### Phase 3: Teach level by level

For each level:

1. **Explain the concepts at this level.** Use diagrams (ASCII/text), concrete examples, and analogies. Every abstract concept needs at least one concrete example showing real inputs, outputs, or commands.

2. **Use comparisons when helpful.** If the user knows a related system (e.g., they know Docker but not Kubernetes), frame new concepts in terms of what they already know. Check memory and prior conversation for clues about their background.

3. **End with a pagination prompt.** After each level, offer the user a choice:
   ```
   Continue to Level N+1: [brief preview of what's next]? (Y/N)
   Or ask me anything about Level N — or say "quiz me" to test your understanding.
   ```

4. **Be open to diversions.** If the user asks a question that jumps ahead or sideways, answer it fully, then return to where you were in the ladder. Don't be rigid about the plan.

5. **Track what the user struggles with.** If they ask clarifying questions or get quiz answers wrong on a topic, note that area as one to revisit or spend more time on at deeper levels.

### Phase 4: Interactive quizzing

When the user says "quiz me":

1. **Design 5-6 questions** spanning all levels covered so far. Mix question types:
   - **Conceptual**: "How many X are involved when Y happens, and do they share state?"
   - **Scenario-based**: "You have this config. What happens when Z fails?"
   - **Gotcha/tricky**: Test common misconceptions or subtle distinctions.
   - **Applied**: "Given this situation, which component handles it and why?"

2. **Let the user answer all questions in one go.** Don't interrupt with scoring after each one. Batch feedback is less annoying and lets them think freely.

3. **Score honestly and critically.** For each answer:
   - Correct: brief confirmation, maybe add a nuance they didn't mention.
   - Partially correct: acknowledge what's right, clearly explain what's wrong or missing.
   - Wrong: explain the correct answer fully with the reasoning. Don't soften it — wrong is wrong.

4. **Diagnose patterns.** After scoring, identify which areas are strong and which are weak. Explicitly recommend whether to continue down the ladder or revisit a specific level/topic.

5. **Offer to go deeper on weak areas.** The quiz isn't a gate — it's a diagnostic. Use mistakes to guide where to spend more time.

## Formatting guidelines

- **ASCII diagrams** for architecture and data flow. Keep them under 15 lines. Use box-drawing characters or simple `──▶` arrows.
- **Tables** for comparisons (e.g., "CLI mode vs Gateway mode", "feature X vs feature Y").
- **Code blocks** for real commands, config examples, and file paths. Never show hypothetical code when real code exists.
- **Bold** for key terms on first introduction. Don't overuse.
- **Headers** (`##`) to structure each level. Use the format `## Level N: [Title]`.

## Pitfalls to avoid

- **Don't dump everything at once.** The whole point is pacing. If you find yourself writing more than ~1500 tokens per level, split it.
- **Don't skip the concrete examples.** Abstract explanations without examples don't stick. "The scheduler assigns pods to nodes" means nothing until you show a real pod spec and trace what happens to it.
- **Don't be afraid to say "this is weird."** If a design decision is surprising or counterintuitive, call it out. Acknowledging the weirdness helps the user's mental model more than pretending everything is elegant.
- **Don't quiz too early.** At least 2-3 levels should be covered before the first quiz makes sense.
- **Don't give easy quizzes.** Questions where the answer is obvious from the explanation don't test understanding — they test short-term memory. Good quiz questions require the user to *apply* what they learned to a new scenario.

## Verification

The skill is working well when:
- The user controls the pacing (they say "continue" or ask questions, not you monologuing)
- Each level builds on the previous one without repeating it
- The user can answer scenario-based questions, not just recall facts
- Diversions (user questions) are handled gracefully and the conversation returns to the ladder
- Quiz results accurately identify areas where the user needs more depth
