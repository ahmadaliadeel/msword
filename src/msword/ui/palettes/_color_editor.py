# mypy: disable-error-code="call-arg, attr-defined, arg-type, no-any-return, call-overload"
"""Color-swatch editor dialog used by :mod:`msword.ui.palettes.colors`.

Edits a single :class:`ColorSwatch` (or builds a new one) with a
profile-aware component editor:

* sRGB — three (r, g, b) sliders 0..255 plus a hex line edit.
* CMYK — four (c, m, y, k) sliders 0..100 (percent).
* spot — single tint slider 0..100 (percent); profile picker is locked
  to a non-process profile.

A "Spot color" toggle flips the current swatch's separation flag and
rewires the component editor to the tint-only form.

A live preview rectangle on the right re-fills as components change so
designers see what they are picking.

On accept the dialog dispatches an :class:`AddColorSwatchCommand` (when
``existing_name is None``) or an :class:`EditColorSwatchCommand` (when
editing an existing swatch).
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from msword.commands import (
    AddColorSwatchCommand,
    EditColorSwatchCommand,
)
from msword.model.color import ColorSwatch
from msword.model.document import Document

_SRGB_KIND = "sRGB"
_CMYK_KIND = "CMYK"


def _hex_from_components(r: float, g: float, b: float) -> str:
    ri = max(0, min(255, round(r * 255)))
    gi = max(0, min(255, round(g * 255)))
    bi = max(0, min(255, round(b * 255)))
    return f"#{ri:02X}{gi:02X}{bi:02X}"


def _components_from_hex(text: str) -> tuple[float, float, float] | None:
    s = text.strip().lstrip("#")
    if len(s) != 6:
        return None
    try:
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
    except ValueError:
        return None
    return (r, g, b)


class _SrgbPanel(QWidget):
    """Three 0..255 sliders + a #RRGGBB line edit.

    Slider attribute names (``r_slider`` / ``g_slider`` / ``b_slider``)
    avoid colliding with :class:`QWidget`'s ``x()``/``y()`` accessors
    (``y`` would otherwise shadow a Qt method) and read clearly at the
    call site.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)

        self.r_slider = QSlider(Qt.Orientation.Horizontal)
        self.g_slider = QSlider(Qt.Orientation.Horizontal)
        self.b_slider = QSlider(Qt.Orientation.Horizontal)
        for s in (self.r_slider, self.g_slider, self.b_slider):
            s.setRange(0, 255)
        form.addRow("R:", self.r_slider)
        form.addRow("G:", self.g_slider)
        form.addRow("B:", self.b_slider)

        self.hex_edit = QLineEdit()
        self.hex_edit.setPlaceholderText("#RRGGBB")
        self.hex_edit.setMaxLength(7)
        form.addRow("Hex:", self.hex_edit)

    def set_components(self, comps: tuple[float, ...]) -> None:
        if len(comps) != 3:
            comps = (0.0, 0.0, 0.0)
        r, g, b = comps
        for slider, v in (
            (self.r_slider, r),
            (self.g_slider, g),
            (self.b_slider, b),
        ):
            slider.blockSignals(True)
            slider.setValue(round(v * 255))
            slider.blockSignals(False)
        self.hex_edit.blockSignals(True)
        self.hex_edit.setText(_hex_from_components(r, g, b))
        self.hex_edit.blockSignals(False)

    def components(self) -> tuple[float, ...]:
        return (
            self.r_slider.value() / 255.0,
            self.g_slider.value() / 255.0,
            self.b_slider.value() / 255.0,
        )

    def to_rgb(self) -> tuple[float, float, float]:
        c = self.components()
        return (c[0], c[1], c[2])


