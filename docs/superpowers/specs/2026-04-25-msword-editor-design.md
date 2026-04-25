# msword — Professional Document Editor & DTP Platform

**Status:** Design / spec
**Date:** 2026-04-25
**Owner:** Ahmed Ali Adeel (`ahmedaliadeel@gmail.com`)
**Working dir:** `/home/maxprime/Documents/dev/msword`

## 1. Goal

Build a desktop document editor that *starts* feature-comparable to MS Word for body-text editing but is architected from day one as a frame-based, page-canvas DTP platform on the path to feature parity with QuarkXPress and Adobe InDesign.

The product is a **pro-grade v1** ("Tier C") delivered through parallel work units. v1 includes: frame-first page canvas, linked text frames, multi-column layout, master pages, baseline grid, paragraph + character + object styles, advanced typography (kerning, tracking, OpenType features), images, shapes, tables, RTL/LTR/Bidi for Arabic & Urdu, color swatches with sRGB + CMYK profiles, vector PDF export with PDF/X-1a / PDF/X-4 output, DOCX import/export, find/replace with regex, footnotes, TOC, **block-based editing (Tiptap-equivalent)** inside text frames, and a **QuarkXPress-style application shell** (menu bar + measurements palette + tools palette + dockable right-side palettes).

## 2. Anchor decisions (already made)

| Decision | Choice |
|---|---|
| Layout mental model | **Frame-first** (InDesign / QuarkXPress style); body flow is a text frame. |
| Text shaping & layout | **`QTextLayout` per paragraph + custom frame composer.** Bidi/Arabic/Urdu via Qt's HarfBuzz/ICU integration. |
| v1 scope tier | **Tier C — pro-grade.** |
| App shell | **QuarkXPress-style** menu bar + measurements palette + tools palette + dockable palettes. **No ribbon.** |
| Text editing model | **Block-based** (Tiptap-equivalent): blocks are the structural unit, runs the inline-styling unit. |
| Native file format | `.msdoc` — ZIP container with JSON + assets. |
| Interop | DOCX import/export in v1; IDML deferred to Phase 2. |
| Package manager | **uv**. |
| GUI toolkit | **PySide6** (Qt 6.6+). |

## 3. Architecture pattern — "Document-MVC"

Single source of truth, with strict directional data flow.

- **Document** — one `Document` instance per open file. Owns the model tree, undo stack, asset registry, change-notification bus (Qt signals). Authoritative state.
- **Model** — pure data nodes (`Page`, `Frame`, `Story`, `Block`, `Run`, `Style`, `Asset`). No Qt widgets. No rendering. No I/O. Serializable; snapshot-able for undo.
- **View** — anything that displays the document. Page canvas, outline tree, pages palette (thumbnails + master pages), layers palette, style sheets, colors, glyphs, measurements palette. Views are subscribers — they never own state; they re-render on `Document.changed` signals.
- **Controller** — `Tools` (selection, item, text, picture, shape, pen, line, table, linker, hand, zoom) + `Commands` (mutations). All mutations go through the `UndoStack` via `Command` objects; no view or tool ever mutates the model directly.

The non-negotiable invariant: **a view re-rendering after a change cannot diverge from a view re-opening the file from disk.** If they ever differ, the bug is in the model or the change notification — never in the view.

## 4. Data model

```
Document
├── meta                  (title, author, locale, default-language)
├── color_profiles        (sRGB + CMYK ICC)
├── color_swatches        (named, supports spot colors)
├── paragraph_styles      (named, hierarchical via "based-on")
├── character_styles
├── object_styles         (frame-level: stroke, fill, padding, columns, text-inset)
├── master_pages          (templates: A-Master, B-Master, …; can be based-on each other)
├── pages[]               (each references a master; can override master items)
├── stories[]             (text content; one story flows across N linked frames)
└── assets/               (images, fonts) — content-addressed by SHA-256
```

### 4.1 Frames

`Frame` (abstract) → `TextFrame`, `ImageFrame`, `ShapeFrame`, `TableFrame`, `GroupFrame`.
Every frame has: `id`, `page_id`, `x`, `y`, `w`, `h`, `rotation`, `skew`, `z_order`, `locked`, `visible`, `object_style_ref`, `text_wrap` (none/box/contour), `padding`, optional `parent_group`.

