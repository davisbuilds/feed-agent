---
name: compact-session
description: Create comprehensive session summaries for context preservation and seamless handoff. Use when (1) conversation approaching context limits, (2) user requests session summary, (3) preparing handoff documentation to another agent or fresh instance, (4) archiving work for future reference.
---

# Compact Session

Create summaries that enable a fresh instance to continue work seamlessly with no prior context.

## Core Goal

Answer: "If I were dropped into this conversation cold, what would I need to pick up exactly where we left off?"

## Output File Location

Write the session summary to: `docs/sessions/COMPACT_{SESSION-NAME}_{YYYY-MM-DD}.md`

**Determining SESSION-NAME automatically:**
Derive a concise, descriptive name (2-4 words, kebab-case) from the session context:

- Primary feature or component being worked on (e.g., "user-auth", "payment-flow")
- Main bug or issue addressed (e.g., "websocket-reconnect", "memory-leak")
- Technology or tool focus (e.g., "pdf-processing", "react-migration")
- Type of work if mixed topics (e.g., "dashboard-refactor", "api-integration")

Examples:

- Bug fix session → "react-profile-bug"
- Feature work → "realtime-notifications"
- Refactoring → "state-management-refactor"
- Multiple small tasks → "miscellaneous-fixes"

**File creation steps:**

1. Determine the project root directory (where the user is working)
2. Derive SESSION-NAME from the session context
3. Get current date in YYYY-MM-DD format
4. Create `docs/sessions/` directory if it doesn't exist
5. Write summary to `docs/sessions/COMPACT_{SESSION-NAME}_{YYYY-MM-DD}.md`
6. Inform user of the file location

## Summary Structure

Generate summaries with these 9 numbered sections:

### 1. Primary Request and Intent

- User's high-level goals and problem being solved
- Desired end state and constraints/preferences expressed
- Focus on intent, not just literal requests

### 2. Key Technical Concepts

- Technologies, frameworks, libraries in use
- Architectural patterns or conventions
- Project-specific terminology

### 3. Files and Code Sections

For each modified or relevant file:

- **Full absolute path** - Brief description
- What was changed and why
- Key code snippets with language identifiers

```typescript
// Include enough context to understand the change
```

### 4. Errors and Fixes

For any bugs encountered:

- **Symptom**: What the user observed
- **Root Cause**: Why it happened (be specific)
- **Solution**: What was changed and why it works
- Include before/after code when relevant

### 5. Problem Solving Approach

- Why was approach X chosen over Y?
- What alternatives were considered?
- What assumptions were made?

### 6. User Messages

- Preserve exact user requests in chronological order
- Quote directly when phrasing matters
- These are ground truth for understanding intent

### 7. Pending Tasks

List incomplete work with enough detail to resume:

- What specific steps remain?
- What files need modification?
- What was the next immediate action?

### 8. Current Work State

- What file was being edited?
- What line or function was in progress?
- What was the most recent tool call or action?

### 9. Suggested Next Step

Provide a single concrete action to resume:

- Be specific enough to execute immediately
- Reference exact file paths and function names

## Critical Requirements

**Prioritize Resumability**

- Future instance should continue without clarifying questions
- Include enough code context for edits without re-reading entire files
- Preserve error messages and stack traces verbatim

**Be Precise, Not Verbose**

- Use exact file paths, function names, line numbers
- Quote code directly rather than paraphrasing
- Avoid vague descriptions like "updated the file" — say what changed

**Track State, Not Just History**

- Distinguish completed vs. in-progress vs. pending work
- Note committed vs. uncommitted changes if git available
- Preserve todo list state if one exists

**Preserve User Voice**

- Keep user's exact phrasing for requirements
- Note implicit preferences (coding style, communication style)
- Record any corrections or clarifications provided

## Format Conventions

- Use markdown with clear headers
- Code blocks with syntax highlighting
- **Bold** for file paths and key terms
- `inline code` for function/variable names
- Write "None" for inapplicable sections rather than omitting them

The summary should feel like watching a fast-forward of the entire session.

## Template

See `assets/summary-template.md` for a blank template to start from.
