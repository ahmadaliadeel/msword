"""Style-editor dialog used by :mod:`msword.ui.palettes.style_sheets`.

Edits a single :class:`ParagraphStyle` (full tab set) or
:class:`CharacterStyle` (basic tab only). On accept, builds the
appropriate ``Edit*StyleCommand`` and dispatches it; cycle detection on
the "based on" picker is enforced both inline (rejecting bad picks in
the combo) and at command-redo time as a defence in depth.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from msword.commands import (
    EditCharacterStyleCommand,
    EditParagraphStyleCommand,
)
from msword.commands.base import Document as CommandDocument
from msword.model.document import Document
from msword.model.style import (
    CharacterStyle,
    ParagraphStyle,
    Style,
    StyleCycleError,
    StyleResolver,
)

_ALIGNMENTS = ["left", "right", "center", "justify", "start", "end"]
_OPENTYPE_FEATURES = [
    "liga",
    "dlig",
    "smcp",
    "onum",
    "lnum",
    "tnum",
    "pnum",
    "ss01",
    "ss02",
    "cv01",
]


def _opt_spin(value: float | None) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(-9999.0, 9999.0)
    spin.setDecimals(2)
    spin.setSpecialValueText("—")
    spin.setMinimum(-9999.0)
    if value is None:
        spin.setValue(spin.minimum())
    else:
        spin.setValue(value)
    return spin


def _spin_value(spin: QDoubleSpinBox) -> float | None:
    if spin.value() == spin.minimum():
        return None
    return float(spin.value())


def _tri(value: bool | None) -> Qt.CheckState:
    """Translate Optional[bool] into a Qt.CheckState."""
    if value is None:
        return Qt.CheckState.PartiallyChecked
    return Qt.CheckState.Checked if value else Qt.CheckState.Unchecked


def _from_tri(state: Qt.CheckState) -> bool | None:
    if state == Qt.CheckState.PartiallyChecked:
        return None
    return state == Qt.CheckState.Checked


class StyleEditorDialog(QDialog):
    """Tabbed editor for paragraph + character styles.

    Paragraph styles get the full tab set (Basic / Indents & Spacing /
    Hyphenation / OpenType). Character styles get the Basic + OpenType
    tabs only.
    """

    def __init__(
        self,
        document: Document,
        *,
        kind: str,
        style: ParagraphStyle | CharacterStyle,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if kind not in {"paragraph", "character"}:
            raise ValueError(f"kind must be paragraph|character, got {kind!r}")
        self._document = document
        self._kind = kind
        self._original_name = style.name
        self._style = style

        self.setWindowTitle(f"Edit {kind.title()} Style — {style.name}")
        self.setObjectName("StyleEditorDialog")

        outer = QVBoxLayout(self)
        self._tabs = QTabWidget(self)
        outer.addWidget(self._tabs)

        header = QWidget(self)
        hl = QFormLayout(header)
        self._name_edit = QLineEdit(style.name)
        hl.addRow("Name:", self._name_edit)

        self._based_on = QComboBox()
        self._based_on.addItem("(none)", userData=None)
        self._populate_based_on(style)
        hl.addRow("Based on:", self._based_on)

        outer.insertWidget(0, header)

        self._build_basic_tab()
        if kind == "paragraph":
            self._build_indents_tab()
            self._build_hyphenation_tab()
        self._build_opentype_tab()

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        outer.addWidget(self._buttons)

    # ------------------------------------------------------------------
    # tab builders
    # ------------------------------------------------------------------
    def _build_basic_tab(self) -> None:
        tab = QWidget()
        form = QFormLayout(tab)
        self._font_family = QLineEdit(getattr(self._style, "font_family", None) or "")
        self._font_family.setPlaceholderText("(inherit)")
        form.addRow("Font family:", self._font_family)

        self._font_size = _opt_spin(getattr(self._style, "font_size_pt", None))
        form.addRow("Font size (pt):", self._font_size)

        if self._kind == "paragraph":
            ps = cast(ParagraphStyle, self._style)
            self._leading = _opt_spin(ps.leading_pt)
            form.addRow("Leading (pt):", self._leading)
            self._alignment = QComboBox()
            self._alignment.addItem("(inherit)", userData=None)
            for a in _ALIGNMENTS:
                self._alignment.addItem(a, userData=a)
            if ps.alignment is not None:
                idx = self._alignment.findData(ps.alignment)
                if idx >= 0:
                    self._alignment.setCurrentIndex(idx)
            form.addRow("Alignment:", self._alignment)
        else:
            cs = cast(CharacterStyle, self._style)
            self._bold = QCheckBox()
            self._bold.setTristate(True)
            self._bold.setCheckState(_tri(cs.bold))
            form.addRow("Bold:", self._bold)
            self._italic = QCheckBox()
            self._italic.setTristate(True)
            self._italic.setCheckState(_tri(cs.italic))
            form.addRow("Italic:", self._italic)
            self._underline = QCheckBox()
            self._underline.setTristate(True)
            self._underline.setCheckState(_tri(cs.underline))
            form.addRow("Underline:", self._underline)
            self._strike = QCheckBox()
            self._strike.setTristate(True)
            self._strike.setCheckState(_tri(cs.strike))
            form.addRow("Strikethrough:", self._strike)
            self._tracking = _opt_spin(cs.tracking)
            form.addRow("Tracking:", self._tracking)
            self._baseline_shift = _opt_spin(cs.baseline_shift_pt)
            form.addRow("Baseline shift (pt):", self._baseline_shift)

        self._tabs.addTab(tab, "Basic")

    def _build_indents_tab(self) -> None:
        ps = cast(ParagraphStyle, self._style)
        tab = QWidget()
        form = QFormLayout(tab)
        self._space_before = _opt_spin(ps.space_before_pt)
        form.addRow("Space before (pt):", self._space_before)
        self._space_after = _opt_spin(ps.space_after_pt)
        form.addRow("Space after (pt):", self._space_after)
        self._first_indent = _opt_spin(ps.first_indent_pt)
        form.addRow("First-line indent (pt):", self._first_indent)
        self._left_indent = _opt_spin(ps.left_indent_pt)
        form.addRow("Left indent (pt):", self._left_indent)
        self._right_indent = _opt_spin(ps.right_indent_pt)
        form.addRow("Right indent (pt):", self._right_indent)
        self._tabs.addTab(tab, "Indents & Spacing")

    def _build_hyphenation_tab(self) -> None:
        ps = cast(ParagraphStyle, self._style)
        tab = QWidget()
        form = QFormLayout(tab)
        self._hyphenate = QCheckBox()
        self._hyphenate.setTristate(True)
        self._hyphenate.setCheckState(_tri(ps.hyphenate))
        form.addRow("Hyphenate:", self._hyphenate)
        self._tabs.addTab(tab, "Hyphenation")

    def _build_opentype_tab(self) -> None:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.addWidget(QLabel("OpenType features:"))
        self._opentype_list = QListWidget()
        existing = getattr(self._style, "opentype_features", None)
        active: set[str] = set(existing) if existing else set()
        for feat in _OPENTYPE_FEATURES:
            item = QListWidgetItem(feat)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if feat in active else Qt.CheckState.Unchecked
            )
            self._opentype_list.addItem(item)
        v.addWidget(self._opentype_list)
        self._tabs.addTab(tab, "OpenType")

    # ------------------------------------------------------------------
    # based-on combo
    # ------------------------------------------------------------------
    def _populate_based_on(self, style: ParagraphStyle | CharacterStyle) -> None:
        if self._kind == "paragraph":
            styles: list[Style] = cast(
                list[Style], self._document.paragraph_styles
            )
        else:
            styles = cast(list[Style], self._document.character_styles)

        for other in sorted(styles, key=lambda s: s.name):
            if other.name == style.name:
                continue
            if StyleResolver.detect_cycle(styles, style.name, other.name):
                continue
            self._based_on.addItem(other.name, userData=other.name)
        if style.based_on is not None:
            idx = self._based_on.findData(style.based_on)
            if idx >= 0:
                self._based_on.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # accept -> build edited style + dispatch command
    # ------------------------------------------------------------------
    def _collect_opentype(self) -> frozenset[str]:
        active: set[str] = set()
        for i in range(self._opentype_list.count()):
            item = self._opentype_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                active.add(item.text())
        return frozenset(active)

    def _collect_paragraph(self) -> ParagraphStyle:
        ps = cast(ParagraphStyle, self._style)
        based_on_data = self._based_on.currentData()
        based_on: str | None = based_on_data if isinstance(based_on_data, str) else None
        alignment_data = self._alignment.currentData()
        alignment: Any = alignment_data if isinstance(alignment_data, str) else None
        features = self._collect_opentype()
        return replace(
            ps,
            name=self._name_edit.text().strip() or ps.name,
            based_on=based_on,
            font_family=self._font_family.text() or None,
            font_size_pt=_spin_value(self._font_size),
            leading_pt=_spin_value(self._leading),
            alignment=alignment,
            space_before_pt=_spin_value(self._space_before),
            space_after_pt=_spin_value(self._space_after),
            first_indent_pt=_spin_value(self._first_indent),
            left_indent_pt=_spin_value(self._left_indent),
            right_indent_pt=_spin_value(self._right_indent),
            hyphenate=_from_tri(self._hyphenate.checkState()),
            opentype_features=features if features else None,
        )

    def _collect_character(self) -> CharacterStyle:
        cs = cast(CharacterStyle, self._style)
        based_on_data = self._based_on.currentData()
        based_on: str | None = based_on_data if isinstance(based_on_data, str) else None
        features = self._collect_opentype()
        return replace(
            cs,
            name=self._name_edit.text().strip() or cs.name,
            based_on=based_on,
            font_family=self._font_family.text() or None,
            font_size_pt=_spin_value(self._font_size),
            bold=_from_tri(self._bold.checkState()),
            italic=_from_tri(self._italic.checkState()),
            underline=_from_tri(self._underline.checkState()),
            strike=_from_tri(self._strike.checkState()),
            tracking=_spin_value(self._tracking),
            baseline_shift_pt=_spin_value(self._baseline_shift),
            opentype_features=features if features else None,
        )

    def _on_accept(self) -> None:
        cmd_doc = cast(CommandDocument, self._document)
        try:
            if self._kind == "paragraph":
                EditParagraphStyleCommand(
                    document=cmd_doc,
                    name=self._original_name,
                    new_style=self._collect_paragraph(),
                ).redo()
            else:
                EditCharacterStyleCommand(
                    document=cmd_doc,
                    name=self._original_name,
                    new_style=self._collect_character(),
                ).redo()
        except StyleCycleError as exc:
            QMessageBox.critical(self, "Cycle in style hierarchy", str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.accept()
