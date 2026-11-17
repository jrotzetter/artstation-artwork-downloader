# Copyright (c) 2025-2026 Jérémy Rotzetter

import logging
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from curl_cffi import requests as cffi_requests
from showinfm import show_in_file_manager

from . import __version__, ui
from .artstation_api import extract_hashid, fetch_project, load_json
from .custom_themes import dark_theme, light_theme
from .downloader import DownloadWorker

logger = logging.getLogger(__name__)


class ArtStationArtworkDownloader(tk.Tk):
    def __init__(self):
        super().__init__()
        logger.debug("App started")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.title("ArtStation Artwork Project Downloader")
        ui.center_window(self, 900, 820)
        self.minsize(width=900, height=820)

        self.style = ttk.Style(self)
        self.style.theme_create("light", parent="clam", settings=light_theme)
        self.style.theme_create("dark", parent="clam", settings=dark_theme)
        self.style.theme_use("light")
        self.current_theme = "light"

        # --- State ---
        self._gui_queue = queue.Queue()
        self._resp_queue = queue.Queue()  # main -> worker responses
        self._cancel_event = threading.Event()
        self._polling = False
        self._session = cffi_requests.Session(impersonate="chrome", timeout=15)

        # --- Tk variables ---
        self.SAVE_PATH = tk.StringVar()
        self.PROJECT_ID = tk.StringVar()
        self.CUSTOM_NAME = tk.BooleanVar()
        self.PROGRESS = tk.StringVar()
        self.SKIP_EXISTING = tk.BooleanVar(value=True)
        self.OVERWRITE = tk.BooleanVar()

        # --- Menubar ---
        self.menubar, self._theme_menu_index = ui.build_menubar(
            self,
            on_about=lambda: ui.show_about(__version__),
            on_use=ui.show_use,
            on_filename_help=ui.show_filename_help,
            on_get_json_url=self.get_json_url,
            on_load_json_clp=self.load_json_clp,
            on_change_theme=self._change_theme,
            on_close=self._on_close,
        )

        # --- Context menus ---
        self.image_list_menu = ui.build_image_list_menu(
            self,
            on_copy=lambda: ui.copy_filename(self, self.image_list),
            on_select_all=lambda: self.image_list.selection_set(0, tk.END),
            on_invert=lambda: ui.invert_selection(self.image_list),
            on_clear=lambda: self.image_list.selection_clear(0, tk.END),
        )
        self.log_lb_menu = ui.build_log_menu(
            self,
            on_show_on_disk=lambda: ui.show_on_disk(self, self.log_lb),
        )

        # --- Frames ---
        self.main_frm = ttk.Frame(master=self)
        self.main_frm.pack(fill=tk.BOTH, expand=True)

        opts = ui.build_options_frame(self.main_frm, self.SAVE_PATH)
        self.img_quality = opts["img_quality"]
        opts["select_path_btn"].config(command=self.select_path)
        opts["open_dir_btn"].config(command=self.open_download_dir)

        src = ui.build_source_frame(self.main_frm, self.PROJECT_ID)
        self.project_ent = src["project_ent"]
        src["load_btn"].config(command=self.load_json_url)
        src["clear_btn"].config(command=self._clear_list)
        src["add_btn"].config(command=self._add_url)
        src["remove_btn"].config(command=self._remove_url)

        sel = ui.build_selection_frame(self.main_frm, self.image_list_menu)
        self.image_list = sel["image_list"]

        dwnld = ui.build_download_frame(
            self.main_frm, self.SKIP_EXISTING, self.CUSTOM_NAME
        )
        self.custom_entry = dwnld["custom_entry"]
        dwnld["custom_check"].config(
            command=lambda: self.show_entry(self.CUSTOM_NAME, self.custom_entry)
        )
        self.stop_btn = dwnld["stop_btn"]
        self.run_btn = dwnld["run_btn"]
        self.run_btn.config(command=self._download_images)
        self.stop_btn.config(command=self._stop_download)

        prog = ui.build_progressbar_frame(self.main_frm, self.PROGRESS)
        self.progbar = prog["progbar"]

        log = ui.build_log_frame(self.main_frm, self.log_lb_menu)
        self.log_lb = log["log_lb"]
        log["clear_btn"].config(command=lambda: self.log_lb.delete(0, tk.END))

        # --- References used by _set_downloading ---
        self.load_project_btn = src["load_btn"]
        self.clear_list_btn = src["clear_btn"]
        self.add_artwork_btn = src["add_btn"]
        self.remove_artwork_btn = src["remove_btn"]

    # === Lifecycle ===========================================================

    def _on_close(self):
        logger.debug("App closed")
        self._cancel_event.set()  # Signal worker to stop
        if hasattr(self, "_download_thread") and self._download_thread.is_alive():
            self._log_append("\u25a0 Closing - finishing current file...")
            self.update()  # Flush display so the user actually sees it
            self._download_thread.join(timeout=30)
            if self._download_thread.is_alive():
                logger.warning(
                    "Download thread still alive after 30s timeout; "
                    "current file may be incomplete"
                )
            else:
                logger.debug("Download thread finished cleanly")
        self._session.close()
        self.destroy()

    # === Theme ===============================================================

    def _change_theme(self):
        if self.current_theme == "light":
            self.style.theme_use("dark")
            self.configure(bg="#2d2d2d")
            self.current_theme = "dark"
            # Dark mode listbox
            self.image_list.config(bg="#262626", fg="#e5e5e5")
            self.log_lb.config(bg="#262626", fg="#e5e5e5")
            new_label = "Switch to Light Mode"
        else:
            self.style.theme_use("light")
            self.configure(bg="white")
            self.current_theme = "light"
            # Light mode listbox
            self.image_list.config(bg="white", fg="black")
            self.log_lb.config(bg="white", fg="black")
            new_label = "Switch to Dark Mode "

        self.menubar.entryconfigure(self._theme_menu_index, label=new_label)

    # === File / clipboard / fetch ops ========================================

    def select_path(self):
        self.SAVE_PATH.set(filedialog.askdirectory())

    def open_download_dir(self):
        download_path = self.SAVE_PATH.get()
        if not download_path:
            messagebox.showerror(
                "Error", "Please select a directory in which to save your downloads"
            )
            return
        if not os.path.exists(download_path):
            messagebox.showerror("Error", "Directory does not exist")
            return
        # The path needs to be OS specific, i.e. on Windows path needs to
        # contain backslashes
        show_in_file_manager(path_or_uri=os.path.abspath(download_path))

    def get_json_url(self):
        hashid = extract_hashid(self.project_ent.get())
        if not hashid:
            messagebox.showerror("Error", "No valid Artstation hash ID found in input")
            return
        self.clipboard_clear()
        self.clipboard_append(f"https://www.artstation.com/projects/{hashid}.json")

    def load_json_clp(self):
        try:
            data = load_json(self.clipboard_get())
        except tk.TclError:
            messagebox.showerror("Error", "Clipboard is empty")
            return
        if data is None:
            messagebox.showerror("Error", "Invalid JSON in clipboard")
            return
        self._populate_image_list(data)

    def load_json_url(self):
        hashid = extract_hashid(self.project_ent.get())
        if not hashid:
            messagebox.showerror("Error", "No valid Artstation hash ID found in input")
            return
        try:
            data = fetch_project(self._session, hashid)
            self._populate_image_list(data)
        except Exception as e:
            logger.error("Failed to fetch project data: %s", e)
            messagebox.showerror("Error", f"Failed to get JSON:\n\n{e}")

    # === Image list management ===============================================

    def _populate_image_list(self, json_content):
        self.image_list.delete(0, tk.END)
        try:
            self.PROJECT_ID.set(json_content["hash_id"])
            assets = json_content["assets"]
        except KeyError as e:
            messagebox.showwarning("Warning", f"'{e}' not found in JSON")
            return
        # Covers and videos will lead to a 403 when trying to download, best to filter them out
        urls = [
            asset["image_url"] for asset in assets if asset["asset_type"] == "image"
        ]
        if urls:
            for img in urls:
                self.image_list.insert(tk.END, img)
        else:
            messagebox.showinfo("Info", "No images found")

    def _add_url(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showerror("Error", "Clipboard is empty")
            return
        if "images/images" not in text:
            messagebox.showerror(
                "Error", "Clipboard does not contain URL to an artwork on ArtStation"
            )
            return
        if text in self.image_list.get(0, "end"):
            messagebox.showerror("Error", "Artwork URL already present")
            return
        self.image_list.insert(tk.END, text)

    def _remove_url(self):
        # Delete items in reverse index order, which ensures that removing an
        # item doesn't affect the positions/index of the remaining items to be deleted
        for index in reversed(self.image_list.curselection()):
            self.image_list.delete(index)

    def _clear_list(self):
        self.PROJECT_ID.set("")
        self.image_list.delete(0, tk.END)

    # === UI state helpers ====================================================

    def show_entry(self, var: tk.BooleanVar, ent: tk.Entry):
        ent.configure(state="normal" if var.get() else "disabled")

    def _set_downloading(self, active: bool):
        state = "disabled" if active else "normal"
        self.run_btn.config(state=state)
        self.stop_btn.config(state="normal" if active else "disabled")
        self.load_project_btn.config(state=state)
        self.clear_list_btn.config(state=state)
        self.add_artwork_btn.config(state=state)
        self.remove_artwork_btn.config(state=state)

    def _log_append(self, msg: str):
        self.log_lb.insert(tk.END, msg)
        self.log_lb.see(tk.END)

    def update_progress(self, index: int, total: int):
        self.progbar["value"] = index
        self.PROGRESS.set(f"{index}/{total}")

    # === Download orchestration ==============================================

    def _stop_download(self):
        if self._cancel_event.is_set():
            return
        self._cancel_event.set()
        self._log_append("\u25a0 Stop requested - finishing current file...")

    def _download_images(self):
        save_path = self.SAVE_PATH.get()
        if not save_path:
            messagebox.showerror(
                "Error", "Please select a directory in which to save your downloads"
            )
            return
        if not os.path.exists(save_path):
            messagebox.showerror("Error", "Directory does not exist")
            return

        # Capture listbox selection before spawning thread
        selections = self.image_list.curselection()
        selected_images = [self.image_list.get(i) for i in selections]
        if not selected_images or self._polling:
            return

        self._cancel_event.clear()
        self._set_downloading(True)

        worker = DownloadWorker(
            on_log=lambda msg: self._gui_queue.put(("log", msg)),
            on_progress=lambda cur, total: self._gui_queue.put(
                ("progress", cur, total)
            ),
            on_dialog=self._ask_on_main,
            skipvar=self.SKIP_EXISTING,
            overwritevar=self.OVERWRITE,
            parent=self,
            cancel_event=self._cancel_event,
            on_done=lambda: self._gui_queue.put(("done",)),
        )

        # Reset progress bar (main thread)
        self.PROGRESS.set(f"0/{len(selected_images)}")
        self.progbar.config(maximum=len(selected_images))
        self.progbar["value"] = 0

        # Spawn worker
        self._download_thread = threading.Thread(
            target=worker.run,
            kwargs={
                "selected_images": selected_images,
                "save_path": save_path,
                "img_option": self.img_quality.get(),
                "custom_name": self.custom_entry.get(),
                "custom_name_check": self.CUSTOM_NAME.get(),
                "skip_existing": self.SKIP_EXISTING.get(),
            },
            daemon=True,
        )
        self._download_thread.start()
        if not self._polling:  # Start polling if not already running
            self._polling = True
            self._poll_queue()

    # === Thread bridge =======================================================

    def _poll_queue(self):
        try:
            while True:
                msg = self._gui_queue.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self.log_lb.insert(tk.END, msg[1])
                    self.log_lb.see(tk.END)
                elif kind == "progress":
                    self.update_progress(msg[1], msg[2])
                elif kind == "dialog":
                    _, dialog_fn, kwargs, result_event = msg
                    try:
                        self._resp_queue.put(
                            dialog_fn(**kwargs)
                        )  # Blocks until user responds
                    except Exception as e:
                        self._resp_queue.put(e)
                    finally:
                        result_event.set()
                elif kind == "done":
                    self._polling = False
                    self._set_downloading(False)
                    return  # Stop the after-loop
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _ask_on_main(self, dialog_fn, **kwargs):
        """Show a modal dialog on the main thread, return its result here."""
        event = threading.Event()
        self._gui_queue.put(("dialog", dialog_fn, kwargs, event))
        event.wait()  # Block until main thread is done
        return self._resp_queue.get()  # Grab the user's answer


def main() -> None:
    # Configure logging
    frozen = getattr(sys, "frozen", False)
    log_dir = (
        os.path.dirname(sys.executable)
        if frozen
        else os.path.dirname(os.path.abspath(__file__))
    )
    logging.basicConfig(
        level=logging.WARNING
        if frozen
        else logging.DEBUG,  # WARNING in frozen builds, DEBUG from source
        format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        handlers=[
            logging.FileHandler(
                os.path.join(log_dir, "artstation_artwork_downloader.log")
            ),
            logging.StreamHandler(),  # Also to console when running from terminal
        ],
    )
    ArtStationArtworkDownloader().mainloop()


if __name__ == "__main__":
    main()
