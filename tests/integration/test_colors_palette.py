"""Integration tests for unit-26 — `ui-colors-palette`.

Exercises the palette at the public seam: it consumes a stub
:class:`Document` (color profiles + swatches + a selected-frame slot) and
emits mutations exclusively through Commands.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent

from msword.commands import (
    AddColorSwatchCommand,
    DeleteColorSwatchCommand,
    DuplicateColorSwatchCommand,
    EditColorSwatchCommand,
    SetFrameFillCommand,
    SetFrameStrokeCommand,
)
from msword.model.color import ColorProfile, ColorSwatch
from msword.model.document import Document, _StubFrame
from msword.ui.palettes._color_editor import ColorEditor
from msword.ui.palettes.colors import ColorsPalette


def _build_document_with_three() -> Document:
    doc = Document()
    doc.color_profiles["sRGB"] = ColorProfile(name="sRGB", kind="sRGB")
    doc.color_profiles["CMYK"] = ColorProfile(name="CMYK", kind="CMYK")
    doc.color_swatches["Black"] = ColorSwatch(
        name="Black", profile_name="sRGB", components=(0.0, 0.0, 0.0)
    )
    doc.color_swatches["White"] = ColorSwatch(
        name="White", profile_name="sRGB", components=(1.0, 1.0, 1.0)
    )
    doc.color_swatches["Cyan"] = ColorSwatch(
        name="Cyan", profile_name="CMYK", components=(1.0, 0.0, 0.0, 0.0)
    )
    return doc


def test_three_swatches_render_three_cells(qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = _build_document_with_three()
    palette = ColorsPalette(doc)
    qtbot.addWidget(palette)

    grid = palette._grid
    assert grid.count() == 3
    names = {grid.item(i).text() for i in range(grid.count())}
    assert names == {"Black", "White", "Cyan"}
    # tile icon was rendered
    assert not grid.item(0).icon().isNull()
    # tooltip carries name + profile
    tooltips = {grid.item(i).toolTip() for i in range(grid.count())}
    assert any("Cyan" in tip and "CMYK" in tip for tip in tooltips)


def test_new_swatch_dispatches_add_command(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Click + → editor opens; pick name + sRGB(1,0,0) → AddColorSwatchCommand."""
    doc = _build_document_with_three()
    palette = ColorsPalette(doc)
    qtbot.addWidget(palette)

    # Spy AddColorSwatchCommand.redo
    dispatched: list[ColorSwatch] = []
    real_redo = AddColorSwatchCommand.redo

    def spy_redo(self: AddColorSwatchCommand) -> None:
        dispatched.append(self.swatch)
        real_redo(self)

    monkeypatch.setattr(AddColorSwatchCommand, "redo", spy_redo)

    # Auto-drive the editor: open it, fill it in, accept it.
    captured: list[ColorEditor] = []

    def fake_exec(self: ColorEditor) -> int:
        captured.append(self)
        # drive the editor: name=MyRed, sRGB profile, R=255,G=0,B=0
        self._name_edit.setText("MyRed")
        idx = self._profile_picker.findData("sRGB")
        assert idx >= 0
        self._profile_picker.setCurrentIndex(idx)
        self._spot_toggle.setCurrentIndex(0)  # process
        self._srgb.r_slider.setValue(255)
        self._srgb.g_slider.setValue(0)
        self._srgb.b_slider.setValue(0)
        self._on_accept()
        return int(ColorEditor.DialogCode.Accepted) if self.result() else int(
            ColorEditor.DialogCode.Rejected
        )

    monkeypatch.setattr(ColorEditor, "exec", fake_exec)

    palette._action_new.trigger()

    # editor was opened
    assert len(captured) == 1
    # AddColorSwatchCommand fired with the user's values
    assert len(dispatched) == 1
    swatch = dispatched[0]
    assert swatch.name == "MyRed"
    assert swatch.profile_name == "sRGB"
    assert swatch.components == (1.0, 0.0, 0.0)
    assert swatch.is_spot is False

    # registry has the new swatch and the grid was refreshed
    assert "MyRed" in doc.color_swatches
    grid_names = {palette._grid.item(i).text() for i in range(palette._grid.count())}
    assert "MyRed" in grid_names


