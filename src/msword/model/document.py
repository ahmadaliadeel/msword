"""Document — the root container of the model tree.

Per spec §3 (Document-MVC) every open file is one `Document` instance:
  * It is the *authoritative state* — views subscribe and re-render on
    `changed`, never owning state themselves.
  * All mutations go through Commands on the QUndoStack (unit-9). The model
    methods on this class are the *primitive operations* those Commands wrap;
    they emit the right notifications but do not push to any undo stack.
  * The package is pure data — `QObject` is used solely to host `Signal`s for
    the change bus, as allowed by the unit-2 anchor invariants.

Per spec §4 the Document owns: meta, color profiles, color swatches,
paragraph/character/object styles, master pages, pages, stories, and an
asset registry. Several of those collections are stubbed here as plain
lists; the concrete element types land in later units (styles in unit-8,
stories in unit-4, color profiles/swatches in unit-8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Signal

from msword.model.asset import AssetRegistry
from msword.model.master_page import MasterPage
from msword.model.page import Page


@dataclass(slots=True)
class DocumentMeta:
    """Top-of-document metadata — title / author / locale / language.

    `locale` follows BCP-47 (e.g. "en-US", "ar-SA", "ur-PK"). `default_language`
    is the language tag inherited by runs that don't override it (spec §4.2).
    """

    title: str = ""
    author: str = ""
    locale: str = "en-US"
    default_language: str = "en"

    def to_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "author": self.author,
            "locale": self.locale,
            "default_language": self.default_language,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentMeta:
        return cls(
            title=str(data.get("title", "")),
            author=str(data.get("author", "")),
            locale=str(data.get("locale", "en-US")),
            default_language=str(data.get("default_language", "en")),
        )


class Document(QObject):
    """Root container: owns pages, master pages, styles, stories, assets.

    Signals:
        changed:           emitted on *any* mutation (umbrella for views that
                           don't care about the specific change kind).
        page_added(int):   index of newly-added page.
        page_removed(int): index from which a page was removed.
        page_reordered(int, int): old_index, new_index.
        master_page_added(str):   id of added master.
        master_page_removed(str): id of removed master.
    """

    changed = Signal()
    page_added = Signal(int)
    page_removed = Signal(int)
    page_reordered = Signal(int, int)
    master_page_added = Signal(str)
    master_page_removed = Signal(str)
    selection_changed = Signal()
    caret_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.meta: DocumentMeta = DocumentMeta()
        # Stubs: concrete element types land in later units.
        self.color_profiles: list[Any] = []  # stub: replaced by unit-8
        self.color_swatches: list[Any] = []  # stub: replaced by unit-8
        self.paragraph_styles: list[Any] = []  # stub: replaced by unit-8
        self.character_styles: list[Any] = []  # stub: replaced by unit-8
        self.object_styles: list[Any] = []  # stub: replaced by unit-8
        self.master_pages: list[MasterPage] = []
        self.pages: list[Page] = []
        self.stories: list[Any] = []  # stub: replaced by unit-4
        self.assets: AssetRegistry = AssetRegistry(self)
        # UI/session state — used by the measurements palette and the canvas.
        self.zoom: float = 1.0
        self.view_mode: str = "paged"
        self.aspect_locks: dict[str, bool] = {}
        self.baseline_grid_overrides: dict[str, bool] = {}
        self.active_paragraph_style: str | None = None
        # Selection: lazy import to avoid a circular dependency in the model
        # package; populated as the user interacts with the canvas.
        from msword.model.selection import Selection as _Selection

        self.selection: Any = _Selection()
        # Undo stack: provide a minimal duck-typed stub so views/tests can
        # call `.push(...)` and inspect `.last` without explicit wiring.
        # Production code attaches a real `msword.commands.UndoStack`.
        class _StubStack:
            def __init__(self) -> None:
                self.commands: list[Any] = []

            def push(self, cmd: Any) -> None:
                self.commands.append(cmd)

            @property
            def last(self) -> Any:
                return self.commands[-1] if self.commands else None

        self.undo_stack: Any = _StubStack()
        # Display title used by the main window.
        self.title: str = "Untitled"

    def display_title(self) -> str:
        """Title shown in the window chrome."""
        return self.title

    def find_color_profile(self, name: str) -> Any:
        """Return the registered profile with `name`, or None."""
        return next((p for p in self.color_profiles if p.name == name), None)

    def find_color_swatch(self, name: str) -> Any:
        """Return the registered swatch with `name`, or None."""
        return next((s for s in self.color_swatches if s.name == name), None)

    def set_selection(self, selection: Any) -> None:
        """Replace the current selection and emit `selection_changed`.

        Also emits `caret_changed` when the caret has moved (different
        `caret_run` or `caret_frame`).
        """
        prev = self.selection
        self.selection = selection
        self.selection_changed.emit()
        prev_caret = (getattr(prev, "caret_run", None), getattr(prev, "caret_frame", None))
        new_caret = (getattr(selection, "caret_run", None), getattr(selection, "caret_frame", None))
        if prev_caret != new_caret:
            self.caret_changed.emit()

    def find_frame(self, frame_id: str) -> Any:
        """Return the frame with the given id from any page, or `None`."""
        for page in self.pages:
            for frame in page.frames:
                if getattr(frame, "id", None) == frame_id:
                    return frame
        return None

    def add_frame(self, page_id: str, frame: Any) -> None:
        """Append `frame` to the page identified by `page_id`."""
        page = self._page_by_id(page_id)
        page.frames.append(frame)
        self.changed.emit()

    def remove_frame(self, page_id: str, frame_id: str) -> Any:
        """Remove and return the frame `frame_id` from `page_id`."""
        page = self._page_by_id(page_id)
        for i, frame in enumerate(page.frames):
            if getattr(frame, "id", None) == frame_id:
                removed = page.frames.pop(i)
                self.changed.emit()
                return removed
        raise KeyError(f"frame {frame_id!r} not found on page {page_id!r}")

    def get_frame(self, page_id: str, frame_id: str) -> Any:
        """Return the frame `frame_id` from page `page_id`."""
        page = self._page_by_id(page_id)
        for frame in page.frames:
            if getattr(frame, "id", None) == frame_id:
                return frame
        raise KeyError(f"frame {frame_id!r} not found on page {page_id!r}")

    def _page_by_id(self, page_id: str) -> Page:
        for page in self.pages:
            if page.id == page_id:
                return page
        raise KeyError(f"page {page_id!r} not found")

    # ----- pages -----------------------------------------------------------

    def add_page(self, page: Page, index: int | None = None) -> int:
        """Insert `page`; append if `index` is None. Returns the final index."""
        if index is None:
            index = len(self.pages)
        if not 0 <= index <= len(self.pages):
            raise IndexError(f"page index {index} out of range [0, {len(self.pages)}]")
        self.pages.insert(index, page)
        self.page_added.emit(index)
        self.changed.emit()
        return index

    def remove_page(self, index: int) -> Page:
        """Remove and return the page at `index`."""
        if not 0 <= index < len(self.pages):
            raise IndexError(f"page index {index} out of range [0, {len(self.pages)})")
        page = self.pages.pop(index)
        self.page_removed.emit(index)
        self.changed.emit()
        return page

    def move_page(self, old_index: int, new_index: int) -> None:
        """Move a page from `old_index` to `new_index`.

        `new_index` is interpreted in the *post-removal* coordinate space
        (the conventional list-reorder convention), so moving from 0 to 2 in
        a 3-page document leaves the page at the last slot.
        """
        if not 0 <= old_index < len(self.pages):
            raise IndexError(
                f"old page index {old_index} out of range [0, {len(self.pages)})"
            )
        if not 0 <= new_index < len(self.pages):
            raise IndexError(
                f"new page index {new_index} out of range [0, {len(self.pages)})"
            )
        if old_index == new_index:
            return
        page = self.pages.pop(old_index)
        self.pages.insert(new_index, page)
        self.page_reordered.emit(old_index, new_index)
        self.changed.emit()

    # ----- styles ----------------------------------------------------------

    def find_paragraph_style(self, name: str) -> Any:
        """Return the paragraph style named `name`, or `None` if absent."""
        return next((s for s in self.paragraph_styles if s.name == name), None)

    def find_character_style(self, name: str) -> Any:
        """Return the character style named `name`, or `None` if absent."""
        return next((s for s in self.character_styles if s.name == name), None)

    # ----- stories ---------------------------------------------------------

    def find_story(self, story_id: str) -> Any | None:
        """Return the story whose `id` matches `story_id`, else `None`."""
        for story in self.stories:
            if getattr(story, "id", None) == story_id:
                return story
        return None

    # ----- master pages ----------------------------------------------------

    def add_master_page(self, master: MasterPage) -> None:
        if any(m.id == master.id for m in self.master_pages):
            raise ValueError(f"master page id {master.id!r} already registered")
        self.master_pages.append(master)
        self.master_page_added.emit(master.id)
        self.changed.emit()

    def remove_master_page(self, master_id: str) -> MasterPage:
        for i, master in enumerate(self.master_pages):
            if master.id == master_id:
                del self.master_pages[i]
                self.master_page_removed.emit(master_id)
                self.changed.emit()
                return master
        raise KeyError(f"master page id {master_id!r} not found")

    # ----- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly snapshot of the document.

        Asset *bytes* are not embedded — only their metadata. The full
        `.msdoc` writer (unit-10) pairs this dict with the asset payloads.
        """
        return {
            "meta": self.meta.to_dict(),
            "color_profiles": [_to_jsonable(p) for p in self.color_profiles],
            "color_swatches": [_to_jsonable(s) for s in self.color_swatches],
            "paragraph_styles": [_to_jsonable(s) for s in self.paragraph_styles],
            "character_styles": [_to_jsonable(s) for s in self.character_styles],
            "object_styles": [_to_jsonable(s) for s in self.object_styles],
            "master_pages": [m.to_dict() for m in self.master_pages],
            "pages": [p.to_dict() for p in self.pages],
            "stories": [_to_jsonable(s) for s in self.stories],
            "assets": [a.to_dict() for a in self.assets],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], parent: QObject | None = None) -> Document:
        doc = cls(parent)
        doc.meta = DocumentMeta.from_dict(data.get("meta", {}))
        doc.color_profiles = list(data.get("color_profiles", []))
        doc.color_swatches = list(data.get("color_swatches", []))
        doc.paragraph_styles = list(data.get("paragraph_styles", []))
        doc.character_styles = list(data.get("character_styles", []))
        doc.object_styles = list(data.get("object_styles", []))
        doc.master_pages = [MasterPage.from_dict(m) for m in data.get("master_pages", [])]
        doc.pages = [Page.from_dict(p) for p in data.get("pages", [])]
        doc.stories = list(data.get("stories", []))
        # Asset *bytes* are not in the JSON snapshot — see `to_dict`. The full
        # reader (unit-10) populates `doc.assets` from the ZIP payload.
        return doc


def _to_jsonable(value: Any) -> Any:
    """Serialize a registry entry (style, swatch, profile, story) to JSON.

    Prefers an explicit ``to_dict()`` when defined; otherwise walks plain
    dataclasses. Anything else round-trips unchanged so test stubs stay
    transparent.
    """
    from dataclasses import asdict, is_dataclass

    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return value
