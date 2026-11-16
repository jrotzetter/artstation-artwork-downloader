import json
import threading
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest
from curl_cffi.requests.exceptions import HTTPError

from artstation_artwork_downloader.main import _fetch_with_retry

# \\\ _fetch_with_retry \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestFetchWithRetry:
    def test_success_first_try(self):
        session = MagicMock()
        resp = MagicMock(status_code=200)
        resp.raise_for_status.return_value = None
        session.get.return_value = resp

        result = _fetch_with_retry(session, "http://x", max_retries=3, delay=0)
        assert result is resp
        assert session.get.call_count == 1

    def test_retry_on_403_then_success(self):
        session = MagicMock()
        bad = MagicMock(status_code=403)
        good = MagicMock(status_code=200)
        good.raise_for_status.return_value = None
        session.get.side_effect = [bad, good]

        result = _fetch_with_retry(session, "http://x", max_retries=3, delay=0)
        assert result is good
        assert session.get.call_count == 2

    def test_retry_on_all_5xx_codes(self):
        for code in (500, 502, 503, 504):
            session = MagicMock()
            bad = MagicMock(status_code=code)
            good = MagicMock(status_code=200)
            good.raise_for_status.return_value = None
            session.get.side_effect = [bad, good]

            result = _fetch_with_retry(session, "http://x", max_retries=3, delay=0)
            assert result is good

    def test_exhausts_retries_raises(self):
        session = MagicMock()
        bad = MagicMock(status_code=403)
        bad.raise_for_status.side_effect = HTTPError("403")
        session.get.return_value = bad

        with pytest.raises(HTTPError):
            _fetch_with_retry(session, "http://x", max_retries=3, delay=0)
        assert session.get.call_count == 3

    def test_non_retryable_404_raises_immediately(self):
        session = MagicMock()
        resp = MagicMock(status_code=404)
        resp.raise_for_status.side_effect = HTTPError("404")
        session.get.return_value = resp

        with pytest.raises(HTTPError):
            _fetch_with_retry(session, "http://x", max_retries=3, delay=0)
        assert session.get.call_count == 1

    def test_429_not_retried(self):
        session = MagicMock()
        resp = MagicMock(status_code=429)
        resp.raise_for_status.side_effect = HTTPError("429")
        session.get.return_value = resp

        with pytest.raises(HTTPError):
            _fetch_with_retry(session, "http://x", max_retries=3, delay=0)
        assert session.get.call_count == 1


# \\\ _on_close \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestOnClose:
    def test_cleanup(self, app):
        with patch.object(app, "destroy"):
            app._on_close()
        assert app._cancel_event.is_set()
        app._session.close.assert_called_once()


# \\\ extract_hashid \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestExtractHashid:
    def test_full_url(self, app):
        assert app.extract_hashid("https://artstation.com/artwork/abc123") == "abc123"

    def test_bare_id(self, app):
        assert app.extract_hashid("abc123") == "abc123"

    def test_invalid_chars(self, app):
        assert app.extract_hashid("abc-123!") is None

    def test_empty(self, app):
        assert app.extract_hashid("") is None


# \\\ get_json_url \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestGetJsonUrl:
    def test_copies_correct_url(self, app):
        app.project_ent.delete(0, tk.END)
        app.project_ent.insert(0, "abc123")
        app.get_json_url()
        assert app.clipboard_get() == "https://www.artstation.com/projects/abc123.json"

    def test_invalid_input_shows_error(self, app):
        app.project_ent.delete(0, tk.END)
        app.project_ent.insert(0, "!!!")
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            app.get_json_url()
            mb.showerror.assert_called_once()


# \\\ load_json (static method) \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestLoadJson:
    def test_valid_json(self, app):
        result = app.load_json('{"a": 1}')
        assert result == {"a": 1}

    def test_invalid_json_returns_none(self, app):
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            result = app.load_json("not json{{{")
            assert result is None
            mb.showerror.assert_called_once()