def test_click_swatch_with_selected_frame_dispatches_set_frame_fill(  # type: ignore[no-untyped-def]
    qtbot, monkeypatch
) -> None:
    """Click Cyan with a frame selected → SetFrameFillCommand("Cyan")."""
    doc = _build_document_with_three()
    doc.selected_frame = _StubFrame()
    palette = ColorsPalette(doc)
    qtbot.addWidget(palette)

    captured: list[tuple[type, str]] = []
    real_redo = SetFrameFillCommand.redo

    def spy_redo(self: SetFrameFillCommand) -> None:
        captured.append((type(self), self.swatch_name))
        real_redo(self)

    monkeypatch.setattr(SetFrameFillCommand, "redo", spy_redo)

    grid = palette._grid
    cyan = next(
        grid.item(i) for i in range(grid.count()) if grid.item(i).text() == "Cyan"
    )
    palette._on_swatch_clicked(cyan, shift=False)

    assert captured == [(SetFrameFillCommand, "Cyan")]
    assert doc.selected_frame is not None
    assert doc.selected_frame.fill == "Cyan"


def test_shift_click_swatch_dispatches_set_frame_stroke(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Shift-click Cyan → SetFrameStrokeCommand("Cyan")."""
    doc = _build_document_with_three()
    doc.selected_frame = _StubFrame()
    palette = ColorsPalette(doc)
    qtbot.addWidget(palette)

    captured: list[tuple[type, str]] = []
    real_redo = SetFrameStrokeCommand.redo

    def spy_redo(self: SetFrameStrokeCommand) -> None:
        captured.append((type(self), self.swatch_name))
        real_redo(self)

    monkeypatch.setattr(SetFrameStrokeCommand, "redo", spy_redo)

    grid = palette._grid
    cyan = next(
        grid.item(i) for i in range(grid.count()) if grid.item(i).text() == "Cyan"
    )
    palette._on_swatch_clicked(cyan, shift=True)

    assert captured == [(SetFrameStrokeCommand, "Cyan")]
    assert doc.selected_frame is not None
    assert doc.selected_frame.stroke == "Cyan"


def test_click_swatch_with_no_selected_frame_is_noop(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Without a selected frame, clicking a swatch must not error."""
    doc = _build_document_with_three()
    assert doc.selected_frame is None
    palette = ColorsPalette(doc)
    qtbot.addWidget(palette)
    grid = palette._grid
    item = grid.item(0)
    palette._on_swatch_clicked(item, shift=False)
    palette._on_swatch_clicked(item, shift=True)


def test_grid_mouse_press_routes_through_palette(qtbot) -> None:  # type: ignore[no-untyped-def]
    """A real left-click on a tile must drive the palette's click handler."""
    doc = _build_document_with_three()
    doc.selected_frame = _StubFrame()
    palette = ColorsPalette(doc)
    qtbot.addWidget(palette)
    palette.show()
    qtbot.waitExposed(palette)

    grid = palette._grid
    cyan_item = next(
        grid.item(i) for i in range(grid.count()) if grid.item(i).text() == "Cyan"
    )
    rect = grid.visualItemRect(cyan_item)
    assert rect.isValid()
    pos = rect.center()

    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    grid.mousePressEvent(event)
    assert doc.selected_frame is not None
    assert doc.selected_frame.fill == "Cyan"


def test_duplicate_swatch_dispatches_duplicate_command(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    doc = _build_document_with_three()
    palette = ColorsPalette(doc)
    qtbot.addWidget(palette)

    captured: list[tuple[str, str]] = []
    real_redo = DuplicateColorSwatchCommand.redo

    def spy_redo(self: DuplicateColorSwatchCommand) -> None:
        captured.append((self.source_name, self.new_name))
        real_redo(self)

    monkeypatch.setattr(DuplicateColorSwatchCommand, "redo", spy_redo)

    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *a, **kw: ("Black 50", True)),
    )

    grid = palette._grid
    for i in range(grid.count()):
        if grid.item(i).text() == "Black":
            grid.setCurrentRow(i)
            break
    palette._action_duplicate.trigger()

    assert captured == [("Black", "Black 50")]
    assert "Black 50" in doc.color_swatches


