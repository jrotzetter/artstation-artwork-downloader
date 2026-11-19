import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from artstation_artwork_downloader.renamedialog import AskRenameDialog, ask_rename

# === UTILITIES ===============================================================


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()  # withdraw() prevents the window from flashing on screen during tests
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def _no_window_flash(monkeypatch):
    """Prevent Toplevel windows from briefly mapping (Tk C-level MapFrame)."""
    orig_init = tk.Toplevel.__init__

    def patched_init(self, *args, **kw):
        orig_init(self, *args, **kw)
        self.overrideredirect(True)

    monkeypatch.setattr(tk.Toplevel, "__init__", patched_init)


def _make_dialog(root, **overrides):
    """Create an AskRenameDialog without running mainloop."""
    kwargs = {
        "checkvar": tk.BooleanVar(value=False),
        "overwritevar": tk.BooleanVar(value=False),
        "file_path": "/tmp/test-file.png",
        "title": "Test",
        "prompt": "Enter new name:",
        "initialvalue": "existing-file-on-disk",
        "size_diff": "1.1 MB",
        "download_is_bigger": 1,
        "parent": root,
    }
    kwargs.update(overrides)
    # Dialog.__init__ calls wait_visibility() + wait_window() to block until
    # the user closes the dialog; patch them out to construct without a mainloop.
    with (
        patch.object(AskRenameDialog, "wait_window"),
        patch.object(AskRenameDialog, "wait_visibility"),
    ):
        d = AskRenameDialog(**kwargs)
    return d


def _get_body_frame(dialog):
    """The internal Frame created by Dialog.__init__ and passed to body().

    Identified via the entry widget's parent, which is the body frame
    regardless of child ordering or additional frames."""
    frame = dialog.entry.master
    assert isinstance(frame, tk.Frame), (
        f"Expected body frame, got {type(frame).__name__}"
    )
    return frame


def _get_labels(master):
    return [w.cget("text") for w in master.winfo_children() if isinstance(w, tk.Label)]


def _find_button(dialog, text):
    """Find a tk.Button by its text, searching the full widget tree."""

    def _walk(w):
        for child in w.winfo_children():
            if isinstance(child, tk.Button) and child.cget("text") == text:
                return child
            found = _walk(child)
            if found:
                return found

    return _walk(dialog)


# === TESTS ===================================================================


class TestBody:
    def test_initialvalue_shown_in_entry(self, tk_root):
        d = _make_dialog(tk_root, initialvalue="existing-art")
        assert d.entry.get() == "existing-art"

    def test_entry_empty_when_no_initialvalue(self, tk_root):
        d = _make_dialog(tk_root, initialvalue=None)
        assert d.entry.get() == ""

    def test_select_range_called_with_full_text(self, tk_root):
        """Test that the text inside the entry is pre-selected."""
        with patch.object(tk.Entry, "select_range") as mock_sel:
            _make_dialog(tk_root, initialvalue="select-me")
        mock_sel.assert_called_once_with(0, tk.END)

    def test_select_range_not_called_when_no_initialvalue(self, tk_root):
        with patch.object(tk.Entry, "select_range") as mock_sel:
            _make_dialog(tk_root, initialvalue=None)
        mock_sel.assert_not_called()

    def test_size_label_disk_bigger(self, tk_root):
        d = _make_dialog(tk_root, download_is_bigger=0, size_diff="500 KB")
        master = _get_body_frame(d)
        assert (
            "The file on disk is 500 KB larger than the file to be downloaded."
            in _get_labels(master)
        )

    def test_size_label_download_bigger(self, tk_root):
        d = _make_dialog(tk_root, download_is_bigger=1, size_diff="2.5 MB")
        master = _get_body_frame(d)
        assert (
            "The file to be downloaded is 2.5 MB larger than the file on disk."
            in _get_labels(master)
        )

    def test_size_label_equal(self, tk_root):
        d = _make_dialog(tk_root, download_is_bigger=2)
        master = _get_body_frame(d)
        assert "Both files are equal in size." in _get_labels(master)

    def test_size_label_unknown(self, tk_root):
        d = _make_dialog(tk_root, download_is_bigger=None)
        master = _get_body_frame(d)
        assert "Difference in file sizes could not be determined." in _get_labels(
            master
        )

    def test_file_exists_label_shows_initialvalue(self, tk_root):
        d = _make_dialog(tk_root, initialvalue="existing-art.png")
        master = _get_body_frame(d)
        assert any(
            "existing-art.png" in t and "already exists" in t
            for t in _get_labels(master)
        )

    def test_prompt_label_shows_prompt(self, tk_root):
        d = _make_dialog(tk_root, prompt="Type the new name:")
        master = _get_body_frame(d)
        assert "Type the new name:" in _get_labels(master)

    def test_show_on_disk_button_exists(self, tk_root):
        d = _make_dialog(tk_root)
        btn = _find_button(d, "Show file on disk")
        assert btn is not None


