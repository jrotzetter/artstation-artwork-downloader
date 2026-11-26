import re
import threading
from unittest.mock import MagicMock, call, patch

import requests

from artstation_artwork_downloader.downloader import (
    EXTN_FROM_CONTENT_TYPE,
    HEADERS,
    MAX_RETRIES,
    DownloadWorker,
    determine_img_dimension,
    get_extension,
    get_filename,
    no_cache,
)

# === PURE UTILITIES ==========================================================


class TestNoCache:
    def test_appends_query_with_question_mark(self):
        result = no_cache("https://cdn.example.com/img.jpg")
        assert result.startswith("https://cdn.example.com/img.jpg?")
        suffix = result.split("?", 1)[1]
        assert len(suffix) == 32
        assert re.fullmatch(r"[0-9a-f]{32}", suffix)

    def test_appends_query_with_ampersand_when_params_exist(self):
        result = no_cache("https://cdn.example.com/img.jpg?w=800")
        assert result.startswith("https://cdn.example.com/img.jpg?w=800&")
        suffix = result.rsplit("&", 1)[1]
        assert len(suffix) == 32
        assert re.fullmatch(r"[0-9a-f]{32}", suffix)

    def test_unique_each_call(self):
        a = no_cache("https://cdn.example.com/a.jpg")
        b = no_cache("https://cdn.example.com/a.jpg")
        assert a != b


class TestGetFilename:
    def test_simple_url(self):
        assert get_filename("https://cdn.example.com/images/foo.jpg") == "foo"

    def test_strips_query_params(self):
        assert (
            get_filename("https://cdn.example.com/images/foo.webp?w=800&f=jpg") == "foo"
        )

    def test_nested_path(self):
        assert (
            get_filename("https://cdn.example.com/a/b/c/example-art.png")
            == "example-art"
        )

    def test_no_extension(self):
        assert get_filename("https://cdn.example.com/images/noext") == "noext"


class TestGetExtension:
    def _resp(self, content_type=None):
        r = MagicMock()
        r.headers = {"Content-Type": content_type} if content_type else {}
        return r

    def test_from_content_type(self):
        resp = self._resp("image/png")
        assert (
            get_extension("https://cdn.example.com/file", resp, EXTN_FROM_CONTENT_TYPE)
            == ".png"
        )

    def test_content_type_with_charset(self):
        resp = self._resp("image/jpeg; charset=binary")
        assert (
            get_extension("https://cdn.example.com/file", resp, EXTN_FROM_CONTENT_TYPE)
            == ".jpg"
        )

    def test_content_type_case_insensitive(self):
        resp = self._resp("IMAGE/WEBP")
        assert (
            get_extension("https://cdn.example.com/file", resp, EXTN_FROM_CONTENT_TYPE)
            == ".webp"
        )

    def test_fallback_to_url_suffix(self):
        resp = self._resp("application/octet-stream")
        assert (
            get_extension(
                "https://cdn.example.com/file.avif?x=1", resp, EXTN_FROM_CONTENT_TYPE
            )
            == ".avif"
        )

    def test_no_content_type_header(self):
        resp = self._resp()
        assert (
            get_extension(
                "https://cdn.example.com/file.gif", resp, EXTN_FROM_CONTENT_TYPE
            )
            == ".gif"
        )


class TestDetermineImgDimension:
    def test_gif_passthrough(self):
        url = "https://cdn.example.com/original/anim.gif"
        assert determine_img_dimension(url, "8k", "anim", lambda f: True) == url

    def test_original_dim_user_says_yes(self):
        url = "https://cdn.example.com/original/art.jpg"
        assert determine_img_dimension(url, "8k", "art", lambda f: True) == url

    def test_original_dim_user_says_no(self):
        url = "https://cdn.example.com/original/art.jpg"
        result = determine_img_dimension(url, "8k", "art", lambda f: False)
        assert result == "https://cdn.example.com/8k/art.jpg"

    def test_normal_url_dimension_swap(self):
        url = "https://cdn.example.com/8k/art.jpg"
        result = determine_img_dimension(url, "4k", "art", lambda f: False)
        assert result == "https://cdn.example.com/4k/art.jpg"

    def test_ask_original_not_called_for_gif(self):
        url = "https://cdn.example.com/original/anim.gif"
        mock_ask = MagicMock(side_effect=AssertionError("should not be called"))
        assert determine_img_dimension(url, "8k", "anim", mock_ask) == url


