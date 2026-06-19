# Design Tokens

Single source of truth for color in the Beyond the Loop frontend.

## TL;DR

- **Use semantic tokens.** `bg-surface`, `text-fg-muted`, `border-border`, `bg-accent`, …
- **Don't use primitive scales.** `bg-lightGray-*`, `dark:bg-customGray-*`, `bg-customBlue-*` and `dark:bg-blue-*` are legacy and being removed.
- **No more `dark:` pairs for color.** A single `bg-surface` works in both modes — the variable flips, not the class.
- When in doubt, run `/check-tokens` (Claude Code slash command) on your diff before committing.

## Why

The app accumulated three overlapping gray scales (`gray`, `lightGray`, `customGray`) plus two blue scales (`customBlue`, Tailwind's `blue`). The same UI role — say "default card background" — was written ~5 different ways depending on which file you opened. Theme swapping, contrast tuning, and accessibility work were all blocked.

Semantic tokens decouple **what a color means** ("the surface this card sits on") from **what value it currently has** (`#F5F5F5`). Once every component talks in roles, we can change the entire palette in one commit without touching component code.

## Architecture (3 layers)

```
Layer 3   Component classes        .chat-bubble-user            (rare, only when truly reusable)
Layer 2   Semantic tokens          bg-surface, text-fg-muted    ← write code against these
Layer 1   Primitive scales         lightGray-300, customGray-…  ← legacy, frozen, do not use
```

Layer 2 is implemented as CSS custom properties in [`src/app.css`](../src/app.css) (`:root` for light, `.dark` for dark) and exposed to Tailwind in [`tailwind.config.js`](../tailwind.config.js) via `rgb(var(--token) / <alpha-value>)`. The `<alpha-value>` placeholder means `bg-surface/50`, `border-border/30` etc. keep working.

## Token catalogue

### Surfaces (backgrounds)

| Token            | When to use                                                     | Light → Dark example                                |
| ---------------- | --------------------------------------------------------------- | --------------------------------------------------- |
| `bg-surface-canvas`   | Root app shell / layout backdrop                           | Used by `routes/(app)/+layout.svelte`, `AppSidebar` |
| `bg-surface`          | Default panel/card body                                    | `SettingsModal`, `Knowledge` card body              |
| `bg-surface-raised`   | Sits visually above default — modals, message input        | `MessageInput`, `UserMessage` bubble                |
| `bg-surface-muted`    | Slightly recessed area (chips, suggestion cards)           | `Suggestions`                                       |
| `bg-surface-overlay`  | Modal scrim. Use with alpha: `bg-surface-overlay/50`       | `SettingsModal` backdrop                            |
| `bg-surface-code`     | Code blocks. Tied to the syntax-highlight theme.           | `.codespan`, `.tiptap > pre`                        |
| `bg-surface-hover`    | Hover state of list items, ghost buttons                   | `Sidebar/ChatItem`, dropdown items                  |
| `bg-surface-selected` | Selected / active list item                                | Active chat in sidebar                              |
| `bg-surface-disabled` | Disabled control background                                | Disabled buttons                                    |

### Foreground / text (`text-fg-…`)

| Token                  | When to use                                            |
| ---------------------- | ------------------------------------------------------ |
| `text-fg`              | Default body text, headlines                           |
| `text-fg-muted`        | Form labels, secondary body copy                       |
| `text-fg-subtle`       | Timestamps, captions, helper text                      |
| `text-fg-placeholder`  | Input placeholders                                     |
| `text-fg-disabled`     | Disabled labels                                        |
| `text-fg-on-accent`    | Text sitting on top of an `accent` background          |
| `text-fg-link`         | Inline links                                           |

### Borders

| Token                | When to use                                              |
| -------------------- | -------------------------------------------------------- |
| `border-border`      | Default inputs, cards, secondary buttons                 |
| `border-border-subtle` | Barely-there separators (shell ↔ content)              |
| `border-border-strong` | Emphasis: table headers, key dividers                  |
| `border-border-focus`  | Focus rings (use via `focus:border-border-focus`)      |

> Bare `class="border"` (no color suffix) automatically uses `--border-default`. Add a suffix only when overriding.

### Accent / brand

| Token                  | When to use                                              |
| ---------------------- | -------------------------------------------------------- |
| `bg-accent`            | Primary action buttons (Save, Send, Submit)              |
| `bg-accent-hover`      | Hover state of primary buttons                           |
| `bg-accent-subtle`     | Tinted backgrounds — combine with alpha (`/10`, `/15`)   |
| `text-accent-foreground` | Text on top of `bg-accent`                             |
| `text-fg-link`         | Inline links (`text-fg-link` is the canonical link color)|

`accent` is identical in light and dark mode — brand is brand. Pre-token, dark mode accidentally swapped to Tailwind's `blue-500`/`blue-600`; that's harmonised now.

### Status (info / success / warning / danger)

Each status has `-bg`, `-border`, `-fg`. The `danger` family additionally exposes `DEFAULT`, `hover`, and `foreground` for solid destructive buttons.

```svelte
<!-- AlertBanner success variant -->
<div class="bg-success-bg border border-success-border text-success-fg">…</div>

<!-- Destructive button -->
<button class="bg-danger hover:bg-danger-hover text-danger-foreground">Delete</button>
```

### Chat-specific (Layer 3)

`bg-chat-user`, `bg-chat-assistant`, `bg-chat-input`. Use only in their respective components. If a value collapses to `surface-raised` after the migration, we'll delete the chat-specific token.

## Recipes

### Card with header

```svelte
<div class="bg-surface border rounded-mdx">
  <header class="border-b border-border-subtle px-4 py-3">
    <h3 class="text-fg font-medium">Knowledge bases</h3>
    <p class="text-fg-subtle text-sm">Connect documents to your assistant.</p>
  </header>
  <div class="p-4 text-fg-muted">…</div>
</div>
```

### Primary + secondary button pair

```svelte
<button class="bg-surface border hover:bg-surface-hover text-fg">Cancel</button>
<button class="bg-accent hover:bg-accent-hover text-accent-foreground">Save</button>
```

### Input field

```svelte
<input
  class="bg-surface-raised border text-fg placeholder:text-fg-placeholder
         focus:border-border-focus"
/>
```

### Modal

```svelte
<div class="fixed inset-0 bg-surface-overlay/50 backdrop-blur-[7.44px]">
  <div class="bg-surface border rounded-mdx p-6">…</div>
</div>
```

## Migration

We migrate one role at a time, in small, individually reviewable commits. Each commit is no-op visually — the underlying values are unchanged. Once everything is on tokens, a single follow-up commit re-tunes values for higher contrast and clearer hierarchy.

Rough order: surfaces → borders → text → buttons → chat → status → code-block → primitive cleanup. Don't migrate ahead of the team without coordination — easy merge conflicts otherwise.

## Anti-patterns

```diff
- <div class="bg-lightGray-550 dark:bg-customGray-800">           <!-- DO NOT -->
+ <div class="bg-surface">

- <p class="text-lightGray-1200 dark:text-gray-400">…</p>          <!-- DO NOT -->
+ <p class="text-fg-subtle">…</p>

- <button class="bg-customBlue-600 hover:bg-customBlue-500
-                dark:bg-blue-600 dark:hover:bg-blue-500">Save</button>
+ <button class="bg-accent hover:bg-accent-hover text-accent-foreground">Save</button>
```

**Common mistakes:**

- Writing `dark:` color variants. The token already encodes both modes — `bg-surface` is enough.
- Reaching for `text-fg-muted` when you mean `text-fg-subtle`, or vice versa. Rule of thumb: `muted` = body copy in a calmer weight; `subtle` = supporting metadata (timestamps, helper text).
- Picking `surface-canvas` for a card. Canvas is the *layout backdrop* (one per page); cards sit on `surface` or `surface-raised`.
- Using primitive `bg-red-500` for delete. Use `bg-danger`.

## Adding a new token

Don't, unless an existing one really doesn't fit and the role will recur in ≥3 places. New tokens are added in two places: `:root` and `.dark` in `app.css` (the value), and `tailwind.config.js` `colors` (the utility-class wiring). Document the new token here.

If you find yourself wanting a new token for a single component, prefer a Layer-3 component class instead.

## Reference

- CSS variables: [`src/app.css`](../src/app.css)
- Tailwind wiring: [`tailwind.config.js`](../tailwind.config.js)
- Claude review command: `/check-tokens` (runs a diff audit against this guide)