class TestButtonBox:
    def test_creates_expected_buttons(self, tk_root):
        d = _make_dialog(tk_root)
        # Buttons are packed into a Frame child of the dialog
        buttons = [
            w
            for w in d.winfo_children()
            if isinstance(w, tk.Frame)
            for w in w.winfo_children()
            if isinstance(w, tk.Button)
        ]
        texts = [b.cget("text") for b in buttons]
        assert "Rename" in texts
        assert "Skip" in texts
        assert "Skip all" in texts
        assert "Overwrite" in texts

    def test_return_binding_is_set(self, tk_root):
        d = _make_dialog(tk_root)
        # bind() returns "" if unbound, the Tcl command string otherwise
        assert d.bind("<Return>") != ""

    def test_escape_binding_is_set(self, tk_root):
        d = _make_dialog(tk_root)
        # bind() returns "" if unbound, the Tcl command string otherwise
        assert d.bind("<Escape>") != ""


class TestOkLifecycle:
    """ok() -> validate() -> apply() -> cancel() -> destroy() chain."""

    def test_ok_sets_result_and_destroys(self, tk_root):
        d = _make_dialog(tk_root, initialvalue="original")
        d.entry.delete(0, tk.END)
        d.entry.insert(0, "renamed-file")

        d.ok()

        assert d.result == "renamed-file"
        assert d.entry is None  # destroy() was called

    def test_ok_with_initialvalue_unchanged(self, tk_root):
        """If the user presses Rename without editing, result = initialvalue."""
        d = _make_dialog(tk_root, initialvalue="keep-me")

        d.ok()

        assert d.result == "keep-me"
        assert d.entry is None

    def test_ok_with_empty_entry_does_not_destroy(self, tk_root):
        """validate() rejects empty input, so ok() does not proceed to destroy."""
        d = _make_dialog(tk_root, initialvalue="original")
        d.entry.delete(0, tk.END)
        with patch("artstation_artwork_downloader.renamedialog.messagebox.showerror"):
            d.ok()
        assert d.entry is not None  # dialog stays open

    def test_ok_does_not_overwrite_result_via_apply(self, tk_root):
        """Inherited apply() is a no-op; result from validate() is preserved."""
        d = _make_dialog(tk_root, initialvalue="abc")

        d.ok()

        # If apply() had set result = None (or returned a value that
        # was assigned to self.result), this would fail.
        assert d.result == "abc"


class TestCancel:
    """cancel() path: result stays None, dialog is destroyed."""

    def test_cancel_leaves_result_none(self, tk_root):
        d = _make_dialog(tk_root)

        d.cancel()

        assert d.result is None
        assert d.entry is None

    def test_skip_all_sets_checkvar_and_cancels(self, tk_root):
        checkvar = tk.BooleanVar(value=False)
        d = _make_dialog(tk_root, checkvar=checkvar)
        with patch.object(d, "cancel") as mock_cancel:
            d.skip_all()
        assert checkvar.get() is True
        mock_cancel.assert_called_once()

    def test_overwrite_sets_overwritevar_and_cancels(self, tk_root):
        overwritevar = tk.BooleanVar(value=False)
        d = _make_dialog(tk_root, overwritevar=overwritevar)
        with patch.object(d, "cancel") as mock_cancel:
            d.overwrite()
        assert overwritevar.get() is True
        mock_cancel.assert_called_once()

    def test_skip_button_cancels_without_setting_result(self, tk_root):
        """Verifies the Skip button is wired to cancel(), not ok()."""
        d = _make_dialog(tk_root)
        skip_btn = _find_button(d, "Skip")
        skip_btn.invoke()
        assert d.result is None
        assert d.entry is None

    def test_wm_delete_window_triggers_cancel(self, tk_root):
        """Closing the window (X button) should behave like Skip."""
        d = _make_dialog(tk_root)
        # Dialog.__init__ registers cancel via protocol("WM_DELETE_WINDOW", ...),
        # which is a WM *protocol*, not a Tk event. Retrieve the bound Tcl
        # command and call it directly to simulate the user clicking the X button.
        d.tk.call(d.protocol("WM_DELETE_WINDOW"))

        assert d.result is None
        assert d.entry is None