# === DownloadWorker helpers ==================================================


def _make_worker(**overrides):
    """Create a DownloadWorker with mocked callbacks. Returns (worker, mocks)."""
    mocks = {
        "on_log": MagicMock(),
        "on_progress": MagicMock(),
        "on_dialog": MagicMock(return_value=(None, False)),
        "skipvar": MagicMock(get=lambda: False),
        "overwritevar": MagicMock(get=lambda: False),
        "parent": MagicMock(),
        "cancel_event": threading.Event(),
        "on_done": MagicMock(),
    }
    mocks.update(overrides)
    worker = DownloadWorker(**mocks)
    return worker, mocks


def _mock_response(
    content=b"fake image data", content_type="image/png", content_length=None
):
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {}
    if content_type:
        resp.headers["Content-Type"] = content_type
    if content_length is not None:
        resp.headers["Content-Length"] = str(content_length)
    resp.iter_content = lambda chunk_size=None: iter([content])
    resp.raise_for_status.return_value = None
    return resp


def _mock_error_response(status_code):
    """Build a response whose raise_for_status() raises HTTPError."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {}
    resp.raise_for_status.side_effect = requests.HTTPError(
        str(status_code), response=resp
    )
    return resp


def _run_download(worker, url, filename, save_path, sess):
    """Call _download_file with an explicit session."""
    return worker._download_file(url, filename, str(save_path), sess)


# === run() dispatch ==========================================================


class TestRunDispatch:
    def test_calls_default_when_no_custom(self, tmp_path):
        worker, mocks = _make_worker()
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(
                worker, "_download_file", return_value='+ Saved: "a.jpg" (1x1, 10 B)'
            ) as mock_dl,
        ):
            worker.run(
                ["https://cdn.example.com/a.jpg"], str(tmp_path), "8k", "", False, False
            )

        mock_dl.assert_called_once()
        mocks["on_done"].assert_called_once()

    def test_calls_custom_when_enabled(self, tmp_path):
        worker, mocks = _make_worker()
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(
                worker, "_download_file", return_value='+ Saved: "img1.jpg" (1x1, 10 B)'
            ) as mock_dl,
        ):
            worker.run(
                ["https://cdn.example.com/a.jpg"],
                str(tmp_path),
                "8k",
                "img$#",
                True,
                False,
            )

        mock_dl.assert_called_once()
        # Custom name with $# -> "img1"
        assert mock_dl.call_args[0][1] == "img1"
        mocks["on_done"].assert_called_once()

    def test_always_logs_summary_and_calls_done(self, tmp_path):
        worker, mocks = _make_worker()
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(
                worker, "_download_file", return_value='+ Saved: "a.jpg" (1x1, 10 B)'
            ),
        ):
            worker.run(
                ["https://cdn.example.com/a.jpg"], str(tmp_path), "8k", "", False, False
            )

        summary_calls = [c for c in mocks["on_log"].call_args_list if ">>>" in c[0][0]]
        assert len(summary_calls) == 1
        mocks["on_done"].assert_called_once()

    def test_done_called_after_error_result(self, tmp_path):
        """_download_file returns an error string (never raises); on_done still fires."""
        worker, mocks = _make_worker()

        def _fail(url, filename, save_path, sess):
            worker.errors += 1
            return '! Failed "url": boom'

        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(worker, "_download_file", side_effect=_fail),
        ):
            worker.run(
                ["https://cdn.example.com/a.jpg"], str(tmp_path), "8k", "", False, False
            )

        mocks["on_done"].assert_called_once()
        summary = next(
            c[0][0] for c in mocks["on_log"].call_args_list if ">>>" in c[0][0]
        )
        assert "Errors: 1" in summary


# === _run_default ============================================================


class TestRunDefault:
    def test_cancel_stops_early(self, tmp_path):
        worker, mocks = _make_worker()
        worker._cancel.set()
        worker._skip_existing = False

        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(worker, "_download_file") as mock_dl,
        ):
            worker._run_default(["url1", "url2", "url3"], str(tmp_path), "8k", 3)

        mock_dl.assert_not_called()
        assert worker.skips == 3
        logged = [c[0][0] for c in mocks["on_log"].call_args_list]
        assert any("3 file(s) remaining" in line for line in logged)

    def test_cancel_mid_batch(self, tmp_path):
        worker, mocks = _make_worker()
        worker._skip_existing = False

        def _cancel_after_first(url, filename, save_path, sess):
            worker._cancel.set()
            return '+ Saved: "a.jpg" (1x1, 10 B)'

        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(worker, "_download_file", side_effect=_cancel_after_first),
        ):
            worker._run_default(
                [
                    "https://cdn.example.com/a.jpg",
                    "https://cdn.example.com/b.jpg",
                    "https://cdn.example.com/c.jpg",
                ],
                str(tmp_path),
                "8k",
                3,
            )

        assert worker.saved == 0  # mock doesn't increment; only checking flow
        logged = [c[0][0] for c in mocks["on_log"].call_args_list]
        assert any("2 file(s) remaining" in line for line in logged)

    def test_progress_called_per_image(self, tmp_path):
        worker, mocks = _make_worker()
        worker._skip_existing = False
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(
                worker, "_download_file", return_value='+ Saved: "a.jpg" (1x1, 10 B)'
            ),
        ):
            worker._run_default(
                ["https://cdn.example.com/a.jpg", "https://cdn.example.com/b.jpg"],
                str(tmp_path),
                "8k",
                2,
            )

        assert mocks["on_progress"].call_args_list == [call(1, 2), call(2, 2)]

    def test_429_breaks_loop(self, tmp_path):
        worker, mocks = _make_worker()
        worker._skip_existing = False
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(worker, "_download_file", return_value="429"),
            patch.object(worker, "_handle_rate_limit") as mock_rl,
        ):
            worker._run_default(
                ["https://cdn.example.com/a.jpg", "https://cdn.example.com/b.jpg"],
                str(tmp_path),
                "8k",
                2,
            )

        mock_rl.assert_called_once_with(2)
        # Second image should NOT be attempted
        assert mocks["on_progress"].call_count == 0  # progress only after non-429


# === _run_custom =============================================================


class TestRunCustom:
    def test_n_substitution(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(
                worker, "_download_file", return_value='+ Saved: "x.jpg" (1x1, 10 B)'
            ) as mock_dl,
        ):
            worker._run_custom(
                "custom_name_$N",
                ["https://cdn.example.com/artwork-1.jpg"],
                str(tmp_path),
                "8k",
                1,
            )

        assert mock_dl.call_args[0][1] == "custom_name_artwork-1"

    def test_hash_counter(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(
                worker, "_download_file", return_value='+ Saved: "x.jpg" (1x1, 10 B)'
            ) as mock_dl,
        ):
            worker._run_custom(
                "img$#",
                [
                    "https://cdn.example.com/a.jpg",
                    "https://cdn.example.com/b.jpg",
                    "https://cdn.example.com/c.jpg",
                ],
                str(tmp_path),
                "8k",
                3,
            )

        names = [c[0][1] for c in mock_dl.call_args_list]
        assert names == ["img1", "img2", "img3"]

    def test_hash_n_starting_counter(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(
                worker, "_download_file", return_value='+ Saved: "x.jpg" (1x1, 10 B)'
            ) as mock_dl,
        ):
            worker._run_custom(
                "img$#{5}",
                [
                    "https://cdn.example.com/a.jpg",
                    "https://cdn.example.com/b.jpg",
                    "https://cdn.example.com/c.jpg",
                ],
                str(tmp_path),
                "8k",
                3,
            )

        names = [c[0][1] for c in mock_dl.call_args_list]
        assert names == ["img5", "img6", "img7"]

    def test_auto_numbering_no_placeholder(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(
                worker, "_download_file", return_value='+ Saved: "x.jpg" (1x1, 10 B)'
            ) as mock_dl,
        ):
            worker._run_custom(
                "art",
                [
                    "https://cdn.example.com/a.jpg",
                    "https://cdn.example.com/b.jpg",
                    "https://cdn.example.com/c.jpg",
                ],
                str(tmp_path),
                "8k",
                3,
            )

        names = [c[0][1] for c in mock_dl.call_args_list]
        assert names == ["art1", "art2", "art3"]

    def test_auto_numbering_multi_digit_padding(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        urls = [f"https://cdn.example.com/img{i}.jpg" for i in range(1, 13)]
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(
                worker, "_download_file", return_value='+ Saved: "x.jpg" (1x1, 10 B)'
            ) as mock_dl,
        ):
            worker._run_custom("art", urls, str(tmp_path), "8k", 12)

        names = [c[0][1] for c in mock_dl.call_args_list]
        assert names == [f"art{i:02d}" for i in range(1, 13)]

    def test_multi_digit_padding(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        urls = [f"https://cdn.example.com/img{i}.jpg" for i in range(1, 13)]
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(
                worker, "_download_file", return_value='+ Saved: "x.jpg" (1x1, 10 B)'
            ) as mock_dl,
        ):
            worker._run_custom("art$#", urls, str(tmp_path), "8k", 12)

        names = [c[0][1] for c in mock_dl.call_args_list]
        assert names == [f"art{i:02d}" for i in range(1, 13)]

    def test_single_image_no_auto_number(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(
                worker, "_download_file", return_value='+ Saved: "x.jpg" (1x1, 10 B)'
            ) as mock_dl,
        ):
            worker._run_custom(
                "art", ["https://cdn.example.com/a.jpg"], str(tmp_path), "8k", 1
            )

        assert mock_dl.call_args[0][1] == "art"

    def test_strips_illegal_chars(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(
                worker, "_download_file", return_value='+ Saved: "x.jpg" (1x1, 10 B)'
            ) as mock_dl,
        ):
            worker._run_custom(
                "bad/name:with*chars",
                ["https://cdn.example.com/a.jpg"],
                str(tmp_path),
                "8k",
                1,
            )

        assert mock_dl.call_args[0][1] == "badnamewithchars"

    def test_all_illegal_chars_falls_back_to_default(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        with (
            patch("artstation_artwork_downloader.downloader.requests.Session"),
            patch.object(worker, "_run_default") as mock_default,
        ):
            worker._run_custom(
                "***", ["https://cdn.example.com/a.jpg"], str(tmp_path), "8k", 1
            )

        mock_default.assert_called_once_with(
            ["https://cdn.example.com/a.jpg"], str(tmp_path), "8k", 1
        )


# === _download_file ==========================================================


class TestDownloadFile:
    def test_successful_download(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        content = b"fake"
        resp = _mock_response(
            content=content, content_type="image/png", content_length=len(content)
        )
        sess = MagicMock()
        sess.get.return_value = resp

        with patch(
            "artstation_artwork_downloader.downloader.pymage_size"
        ) as mock_pymage:
            mock_pymage.get_image_size.return_value = MagicMock(
                get_dimensions=lambda: (800, 600)
            )
            result = _run_download(
                worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
            )

        assert result.startswith('+ Saved: "a.png"')
        assert "800x600" in result
        assert worker.saved == 1
        assert (tmp_path / "a.png").read_bytes() == content

    def test_skip_existing_true(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = True
        (tmp_path / "a.png").write_bytes(b"old")
        resp = _mock_response(
            content=b"new", content_type="image/png", content_length=3
        )
        sess = MagicMock()
        sess.get.return_value = resp

        result = _run_download(
            worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
        )

        assert result.startswith("^ Skipped")
        assert worker.skips == 1
        assert worker.saved == 0

    def test_rename_dialog_returns_new_name(self, tmp_path):
        worker, mocks = _make_worker()
        worker._skip_existing = False
        (tmp_path / "a.png").write_bytes(b"old")
        mocks["on_dialog"].return_value = ("renamed", False, False)
        resp = _mock_response(
            content=b"new", content_type="image/png", content_length=3
        )
        sess = MagicMock()
        sess.get.return_value = resp

        with patch(
            "artstation_artwork_downloader.downloader.pymage_size"
        ) as mock_pymage:
            mock_pymage.get_image_size.return_value = MagicMock(
                get_dimensions=lambda: (100, 100)
            )
            result = _run_download(
                worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
            )

        assert "renamed.png" in result
        assert (tmp_path / "renamed.png").exists()
        assert worker.saved == 1

    def test_overwrite_uses_original_name(self, tmp_path):
        worker, mocks = _make_worker()
        worker._skip_existing = False
        (tmp_path / "a.png").write_bytes(b"old")
        mocks["on_dialog"].return_value = (None, True, False)
        resp = _mock_response(
            content=b"new", content_type="image/png", content_length=3
        )
        sess = MagicMock()
        sess.get.return_value = resp

        with patch(
            "artstation_artwork_downloader.downloader.pymage_size"
        ) as mock_pymage:
            mock_pymage.get_image_size.return_value = MagicMock(
                get_dimensions=lambda: (100, 100)
            )
            result = _run_download(
                worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
            )

        assert "overwritten" in result
        assert (tmp_path / "a.png").read_bytes() == b"new"
        assert worker.warnings == 1

    def test_skip_from_dialog(self, tmp_path):
        worker, mocks = _make_worker()
        worker._skip_existing = False
        (tmp_path / "a.png").write_bytes(b"old")
        mocks["on_dialog"].return_value = (None, False, False)
        resp = _mock_response(
            content=b"new", content_type="image/png", content_length=3
        )
        sess = MagicMock()
        sess.get.return_value = resp

        result = _run_download(
            worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
        )

        assert result.startswith("^ Skipped")
        assert worker.skips == 1

    def test_size_mismatch_warning(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        content = b"fake"
        resp = _mock_response(
            content=content, content_type="image/png", content_length=100
        )
        sess = MagicMock()
        sess.get.return_value = resp

        with patch(
            "artstation_artwork_downloader.downloader.pymage_size"
        ) as mock_pymage:
            mock_pymage.get_image_size.return_value = MagicMock(
                get_dimensions=lambda: (10, 10)
            )
            result = _run_download(
                worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
            )

        assert "Warning: File size mismatch" in result
        assert worker.warnings == 1

    def test_pymage_size_failure_uses_question_marks(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        content = b"fake"
        resp = _mock_response(
            content=content, content_type="image/png", content_length=len(content)
        )
        sess = MagicMock()
        sess.get.return_value = resp

        with patch(
            "artstation_artwork_downloader.downloader.pymage_size"
        ) as mock_pymage:
            mock_pymage.get_image_size.side_effect = Exception("unsupported")
            result = _run_download(
                worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
            )

        assert "?x?" in result
        assert worker.saved == 1

    def test_timeout_retries_then_succeeds(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        resp = _mock_response(content=b"ok", content_type="image/png", content_length=2)
        sess = MagicMock()
        sess.get.side_effect = [requests.Timeout("timeout"), resp]
        worker._cancel.wait = MagicMock(
            return_value=False
        )  # not cancelled during backoff

        with patch(
            "artstation_artwork_downloader.downloader.pymage_size"
        ) as mock_pymage:
            mock_pymage.get_image_size.return_value = MagicMock(
                get_dimensions=lambda: (1, 1)
            )
            result = _run_download(
                worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
            )

        assert result.startswith("+ Saved")
        assert sess.get.call_count == 2

    def test_timeout_exhausted(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        sess = MagicMock()
        sess.get.side_effect = requests.Timeout("timeout")
        worker._cancel.wait = MagicMock(return_value=False)

        result = _run_download(
            worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
        )

        assert result.startswith("! Timeout")
        assert worker.errors == 1
        assert sess.get.call_count == MAX_RETRIES

    def test_http_500_retries_then_succeeds(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        good_resp = _mock_response(
            content=b"ok", content_type="image/png", content_length=2
        )
        bad_resp = _mock_error_response(500)
        sess = MagicMock()
        sess.get.side_effect = [bad_resp, good_resp]
        worker._cancel.wait = MagicMock(return_value=False)

        with patch(
            "artstation_artwork_downloader.downloader.pymage_size"
        ) as mock_pymage:
            mock_pymage.get_image_size.return_value = MagicMock(
                get_dimensions=lambda: (1, 1)
            )
            result = _run_download(
                worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
            )

        assert result.startswith("+ Saved")
        assert sess.get.call_count == 2

    def test_http_429_returns_429(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        bad_resp = _mock_error_response(429)
        sess = MagicMock()
        sess.get.return_value = bad_resp

        result = _run_download(
            worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
        )

        assert result == "429"
        assert worker.errors == 1
        assert sess.get.call_count == 1  # 429 is not retryable

    def test_http_404_no_retry(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        bad_resp = _mock_error_response(404)
        sess = MagicMock()
        sess.get.return_value = bad_resp

        result = _run_download(
            worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
        )

        assert result.startswith("! HTTP error")
        assert sess.get.call_count == 1
        assert worker.errors == 1

    def test_cancel_during_retry(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        sess = MagicMock()
        sess.get.side_effect = requests.Timeout("timeout")
        worker._cancel.wait = MagicMock(return_value=True)  # cancel triggered

        result = _run_download(
            worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
        )

        assert "Cancelled" in result
        assert worker.skips == 1

    def test_cleanup_on_error(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        content = b"data"
        resp = _mock_response(
            content=content, content_type="image/png", content_length=len(content)
        )
        # Make iter_content raise after the file is opened
        resp.iter_content = MagicMock(side_effect=OSError("disk full"))
        sess = MagicMock()
        sess.get.return_value = resp

        result = _run_download(
            worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
        )

        assert result.startswith("!")
        assert worker.errors == 1
        assert not (tmp_path / "a.png").exists()

    def test_no_content_length_header(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        content = b"fake"
        # Get mock response  with no Content-Length header
        resp = _mock_response(
            content=content, content_type="image/png", content_length=None
        )
        sess = MagicMock()
        sess.get.return_value = resp

        with patch(
            "artstation_artwork_downloader.downloader.pymage_size"
        ) as mock_pymage:
            mock_pymage.get_image_size.return_value = MagicMock(
                get_dimensions=lambda: (10, 10)
            )
            result = _run_download(
                worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess
            )

        assert result.startswith('+ Saved: "a.png"')
        assert worker.saved == 1

    def test_get_receives_cache_busted_url_and_headers(self, tmp_path):
        worker, _m = _make_worker()
        worker._skip_existing = False
        content = b"fake"
        resp = _mock_response(
            content=content, content_type="image/png", content_length=len(content)
        )
        sess = MagicMock()
        sess.get.return_value = resp

        with patch(
            "artstation_artwork_downloader.downloader.pymage_size"
        ) as mock_pymage:
            mock_pymage.get_image_size.return_value = MagicMock(
                get_dimensions=lambda: (1, 1)
            )
            _run_download(worker, "https://cdn.example.com/a.jpg", "a", tmp_path, sess)

        url_arg = sess.get.call_args[0][0]
        assert url_arg.startswith("https://cdn.example.com/a.jpg?")
        assert len(url_arg.split("?", 1)[1]) == 32
        assert sess.get.call_args[1]["headers"] is HEADERS


# === _get_new_name ===========================================================


class TestGetNewName:
    def test_returns_original_on_overwrite(self, tmp_path):
        worker, mocks = _make_worker()
        (tmp_path / "a.png").write_bytes(b"old")
        mocks["on_dialog"].return_value = (None, True, False)

        result = worker._get_new_name("a", ".png", str(tmp_path), download_size=100)

        assert result == ("a.png", True)

    def test_returns_none_on_skip(self, tmp_path):
        worker, mocks = _make_worker()
        (tmp_path / "a.png").write_bytes(b"old")
        mocks["on_dialog"].return_value = (None, False, False)

        result = worker._get_new_name("a", ".png", str(tmp_path), download_size=100)

        assert result == (None, False)

    def test_skip_all_propagates_to_worker(self, tmp_path):
        worker, mocks = _make_worker()
        worker._skip_existing = False
        (tmp_path / "a.png").write_bytes(b"old")
        mocks["on_dialog"].return_value = (None, False, True)  # skip_all=True

        worker._get_new_name("a", ".png", str(tmp_path), download_size=100)

        assert worker._skip_existing is True

    def test_n_placeholder_in_user_name(self, tmp_path):
        worker, mocks = _make_worker()
        (tmp_path / "a.png").write_bytes(b"old")
        mocks["on_dialog"].return_value = ("prefix_$N", False, False)

        result = worker._get_new_name("a", ".png", str(tmp_path), download_size=100)

        assert result == ("prefix_a.png", False)

    def test_returns_new_name(self, tmp_path):
        worker, mocks = _make_worker()
        (tmp_path / "a.png").write_bytes(b"old")
        mocks["on_dialog"].return_value = ("b", False, False)

        result = worker._get_new_name("a", ".png", str(tmp_path), download_size=100)

        assert result == ("b.png", False)

    def test_recurses_on_collision(self, tmp_path):
        worker, mocks = _make_worker()
        (tmp_path / "a.png").write_bytes(b"old")
        (tmp_path / "b.png").write_bytes(b"also old")
        mocks["on_dialog"].side_effect = [("b", False, False), ("c", False, False)]

        result = worker._get_new_name("a", ".png", str(tmp_path), download_size=100)

        assert result == ("c.png", False)
        assert mocks["on_dialog"].call_count == 2

    def test_size_comparison_equal(self, tmp_path):
        worker, mocks = _make_worker()
        (tmp_path / "a.png").write_bytes(b"12345")
        mocks["on_dialog"].return_value = ("new", False, False)

        worker._get_new_name("a", ".png", str(tmp_path), download_size=5)

        _, kwargs = mocks["on_dialog"].call_args
        assert kwargs["download_is_bigger"] == 2

    def test_size_comparison_download_bigger(self, tmp_path):
        worker, mocks = _make_worker()
        (tmp_path / "a.png").write_bytes(b"123")
        mocks["on_dialog"].return_value = ("new", False, False)

        worker._get_new_name("a", ".png", str(tmp_path), download_size=100)

        _, kwargs = mocks["on_dialog"].call_args
        assert kwargs["download_is_bigger"] == 1

    def test_size_comparison_disk_bigger(self, tmp_path):
        worker, mocks = _make_worker()
        (tmp_path / "a.png").write_bytes(b"1234567890")
        mocks["on_dialog"].return_value = ("new", False, False)

        worker._get_new_name("a", ".png", str(tmp_path), download_size=3)

        _, kwargs = mocks["on_dialog"].call_args
        assert kwargs["download_is_bigger"] == 0


# === _handle_rate_limit ======================================================


class TestHandleRateLimit:
    def test_inflates_skips_and_shows_dialog(self):
        worker, mocks = _make_worker()
        worker.saved = 1
        worker.errors = 0
        worker.skips = 0

        worker._handle_rate_limit(5)

        assert worker.skips == 4
        mocks["on_dialog"].assert_called_once_with(worker._show_rate_limit_warning)
        assert "Rate limit exceeded" in mocks["on_log"].call_args_list[-1][0][0]

    def test_inflates_with_preexisting_skips(self):
        worker, _m = _make_worker()
        worker.saved = 1
        worker.errors = 1
        worker.skips = 2

        worker._handle_rate_limit(10)

        # remaining = 10 - (1+1+2) = 6
        assert worker.skips == 8


# === _ask_original ===========================================================


class TestAskOriginal:
    def test_returns_true_on_yes(self):
        worker, mocks = _make_worker()
        mocks["on_dialog"].return_value = "yes"
        assert worker._ask_original("art") is True

    def test_returns_false_on_no(self):
        worker, mocks = _make_worker()
        mocks["on_dialog"].return_value = "no"
        assert worker._ask_original("art") is False