`TextFrame` adds: `story_ref`, `story_index` (position in linked chain), `columns`, `gutter`, `column_rule`, `text_direction` (LTR / RTL / inherit), `vertical_align`.

### 4.2 Stories — block-based

Story content is a tree of `Block` nodes (Tiptap semantics). Blocks are the unit of structure; `Run`s inside a block are the unit of inline styling.

```
Story
└── blocks[]
    ├── ParagraphBlock(runs[], paragraph_style_ref)
    ├── HeadingBlock(level: 1..6, runs[], style_ref)
    ├── ListBlock(kind: bullet | ordered | todo, items[Block])
    ├── QuoteBlock(blocks[])
    ├── CodeBlock(language, text, theme)
    ├── TableBlock(rows[], cols[], cells[][Block])         # nestable
    ├── ImageBlock(asset_ref, caption?, layout: inline | float | full-width)
    ├── DividerBlock
    ├── CalloutBlock(kind: info | warn | tip, blocks[])
    └── EmbedBlock(kind, payload)                          # extension point
```

A `Run` carries inline marks: `bold`, `italic`, `underline`, `strike`, `code`, `link`, `color_ref`, `highlight_ref`, `font_ref`, `size`, `tracking`, `baseline_shift`, `opentype_features` (set of feature tags), `language_override`.

Each block type is registered in a `BlockRegistry` with: (a) a JSON serializer/deserializer, (b) a layout adapter that yields the paragraphs the §5 composer consumes, (c) input rules / shortcuts, (d) an optional inspector-panel section.

## 5. Text layout pipeline

Per-story flow:

```
Story → story.iter_paragraphs()
            │  (BlockRegistry walks the block tree, yields paragraphs
            │   with the right paragraph_style + inline marks attached)
            ▼
QTextLayout.beginLayout() → shape with HarfBuzz (Bidi, Arabic, Urdu, complex scripts)
            │
            ▼  for each line
FrameComposer.place(line):
    if line fits in current frame's current column → place
    elif more columns in this frame              → advance column
    elif more frames in chain                    → advance to next linked frame
    else                                         → mark overflow (red "+" indicator)
```

**Incremental re-layout.** When a paragraph changes, we re-shape only that paragraph and ripple from there. When a frame resizes, we re-compose only its story from the affected frame onward.

**Bidi correctness.** `QTextLayout` is Bidi-correct by default (ICU). Frame-level `text_direction` controls (a) column-fill order — RTL frames fill columns right-to-left, (b) default paragraph alignment. Mixed-direction paragraphs work transparently.

**Pro-grade typography.** Kerning + tracking via `QFont::letterSpacing` / `QRawFont`. OpenType features (`liga`, `dlig`, `smcp`, `ss01..20`, `cv01..99`) via `QFont::setFeatures()` (Qt 6.5+). **Knuth–Plass paragraph composer** as an opt-in alternative line-breaker (pure Python in v1; a Rust/PyO3 port is a perf optimization, not v1 work). Baseline grid: paragraph style flag "align to baseline grid" snaps line baselines to the document grid.

## 6. Rendering & canvas

`QGraphicsScene` / `QGraphicsView` for the page canvas. Z-ordering, hit-testing, rubber-band selection, transforms, and group operations come for free.