# \\\ load_json_clp \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestLoadJsonClp:
    def test_valid_json_populates(self, app):
        project_data = {
            "hash_id": "xyz789",
            "assets": [
                {"asset_type": "image", "image_url": "https://cdn.example.com/p.jpg"},
            ],
        }
        with patch.object(app, "clipboard_get", return_value=json.dumps(project_data)):
            app.load_json_clp()
        assert app.image_list.size() == 1
        assert app.LOADED_JSON.get() == "xyz789"

    def test_invalid_json_shows_error(self, app):
        with (
            patch.object(app, "clipboard_get", return_value="not json"),
            patch("artstation_artwork_downloader.main.messagebox") as mb,
        ):
            app.load_json_clp()
            mb.showerror.assert_called_once()
        assert app.image_list.size() == 0

    def test_empty_clipboard_shows_error(self, app):
        with (
            patch.object(app, "clipboard_get", side_effect=tk.TclError),
            patch("artstation_artwork_downloader.main.messagebox") as mb,
        ):
            app.load_json_clp()
            mb.showerror.assert_called_once()


# \\\ load_json_url \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestLoadJsonUrl:
    def test_valid_hash_populates(self, app):
        app.project_ent.delete(0, tk.END)
        app.project_ent.insert(0, "abc123")
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "hash_id": "abc123",
            "assets": [{"asset_type": "image", "image_url": "https://x/a.jpg"}],
        }
        with patch(
            "artstation_artwork_downloader.main._fetch_with_retry",
            return_value=fake_resp,
        ):
            app.load_json_url()
        assert app.image_list.size() == 1
        assert app.LOADED_JSON.get() == "abc123"

    def test_http_error_shows_dialog(self, app):
        app.project_ent.delete(0, tk.END)
        app.project_ent.insert(0, "abc123")
        with (
            patch(
                "artstation_artwork_downloader.main._fetch_with_retry",
                side_effect=HTTPError("500"),
            ),
            patch("artstation_artwork_downloader.main.messagebox") as mb,
        ):
            app.load_json_url()
            mb.showerror.assert_called_once()

    def test_invalid_hash_no_fetch(self, app):
        app.project_ent.delete(0, tk.END)
        app.project_ent.insert(0, "!!!")
        with (
            patch(
                "artstation_artwork_downloader.main._fetch_with_retry",
            ) as mock_fetch,
            patch("artstation_artwork_downloader.main.messagebox") as mb,
        ):
            app.load_json_url()
            mb.showerror.assert_called_once()
        mock_fetch.assert_not_called()


# \\\ _populate_image_list \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestPopulateImageList:
    def test_filters_non_images(self, app):
        project_data = {
            "hash_id": "abc123",
            "assets": [
                {"asset_type": "image", "image_url": "https://cdn.example.com/a.jpg"},
                {"asset_type": "image", "image_url": "https://cdn.example.com/b.jpg"},
                {"asset_type": "video", "image_url": "https://cdn.example.com/v.mp4"},
            ],
        }
        app._populate_image_list(project_data)
        app.update_idletasks()

        assert app.image_list.size() == 2
        assert app.LOADED_JSON.get() == "abc123"

    def test_no_images(self, app):
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            app._populate_image_list({"hash_id": "x", "assets": []})
            mb.showinfo.assert_called()

    def test_missing_hash_id_warns(self, app):
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            app._populate_image_list({"assets": []})
            mb.showwarning.assert_called_once()
        assert app.image_list.size() == 0


# \\\ _add_url \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestAddUrl:
    def test_adds_valid_url(self, app):
        url = "https://cdn.example.com/images/images/abc123.jpg"
        with patch.object(app, "clipboard_get", return_value=url):
            app._add_url()
        assert app.image_list.size() == 1
        assert app.image_list.get(0) == url

    def test_rejects_invalid_clipboard(self, app):
        with (
            patch.object(app, "clipboard_get", return_value="https://example.com/foo"),
            patch("artstation_artwork_downloader.main.messagebox") as mb,
        ):
            app._add_url()
            mb.showerror.assert_called_once()
        assert app.image_list.size() == 0

    def test_rejects_duplicate(self, app):
        url = "https://cdn.example.com/images/images/abc123.jpg"
        app.image_list.insert(tk.END, url)
        with (
            patch.object(app, "clipboard_get", return_value=url),
            patch("artstation_artwork_downloader.main.messagebox") as mb,
        ):
            app._add_url()
            mb.showerror.assert_called_once()
        assert app.image_list.size() == 1

    def test_empty_clipboard(self, app):
        with (
            patch.object(app, "clipboard_get", side_effect=tk.TclError),
            patch("artstation_artwork_downloader.main.messagebox") as mb,
        ):
            app._add_url()
            mb.showerror.assert_called_once()


