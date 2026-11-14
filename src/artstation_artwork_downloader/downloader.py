# Copyright (c) 2026 Jérémy Rotzetter

"""
Download logic for ArtStation Artwork Project Downloader.
No direct widget manipulation; all user-facing interaction is
delegated to injected callbacks.
"""

import logging
import os
import re
import secrets
from collections.abc import Callable
from tkinter import messagebox
from typing import Any

import pymage_size
import renamedialog
import requests
from humanize import naturalsize

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Cache-Control": "max-age=0, no-cache, no-store, must-revalidate",
}

EXTN_FROM_CONTENT_TYPE = {
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/tiff": ".tiff",
    "image/webp": ".webp",
}

MAX_RETRIES = 3
RETRYABLE_STATUS = {403, 500, 502, 503, 504}

# \\\ Pure utilities \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


def no_cache(url: str) -> str:
    """
    Prevent a cache hit to circumvent Cloudflare's 'optimizations'

    Artstation will send different images depending on whether an image
    is a cache hit or miss due to Cloudflare's 'Polish' image optimization [1].
    This feature removes image metadata, including color profiles, which can
    distort the colors [2], and may even recompress an image which might lead to
    image quality loss [3]. Adding a random dummy query parameter should cause a
    cache miss and prevent this from happening [1].

    References:
        [1] https://github.com/r888888888/danbooru/issues/3528\n
        [2] https://pwmon.org/p/5470/cloudflare-discolors-web/\n
        [3] https://blog.cloudflare.com/introducing-polish-automatic-image-optimizati/

    :param url: URL to an artwork image on ArtStation
    :type url: str
    """
    dummy_param = secrets.token_hex(16)
    # dummy_param = secrets.token_urlsafe(16)
    return f"{url}&{dummy_param}"


def get_filename(url: str) -> str:
    """
    Get the filename from a URL without the file extension.

    :param url: URL to file
    :type url: str
    """
    clean_url = url.split("?", 1)[0]
    return os.path.splitext(os.path.basename(clean_url))[0]


def get_extension(
    url: str, resp: requests.Response, allowed_extn: dict[str, str]
) -> str:
    """
    Get the extension of a file from a URL either from server's response
    Content-Type or from the URL suffix if Content-Type does not exist or
    is not in the dictionary of the allowed extensions.

    :param url: URL to file
    :type url: str
    :param resp: Server's response to HTTP request for file
    :type resp: requests.Response
    :param allowed_extn: A dictionary mapping content types to their respective file extensions
    :type allowed_extn: dict[str, str]
    :return: The extension of the file. If not explicitly found in `resp.headers`, it's retrieved from the URL itself
    :rtype: str
    """
    # Get extension from Content-Type header...
    content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    extn = allowed_extn.get(content_type)
    # ...else fallback to URL suffix if not known Content-Type
    if not extn:
        clean_url = url.split("?", 1)[0]
        extn = os.path.splitext(clean_url)[1]
    return extn


def determine_img_dimension(
    url: str, img_dim: str, filename: str, ask_original: Callable[[str], bool]
) -> str:
    """
    Determines the dimension in the URL at which the image should be
    downloaded, updating the URL accordingly. GIFs will always be
    downloaded at their original size.

    :param url: A string representing the original file URL
    :type url: str
    :param img_dim: A string representing the selected image dimension at which the image should be downloaded
    :type img_dim: str
    :param filename: A string representing the filename
    :type filename: str
    :return: The URL with the chosen image dimension
    :rtype: str
    """
    extn = os.path.splitext(url.split("?", 1)[0])[1]
    if extn == ".gif":
        return url
    elif "/original/" in url:
        if ask_original(filename):
            return url
        parts = url.rsplit("/", 2)
        return f"{parts[0]}/{img_dim}/{parts[2]}"
    else:
        parts = url.rsplit("/", 2)
        return f"{parts[0]}/{img_dim}/{parts[2]}"


# \\\ Worker \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\


