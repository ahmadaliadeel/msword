# mypy: disable-error-code="call-arg, attr-defined, arg-type, assignment, no-any-return, union-attr"
"""Style-editor dialog used by :mod:`msword.ui.palettes.style_sheets`.

Edits a single :class:`ParagraphStyle` (full tab set) or
:class:`CharacterStyle` (basic tab only). On accept, builds the
appropriate ``Edit*StyleCommand`` and dispatches it; cycle detection on
the "based on" picker is enforced both inline (rejecting bad picks in
the combo) and at command-redo time as a defence in depth.
"""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from msword.commands import (
    EditCharacterStyleCommand,
    EditParagraphStyleCommand,
)
from msword.model.document import Document
from msword.model.style import (
    CharacterStyle,
    ParagraphStyle,
    StyleCycleError,
    StyleResolver,
)

_ALIGNMENTS = ["left", "right", "center", "justify"]
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
        spin.setValue(spin.minimum())  # shows "—"
    else:
        spin.setValue(value)
    return spin


def _spin_value(spin: QDoubleSpinBox) -> float | None:
    if spin.value() == spin.minimum():
        return None
    return float(spin.value())


class StyleEditorDialog(QDialog):
    """Tabbed editor for paragraph + character styles.

    Paragraph styles get the full tab set (Basic / Indents & Spacing /
    Tabs / Hyphenation / OpenType / Paragraph Rules). Character styles
    get the Basic tab only.
    """

    def __init__(
        self,
        document: Document,
        *,
        kind: str,  # "paragraph" | "character"
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

        # name + based-on header (always visible)
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
            self._build_tabs_tab()
            self._build_hyphenation_tab()
            self._build_opentype_tab(paragraph=True)
            self._build_paragraph_rules_tab()
        else:
            self._build_opentype_tab(paragraph=False)

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

        self._font_size = _opt_spin(getattr(self._style, "font_size", None))
        form.addRow("Font size (pt):", self._font_size)

        if self._kind == "paragraph":
            ps = cast(ParagraphStyle, self._style)
            self._leading = _opt_spin(ps.leading)
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
            self._baseline_shift = _opt_spin(cs.baseline_shift)
            form.addRow("Baseline shift:", self._baseline_shift)

        self._tabs.addTab(tab, "Basic")

    def _build_indents_tab(self) -> None:
        ps = cast(ParagraphStyle, self._style)
        tab = QWidget()
        form = QFormLayout(tab)
        self._space_before = _opt_spin(ps.space_before)
        form.addRow("Space before:", self._space_before)
        self._space_after = _opt_spin(ps.space_after)
        form.addRow("Space after:", self._space_after)
        self._first_line_indent = _opt_spin(ps.first_line_indent)
        form.addRow("First-line indent:", self._first_line_indent)
        self._left_indent = _opt_spin(ps.left_indent)
        form.addRow("Left indent:", self._left_indent)
        self._right_indent = _opt_spin(ps.right_indent)
        form.addRow("Right indent:", self._right_indent)
        self._tabs.addTab(tab, "Indents & Spacing")

    def _build_tabs_tab(self) -> None:
        ps = cast(ParagraphStyle, self._style)
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.addWidget(QLabel("Tab stops (position pt, alignment):"))
        self._tab_list = QListWidget()
        for pos, align in ps.tabs:
            self._tab_list.addItem(f"{pos:.2f}\t{align}")
        v.addWidget(self._tab_list)

        row = QHBoxLayout()
        self._tab_pos = QDoubleSpinBox()
        self._tab_pos.setRange(0.0, 9999.0)
        self._tab_align = QComboBox()
        self._tab_align.addItems(["left", "right", "center", "decimal"])
        add = QPushButton("Add")
        rem = QPushButton("Remove")
        row.addWidget(self._tab_pos)
        row.addWidget(self._tab_align)
        row.addWidget(add)
        row.addWidget(rem)
        v.addLayout(row)

        add.clicked.connect(self._on_add_tab)
        rem.clicked.connect(self._on_remove_tab)
        self._tabs.addTab(tab, "Tabs")

    def _on_add_tab(self) -> None:
        pos = self._tab_pos.value()
        align = self._tab_align.currentText()
        self._tab_list.addItem(f"{pos:.2f}\t{align}")

    def _on_remove_tab(self) -> None:
        for item in self._tab_list.selectedItems():
            self._tab_list.takeItem(self._tab_list.row(item))

    def _build_hyphenation_tab(self) -> None:
        ps = cast(ParagraphStyle, self._style)
        tab = QWidget()
        form = QFormLayout(tab)
        self._hyphenate = QCheckBox()
        self._hyphenate.setTristate(True)
        self._hyphenate.setCheckState(_tri(ps.hyphenate))
        form.addRow("Hyphenate:", self._hyphenate)
        self._hyphenation_zone = _opt_spin(ps.hyphenation_zone)
        form.addRow("Hyphenation zone:", self._hyphenation_zone)
        self._tabs.addTab(tab, "Hyphenation")

    def _build_opentype_tab(self, *, paragraph: bool) -> None:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.addWidget(QLabel("OpenType features:"))
        self._opentype_list = QListWidget()
        active = set(getattr(self._style, "opentype_features", set()) or set())
        for feat in _OPENTYPE_FEATURES:
            item = QListWidgetItem(feat)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if feat in active else Qt.CheckState.Unchecked
            )
            self._opentype_list.addItem(item)
        v.addWidget(self._opentype_list)
        self._tabs.addTab(tab, "OpenType")

    def _build_paragraph_rules_tab(self) -> None:
        ps = cast(ParagraphStyle, self._style)
        tab = QWidget()
        form = QFormLayout(tab)
        self._rule_above = _opt_spin(ps.rule_above_thickness)
        form.addRow("Rule above thickness:", self._rule_above)
        self._rule_below = _opt_spin(ps.rule_below_thickness)
        form.addRow("Rule below thickness:", self._rule_below)
        self._tabs.addTab(tab, "Paragraph Rules")

    # ------------------------------------------------------------------
    # based-on combo
    # ------------------------------------------------------------------
    def _populate_based_on(self, style: ParagraphStyle | CharacterStyle) -> None:
        registry: dict[str, ParagraphStyle] | dict[str, CharacterStyle]
        if self._kind == "paragraph":
            registry = self._document.paragraph_styles
        else:
            registry = self._document.character_styles

        for other_name in sorted(registry):
            if other_name == style.name:
                continue
            # Skip names that would create a cycle if chosen
            if StyleResolver.detect_cycle(registry, style.name, other_name):
                continue
            self._based_on.addItem(other_name, userData=other_name)
        if style.based_on is not None:
            idx = self._based_on.findData(style.based_on)
            if idx >= 0:
                self._based_on.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # accept → build edited style + dispatch command
    # ------------------------------------------------------------------
    def _collect_paragraph(self) -> ParagraphStyle:
        ps = cast(ParagraphStyle, self._style)
        tabs: list[tuple[float, str]] = []
        for i in range(self._tab_list.count()):
            text = self._tab_list.item(i).text()
            pos_str, _, align = text.partition("\t")
            try:
                tabs.append((float(pos_str), align or "left"))
            except ValueError:
                continue

        active_features: set[str] = set()
        for i in range(self._opentype_list.count()):
            item = self._opentype_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                active_features.add(item.text())

        return replace(
            ps,
            name=self._name_edit.text().strip() or ps.name,
            based_on=self._based_on.currentData(),
            font_family=self._font_family.text() or None,
            font_size=_spin_value(self._font_size),
            leading=_spin_value(self._leading),
            alignment=self._alignment.currentData(),
            space_before=_spin_value(self._space_before),
            space_after=_spin_value(self._space_after),
            first_line_indent=_spin_value(self._first_line_indent),
            left_indent=_spin_value(self._left_indent),
            right_indent=_spin_value(self._right_indent),
            tabs=tabs,
            hyphenate=_from_tri(self._hyphenate.checkState()),
            hyphenation_zone=_spin_value(self._hyphenation_zone),
            opentype_features=active_features,
            rule_above_thickness=_spin_value(self._rule_above),
            rule_below_thickness=_spin_value(self._rule_below),
        )

    def _collect_character(self) -> CharacterStyle:
        cs = cast(CharacterStyle, self._style)
        active_features: set[str] = set()
        for i in range(self._opentype_list.count()):
            item = self._opentype_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                active_features.add(item.text())

        return replace(
            cs,
            name=self._name_edit.text().strip() or cs.name,
            based_on=self._based_on.currentData(),
            font_family=self._font_family.text() or None,
            font_size=_spin_value(self._font_size),
            bold=_from_tri(self._bold.checkState()),
            italic=_from_tri(self._italic.checkState()),
            underline=_from_tri(self._underline.checkState()),
            strike=_from_tri(self._strike.checkState()),
            tracking=_spin_value(self._tracking),
            baseline_shift=_spin_value(self._baseline_shift),
            opentype_features=active_features,
        )

    def _on_accept(self) -> None:
        cmd: EditParagraphStyleCommand | EditCharacterStyleCommand
        try:
            if self._kind == "paragraph":
                cmd = EditParagraphStyleCommand(
                    document=self._document,
                    name=self._original_name,
                    new_style=self._collect_paragraph(),
                )
            else:
                cmd = EditCharacterStyleCommand(
                    document=self._document,
                    name=self._original_name,
                    new_style=self._collect_character(),
                )
            cmd.redo()
        except StyleCycleError as exc:
            QMessageBox.critical(self, "Cycle in style hierarchy", str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.accept()


# ---- tristate helpers -----------------------------------------------------


def _tri(value: bool | None) -> Qt.CheckState:
    """Translate Optional[bool] into a Qt.CheckState."""
    if value is None:
        return Qt.CheckState.PartiallyChecked
    return Qt.CheckState.Checked if value else Qt.CheckState.Unchecked


def _from_tri(state: Qt.CheckState) -> bool | None:
    if state == Qt.CheckState.PartiallyChecked:
        return None
    return state == Qt.CheckState.Checked