- `PageItem : QGraphicsItem` — one per page; lays out child `FrameItem`s; renders page chrome (margin guides, column guides, baseline grid, bleed).
- `FrameItem : QGraphicsItem` — base class for frame rendering. Subclasses for text/image/shape/table.
- **View modes** — *paged* (page strip with spreads) and *flow* (continuous, paginated, like Word's "Web Layout"). Toggled in the View menu.
- Zoom / pan / fit-page / fit-spread / fit-width as scene transforms.

## 7. PDF export

Two paths behind one façade.

- **Standard PDF** — `QPdfWriter` + `QPainter`. Text stays as text (vector), images embed at native resolution, transparency preserved. Default for screen / general print.
- **PDF/X-1a / PDF/X-4** — render via `QPdfWriter` to a temp file, then post-process with **`pikepdf`**: embed CMYK ICC output intent, set `TrimBox` / `BleedBox` / `MediaBox`, flatten transparency for PDF/X-1a, ensure full font embedding (no subsetting issues). Color conversion sRGB → CMYK uses **LittleCMS** (via `Pillow` or a direct binding).

## 8. File format — `.msdoc`

ZIP container (renames cleanly, diffable, future-proof):

```
document.msdoc/
├── manifest.json            (version, locale, references, blocks_schema_version)
├── document.json            (pages, frames, styles, swatches, profiles, masters)
├── stories/<id>.json        (one JSON per story — clean diff/merge; block tree)
├── assets/<sha256>.{png,jpg,svg}
└── fonts/<hash>.otf         (only embedded fonts; system fonts referenced by name)
```

**Interop.**
- *DOCX import* — `python-docx` for read; mapped into a single A-Master with one auto-flowed text frame per page; Word styles → paragraph/character styles 1:1.
- *DOCX export* — write OOXML directly via `lxml` (`python-docx` is too opinionated for round-tripping our richer features). Lossy for callouts / embeds (becomes a styled paragraph + a `w:customXmlInsRangeStart` round-trip marker).
- *IDML* — deferred to Phase 2.

## 9. UI shell — QuarkXPress-style

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Menu bar: File  Edit  Style  Item  Page  Layout  View  Utilities  Window │
├──────────────────────────────────────────────────────────────────────────┤
│ Measurements palette (context-aware row, Quark-style)                    │
│  X: ___  Y: ___   W: ___  H: ___   ∠: ___    ⇆⇅  cols: __  gutter: __    │
├────┬────────────────────────────────────────────────────────────┬────────┤
│ T  │                                                            │ Pages  │
│ o  │              Page canvas (QGraphicsView)                   │ + Out- │
│ o  │                                                            │ line   │
│ l  │     ┌────────────┐   ┌────────────┐                        │ tabs   │
│ s  │     │  Page 1    │   │  Page 2    │                        ├────────┤
│    │     └────────────┘   └────────────┘                        │ Layers │
│ ▼  │                                                            ├────────┤
│  ⬚ │                                                            │ Style  │
│  T │                                                            │ sheets │
│  ⌖ │                                                            ├────────┤
│  ⊞ │                                                            │ Colors │
│  ◯ │                                                            ├────────┤
│  ✎ │                                                            │ Glyphs │
│  H │                                                            │        │
├────┴────────────────────────────────────────────────────────────┴────────┤
│ Status: page X/Y · zoom · view-mode · selection info                     │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Menu bar** — `File / Edit / Style / Item / Page / Layout / View / Utilities / Window / Help`. Native menu integration.
- **Tools palette** (left, vertical icon strip via `QToolBar` in `Qt.LeftToolBarArea`): Pointer, Item-mover, Text-frame, Picture-frame, Rectangle, Oval, Polygon, Pen (Bezier), Line, Table, Linker, Unlinker, Hand, Zoom. Modal — selecting a tool changes click semantics on the canvas.
- **Measurements palette** (top, single context-aware row): selection geometry (X/Y/W/H/rotation/skew); switches to text properties (font / size / leading / tracking / alignment / OpenType toggles) when the caret is inside a text frame; switches to column properties (count / gutter / baseline-grid override) when a frame is selected.
- **Right-side palette stack** — `QDockWidget`s, individually detachable, restackable, hideable: **Pages** (thumbnails + master pages + page reordering, tabbed with **Outline**), **Layers**, **Style Sheets** (paragraph + character), **Colors** (swatches), **Glyphs**.
- **Block-editor affordances** layered on top when caret is in a text frame: **slash menu** (`/`-triggered transient `QListView` popup at caret), **bubble menu** (selection-triggered floating mini-toolbar), **block handles** (left-margin `⋮⋮` overlay for drag-reorder / duplicate / delete), **Markdown shortcuts** (`# `, `## `, `- `, `> `, `` ``` ``, `1. `).

## 10. Project layout

```
msword/
├── pyproject.toml                # uv-managed
├── uv.lock
├── src/msword/
│   ├── __main__.py               # entry: `uv run msword`
│   ├── app.py                    # QApplication setup
│   ├── model/                    # pure data
│   │   ├── document.py
│   │   ├── page.py
│   │   ├── master_page.py
│   │   ├── frame.py              # base + TextFrame, ImageFrame, ShapeFrame, TableFrame, GroupFrame
│   │   ├── story.py
│   │   ├── block.py              # Block base + registry
│   │   ├── blocks/               # ParagraphBlock, HeadingBlock, ListBlock, QuoteBlock, CodeBlock, TableBlock, ImageBlock, DividerBlock, CalloutBlock, EmbedBlock
│   │   ├── run.py
│   │   ├── style.py              # ParagraphStyle, CharacterStyle, ObjectStyle
│   │   ├── color.py              # Swatch, ColorProfile
│   │   └── asset.py
│   ├── commands/                 # Command pattern + UndoStack
│   ├── layout/                   # text composer (QTextLayout-based) + Knuth-Plass
│   ├── render/                   # canvas rendering, PDF export, PDF/X
│   ├── io/
│   │   ├── msdoc.py              # native .msdoc read/write
│   │   ├── docx_import.py
│   │   └── docx_export.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── menus.py              # menu bar
│   │   ├── measurements_palette.py
│   │   ├── tools_palette.py
│   │   ├── canvas/               # QGraphicsView + PageItem + FrameItem subclasses
│   │   ├── palettes/             # pages, outline, layers, style_sheets, colors, glyphs (each a QDockWidget)
│   │   ├── block_editor/         # slash menu, bubble menu, block handles, markdown shortcuts
│   │   └── tools/                # tool implementations (selection, text, frame, picture, shape, pen, line, table, linker, hand, zoom)
│   └── i18n/                     # translations
├── tests/
│   ├── unit/                     # pytest, no Qt event loop
│   ├── layout/                   # text composition fixtures (incl. Arabic/Urdu/mixed-script)
│   └── integration/              # pytest-qt, full app workflows
└── docs/
    └── superpowers/specs/        # this file
```

## 11. Tooling

- **uv** — env, deps, lockfile.
- **PySide6** — Qt 6.6+ (`QFont::setFeatures`).
- **ruff** + **mypy --strict**.
- **pytest** + **pytest-qt** — integration.
- **pikepdf** — PDF/X post-processing.
- **python-docx** + **lxml** — DOCX.
- **Pillow** — image decode/transcode.
- **PyICU** — *only if* Qt's Bidi proves insufficient for edge cases; default-no.

## 12. Parallel work units (for `/batch`)

Each unit is independently implementable in an isolated git worktree, mergeable on its own, no shared state with siblings. Sized to be roughly uniform.

| # | Unit | Files / area | One-line description |
|---|---|---|---|
| 1 | `bootstrap-uv-pyside6` | `pyproject.toml`, `uv.lock`, `src/msword/__main__.py`, `app.py`, `tests/conftest.py`, `README.md` | uv-managed PySide6 project skeleton; `uv run msword` opens an empty `QMainWindow`. |
| 2 | `model-document-core` | `model/document.py`, `model/page.py`, `model/master_page.py`, `model/asset.py` | Document tree, page/master-page model, asset registry, change-notification bus. |
| 3 | `model-frame` | `model/frame.py` (base + TextFrame, ImageFrame, ShapeFrame, GroupFrame) | All frame types except TableFrame; geometry, z-order, lock/visibility, text-wrap. |
| 4 | `model-story-and-runs` | `model/story.py`, `model/run.py` | Story container, run model with full inline-mark set. |
| 5 | `model-blocks-schema` | `model/block.py`, `model/blocks/__init__.py` (ParagraphBlock + HeadingBlock + DividerBlock + EmbedBlock base) | Block base class, BlockRegistry, paragraph-iter protocol, schema versioning. |
| 6 | `model-blocks-pack-1` | `model/blocks/list.py`, `quote.py`, `code.py`, `callout.py` | Block types: list, quote, code, callout. |
| 7 | `model-blocks-pack-2` | `model/blocks/image.py`, `model/frame.py` (TableFrame), `model/blocks/table.py` | Block types: image (inline/float/full-width); TableFrame + TableBlock (nestable). |
| 8 | `model-styles` | `model/style.py` (paragraph, character, object styles), `model/color.py` (swatches + ICC profiles) | Hierarchical styles ("based-on"), spot colors, ICC profile registry. |
| 9 | `commands-and-undo` | `commands/` (Command base, UndoStack wiring), unit tests | Command pattern enforcing single-source-of-truth mutation; integrates `QUndoStack`. |
| 10 | `io-msdoc` | `io/msdoc.py`, fixtures | Native `.msdoc` ZIP read/write incl. assets, fonts, blocks_schema_version. |
| 11 | `io-docx-import` | `io/docx_import.py` | DOCX → Document via `python-docx`; Word styles → paragraph/character styles. |
| 12 | `io-docx-export` | `io/docx_export.py` | Document → OOXML via `lxml` direct; round-trip markers for richer features. |
| 13 | `layout-text-composer` | `layout/composer.py`, fixtures (LTR + RTL + Arabic + Urdu) | `QTextLayout`-based per-paragraph shaper + frame/column/chain composer with overflow. |
| 14 | `layout-knuth-plass` | `layout/knuth_plass.py` | Opt-in optimal-line-break paragraph composer (pure Python). |
| 15 | `layout-baseline-grid` | `layout/baseline_grid.py` | Per-paragraph "snap to baseline grid" line-position adjuster. |
| 16 | `render-canvas` | `ui/canvas/page_item.py`, `frame_item.py`, `text_frame_item.py`, `image_frame_item.py`, `shape_frame_item.py`, `table_frame_item.py`, `view.py` | `QGraphicsScene`-based canvas: PageItem, FrameItem subclasses, paged + flow view modes, zoom/pan. |
| 17 | `render-pdf-standard` | `render/pdf.py` | Vector PDF export via `QPdfWriter` + `QPainter`. |
| 18 | `render-pdf-x` | `render/pdf_x.py` | PDF/X-1a + PDF/X-4 post-processing via `pikepdf`; CMYK ICC output intent; trim/bleed. |
| 19 | `ui-main-window-menus` | `ui/main_window.py`, `ui/menus.py` | `QMainWindow` shell with full Quark-style menu bar wired to commands. |
| 20 | `ui-tools-palette` | `ui/tools_palette.py`, `ui/tools/` (selection, text, picture, shape, pen, line, hand, zoom — table & linker in unit 21) | Vertical tools palette; tool framework; basic tools. |
| 21 | `ui-tools-table-and-linker` | `ui/tools/table.py`, `ui/tools/linker.py`, `ui/tools/unlinker.py` | Table-creation tool; frame-link / unlink tools (drives §3 chain). |
| 22 | `ui-measurements-palette` | `ui/measurements_palette.py` | Context-aware top palette: geometry / text properties / column properties. |
| 23 | `ui-pages-palette-and-outline` | `ui/palettes/pages.py`, `ui/palettes/outline.py` | Tabbed dock: Pages (thumbnails + master pages + reordering) and Outline (heading tree). |
| 24 | `ui-layers-palette` | `ui/palettes/layers.py` | Layers panel: per-page layer list, z-order, lock/visibility. |
| 25 | `ui-style-sheets-palette` | `ui/palettes/style_sheets.py` | Paragraph + character style management UI. |
| 26 | `ui-colors-palette` | `ui/palettes/colors.py` | Swatch palette: add/edit, spot colors, ICC profile assignment. |
| 27 | `ui-glyphs-palette` | `ui/palettes/glyphs.py` | Glyph picker w/ OpenType-feature preview. |
| 28 | `ui-block-editor-core` | `ui/block_editor/handles.py`, `ui/block_editor/markdown_shortcuts.py` | Block-handle overlay (`⋮⋮`, drag-reorder/duplicate/delete) + Markdown input rules. |
| 29 | `ui-block-editor-menus` | `ui/block_editor/slash_menu.py`, `ui/block_editor/bubble_menu.py` | Slash command popup + selection-bubble formatting toolbar. |
| 30 | `ui-i18n-and-rtl-shell` | `i18n/`, `ui/main_window.py` (RTL adjustments) | i18n scaffolding; RTL-aware UI mirroring (when document is RTL). |
| 31 | `feat-find-replace` | `ui/find_replace.py`, command bindings | Find/replace with regex, scope (selection / story / document), Bidi-aware. |
| 32 | `feat-footnotes` | `model/blocks/footnote.py`, layout integration | Footnote block + reference run + per-page footnote area in layout pipeline. |
| 33 | `feat-toc` | `feat/toc.py` | Generate TOC from heading blocks; insert as a managed story; live update on heading changes. |

**Net: 33 work units.**

### 12.1 Worker policy

- **Boundaries.** Each unit owns its files exclusively. Two units may *read* a shared file (e.g., `pyproject.toml`) but only the bootstrap unit writes it; subsequent units add their dep via a coordinator-merged commit at the end (or each unit appends to a `requirements.fragment.toml` that the coordinator merges).
- **Public seams.** Unit 1 (`bootstrap`) lands first and provides empty stubs for every package directory referenced by the dependency graph below, so siblings can import without breaking.
- **Dependency graph.** The plan phase will encode this; rough cut: 1 → (2, 8) → (3, 4) → 5 → (6, 7); 9 depends on 2; 10 depends on 2-8 *interfaces only*; 13 depends on 4-5; 16 depends on 3-7 + 13; 17/18 depend on 16; UI palettes (19-29) depend on the model packages they read but not on each other; 30-33 depend on 16 + 19. Units that need a dependency stub it locally (a minimal mock implementing the interface) until the providing unit lands.

## 13. End-to-end test recipe

A `pytest-qt` integration test that exercises the full stack — to be run by every worker after their unit tests pass.

```bash
# from project root
uv sync
uv run pytest tests/integration/test_e2e_smoke.py -v
```

`tests/integration/test_e2e_smoke.py` (lives in unit 1's bootstrap, expanded by units as features land):

1. Launch app via `pytest-qt` `qtbot`.
2. Create new document (Quark-style: A4, single A-Master, one auto-flowed text frame).
3. Insert ~3000 chars of mixed Latin + Arabic + Urdu text → assert no overflow on page 2 (auto-page-add).
4. Apply Heading 1 paragraph style → assert the outline palette shows it.
5. Insert an image frame, drop a fixture PNG → assert thumbnail palette regenerates.
6. Save as `.msdoc` → re-open → assert byte-identical model snapshot.
7. Export PDF → assert text is selectable in the PDF (use `pikepdf` to inspect content streams).
8. Take screenshots of (a) the canvas, (b) the pages palette, (c) the measurements palette in text-mode → save to `tests/integration/screenshots/<unit>/` for visual regression.

A unit may add steps to the smoke test but **must not remove or weaken existing steps**.

If a unit's change has no UI-observable effect (e.g., pure model refactor), it runs only unit tests + the smoke test; no UI screenshots required.

## 14. Out of scope (Phase 2 and later)

- IDML import/export.
- Books / multi-document linking, cross-doc references.
- Data-merge / variable data printing.
- Live preflight panel (basic preflight in v1 is acceptable).
- Web-publishing output (HTML/EPUB).
- Collaborative editing / CRDT.
- Plugin / scripting API (Python scripting via embedded interpreter, à la InDesign's ExtendScript).

## 15. Risks & mitigations

| Risk | Mitigation |
|---|---|
| `QTextLayout` insufficient for some Arabic shaping edge cases | Have `PyICU` ready as a fallback; fixture-driven test set covering Arabic medial/initial/final forms, Urdu Nastaʿlīq joining, Kashida justification. |
| Knuth–Plass too slow in pure Python on long stories | Mark as opt-in; document the perf cliff; identify Rust port as a Phase 2 task. |
| DOCX round-trip lossy for callouts / embeds | Round-trip markers documented; lossy features are warned about at import/export time. |
| QGraphicsView perf on documents with hundreds of pages | Implement tile-based caching of `PageItem`s; only render on-screen + 1 page either side. |
| Custom palette docking diverges from Qt's `QDockWidget` quirks | Stay with `QDockWidget` as far as it goes; document any gaps and re-evaluate before custom-rolling. |