class DownloadWorker:
    """
    Download logic for a list of image URLs.

    Designed to run in a background thread. All user-facing interaction
    (dialogs, logging, progress updates) is delegated to injected callbacks
    so the class never touches Tk widgets directly.

    Instance attributes ``saved``, ``errors``, ``skips``, ``warnings``
    count outcomes for the current batch.
    """

    def __init__(
        self,
        on_log: Callable[[str], None],
        on_progress: Callable[[int, int], None],
        on_dialog: Callable[..., Any],
        skipvar,
        overwritevar,
        parent,
        cancel_event,
        on_done,
    ):
        """
        :param on_log: Callable to append a line to the log
        :type on_log: Callable[[str], None]
        :param on_progress: Callable to update the progress bar (current, total)
        :type on_progress: Callable[[int, int], None]
        :param on_dialog: Bridge that dispatches a callable to the main thread,
                          blocks until it returns, and passes the result back
        :type on_dialog: Callable[..., Any]
        :param skipvar: tk.BooleanVar for "Skip all" (SKIP_EXISTING; passed as checkvar to rename dialog)
        :type skipvar: tk.BooleanVar
        :param overwritevar: tk.BooleanVar for "Overwrite" (OVERWRITE; passed to rename dialog)
        :type overwritevar: tk.BooleanVar
        :param parent: tk widget (root window), passed to dialogs
        :type parent: tk.Misc
        :param cancel_event: threading.Event checked at the top of each iteration;
                             when set, the worker stops after the current file
        :type cancel_event: threading.Event
        :param on_done: Callable invoked in the finally block of run() to signal
                        the main thread that the batch has finished
        :type on_done: Callable[[], None]
        """
        self._log = on_log
        self._progress = on_progress
        self._dialog = on_dialog
        self._skipvar = skipvar
        self._overwritevar = overwritevar
        self._parent = parent
        self._cancel = cancel_event
        self._on_done = on_done

        self.saved = 0
        self.errors = 0
        self.skips = 0
        self.warnings = 0
        self._last_overwrite = False

    # \\ Public entry point \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

    def run(
        self,
        selected_images: list[str],
        save_path: str,
        img_option: str,
        custom_name: str,
        custom_name_check: bool,
        skip_existing: bool,
    ):
        """
        Download all selected images. Call this from a background thread.

        :param selected_images: List of image URLs to download
        :type selected_images: list[str]
        :param save_path: Target directory
        :type save_path: str
        :param img_option: Dimension to request (e.g. "8k", "4k")
        :type img_option: str
        :param custom_name: Custom filename pattern (if custom_name_check is True)
        :type custom_name: str
        :param custom_name_check: Whether to use custom naming
        :type custom_name_check: bool
        :param skip_existing: Initial value for "skip all" (may be updated mid-batch)
        :type skip_existing: bool
        """
        self._skip_existing = skip_existing
        progbar_max = len(selected_images)

        try:
            if custom_name_check and custom_name != "":
                self._run_custom(
                    custom_name,
                    selected_images,
                    save_path,
                    img_option,
                    progbar_max,
                )
            else:
                self._run_default(selected_images, save_path, img_option, progbar_max)

        finally:
            self._log(
                f">>> {progbar_max} Files - Saved: {self.saved}, "
                f"Skipped: {self.skips}, Warnings: {self.warnings}, Errors: {self.errors}"
            )
            self._log("")
            self._on_done()

    # \\ Loops \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

    def _run_default(self, images, save_path, img_option, total):
        """
        Download each image using its original URL-derived filename.

        :param images: List of image URLs to download
        :type images: list[str]
        :param save_path: Target directory
        :type save_path: str
        :param img_option: Dimension to request (e.g. "8k", "4k")
        :type img_option: str
        :param total: Total number of images (for progress reporting)
        :type total: int
        """
        with requests.Session() as sess:
            for index, image in enumerate(images, start=1):
                if self._cancel.is_set():
                    remaining = total - index + 1
                    self.skips += remaining
                    self._log(
                        f"\u25a0 {remaining} file(s) remaining in queue - skipped"
                    )
                    return
                filename = get_filename(image)
                image_url = determine_img_dimension(
                    image, img_option, filename, self._ask_original
                )
                result = self._download_file(image_url, filename, save_path, sess)
                if result == "429":
                    self._handle_rate_limit(total)
                    break
                self._log(result)
                self._progress(index, total)

    def _run_custom(self, custom_name, images, save_path, img_option, total):
        """
        Download each image using a user-supplied custom filename pattern.
        Supports `$N` (original filename) and `$#` / `$#N` (counter) placeholders.

        :param custom_name: Custom filename pattern with optional placeholders
        :type custom_name: str
        :param images: List of image URLs to download
        :type images: list[str]
        :param save_path: Target directory
        :type save_path: str
        :param img_option: Dimension to request (e.g. "8k", "4k")
        :type img_option: str
        :param total: Total number of images (for progress reporting)
        :type total: int
        """
        # Strip characters illegal in Windows filenames (slashes, colons, wildcards, ASCII control chars)
        custom_name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", custom_name).strip()
        counter_match = re.search(r"\$\#{(\d+)}", custom_name)
        counter = int(counter_match.group(1)) if counter_match else 1
        increment = 1
        digits = 1

        with requests.Session() as sess:
            for index, image in enumerate(images, start=1):
                if self._cancel.is_set():
                    remaining = total - index + 1
                    self.skips += remaining
                    self._log(
                        f"\u25a0 {remaining} file(s) remaining in queue - skipped"
                    )
                    return
                filename = custom_name
                if "$N" in filename:
                    filename = filename.replace("$N", get_filename(image))

                if counter_match or "$#" in filename:
                    num_formatted = f"{counter:0{digits}d}"
                    if counter_match:
                        filename = re.sub(r"\$\#{(\d+)}", num_formatted, filename)
                    else:
                        filename = filename.replace("$#", num_formatted)
                elif len(images) > 1:
                    filename = f"{filename}{counter}"

                image_url = determine_img_dimension(
                    image, img_option, filename, self._ask_original
                )
                result = self._download_file(image_url, filename, save_path, sess)
                if result == "429":
                    self._handle_rate_limit(total)
                    break
                self._log(result)
                self._progress(index, total)
                counter += increment

    # \\ Single-image download \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

    def _download_file(self, url, filename, save_path, sess) -> str:
        """
        Download an image from a URL and save it to disk, handling naming
        conflicts, file size verification, and dimension extraction.

        :param url: The URL to download the image from.
        :type url: str
        :param filename: Base name for the saved file (without extension);
            the actual extension is determined from the response.
        :type filename: str
        :param save_path: The path where file will be written.
        :type save_path: str
        :param sess: A ``requests.Session`` used to issue the GET request.
        :type sess: requests.Session
        :return: A human-readable status string prefixed with ``+`` (saved),
            ``^`` (skipped), ``*`` (saved with warning), or ``!`` (failed).
            Returns ``"429"`` on rate-limit.
        :rtype: str
        """
        try:
            # Construct URL to file with added dummy query cache-busting parameter to bypass possible cache hit
            url_no_cache = no_cache(url)

            # --- Retry loop around the GET with backoff ---
            resp = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    resp = sess.get(
                        url_no_cache, timeout=15, stream=True, headers=HEADERS
                    )
                    # Check if response was successful else raise error
                    resp.raise_for_status()
                    break  # Success
                except requests.Timeout:
                    if attempt < MAX_RETRIES:
                        delay = 2 ** (attempt - 1)  # 1s, 2s
                        self._log(
                            f"  ... timeout, retrying in {delay}s ({attempt}/{MAX_RETRIES - 1})"
                        )
                        if self._cancel.wait(delay):
                            self.skips += 1
                            return f'^ Cancelled during retry for "{url}"'
                        url_no_cache = no_cache(url)  # Fresh cache-bust
                    else:
                        raise
                except requests.ConnectionError:
                    if attempt < MAX_RETRIES:
                        delay = 2 ** (attempt - 1)
                        self._log(
                            f"  ... connection error, retrying in {delay}s ({attempt}/{MAX_RETRIES - 1})"
                        )
                        if self._cancel.wait(delay):
                            self.skips += 1
                            return f'^ Cancelled during retry for "{url}"'
                        url_no_cache = no_cache(url)
                    else:
                        raise
                except requests.HTTPError as e:
                    if (
                        e.response.status_code in RETRYABLE_STATUS
                        and attempt < MAX_RETRIES
                    ):
                        delay = 2 ** (attempt - 1)
                        self._log(
                            f"  ... HTTP {e.response.status_code}, retrying in {delay}s ({attempt}/{MAX_RETRIES - 1})"
                        )
                        resp.close()
                        if self._cancel.wait(delay):
                            self.skips += 1
                            return f'^ Cancelled during retry for "{url}"'
                        url_no_cache = no_cache(url)
                    else:
                        raise
            # --- End retry loop ---

            with resp:
                # Get the expected content length (i.e. file size) from response header
                content_length = int(resp.headers.get("Content-Length", 0))
                ext = get_extension(url_no_cache, resp, EXTN_FROM_CONTENT_TYPE)
                file = f"{filename}{ext}"
                file_path = os.path.join(save_path, file)
                new_name = None

                # Check if a file with the same name already exists
                if os.path.isfile(file_path):
                    # If SKIP_EXISTING is not checked, prompt user how to handle
                    if not self._skip_existing:
                        if content_length != 0:
                            new_name = self._get_new_name(
                                filename, ext, save_path, content_length
                            )
                        else:
                            new_name = self._get_new_name(filename, ext, save_path)

                    if new_name is None:
                        self.skips += 1
                        return f'^ Skipped "{file}" as it already exists'

                    file_path = os.path.join(save_path, new_name)

                with open(file_path, "wb") as f:
                    # Download the image in chunks instead of loading the entire
                    # file into memory to avoid memory issues
                    for chunk in resp.iter_content(chunk_size=8192):
                        if not chunk:
                            continue  # filters out keep-alive packets so only real file data is written
                        f.write(chunk)

            self.saved += 1
            # Get file size of downloaded image
            file_size = os.path.getsize(file_path)
            human_size = naturalsize(file_size)

            try:
                # Get image dimensions of downloaded file
                img_format = pymage_size.get_image_size(file_path)
                width, height = img_format.get_dimensions()
            except Exception:
                # Give image width and height as `?` in case there is an error
                # e.g. file type is not supported by pymage_size
                logger.debug("Could not get dimensions for %s, using ?/?", file_path)
                width, height = "?", "?"

            if content_length != 0 and content_length != file_size:
                # Check if there is a size difference between reported size
                # found in the response.header (if present) and downloaded file
                # if there is, that could mean there was a cache HIT and a
                # compressed file was downloaded
                self.warnings += 1
                diff = naturalsize(abs(content_length - file_size))
                return (
                    f'* Saved: "{file}" ({width}x{height}, {human_size}) '
                    f"- Warning: File size mismatch between local copy and "
                    f"ArtStation by {diff}"
                )

            if new_name is not None:
                # OVERWRITE was set by the dialog on the main thread;
                # read it via the result returned by _show_rename_dialog
                if self._last_overwrite:
                    self.warnings += 1
                    return (
                        f'* Saved: "{new_name}" ({width}x{height}, {human_size}) '
                        f"- Warning: The original file was overwritten"
                    )
                return f'+ Saved: "{file}" as "{new_name}" ({width}x{height}, {human_size})'

            return f'+ Saved: "{file}" ({width}x{height}, {human_size})'

        except requests.HTTPError as e:
            self.errors += 1
            logger.error("HTTP %s for %s", e.response.status_code, url)
            if e.response.status_code == 429:
                return "429"
            return f"! HTTP error after {MAX_RETRIES} attempts: {e}"
        except requests.Timeout:
            self.errors += 1
            logger.error("Timeout for %s", url)
            return f'! Timeout after {MAX_RETRIES} attempts for "{url}"'
        except requests.RequestException as e:
            self.errors += 1
            logger.error("Request failed for %s: %s", url, e)
            return f'! Failed "{url}": {e}'
        except Exception:
            self.errors += 1
            logger.exception("Unexpected error downloading %s", url)
            return f'! Unexpected error for "{url}"'

    # \\ Rename / overwrite \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

    def _get_new_name(
        self, filename: str, ext: str, save_path: str, download_size: int | None = None
    ) -> str | None:
        """
        Prompt the user to rename a file that already exists in the target
        directory, or to skip/overwrite it. Recurses if the user-chosen
        name also collides with an existing file.

        :param filename: The original name of the file (without extension)
        :type filename: str
        :param ext: The extension of the file
        :type ext: str
        :param save_path: The path to the target directory where files will be saved
        :type save_path: str
        :param download_size: The expected size in bytes of the file to be downloaded
         (if Content-Length is available). If provided, it can indicate whether
         a previously downloaded file is bigger or smaller than the current one
        :type download_size: int | None
        :return: The filename to save as (may be the original name on overwrite),
         or `None` if the file should be skipped.
        :rtype: str | None
        """
        file_path = os.path.join(save_path, f"{filename}{ext}")

        if download_size is not None:
            on_disk = os.path.getsize(file_path)
            # Check whether the reported download size matches file size on disk
            if download_size == on_disk:
                download_is_bigger = 2
            elif download_size > on_disk:
                download_is_bigger = 1
            else:
                download_is_bigger = 0
            size_diff = naturalsize(abs(download_size - on_disk))
        else:
            download_is_bigger = None
            size_diff = None

        # Runs entirely on the main thread via the _dialog bridge
        new_filename, overwrite = self._dialog(
            self._show_rename,
            file_path=file_path,
            initialvalue=filename,
            size_diff=size_diff,
            download_is_bigger=download_is_bigger,
        )
        # Store for the caller (_download_file) to read
        self._last_overwrite = overwrite

        # If the user clicked on the overwrite button, use the original name
        if new_filename is None and overwrite:
            return f"{filename}{ext}"
        # If the user clicked on skip button or entered an empty string,
        # exit function and skip download of this file
        if new_filename is None or new_filename == "":
            return None

        # Check whether a file with this new name exists
        if "$N" in new_filename:
            new_filename = new_filename.replace("$N", filename)
        new_file = f"{new_filename}{ext}"
        new_file_path = os.path.join(save_path, new_file)

        if os.path.isfile(new_file_path):
            if download_size is None:
                return self._get_new_name(new_filename, ext, save_path)
            return self._get_new_name(new_filename, ext, save_path, download_size)
        return new_file

    def _show_rename(self, file_path, initialvalue, size_diff, download_is_bigger):
        """
        Runs on the main thread (dispatched by _dialog). Resets OVERWRITE,
        calls renamedialog.ask_rename, reads OVERWRITE and SKIP_EXISTING.
        Returns (new_filename | None, overwrite: bool).
        """
        self._overwritevar.set(False)
        new_filename = renamedialog.ask_rename(
            checkvar=self._skipvar,
            overwritevar=self._overwritevar,
            file_path=file_path,
            initialvalue=initialvalue,
            size_diff=size_diff,
            download_is_bigger=download_is_bigger,
            parent=self._parent,
        )
        overwrite = self._overwritevar.get()
        # "Skip all" may have set self._skipvar; propagate to the worker's plain bool
        self._skip_existing = self._skipvar.get()
        return (new_filename, overwrite)

    # \\ Original-dimension prompt \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

    def _ask_original(self, filename: str) -> bool:
        """
        Ask the user whether to download at original dimension instead of
        the selected one. Returns True if the user chose "yes".
        """
        answer = self._dialog(self._show_original_prompt, filename=filename)
        return answer == "yes"

    def _show_original_prompt(self, filename):
        """Runs on the main thread via the dialog bridge. Returns 'yes' or 'no'."""

        return messagebox.askquestion(
            "Download original image?",
            f"The original image is available. Would you like to download "
            f'"{filename}" in its original dimension instead of the selected dimension?',
            parent=self._parent,
        )

    # \\ Rate limit \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

    def _handle_rate_limit(self, total):
        """
        Handle a 429 rate-limit response. Inflates the skip counter by the
        number of remaining files so the final summary totals are accurate,
        then shows a warning dialog and logs the cancellation.

        :param total: Total number of images in the current batch
        :type total: int
        """
        self.skips += total - (self.saved + self.errors + self.skips)
        self._dialog(self._show_rate_limit_warning)
        self._log("< Rate limit exceeded, cancelling download of remaining files...")

    def _show_rate_limit_warning(self):
        """Runs on the main thread via the dialog bridge."""

        messagebox.showwarning(
            "Warning: 429 Too Many Requests",
            "Rate limit exceeded. Best take a break and try again later.",
            parent=self._parent,
        )