class TestValidate:
    """validate() contract: returns 1 and sets self.result for non-empty input;
    returns 0 and leaves self.result untouched for empty/whitespace input."""

    def test_validate_returns_0_for_empty_input(self, tk_root):
        d = _make_dialog(tk_root, initialvalue="x")
        d.entry.delete(0, tk.END)
        with patch("artstation_artwork_downloader.renamedialog.messagebox.showerror"):
            assert d.validate() == 0
        assert d.result is None

    def test_validate_returns_0_for_whitespace(self, tk_root):
        d = _make_dialog(tk_root, initialvalue=None)
        d.entry.insert(0, "   ")
        with patch("artstation_artwork_downloader.renamedialog.messagebox.showerror"):
            assert d.validate() == 0
        assert d.result is None

    def test_validate_sets_result_to_current_entry_text(self, tk_root):
        d = _make_dialog(tk_root, initialvalue="old")
        d.entry.delete(0, tk.END)
        d.entry.insert(0, "new")

        assert d.validate() == 1
        assert d.result == "new"


class TestShowOnDisk:
    def test_show_on_disk_file_exists(self, tk_root):
        d = _make_dialog(tk_root, file_path="/tmp/foo.png")
        with (
            patch(
                "artstation_artwork_downloader.renamedialog.os.path.exists",
                return_value=True,
            ),
            patch(
                "artstation_artwork_downloader.renamedialog.show_in_file_manager"
            ) as mock_fm,
        ):
            d.show_on_disk()
        mock_fm.assert_called_once_with("/tmp/foo.png")

    def test_show_on_disk_file_not_found_shows_warning(self, tk_root):
        d = _make_dialog(tk_root, file_path="/nonexistent/file.png")
        with (
            patch(
                "artstation_artwork_downloader.renamedialog.os.path.exists",
                return_value=False,
            ),
            patch(
                "artstation_artwork_downloader.renamedialog.messagebox.showwarning"
            ) as mock_warn,
        ):
            d.show_on_disk()
        mock_warn.assert_called_once()
        title, message = mock_warn.call_args.args
        assert title == "File not found"
        assert "/nonexistent/file.png" in message


class TestAskRenameFunction:
    def test_returns_result_from_dialog(self, tk_root):
        mock_d = MagicMock()
        mock_d.result = "renamed"
        with patch(
            "artstation_artwork_downloader.renamedialog.AskRenameDialog",
            return_value=mock_d,
        ) as mock_cls:
            result = ask_rename(
                checkvar=tk.BooleanVar(),
                overwritevar=tk.BooleanVar(),
                file_path="/tmp/x.png",
                parent=tk_root,
            )
        assert result == "renamed"
        mock_cls.assert_called_once()
        _, kwargs = mock_cls.call_args
        assert kwargs["file_path"] == "/tmp/x.png"
        assert kwargs["parent"] is tk_root

    def test_passes_optional_args(self, tk_root):
        mock_d = MagicMock()
        mock_d.result = "ok"
        with patch(
            "artstation_artwork_downloader.renamedialog.AskRenameDialog",
            return_value=mock_d,
        ) as mock_cls:
            ask_rename(
                checkvar=tk.BooleanVar(),
                overwritevar=tk.BooleanVar(),
                file_path="/tmp/x.png",
                title="Fake Title",
                prompt="Fake Prompt",
                initialvalue="orig",
                size_diff="3 MB",
                download_is_bigger=0,
                parent=tk_root,
            )
        _, kwargs = mock_cls.call_args
        assert kwargs["file_path"] == "/tmp/x.png"
        assert kwargs["title"] == "Fake Title"
        assert kwargs["prompt"] == "Fake Prompt"
        assert kwargs["initialvalue"] == "orig"
        assert kwargs["size_diff"] == "3 MB"
        assert kwargs["download_is_bigger"] == 0
        assert kwargs["parent"] is tk_root


class TestDestroy:
    def test_destroy_sets_entry_to_none(self, tk_root):
        """destroy() is overridden to null self.entry, preventing dangling widget refs."""
        d = _make_dialog(tk_root)
        assert d.entry is not None
        d.destroy()
        assert d.entry is None
