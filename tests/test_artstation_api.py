from unittest.mock import MagicMock, patch

import pytest
import requests

from artstation_artwork_downloader.artstation_api import (
    RETRYABLE,
    extract_hashid,
    fetch_project,
    fetch_with_retry,
    load_json,
)

# === extract_hashid ===========================================================


class TestExtractHashid:
    def test_raw_hashid(self):
        assert extract_hashid("abc123") == "abc123"

    def test_url_with_hashid(self):
        url = "https://www.artstation.com/artwork/xyz789"
        assert extract_hashid(url) == "xyz789"

    def test_url_with_query_params(self):
        url = "https://www.artstation.com/artwork/abc123?foo=bar123456789"
        assert extract_hashid(url) == "abc123"

    def test_url_trailing_slash(self):
        assert extract_hashid("https://www.artstation.com/artwork/abc123/") == "abc123"

    def test_whitespace_stripped(self):
        assert extract_hashid("  abc123  ") == "abc123"

    def test_empty_string(self):
        assert extract_hashid("") is None

    def test_whitespace_only(self):
        assert extract_hashid("   ") is None

    def test_invalid_characters(self):
        assert extract_hashid("abc-123") is None

    def test_invalid_characters_in_url(self):
        # regex stops at non-alphanumeric
        url = "https://www.artstation.com/artwork/abc-123"
        assert extract_hashid(url) == "abc"

    def test_mixed_case(self):
        assert extract_hashid("A1b2C3") == "A1b2C3"

    def test_digits_only(self):
        assert extract_hashid("12345") == "12345"


# === load_json ================================================================


class TestLoadJson:
    def test_valid_object(self):
        assert load_json('{"hash_id": "A1b2C3"}') == {"hash_id": "A1b2C3"}

    def test_valid_array(self):
        assert load_json("[1, 2, 3]") == [1, 2, 3]

    def test_valid_number(self):
        assert load_json("42") == 42

    def test_valid_null(self):
        assert load_json("null") is None

    def test_invalid_json(self):
        assert load_json("{invalid}") is None

    def test_empty_string(self):
        assert load_json("") is None


# === fetch_with_retry =========================================================


def _make_response(status_code, json_data=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status_code} Error")
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestFetchWithRetry:
    @patch("artstation_artwork_downloader.artstation_api.time.sleep")
    def test_success_first_try(self, mock_sleep):
        session = MagicMock()
        resp = _make_response(200)
        session.get.return_value = resp

        result = fetch_with_retry(session, "http://example.com")

        assert result is resp
        assert session.get.call_count == 1
        mock_sleep.assert_not_called()

    @patch("artstation_artwork_downloader.artstation_api.time.sleep")
    def test_retry_on_403_then_success(self, mock_sleep):
        session = MagicMock()
        session.get.side_effect = [_make_response(403), _make_response(200)]

        result = fetch_with_retry(session, "http://example.com", delay=0.1)

        assert result.status_code == 200
        assert session.get.call_count == 2
        mock_sleep.assert_called_once_with(0.1)

    @patch("artstation_artwork_downloader.artstation_api.time.sleep")
    def test_retry_on_500_then_success(self, mock_sleep):
        session = MagicMock()
        session.get.side_effect = [_make_response(500), _make_response(200)]

        result = fetch_with_retry(session, "http://example.com", delay=0.1)

        assert result.status_code == 200
        assert session.get.call_count == 2

    @patch("artstation_artwork_downloader.artstation_api.time.sleep")
    def test_exhausts_retries_raises(self, mock_sleep):
        session = MagicMock()
        session.get.return_value = _make_response(503)

        with pytest.raises(requests.HTTPError):
            fetch_with_retry(session, "http://example.com", max_retries=3, delay=0.1)

        assert session.get.call_count == 3
        assert mock_sleep.call_count == 2  # sleeps between retries, not after last

    @patch("artstation_artwork_downloader.artstation_api.time.sleep")
    def test_exhausts_retries_on_403(self, mock_sleep):
        session = MagicMock()
        session.get.return_value = _make_response(403)

        with pytest.raises(requests.HTTPError):
            fetch_with_retry(session, "http://example.com", max_retries=2)

        assert session.get.call_count == 2
        assert mock_sleep.call_count == 1

    @patch("artstation_artwork_downloader.artstation_api.time.sleep")
    def test_no_retry_on_429(self, mock_sleep):
        session = MagicMock()
        session.get.return_value = _make_response(429)

        with pytest.raises(requests.HTTPError):
            fetch_with_retry(session, "http://example.com")

        assert session.get.call_count == 1
        mock_sleep.assert_not_called()

    @patch("artstation_artwork_downloader.artstation_api.time.sleep")
    def test_no_retry_on_404(self, mock_sleep):
        session = MagicMock()
        session.get.return_value = _make_response(404)

        with pytest.raises(requests.HTTPError):
            fetch_with_retry(session, "http://example.com")

        assert session.get.call_count == 1
        mock_sleep.assert_not_called()

    @patch("artstation_artwork_downloader.artstation_api.time.sleep")
    @pytest.mark.parametrize("code", sorted(RETRYABLE))
    def test_all_retryable_codes(self, mock_sleep, code):
        session = MagicMock()
        session.get.side_effect = [_make_response(code), _make_response(200)]
        result = fetch_with_retry(session, "http://example.com", delay=0.01)
        assert result.status_code == 200

    @patch("artstation_artwork_downloader.artstation_api.time.sleep")
    def test_max_retries_one_no_retry(self, mock_sleep):
        # Edge case: max_retries=1 means no retry is possible
        session = MagicMock()
        session.get.return_value = _make_response(500)
        with pytest.raises(requests.HTTPError):
            fetch_with_retry(session, "http://example.com", max_retries=1)
        assert session.get.call_count == 1
        mock_sleep.assert_not_called()


# === fetch_project ============================================================


class TestFetchProject:
    @patch("artstation_artwork_downloader.artstation_api.time.sleep")
    def test_returns_parsed_json(self, mock_sleep):
        session = MagicMock()
        data = {"title": "Test Project", "id": 123}
        resp = _make_response(200, json_data=data)
        session.get.return_value = resp

        result = fetch_project(session, "abc123")

        assert result == data
        session.get.assert_called_once_with(
            "https://www.artstation.com/projects/abc123.json"
        )

    @patch("artstation_artwork_downloader.artstation_api.time.sleep")
    def test_retries_on_failure(self, mock_sleep):
        session = MagicMock()
        data = {"title": "OK"}
        session.get.side_effect = [
            _make_response(502),
            _make_response(200, json_data=data),
        ]

        result = fetch_project(session, "xyz")

        assert result == data
        assert session.get.call_count == 2

    def test_fetch_project_malformed_json(self):
        session = MagicMock()
        resp = _make_response(200)
        resp.json.side_effect = requests.exceptions.JSONDecodeError("bad", "", 0)
        session.get.return_value = resp

        with pytest.raises(requests.exceptions.JSONDecodeError):
            fetch_project(session, "abc")