# \\\ _remove_url \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestRemoveUrl:
    def test_remove_selected(self, app):
        app.image_list.insert(tk.END, "url1")
        app.image_list.insert(tk.END, "url2")
        app.image_list.selection_set(0)
        app._remove_url()
        app.update_idletasks()
        assert app.image_list.get(0) == "url2"


# \\\ _clear_json \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestClearJson:
    def test_clears_list_and_var(self, app):
        app.LOADED_JSON.set("abc")
        app.image_list.insert(tk.END, "url1")
        app.image_list.insert(tk.END, "url2")
        app._clear_json()
        app.update_idletasks()
        assert app.image_list.size() == 0
        assert app.LOADED_JSON.get() == ""


# \\\ show_entry \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestShowEntry:
    def test_enable(self, app):
        var = tk.BooleanVar(value=True)
        ent = app.custom_entry
        app.show_entry(var, ent)
        assert str(ent.cget("state")) == "normal"

    def test_disable(self, app):
        var = tk.BooleanVar(value=False)
        ent = app.custom_entry
        ent.configure(state="normal")
        app.show_entry(var, ent)
        assert str(ent.cget("state")) == "disabled"


# \\\ _set_downloading \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestSetDownloading:
    def test_active_disables_run(self, app):
        app._set_downloading(True)
        assert str(app.run_btn.cget("state")) == "disabled"
        assert str(app.stop_btn.cget("state")) == "normal"
        assert str(app.load_json_url_btn.cget("state")) == "disabled"

    def test_inactive_enables_run(self, app):
        app._set_downloading(True)
        app._set_downloading(False)
        assert str(app.run_btn.cget("state")) == "normal"
        assert str(app.stop_btn.cget("state")) == "disabled"


# \\\ _stop_download \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestStopDownload:
    def test_sets_cancel_event(self, app):
        app._cancel_event.clear()
        app._stop_download()
        assert app._cancel_event.is_set()
        assert "Stop requested" in app.log_lb.get(0)

    def test_idempotent(self, app):
        app._cancel_event.clear()
        app._stop_download()
        app._stop_download()
        # Only one log line should be appended
        assert app.log_lb.size() == 1


# \\\ update_progress \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestUpdateProgress:
    def test_updates_value_and_label(self, app):
        app.progbar.config(maximum=10)
        app.update_progress(5, 10)
        assert app.progbar["value"] == 5
        assert app.PROGRESS.get() == "5/10"


# \\\ _download_images (full path with mocked worker) \\\\\\\\\\\\\\\\\\\\\\\\\


class TestDownloadImages:
    def test_empty_save_path_shows_error(self, app):
        app.SAVE_PATH.set("")
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            app._download_images()
            mb.showerror.assert_called_once()
        assert app._polling is False

    def test_no_selection_returns_early(self, app, tmp_path):
        app.SAVE_PATH.set(str(tmp_path))
        # No items in listbox
        app._download_images()
        assert app._polling is False

    def test_spawns_worker_and_polls(self, app, tmp_path):
        app.SAVE_PATH.set(str(tmp_path))
        app.image_list.insert(tk.END, "https://cdn.example.com/images/images/a.jpg")
        app.image_list.selection_set(0)

        with patch("artstation_artwork_downloader.main.DownloadWorker") as MockWorker:
            instance = MockWorker.return_value
            instance.run = lambda **kw: None
            with patch.object(app, "after"):
                app._download_images()

        assert app._polling is True
        assert str(app.run_btn.cget("state")) == "disabled"
        assert app.PROGRESS.get() == "0/1"

    def test_nonexistent_dir_shows_error(self, app):
        app.SAVE_PATH.set("/does/not/exist/xyz")
        app.image_list.insert(tk.END, "url")
        app.image_list.selection_set(0)
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            app._download_images()
            mb.showerror.assert_called_once()
        assert app._polling is False

    def test_no_worker_when_already_polling(self, app, tmp_path):
        app.SAVE_PATH.set(str(tmp_path))
        app.image_list.insert(tk.END, "https://cdn.example.com/images/images/a.jpg")
        app.image_list.selection_set(0)
        app._polling = True

        with patch("artstation_artwork_downloader.main.DownloadWorker") as MockWorker:
            app._download_images()
        MockWorker.assert_not_called()


