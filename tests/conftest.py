from tkinter import TclError
from unittest.mock import MagicMock, patch

import pytest

import artstation_artwork_downloader.main as app_module
from artstation_artwork_downloader.main import ArtStationArtworkDownloader


@pytest.fixture
def app():
    """Instantiate the Tk app with external I/O mocked out."""
    with patch.object(app_module.cffi_requests, "Session") as mock_sess:
        mock_sess.return_value = MagicMock()
        a = ArtStationArtworkDownloader()
        a.update_idletasks()
        yield a
        try:
            a.destroy()
        except TclError:
            pass