class _CmykPanel(QWidget):
    """Four 0..100 percent sliders.

    Slider attribute names use the ``_slider`` suffix to avoid clashing
    with :class:`QWidget`'s ``y()`` (``y`` would otherwise shadow it).
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        self.c_slider = QSlider(Qt.Orientation.Horizontal)
        self.m_slider = QSlider(Qt.Orientation.Horizontal)
        self.y_slider = QSlider(Qt.Orientation.Horizontal)
        self.k_slider = QSlider(Qt.Orientation.Horizontal)
        for s in (self.c_slider, self.m_slider, self.y_slider, self.k_slider):
            s.setRange(0, 100)
        form.addRow("C %:", self.c_slider)
        form.addRow("M %:", self.m_slider)
        form.addRow("Y %:", self.y_slider)
        form.addRow("K %:", self.k_slider)

    def set_components(self, comps: tuple[float, ...]) -> None:
        if len(comps) != 4:
            comps = (0.0, 0.0, 0.0, 0.0)
        c, m, y, k = comps
        for slider, v in (
            (self.c_slider, c),
            (self.m_slider, m),
            (self.y_slider, y),
            (self.k_slider, k),
        ):
            slider.blockSignals(True)
            slider.setValue(round(v * 100))
            slider.blockSignals(False)

    def components(self) -> tuple[float, ...]:
        return (
            self.c_slider.value() / 100.0,
            self.m_slider.value() / 100.0,
            self.y_slider.value() / 100.0,
            self.k_slider.value() / 100.0,
        )

    def to_rgb(self) -> tuple[float, float, float]:
        c, m, y, k = self.components()
        inv_k = 1.0 - k
        return ((1.0 - c) * inv_k, (1.0 - m) * inv_k, (1.0 - y) * inv_k)


class _SpotPanel(QWidget):
    """Single-tint slider for spot inks."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        self.tint = QSlider(Qt.Orientation.Horizontal)
        self.tint.setRange(0, 100)
        self.tint.setValue(100)
        form.addRow("Tint %:", self.tint)

    def set_components(self, comps: tuple[float, ...]) -> None:
        if len(comps) != 1:
            comps = (1.0,)
        self.tint.blockSignals(True)
        self.tint.setValue(round(comps[0] * 100))
        self.tint.blockSignals(False)

    def components(self) -> tuple[float, ...]:
        return (self.tint.value() / 100.0,)

    def to_rgb(self) -> tuple[float, float, float]:
        v = 1.0 - self.tint.value() / 100.0
        return (v, v, v)