# \\\ show_context_menu \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestShowContextMenu:
    def test_pops_menu(self, app):
        mock_event = MagicMock()
        mock_event.widget = app.image_list
        mock_event.x_root = 100
        mock_event.y_root = 200

        with (
            patch.object(app.image_list_menu, "tk_popup") as mock_popup,
            patch.object(app.image_list_menu, "grab_release"),
        ):
            app.show_context_menu(mock_event)
            mock_popup.assert_called_once_with(100, 200)

    def test_no_menu_assigned(self, app):
        bare_widget = MagicMock()
        bare_widget.context_menu = None

        mock_event = MagicMock()
        mock_event.widget = bare_widget

        # Should not raise
        app.show_context_menu(mock_event)


# \\\ _poll_queue (message dispatch from worker thread) \\\\\\\\\\\\\\\\\\\\\\\


class TestPollQueue:
    def test_log_message(self, app):
        app._polling = True
        app._gui_queue.put(("log", "hello"))
        with patch.object(app, "after"):
            app._poll_queue()
        app.update_idletasks()
        assert app.log_lb.get(0) == "hello"
        assert app._polling is True

    def test_done_message_stops_polling(self, app):
        app._polling = True
        app._gui_queue.put(("done",))
        with patch.object(app, "after"):
            app._poll_queue()
        assert app._polling is False
        assert str(app.run_btn.cget("state")) == "normal"

    def test_progress_message(self, app):
        app._polling = True
        app.progbar.config(maximum=5)
        app._gui_queue.put(("progress", 3, 5))
        with patch.object(app, "after"):
            app._poll_queue()
        assert app.PROGRESS.get() == "3/5"

    def test_dialog_result_dispatched(self, app):
        app._polling = True
        result_event = threading.Event()
        app._gui_queue.put(("dialog", lambda: "user_answer", {}, result_event))
        with patch.object(app, "after"):
            app._poll_queue()
        assert result_event.is_set()
        assert app._resp_queue.get() == "user_answer"

    def test_dialog_exception_captured(self, app):
        app._polling = True
        result_event = threading.Event()

        def raise_fn():
            raise RuntimeError("boom")

        app._gui_queue.put(("dialog", raise_fn, {}, result_event))
        with patch.object(app, "after"):
            app._poll_queue()
        assert result_event.is_set()
        result = app._resp_queue.get()
        assert isinstance(result, RuntimeError)


# \\\ _ask_on_main \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestAskOnMain:
    def test_blocks_until_main_responds(self, app):

        result_holder = []

        def ask_thread():
            result_holder.append(app._ask_on_main(lambda: "ok"))

        t = threading.Thread(target=ask_thread)
        t.start()

        # Simulate main thread: drain queue, respond, release
        msg = app._gui_queue.get(timeout=2)
        assert msg[0] == "dialog"
        _, dialog_fn, kwargs, event = msg
        app._resp_queue.put(dialog_fn(**kwargs))
        event.set()

        t.join(timeout=2)
        assert result_holder == ["ok"]

    def test_exception_propagated(self, app):

        result_holder = []

        def ask_thread():
            result_holder.append(app._ask_on_main(lambda: 1 / 0))

        t = threading.Thread(target=ask_thread)
        t.start()

        msg = app._gui_queue.get(
            timeout=2
        )  # timeout=2 to avoid deadlocks from blocking the test
        _, dialog_fn, kwargs, event = msg
        try:
            app._resp_queue.put(dialog_fn(**kwargs))
        except ZeroDivisionError as e:
            app._resp_queue.put(e)
        event.set()

        t.join(timeout=2)
        assert isinstance(result_holder[0], ZeroDivisionError)