def test_delete_swatch_dispatches_delete_command(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    doc = _build_document_with_three()
    palette = ColorsPalette(doc)
    qtbot.addWidget(palette)

    captured: list[str] = []
    real_redo = DeleteColorSwatchCommand.redo

    def spy_redo(self: DeleteColorSwatchCommand) -> None:
        captured.append(self.name)
        real_redo(self)

    monkeypatch.setattr(DeleteColorSwatchCommand, "redo", spy_redo)

    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Yes),
    )

    grid = palette._grid
    for i in range(grid.count()):
        if grid.item(i).text() == "White":
            grid.setCurrentRow(i)
            break
    palette._action_delete.trigger()

    assert captured == ["White"]
    assert "White" not in doc.color_swatches


def test_edit_swatch_dispatches_edit_command(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Editing Black through the dialog dispatches EditColorSwatchCommand."""
    doc = _build_document_with_three()
    palette = ColorsPalette(doc)
    qtbot.addWidget(palette)

    captured: list[ColorSwatch] = []
    real_redo = EditColorSwatchCommand.redo

    def spy_redo(self: EditColorSwatchCommand) -> None:
        captured.append(self.new_swatch)
        real_redo(self)

    monkeypatch.setattr(EditColorSwatchCommand, "redo", spy_redo)

    def fake_exec(self: ColorEditor) -> int:
        # bump the green channel to 0.5
        self._srgb.g_slider.setValue(128)
        self._on_accept()
        return int(ColorEditor.DialogCode.Accepted) if self.result() else int(
            ColorEditor.DialogCode.Rejected
        )

    monkeypatch.setattr(ColorEditor, "exec", fake_exec)

    grid = palette._grid
    for i in range(grid.count()):
        if grid.item(i).text() == "Black":
            grid.setCurrentRow(i)
            break
    palette._action_edit.trigger()

    assert len(captured) == 1
    assert captured[0].name == "Black"
    # green ≈ 0.5
    assert captured[0].components[0] == 0.0
    assert abs(captured[0].components[1] - 128 / 255) < 1e-6
    assert captured[0].components[2] == 0.0


def test_drag_starts_with_swatch_name_payload(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The grid's drag setup must produce a swatch-name mime payload.

    We can't easily run the OS drag loop in a headless test, so we
    invoke the internal drag-start helper directly; the contract under
    test is the mime data shape — that's what the canvas drop handler
    will consume.
    """
    from PySide6.QtCore import QMimeData
    from PySide6.QtGui import QDrag

    doc = _build_document_with_three()
    palette = ColorsPalette(doc)
    qtbot.addWidget(palette)

    captured: list[QMimeData] = []

    def fake_exec(self, _action):  # type: ignore[no-untyped-def]
        captured.append(self.mimeData())
        return Qt.DropAction.IgnoreAction

    monkeypatch.setattr(QDrag, "exec", fake_exec)

    item = palette._grid.item(0)
    palette._grid._start_drag(item)

    assert len(captured) == 1
    mime = captured[0]
    assert mime.hasFormat(ColorsPalette.SWATCH_MIME)
    payload = bytes(mime.data(ColorsPalette.SWATCH_MIME)).decode("utf-8")
    assert payload == palette._grid.item(0).text()


def test_palette_is_dock_widget(qtbot) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtWidgets import QDockWidget

    doc = _build_document_with_three()
    palette = ColorsPalette(doc)
    qtbot.addWidget(palette)
    assert isinstance(palette, QDockWidget)
    assert palette.windowTitle() == "Colors"