class ColorEditor(QDialog):
    """Tabbed-style swatch editor.

    Parameters
    ----------
    document
        The document whose swatch + profile registries are being edited.
    existing_name
        ``None`` for "create new"; otherwise the swatch name being edited.
    parent
        Optional Qt parent.
    """

    def __init__(
        self,
        document: Document,
        *,
        existing_name: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._existing_name = existing_name
        self.setObjectName("ColorEditor")
        self.setWindowTitle(
            f"Edit Swatch — {existing_name}" if existing_name else "New Swatch"
        )

        outer = QVBoxLayout(self)

        body = QHBoxLayout()
        outer.addLayout(body)

        # left: form
        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        left_layout.addLayout(form)

        self._name_edit = QLineEdit()
        form.addRow("Name:", self._name_edit)

        self._profile_picker = QComboBox()
        # Populate from document's profile registry; if the doc has no
        # CMYK / spot profiles registered we still expose the kinds so
        # the user can build swatches of those kinds. The renderer will
        # synthesise a default profile of the matching kind on save.
        self._populate_profile_picker()
        form.addRow("Profile:", self._profile_picker)

        self._spot_toggle = QComboBox()
        self._spot_toggle.addItem("Process", userData=False)
        self._spot_toggle.addItem("Spot color", userData=True)
        form.addRow("Separation:", self._spot_toggle)

        # stacked component editors
        self._stack = QStackedWidget(self)
        self._srgb = _SrgbPanel(self._stack)
        self._cmyk = _CmykPanel(self._stack)
        self._spot = _SpotPanel(self._stack)
        self._stack.addWidget(self._srgb)
        self._stack.addWidget(self._cmyk)
        self._stack.addWidget(self._spot)
        left_layout.addWidget(self._stack)

        body.addWidget(left, stretch=1)

        # right: live preview
        self._preview = QFrame(self)
        self._preview.setFrameShape(QFrame.Shape.Box)
        self._preview.setMinimumSize(120, 120)
        self._preview.setAutoFillBackground(True)
        body.addWidget(self._preview, stretch=0)

        # buttons
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        outer.addWidget(self._buttons)

        # signals — live preview + cross-panel sync
        self._profile_picker.currentIndexChanged.connect(self._on_profile_changed)
        self._spot_toggle.currentIndexChanged.connect(self._on_spot_toggle)
        for slider in (
            self._srgb.r_slider,
            self._srgb.g_slider,
            self._srgb.b_slider,
        ):
            slider.valueChanged.connect(self._on_srgb_slider)
        self._srgb.hex_edit.editingFinished.connect(self._on_hex_edited)
        for slider in (
            self._cmyk.c_slider,
            self._cmyk.m_slider,
            self._cmyk.y_slider,
            self._cmyk.k_slider,
        ):
            slider.valueChanged.connect(self._update_preview)
        self._spot.tint.valueChanged.connect(self._update_preview)

        # seed initial state from the existing swatch if any
        self._initialise_from_existing()
        self._update_preview()

    # ------------------------------------------------------------------
    # population / state seeding
    # ------------------------------------------------------------------
    def _populate_profile_picker(self) -> None:
        # The model's profile registry may not have a CMYK or spot profile
        # yet; we always offer the three kinds so swatch creation is not
        # blocked. Ensure each shown profile has a unique label.
        seen: set[str] = set()
        # Real profiles first
        for prof in self._document.color_profiles.values():
            self._profile_picker.addItem(f"{prof.name} ({prof.kind})", userData=prof.name)
            seen.add(prof.name)
        # Synthetic placeholders so each kind is reachable.
        for synth in ("CMYK", "Spot"):
            if synth not in seen:
                self._profile_picker.addItem(
                    synth,
                    userData=synth,
                )

    def _initialise_from_existing(self) -> None:
        if self._existing_name is None:
            # default: sRGB process, black
            idx = self._profile_picker.findData("sRGB")
            if idx >= 0:
                self._profile_picker.setCurrentIndex(idx)
            self._spot_toggle.setCurrentIndex(0)
            self._stack.setCurrentWidget(self._srgb)
            self._srgb.set_components((0.0, 0.0, 0.0))
            return

        swatch = self._document.color_swatches[self._existing_name]
        self._name_edit.setText(swatch.name)
        idx = self._profile_picker.findData(swatch.profile_name)
        if idx < 0:
            # Profile not registered — add a row for it.
            self._profile_picker.addItem(swatch.profile_name, userData=swatch.profile_name)
            idx = self._profile_picker.count() - 1
        self._profile_picker.setCurrentIndex(idx)
        self._spot_toggle.setCurrentIndex(1 if swatch.is_spot else 0)
        # Choose stack page from current toggle / profile
        self._sync_stack_page()
        if swatch.is_spot:
            self._spot.set_components(swatch.components)
        else:
            kind = self._kind_for(swatch.profile_name)
            if kind == _CMYK_KIND:
                self._cmyk.set_components(swatch.components)
            else:
                self._srgb.set_components(swatch.components)

    # ------------------------------------------------------------------
    # signals
    # ------------------------------------------------------------------
    def _on_profile_changed(self, _index: int) -> None:
        self._sync_stack_page()
        self._update_preview()

    def _on_spot_toggle(self, _index: int) -> None:
        self._sync_stack_page()
        self._update_preview()

    def _on_srgb_slider(self, _value: int) -> None:
        r, g, b = self._srgb.components()
        self._srgb.hex_edit.blockSignals(True)
        self._srgb.hex_edit.setText(_hex_from_components(r, g, b))
        self._srgb.hex_edit.blockSignals(False)
        self._update_preview()

    def _on_hex_edited(self) -> None:
        comps = _components_from_hex(self._srgb.hex_edit.text())
        if comps is None:
            # restore from sliders
            r, g, b = self._srgb.components()
            self._srgb.hex_edit.setText(_hex_from_components(r, g, b))
            return
        self._srgb.set_components(comps)
        self._update_preview()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _kind_for(self, profile_name: str) -> str:
        """Resolve a profile name to its kind ("sRGB" / "CMYK").

        Caller short-circuits on the spot toggle, so spot profiles are not
        resolved here. Falls back to substring inference for synthetic
        profile entries the document may not have registered yet.
        """
        prof = self._document.color_profiles.get(profile_name)
        if prof is not None:
            return prof.kind
        if "cmyk" in profile_name.lower():
            return _CMYK_KIND
        return _SRGB_KIND

    def _is_spot(self) -> bool:
        return bool(self._spot_toggle.currentData())

    def _sync_stack_page(self) -> None:
        if self._is_spot():
            self._stack.setCurrentWidget(self._spot)
            return
        kind = self._kind_for(str(self._profile_picker.currentData() or ""))
        if kind == _CMYK_KIND:
            self._stack.setCurrentWidget(self._cmyk)
        else:
            self._stack.setCurrentWidget(self._srgb)

    def _current_components(self) -> tuple[float, ...]:
        page = self._stack.currentWidget()
        return cast("_SrgbPanel | _CmykPanel | _SpotPanel", page).components()

    def _current_rgb(self) -> tuple[float, float, float]:
        page = self._stack.currentWidget()
        return cast("_SrgbPanel | _CmykPanel | _SpotPanel", page).to_rgb()

    def _update_preview(self) -> None:
        r, g, b = self._current_rgb()
        color = QColor.fromRgbF(r, g, b)
        pal = self._preview.palette()
        pal.setColor(QPalette.ColorRole.Window, color)
        self._preview.setPalette(pal)

    # ------------------------------------------------------------------
    # accept
    # ------------------------------------------------------------------
    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Please enter a swatch name.")
            return
        profile_data = self._profile_picker.currentData()
        profile_name = str(profile_data) if profile_data is not None else "sRGB"
        is_spot = self._is_spot()
        components = self._current_components()
        new_swatch = ColorSwatch(
            name=name,
            profile_name=profile_name,
            components=components,
            is_spot=is_spot,
        )

        if name != self._existing_name and name in self._document.color_swatches:
            QMessageBox.warning(self, "Duplicate", f"Swatch {name!r} already exists.")
            return
        if self._existing_name is None:
            AddColorSwatchCommand(self._document, new_swatch).redo()
        else:
            EditColorSwatchCommand(
                self._document,
                self._existing_name,
                new_swatch,
            ).redo()

        self.accept()


__all__ = ["ColorEditor"]