# \\\ show_on_disk \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestShowOnDisk:
    def test_no_selection_warns(self, app):
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            app.show_on_disk(app.log_lb)
            mb.showwarning.assert_called_once()

    def test_invalid_prefix_warns(self, app):
        app.log_lb.insert(tk.END, "some plain text")
        app.log_lb.selection_set(0)
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            app.show_on_disk(app.log_lb)
            mb.showwarning.assert_called_once()

    def test_valid_entry_opens_file(self, app, tmp_path):
        # Create the file so os.path.isfile passes
        target = tmp_path / "result.jpg"
        target.write_bytes(b"fake")
        app.SAVE_PATH.set(str(tmp_path))
        app.log_lb.insert(tk.END, '+ Saved "result.jpg"')
        app.log_lb.selection_set(0)
        with patch(
            "artstation_artwork_downloader.main.show_in_file_manager"
        ) as mock_fm:
            app.show_on_disk(app.log_lb)
            mock_fm.assert_called_once_with(str(target))

    def test_missing_file_warns(self, app, tmp_path):
        app.SAVE_PATH.set(str(tmp_path))
        app.log_lb.insert(tk.END, '+ Saved "missing.jpg"')
        app.log_lb.selection_set(0)
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            app.show_on_disk(app.log_lb)
            mb.showwarning.assert_called_once()


# \\\ copy_filename \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestCopyFilename:
    def test_copies_stripped_name(self, app):
        app.image_list.insert(
            tk.END,
            "https://cdn.example.com/images/images/artist-name-img.jpg?123456789",
        )
        app.image_list.selection_set(0)
        app.copy_filename(app.image_list)
        assert app.clipboard_get() == "artist-name-img"

    def test_no_selection_warns(self, app):
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            app.copy_filename(app.image_list)
            mb.showwarning.assert_called_once()

    def test_multi_selection_warns(self, app):
        app.image_list.insert(tk.END, "a.jpg")
        app.image_list.insert(tk.END, "b.jpg")
        app.image_list.selection_set(0, tk.END)
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            app.copy_filename(app.image_list)
            mb.showwarning.assert_called_once()


# \\\ invert_selection \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestInvertSelection:
    def test_inverts(self, app):
        for i in range(5):
            app.image_list.insert(tk.END, f"url{i}")
        app.image_list.selection_set(0)
        app.image_list.selection_set(2)
        app.invert_selection(app.image_list)
        app.update_idletasks()
        assert set(app.image_list.curselection()) == {1, 3, 4}

    def test_invert_none_selected(self, app):
        app.image_list.insert(tk.END, "a")
        app.image_list.insert(tk.END, "b")
        app.invert_selection(app.image_list)
        app.update_idletasks()
        assert set(app.image_list.curselection()) == {0, 1}


# \\\ _change_theme \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestThemeToggle:
    def test_toggle(self, app):
        assert app.current_theme == "light"
        app._change_theme()
        app.update_idletasks()
        assert app.current_theme == "dark"
        app._change_theme()
        app.update_idletasks()
        assert app.current_theme == "light"


# \\\ open_download_dir \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class TestOpenDownloadDir:
    def test_empty_path_error(self, app):
        app.SAVE_PATH.set("")
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            app.open_download_dir()
            mb.showerror.assert_called_once()

    def test_nonexistent_path_error(self, app):
        app.SAVE_PATH.set("/nonexistent/path/xyz")
        with patch("artstation_artwork_downloader.main.messagebox") as mb:
            app.open_download_dir()
            mb.showerror.assert_called_once()

    def test_valid_path_calls_show_in_fm(self, app, tmp_path):
        app.SAVE_PATH.set(str(tmp_path))
        with patch(
            "artstation_artwork_downloader.main.show_in_file_manager"
        ) as mock_fm:
            app.open_download_dir()
            mock_fm.assert_called_once()
