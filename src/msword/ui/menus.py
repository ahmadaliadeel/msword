"""Quark-style menu bar for msword.

Per spec sections 9 and 12 (unit #19), the application shell is a
QuarkXPress-style menu bar — *not* a Word ribbon. Every menu action issues a
:class:`Command` that is pushed onto an :class:`UndoStack`. While units #2
(model-document-core) and #9 (commands-and-undo) are still in flight, this unit
provides minimal in-tree stubs for ``Document``, ``UndoStack``, and a
``LogActionCommand`` so the menu wiring is exercisable end-to-end. Once the
real modules land, callers can swap them in by passing concrete instances to
:class:`~msword.ui.main_window.MainWindow`.

Menu structure follows spec §9:

* File: New, Open, Open Recent, Save, Save As, Close, Export PDF, Export
  PDF/X, Import DOCX, Export DOCX, Quit.
* Edit: Undo, Redo, Cut, Copy, Paste, Paste in Place, Select All, Deselect,
  Find, Replace, Preferences.
* Style: Paragraph Styles, Character Styles, Object Styles, Edit Style
  Sheets, Apply Style.
* Item: Frame Type (sub), Lock/Unlock, Send to Front, Bring Forward, Send
  Backward, Send to Back, Group, Ungroup, Linker tools, Step and Repeat.
* Page: Insert, Duplicate, Delete, Move, Page Properties, Master Page Apply,
  Manage Master Pages.
* Layout: Layout Setup, Page Setup, Margins & Columns, Baseline Grid, Bleed
  and Slug.
* View: Paged (radio), Flow (radio), Zoom (sub), Show Guides, Show Baseline
  Grid, Show Invisibles, Show Linker.
* Utilities: Spell-check, Hyphenation, Glyphs Palette, Suitcase, Color
  Profiles.
* Window: Document tabs, Palette toggles.
* Help: About, Documentation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Protocol

from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMenu, QMenuBar, QWidget

# ---------------------------------------------------------------------------
# Stubs for Document / Command / UndoStack
#
# These intentionally have tiny surface areas — just enough to wire menu
# actions end-to-end. They will be superseded by the real implementations
# from units #2 and #9.
# ---------------------------------------------------------------------------


class Document:
    """Minimal document stub.

    Real implementation lands with unit #2 (``model-document-core``). This
    stub exposes the bare minimum that the menu/main-window wiring needs:
    a mutable title used to drive the window-title format ``msword — {title}``.
    """

    def __init__(self, title: str = "Untitled") -> None:
        self.title = title

    def display_title(self) -> str:
        return self.title


class Command(Protocol):
    """Command pattern protocol — see spec §3.

    Real ``Command`` base class lands with unit #9. We define a Protocol so
    ``UndoStack`` accepts both this stub's :class:`LogActionCommand` and any
    future real command type.
    """

    text: str

    def redo(self) -> None: ...

    def undo(self) -> None: ...


@dataclass
class LogActionCommand:
    """Stub command that records the menu action label.

    ``redo`` and ``undo`` simply append to a shared log list, which gives
    tests an observable side-effect without needing the full command
    machinery from unit #9.
    """

    text: str
    log: list[str] = field(default_factory=list)

    def redo(self) -> None:
        self.log.append(f"redo:{self.text}")

    def undo(self) -> None:
        self.log.append(f"undo:{self.text}")


class UndoStack:
    """In-tree stub of ``QUndoStack``-like behaviour.

    Real implementation lands with unit #9. This stub keeps a simple list of
    pushed commands and an index so ``undo`` / ``redo`` work for tests. Push
    invokes ``redo`` (matching ``QUndoStack`` semantics) so callers don't
    have to do it manually.
    """

    def __init__(self) -> None:
        self._commands: list[Command] = []
        self._index: int = 0  # number of currently-applied commands

    def push(self, command: Command) -> None:
        # Drop any redo tail.
        del self._commands[self._index :]
        self._commands.append(command)
        command.redo()
        self._index += 1

    def undo(self) -> None:
        if self._index == 0:
            return
        self._index -= 1
        self._commands[self._index].undo()

    def redo(self) -> None:
        if self._index >= len(self._commands):
            return
        self._commands[self._index].redo()
        self._index += 1

    def can_undo(self) -> bool:
        return self._index > 0

    def can_redo(self) -> bool:
        return self._index < len(self._commands)

    def count(self) -> int:
        return len(self._commands)


# ---------------------------------------------------------------------------
# Menu spec — declarative, used to drive both wiring and tests.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActionSpec:
    """Declarative description of a menu action.

    ``shortcut`` is a Qt-parsable key sequence string (e.g. ``"Ctrl+S"``).
    ``submenu`` flags the entry as a submenu (its label still appears in the
    parent). ``checkable`` and ``radio_group`` describe togglable / mutually
    exclusive entries (View → Paged / Flow).
    """

    label: str
    shortcut: str | None = None
    tooltip: str | None = None
    submenu: bool = False
    checkable: bool = False
    radio_group: str | None = None
    checked: bool = False


@dataclass(frozen=True)
class MenuSpec:
    title: str
    actions: tuple[ActionSpec, ...]


# Spec §9 — full menu structure. Order matters and is asserted by tests.
MENU_SPECS: tuple[MenuSpec, ...] = (
    MenuSpec(
        "File",
        (
            ActionSpec("New", "Ctrl+N", "Create a new document"),
            ActionSpec("Open…", "Ctrl+O", "Open an existing document"),
            ActionSpec("Open Recent", tooltip="Recently opened documents", submenu=True),
            ActionSpec("Save", "Ctrl+S", "Save the current document"),
            ActionSpec("Save As…", "Ctrl+Shift+S", "Save the document under a new name"),
            ActionSpec("Close", "Ctrl+W", "Close the current document"),
            ActionSpec("Export PDF…", "Ctrl+Shift+P", "Export to vector PDF"),
            ActionSpec("Export PDF/X…", tooltip="Export to PDF/X-1a or PDF/X-4"),
            ActionSpec("Import DOCX…", tooltip="Import a Word document"),
            ActionSpec("Export DOCX…", tooltip="Export to a Word document"),
            ActionSpec("Quit", "Ctrl+Q", "Quit msword"),
        ),
    ),
    MenuSpec(
        "Edit",
        (
            ActionSpec("Undo", "Ctrl+Z", "Undo the last action"),
            ActionSpec("Redo", "Ctrl+Shift+Z", "Redo the last undone action"),
            ActionSpec("Cut", "Ctrl+X", "Cut the selection"),
            ActionSpec("Copy", "Ctrl+C", "Copy the selection"),
            ActionSpec("Paste", "Ctrl+V", "Paste the clipboard"),
            ActionSpec("Paste in Place", "Ctrl+Alt+Shift+V", "Paste at the original position"),
            ActionSpec("Select All", "Ctrl+A", "Select everything"),
            ActionSpec("Deselect", "Ctrl+Shift+A", "Clear the selection"),
            ActionSpec("Find…", "Ctrl+F", "Find text"),
            ActionSpec("Replace…", "Ctrl+H", "Find and replace text"),
            ActionSpec("Preferences…", "Ctrl+,", "Application preferences"),
        ),
    ),
    MenuSpec(
        "Style",
        (
            ActionSpec("Paragraph Styles", tooltip="Manage paragraph styles"),
            ActionSpec("Character Styles", tooltip="Manage character styles"),
            ActionSpec("Object Styles", tooltip="Manage object (frame) styles"),
            ActionSpec("Edit Style Sheets…", tooltip="Edit all style sheets"),
            ActionSpec("Apply Style…", tooltip="Apply a style by name"),
        ),
    ),
    MenuSpec(
        "Item",
        (
            ActionSpec("Frame Type", tooltip="Change the frame type", submenu=True),
            ActionSpec("Lock/Unlock", "Ctrl+L", "Lock or unlock the selected item"),
            ActionSpec("Send to Front", "Ctrl+Shift+]", "Send the selection to the front"),
            ActionSpec("Bring Forward", "Ctrl+]", "Bring the selection forward one level"),
            ActionSpec("Send Backward", "Ctrl+[", "Send the selection back one level"),
            ActionSpec("Send to Back", "Ctrl+Shift+[", "Send the selection to the back"),
            ActionSpec("Group", "Ctrl+G", "Group the selected items"),
            ActionSpec("Ungroup", "Ctrl+Shift+G", "Ungroup the selected group"),
            ActionSpec("Linker tools", tooltip="Frame linker / unlinker tools"),
            ActionSpec("Step and Repeat…", tooltip="Step and repeat the selection"),
        ),
    ),
    MenuSpec(
        "Page",
        (
            ActionSpec("Insert…", tooltip="Insert a new page"),
            ActionSpec("Duplicate", tooltip="Duplicate the current page"),
            ActionSpec("Delete", tooltip="Delete the current page"),
            ActionSpec("Move…", tooltip="Move the current page"),
            ActionSpec("Page Properties…", tooltip="Edit page properties"),
            ActionSpec("Master Page Apply…", tooltip="Apply a master page"),
            ActionSpec("Manage Master Pages…", tooltip="Edit master pages"),
        ),
    ),
    MenuSpec(
        "Layout",
        (
            ActionSpec("Layout Setup…", tooltip="Configure the layout"),
            ActionSpec("Page Setup…", tooltip="Page size and orientation"),
            ActionSpec("Margins & Columns…", tooltip="Edit margins and columns"),
            ActionSpec("Baseline Grid…", tooltip="Configure the baseline grid"),
            ActionSpec("Bleed and Slug…", tooltip="Configure bleed and slug"),
        ),
    ),
    MenuSpec(
        "View",
        (
            ActionSpec(
                "Paged",
                tooltip="Paged view (page strip with spreads)",
                checkable=True,
                radio_group="view-mode",
                checked=True,
            ),
            ActionSpec(
                "Flow",
                tooltip="Flow view (continuous, paginated)",
                checkable=True,
                radio_group="view-mode",
            ),
            ActionSpec("Zoom", tooltip="Zoom level", submenu=True),
            ActionSpec(
                "Show Guides",
                tooltip="Toggle margin/column guides",
                checkable=True,
                checked=True,
            ),
            ActionSpec("Show Baseline Grid", tooltip="Toggle the baseline grid", checkable=True),
            ActionSpec("Show Invisibles", tooltip="Toggle invisible characters", checkable=True),
            ActionSpec("Show Linker", tooltip="Toggle frame-link arrows", checkable=True),
        ),
    ),
    MenuSpec(
        "Utilities",
        (
            ActionSpec("Spell-check…", "F7", "Run the spell checker"),
            ActionSpec("Hyphenation…", tooltip="Hyphenation settings"),
            ActionSpec("Glyphs Palette", tooltip="Open the glyph picker"),
            ActionSpec("Suitcase…", tooltip="Font suitcase / font manager"),
            ActionSpec("Color Profiles…", tooltip="ICC color profile manager"),
        ),
    ),
    MenuSpec(
        "Window",
        (
            ActionSpec("Document tabs", tooltip="Open document tabs", submenu=True),
            ActionSpec("Palette toggles", tooltip="Toggle dockable palettes", submenu=True),
        ),
    ),
    MenuSpec(
        "Help",
        (
            ActionSpec("About msword", tooltip="About this application"),
            ActionSpec("Documentation", "F1", "Open the documentation"),
        ),
    ),
)


# ---------------------------------------------------------------------------
# MenuBar
# ---------------------------------------------------------------------------


# Type alias for a callback that constructs a Command from an action label.
CommandFactory = Callable[[str], Command]


def _default_command_factory(label: str) -> Command:
    return LogActionCommand(text=label)


class MenuBar(QMenuBar):
    """Quark-style menu bar wired to an :class:`UndoStack`.

    Each leaf action is connected to a slot that builds a ``Command`` (via
    ``command_factory``) and pushes it onto ``undo_stack``. The Edit → Undo
    and Edit → Redo entries are special-cased to call ``undo_stack.undo()``
    and ``undo_stack.redo()`` directly. The File → New action invokes
    ``new_document_callback`` (typically ``MainWindow.on_new_document``).
    """

    def __init__(
        self,
        undo_stack: UndoStack,
        *,
        new_document_callback: Callable[[], None] | None = None,
        command_factory: CommandFactory | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._undo_stack = undo_stack
        self._new_document_callback = new_document_callback
        self._command_factory = command_factory or _default_command_factory
        # ``actions_by_label`` indexes only leaf actions; submenu entries
        # are not pushed onto the undo stack and are not included here.
        self.actions_by_label: dict[str, QAction] = {}
        self.menus_by_title: dict[str, QMenu] = {}
        self._radio_groups: dict[str, QActionGroup] = {}
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        for menu_spec in MENU_SPECS:
            menu = self.addMenu(menu_spec.title)
            assert menu is not None  # addMenu(str) always returns a QMenu
            self.menus_by_title[menu_spec.title] = menu
            for action_spec in menu_spec.actions:
                self._add_action(menu, action_spec)

    def _add_action(self, menu: QMenu, spec: ActionSpec) -> None:
        if spec.submenu:
            # A submenu placeholder. Real population happens in the units
            # that own the relevant feature (e.g. Open Recent in unit #10).
            sub = menu.addMenu(spec.label)
            assert sub is not None
            if spec.tooltip is not None:
                sub.setToolTip(spec.tooltip)
            return

        action = QAction(spec.label, self)
        if spec.shortcut is not None:
            action.setShortcut(QKeySequence(spec.shortcut))
        if spec.tooltip is not None:
            action.setToolTip(spec.tooltip)
            action.setStatusTip(spec.tooltip)
        if spec.checkable:
            action.setCheckable(True)
            action.setChecked(spec.checked)
        if spec.radio_group is not None:
            group = self._radio_groups.setdefault(
                spec.radio_group, QActionGroup(self)
            )
            group.setExclusive(True)
            action.setActionGroup(group)

        menu.addAction(action)
        self.actions_by_label[spec.label] = action
        self._connect(action, spec)

    def _connect(self, action: QAction, spec: ActionSpec) -> None:
        label = spec.label
        if label == "Undo":
            # Defer attribute lookup to trigger time so tests (and downstream
            # code) can swap the bound method on the stack instance.
            action.triggered.connect(lambda _checked=False: self._undo_stack.undo())
            return
        if label == "Redo":
            action.triggered.connect(lambda _checked=False: self._undo_stack.redo())
            return
        if label == "New" and self._new_document_callback is not None:
            cb = self._new_document_callback
            action.triggered.connect(lambda _checked=False: cb())
            return

        # Default: push a Command on the undo stack. Quit / window-close
        # behaviour stays a main-window responsibility — this only logs the
        # action for traceability.
        factory = self._command_factory
        stack = self._undo_stack
        action.triggered.connect(
            lambda _checked=False, lbl=label: stack.push(factory(lbl))
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def menu_titles(self) -> list[str]:
        return [m.title for m in MENU_SPECS]

    def labels_for(self, menu_title: str) -> list[str]:
        for m in MENU_SPECS:
            if m.title == menu_title:
                return [a.label for a in m.actions]
        raise KeyError(menu_title)

    def all_action_labels(self) -> Iterable[str]:
        return self.actions_by_label.keys()
