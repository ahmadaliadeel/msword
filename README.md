# msword

Professional document editor & desktop-publishing platform built on PySide6.

- **Frame-first** page-canvas layout (QuarkXPress / InDesign mental model).
- **Block-based** text editing (Tiptap-equivalent) with slash menu, bubble menu, drag-reorder block handles, Markdown shortcuts.
- **Full Bidi** / RTL / LTR for Arabic, Urdu, Hebrew, mixed-script documents.
- **Linked text frames**, multi-column layout, master pages, baseline grid.
- **Pro typography**: kerning, tracking, OpenType features, Knuth–Plass paragraph composer.
- **Vector PDF export** with PDF/X-1a / PDF/X-4 (CMYK ICC, trim/bleed).
- **DOCX import & export.**
- **QuarkXPress-style** application shell: menu bar + measurements palette + tools palette + dockable Pages / Layers / Style Sheets / Colors / Glyphs palettes.

## Architecture

Document-MVC, single source of truth. Mutations only via Commands on the UndoStack; views are pure subscribers.

See [`docs/superpowers/specs/2026-04-25-msword-editor-design.md`](docs/superpowers/specs/2026-04-25-msword-editor-design.md) for the full design.

## Quick start

```sh
uv sync
uv run msword
```

## Development

```sh
uv run pytest                  # unit + integration tests
uv run ruff check src tests    # lint
uv run mypy src                # type-check
```

## Status

Pre-alpha. v1 ("Tier C") is being built across 33 parallel work units. Track via the [Pull Requests tab](../../pulls).
