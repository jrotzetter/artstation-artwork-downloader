# Copyright (c) 2025-2026 Jérémy Rotzetter

__version__ = "2.4.4"

import json
import logging
import os
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from curl_cffi import requests as cffi_requests
from custom_themes import dark_theme, light_theme
from downloader import DownloadWorker
from showinfm import show_in_file_manager

# Module-level logger
logger = logging.getLogger(__name__)


class ArtStationArtworkDownloader(tk.Tk):
    def __init__(self):
        super().__init__()
        logger.debug("App started")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.title("ArtStation Artwork Project Downloader")
        self.center_window(900, 820)
        # self.resizable(width=False, height=False)
        self.minsize(width=900, height=820)
        self.style = ttk.Style(self)
        # self.style.theme_use("clam") # the 'focus' color of the combobox's selection is a part of the 'clam' style
        # print(ttk.Style().theme_names())
        # print(ttk.Style().lookup("TButton", "font"))
        self._gui_queue = queue.Queue()
        self._resp_queue = queue.Queue()  # main -> worker responses
        self._polling = False

        self.style.theme_create("light", parent="clam", settings=light_theme)
        self.style.theme_create("dark", parent="clam", settings=dark_theme)
        self.style.theme_use("light")

        self.current_theme = "light"

        ###/// GLOBAL VARIABLES \\\###
        self.SAVE_PATH = tk.StringVar()
        self.LOADED_JSON = tk.StringVar()
        self.JSON = tk.StringVar()
        self.CUSTOM_NAME = tk.BooleanVar()
        self.PROGRESS = tk.StringVar()
        BUTTON_WIDTH = 25
        self.SKIP_EXISTING = tk.BooleanVar(value=True)
        self.OVERWRITE = tk.BooleanVar()

        ###/// TOPMENU \\\###
        self.menubar = tk.Menu(self)
        self.config(menu=self.menubar)

        help_menu = tk.Menu(self.menubar, tearoff=0)
        help_menu.add_command(label="About...", command=self._show_about)
        help_menu.add_command(label="How to use...", command=self._show_use)
        help_menu.add_command(
            label="About custom filenames...", command=self._show_filename_help
        )

        fallback_menu = tk.Menu(self.menubar, tearoff=0)
        fallback_menu.add_command(label="Get URL to JSON", command=self.get_json_url)
        fallback_menu.add_command(
            label="Load JSON from clipboard", command=self.load_json_clp
        )

        self.menubar.add_cascade(label="Help", menu=help_menu)
        self.menubar.add_cascade(label="Fallback Method", menu=fallback_menu)
        self.menubar.add_command(
            label="Switch to Dark Mode ", command=self._change_theme
        )
        self.menubar.add_command(label="Exit", command=self._on_close)

        ###/// IMAGES FRAME CONTEXT MENU \\\###
        self.image_list_menu = tk.Menu(self, tearoff=False)
        self.image_list_menu.add_command(
            label="Copy filename", command=lambda: self.copy_filename(self.image_list)
        )
        self.image_list_menu.add_command(
            label="Select all", command=lambda: self.image_list.selection_set(0, tk.END)
        )
        self.image_list_menu.add_command(
            label="Clear selection",
            command=lambda: self.image_list.selection_clear(0, tk.END),
        )

        ###/// LOG FRAME CONTEXT MENU \\\###
        self.log_lb_menu = tk.Menu(self, tearoff=False)
        self.log_lb_menu.add_command(
            label="Show file on disk", command=lambda: self.show_on_disk(self.log_lb)
        )

        ###/// MAIN FRAME \\\###
        self.main_frm = ttk.Frame(master=self)
        self.main_frm.pack(fill=tk.BOTH, expand=True)

        ###/// OPTIONS FRAME \\\###
        self.options_frm = ttk.LabelFrame(
            master=self.main_frm,
            text="Options",
            relief="groove",
        )

        self.img_quality_lbl = ttk.Label(
            master=self.options_frm,
            text="Select image dimensions:",
        )
        img_scale = ["small", "medium", "large", "4k", "8k"]
        self.img_quality = ttk.Combobox(
            master=self.options_frm,
            values=img_scale,
            state="readonly",
            justify="center",
        )
        self.img_quality.set("8k")

        self.select_path_btn = ttk.Button(
            master=self.options_frm,
            text="Select save location",
            width=BUTTON_WIDTH,
            command=self.select_path,
        )
        self.save_path_lbl = ttk.Label(
            master=self.options_frm, text=" Downloads will be saved to:"
        )
        self.save_path_ent = ttk.Entry(
            master=self.options_frm,
            textvariable=self.SAVE_PATH,
            state="readonly",
        )

        self.open_directory_btn = ttk.Button(
            master=self.options_frm,
            text="Open download directory",
            width=BUTTON_WIDTH,
            command=self.open_download_dir,
        )

        self.options_frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.options_frm.grid_columnconfigure(2, weight=1)
        self.options_frm.grid_rowconfigure((0, 1), weight=1)

        self.img_quality_lbl.grid(row=0, column=0, padx=5, pady=(5, 0))
        self.img_quality.grid(row=1, column=0, padx=10, pady=(0, 10))
        self.select_path_btn.grid(row=1, column=1, padx=10, pady=(0, 10))
        self.save_path_lbl.grid(row=0, column=2, padx=5, pady=(5, 0), sticky="W")
        self.save_path_ent.grid(row=1, column=2, padx=10, pady=(0, 10), sticky="EW")
        self.open_directory_btn.grid(row=0, column=2, padx=10, pady=0, sticky="E")

        ###/// JSON FRAME \\\###
        # Container frame for the two methods to load the image urls
        self.json_frm = ttk.Frame(master=self.main_frm, relief="flat")
        self.json_frm.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        ###/// LOAD JSON FRAME \\\###
        self.load_json_frm = ttk.Frame(master=self.json_frm, relief="groove")

        self.project_lbl = ttk.Label(
            master=self.load_json_frm, text="Project URL or ID:"
        )
        self.project_ent = ttk.Entry(
            master=self.load_json_frm,
            width=BUTTON_WIDTH,
        )

        self.load_json_url_btn = ttk.Button(
            master=self.load_json_frm,
            text="Load project",
            width=BUTTON_WIDTH,
            command=self.load_json_url,
        )

        self.loaded_json_lbl = ttk.Label(
            master=self.load_json_frm, text="Loaded project hash ID:"
        )
        self.loaded_json_ent = ttk.Entry(
            master=self.load_json_frm,
            width=BUTTON_WIDTH,
            textvariable=self.LOADED_JSON,
            state="readonly",
            justify=tk.CENTER,
        )

        self.clear_json_btn = ttk.Button(
            master=self.load_json_frm,
            text="Clear image list",
            width=BUTTON_WIDTH,
            command=self._clear_json,
        )

        self.load_json_frm.pack(
            fill=tk.BOTH, expand=True, padx=(10, 50), pady=10, side="left"
        )
        self.load_json_frm.grid_rowconfigure(
            (0, 1, 2, 3), weight=1
        )  # center widgets vertically by giving them equal weight
        self.load_json_frm.grid_columnconfigure(
            (0, 1), weight=1
        )  # center widgets horizontally by giving them equal weight

        self.project_lbl.grid(row=0, column=0, padx=5, pady=(5, 0))
        self.project_ent.grid(row=1, column=0, padx=10, pady=(0, 10))
        self.load_json_url_btn.grid(row=1, column=1, padx=10, pady=(0, 10))
        self.loaded_json_lbl.grid(row=2, column=0, padx=5, pady=0)
        self.loaded_json_ent.grid(row=3, column=0, padx=10, pady=(0, 10))
        self.clear_json_btn.grid(row=3, column=1, padx=10, pady=(0, 10))

        ###/// ARTWORK FRAME \\\###
        self.artwork_frm = ttk.Frame(
            master=self.json_frm,
            relief="groove",
        )

        self.add_artwork = ttk.Button(
            master=self.artwork_frm,
            text="(+) Add individual artwork URL",
            width=30,
            command=self._add_url,
        )

        self.remove_artwork = ttk.Button(
            master=self.artwork_frm,
            text="(-) Remove selected artwork(s)",
            width=30,
            command=self._remove_url,
        )

        self.artwork_frm.pack(
            fill=tk.BOTH, expand=True, padx=(50, 10), pady=10, side="right"
        )
        self.artwork_frm.grid_rowconfigure((0, 1), weight=1)
        self.artwork_frm.grid_columnconfigure(0, weight=1)

        self.add_artwork.grid(row=0, column=0, padx=10, pady=10)
        self.remove_artwork.grid(row=1, column=0, padx=10)

        ###/// IMAGES FRAME \\\###
        self.output_frm = ttk.LabelFrame(
            master=self.main_frm,
            relief="groove",
            text="Choose which artworks to download:",
        )

        self.img_y_scrollbar = ttk.Scrollbar(self.output_frm, orient="vertical")
        self.img_x_scrollbar = ttk.Scrollbar(self.output_frm, orient="horizontal")
        self.image_list = tk.Listbox(
            master=self.output_frm,
            selectmode="multiple",
            yscrollcommand=self.img_y_scrollbar.set,
            xscrollcommand=self.img_x_scrollbar.set,
        )
        self.img_y_scrollbar.config(command=self.image_list.yview)
        self.img_x_scrollbar.config(command=self.image_list.xview)

        self.image_list.context_menu = self.image_list_menu  # Attach menu to widget
        self.image_list.bind("<Button-3>", self.show_context_menu)

        self.output_frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        self.output_frm.grid_rowconfigure(0, weight=1)
        self.output_frm.grid_columnconfigure(0, weight=1)

        self.image_list.grid(row=0, column=0, padx=5, pady=5, sticky="EW")
        self.img_y_scrollbar.grid(row=0, column=1, sticky="NS")
        self.img_x_scrollbar.grid(row=1, column=0, sticky="EW")

        ###/// DOWNLOAD FRAME \\\###
        self.run_frm = ttk.Frame(master=self.main_frm, relief="groove")

        self.skip_check = ttk.Checkbutton(
            master=self.run_frm,
            variable=self.SKIP_EXISTING,
            onvalue=True,
            offvalue=False,
            text="Always skip existing files?",
        )

        self.custom_entry = ttk.Entry(
            master=self.run_frm, width=BUTTON_WIDTH, state="disabled"
        )

        self.custom_name_check = ttk.Checkbutton(
            master=self.run_frm,
            variable=self.CUSTOM_NAME,
            onvalue=True,
            offvalue=False,
            text="Use custom file name?",
            command=lambda v=self.CUSTOM_NAME, e=self.custom_entry: self.show_entry(
                v, e
            ),
        )

        self.run_btn = ttk.Button(
            master=self.run_frm,
            text="Download artworks",
            width=BUTTON_WIDTH,
            command=self._download_images,
        )

        self.run_frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.run_frm.grid_rowconfigure(0, weight=1)
        self.run_frm.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.skip_check.grid(row=0, column=0, padx=10, pady=10)
        self.custom_entry.grid(row=0, column=2, padx=10, pady=10)
        self.custom_name_check.grid(row=0, column=1, padx=10, pady=10)
        self.run_btn.grid(row=0, column=3, padx=10, pady=10)

        ###/// PROGRESSBAR FRAME \\\
        self.progbar_frm = ttk.Frame(master=self.main_frm)

        self.progbar = ttk.Progressbar(master=self.progbar_frm, mode="determinate")
        self.progbar_lbl = ttk.Label(
            master=self.progbar_frm,
            textvariable=self.PROGRESS,
            anchor="center",
            width=5,
            font=("TkDefaultFont", 10, "bold"),
        )

        self.progbar_frm.pack(fill=tk.BOTH, expand=True)
        self.progbar_frm.grid_columnconfigure(0, weight=1)

        self.progbar.grid(row=0, column=0, padx=10, sticky="EW")
        self.progbar_lbl.grid(row=0, column=0, padx=10, pady=10)

        ###/// LOG FRAME \\\###
        self.log_frm = ttk.LabelFrame(
            master=self.main_frm,
            text="Download Status:",
        )

        self.log_y_scrollbar = ttk.Scrollbar(self.log_frm, orient="vertical")
        self.log_x_scrollbar = ttk.Scrollbar(self.log_frm, orient="horizontal")
        self.log_lb = tk.Listbox(
            master=self.log_frm,
            selectmode="browse",
            activestyle="none",
            yscrollcommand=self.log_y_scrollbar.set,
            xscrollcommand=self.log_x_scrollbar.set,
        )
        self.log_y_scrollbar.config(command=self.log_lb.yview)
        self.log_x_scrollbar.config(command=self.log_lb.xview)

        self.log_lb.context_menu = self.log_lb_menu  # Attach menu to widget
        self.log_lb.bind("<Button-3>", self.show_context_menu)

        self.log_frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
        self.log_frm.grid_rowconfigure(0, weight=1)
        self.log_frm.grid_columnconfigure(0, weight=1)

        self.log_lb.grid(row=0, column=0, padx=5, pady=5, sticky="EW")
        self.log_y_scrollbar.grid(row=0, column=1, sticky="NS")
        self.log_x_scrollbar.grid(row=1, column=0, sticky="EW")

        self.clear_log_btn = ttk.Button(
            master=self.main_frm,
            text="Clear download log",
            width=BUTTON_WIDTH,
            command=lambda: self.log_lb.delete(0, tk.END),
        )
        self.clear_log_btn.pack(anchor="e", padx=32, pady=(0, 5))

    ###/// FUNCTIONS \\\###
    def center_window(self, windowWidth: int, windowHeight: int):
        """
        Function to place the app window in the center of the screen when launching it.

        :param windowWidth: Width of the application's main window
        :type windowWidth: int
        :param windowHeight: Height of the application's main window
        :type windowHeight: int
        """
        # Get screen width and height
        widthScreen = self.winfo_screenwidth()
        heightScreen = self.winfo_screenheight()

        # Calculate x and y coordinates for the main window
        x = (widthScreen / 2) - (windowWidth / 2)
        y = (heightScreen / 2) - (windowHeight / 2)

        # Set the dimensions of the app window and where it is placed
        self.geometry("%dx%d+%d+%d" % (windowWidth, windowHeight, x, y))

    def _on_close(self):
        logger.debug("App closed")
        self.destroy()

    @staticmethod
    def _show_about():
        messagebox.showinfo(
            "About",
            f"ArtStation Artwork Project Downloader\n \nAuthor: jrotzetter \nVersion: {__version__} \nLicense: MIT",
        )

    @staticmethod
    def _show_use():
        messagebox.showinfo(
            "How to use",
            "1. Select a save location and image dimensions\n\n"
            "2. Enter the project URL or ID\n"
            "   (e.g., https://artstation.com/artwork/abc123 or just abc123)\n\n"
            "3. Click 'Load project' to fetch artwork data\n"
            "   (If errors occur, try the Fallback Method)\n\n"
            "4. Select the images you want to download\n\n"
            "5. Click 'Download' to save selected images",
        )

    @staticmethod
    def _show_filename_help():
        help_text = (
            "Available patterns for customizing filenames:\n\n"
            "$N  •  Original Name\n"
            "Inserts the source filename.\n"
            "Example: Artwork_$N  becomes  Artwork_artist-image-1.jpg\n\n"
            "$#  •  Sequence Number\n"
            "Sets the sequence number position.\n"
            "Example: I_00$#_mage  becomes  I_001_mage.jpg\n"
            "(If $# is not included, the number is added to the end)\n\n"
            "$#{N}  •  Starting Number\n"
            "Begins the sequence from a specific whole number.\n"
            "Example: img_$#{5}  becomes  img_5.jpg, img_6.jpg...\n"
            "Example: img_$#{10}  becomes  img_10.jpg, img_11.jpg...\n\n"
            "Note: Sequential numbering is applied automatically when downloading multiple images. "
            "For single-image downloads, no number is added."
        )
        messagebox.showinfo("Custom File Naming Options", help_text)

    def _change_theme(self):
        """
        Toggle the application theme between light and dark modes.

        This method inverts the `current_theme` attribute and applies the
        corresponding color configuration to the main window and child
        widgets. It also updates the menu bar entry to offer the opposite
        theme switch.
        """
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

        self.menubar.entryconfigure(3, label=new_label)

    def select_path(self):
        """
        Ask user for a directory and update variable with path to said directory.
        """
        selected_directory = filedialog.askdirectory()
        self.SAVE_PATH.set(selected_directory)

    def open_download_dir(self):
        """
        Opens the currently selected download directory with the OSs default file explorer.
        """
        download_path = self.SAVE_PATH.get()
        if download_path == "":
            messagebox.showerror(
                "Error", "Please select a directory in which to save your downloads"
            )
            return
        elif not os.path.exists(download_path):
            messagebox.showerror("Error", "Directory does not exist")
            return

        # The path needs to be OS specific, i.e. on Windows path needs to
        # contain backslashes
        download_path_abs = os.path.abspath(download_path)
        show_in_file_manager(path_or_uri=download_path_abs)

    def extract_hashid(self, raw_input: str) -> str | None:
        """
        Extracts and validates a projects hash ID from raw input.
        Accepts either a raw hash ID or a full ArtStation project URL.

        Returns:
            str: The valid alphanumeric hash ID.
            None: If validation fails.
        """
        raw_input = raw_input.strip()

        # Handle empty strings
        if not raw_input:
            return None

        # Extract hash ID if it is a URL
        match = re.search(r"artstation\.com/artwork/([a-zA-Z0-9]+)", raw_input)

        if match:
            hashid = match.group(1)
        else:
            # Assume the input is already just the hash ID if no URL pattern is found
            hashid = raw_input

        # Validate hashid format (should only be alphanumeric)
        if not re.match(r"^[a-zA-Z0-9]+$", hashid):
            return None

        return hashid

    def get_json_url(self):
        """
        Returns the URL to a project's JSON data on ArtStation and copies it to the clipboard.
        """
        raw_input = self.project_ent.get()

        # Extract and validate hash ID
        hashid = self.extract_hashid(raw_input)

        if not hashid:
            messagebox.showerror("Error", "No valid Artstation hash ID found in input.")
            return

        url = f"https://www.artstation.com/projects/{hashid}.json"
        self.clipboard_clear()
        self.clipboard_append(url)

    @staticmethod
    def load_json(json_string: str):
        """
        Parses a string containing a JSON document into a Python object.

        :param json_string: A string containing a JSON document
        :type json_string: str
        """
        try:
            data = json.loads(json_string)
            return data
        except json.JSONDecodeError as e:
            logger.debug("JSON parse failed at position %s: %s", e.pos, e.msg)
            messagebox.showerror("Error", f"Invalid JSON: {e}")

    def load_json_clp(self):
        """
        Load JSON data from the clipboard and populate a tkinter listbox with an URL image list.
        """
        try:
            # Retrieve text from the clipboard
            clipboard_text = self.clipboard_get()

            json_content = self.load_json(clipboard_text)
            if json_content is None:
                return
            self._populate_image_list(json_content)
        except tk.TclError:
            messagebox.showerror("Error", "Clipboard is empty")
            return

    def load_json_url(self):
        """
        Load a project's data from ArtStation and populate a tkinter listbox with a list of image URLs.
        Uses extract_hashid to handle input parsing.
        """
        raw_input = self.project_ent.get()

        # Extract and validate hash ID
        hashid = self.extract_hashid(raw_input)

        if not hashid:
            messagebox.showerror("Error", "No valid Artstation hash ID found in input.")
            return

        # Construct URL and fetch data
        url = f"https://www.artstation.com/projects/{hashid}.json"
        logger.debug("Fetching %s", url)

        try:
            response = cffi_requests.get(url, impersonate="chrome", timeout=15)
            response.raise_for_status()
            json_data = response.json()

            self._populate_image_list(json_data)

        except Exception as e:
            logger.error("Failed to fetch project data from %s: %s", url, e)
            messagebox.showerror("Error", f"Failed to get JSON:\n\n{e}")

    def _populate_image_list(self, json_content):
        """
        This function populates the image listbox with a list of URL's to images from a given JSON document.

        :param json_content: A dictionary containing information about an artwork project on ArtStation
        """
        # Clear all items from the listbox
        self.image_list.delete(0, tk.END)
        try:
            id = json_content["hash_id"]
        except KeyError:
            messagebox.showwarning("Warning", "hash ID not found")
            return

        self.LOADED_JSON.set(id)
        assets = json_content["assets"]
        # covers and videos will lead to a 403 when trying to download, best to filter them out
        urls = [
            asset["image_url"] for asset in assets if asset["asset_type"] == "image"
        ]
        if len(urls) != 0:
            for img in urls:
                self.image_list.insert(tk.END, img)
        else:
            messagebox.showinfo("Info", "No images found")

    def _add_url(self):
        """
        Retrieve URL to an artwork on ArtStation from the clipboard and insert it into the artwork listbox.
        """
        try:
            # Retrieve text from the clipboard
            clipboard_text = self.clipboard_get()

            if "images/images" not in clipboard_text:
                messagebox.showerror(
                    "Error",
                    "Clipboard does not contain URL to an artwork on ArtStation",
                )
                return

            if clipboard_text in self.image_list.get(0, "end"):
                messagebox.showerror("Error", "Artwork URL already present")
                return

            self.image_list.insert(tk.END, clipboard_text)
        except tk.TclError:
            messagebox.showerror("Error", "Clipboard is empty")
            return

    def _remove_url(self):
        """
        This function removes the currently selected artwork URLs from the listbox.
        """
        selected_indices = self.image_list.curselection()

        # Delete items in reverse index order, which ensures that removing an
        # item doesn't affect the positions/index of the remaining items to be deleted
        for index in reversed(selected_indices):
            self.image_list.delete(index)

    def _clear_json(self):
        """
        This function empties the listbox containing URLs to images on ArtStation.
        """
        self.LOADED_JSON.set("")
        self.image_list.delete(0, tk.END)

    def show_entry(self, var: tk.BooleanVar, ent: tk.Entry):
        """
        Change the state of a given tkinter entry widget based on a provided boolean variable.

        :param var: The tkinter boolean variable to determine the widget's state. If `True`, the widget is enabled; if `False`, it is disabled.
        :type var: tk.BooleanVar
        :param ent: The tkinter entry widget whose state should be modified according to the value of `var`.
        :type ent: tk.Entry
        """
        if var.get() == 0:
            ent.configure(state="disabled")
        else:
            ent.configure(state="normal")

    def _set_downloading(self, active: bool):
        """Enable/disable buttons based on download state."""
        state = "disabled" if active else "normal"
        self.run_btn.config(state=state)
        self.load_json_url_btn.config(state=state)
        self.clear_json_btn.config(state=state)
        self.add_artwork.config(state=state)
        self.remove_artwork.config(state=state)

    def update_progress(self, index: int, total: int):
        """
        Update the progressbar to reflect the current progress.

        :param index: The value representing the current item being processed
        :type index: int
        :param total: The total number of items / max value of progressbar that need to be processed, used for normalization purposes in computing the progress percentage
        :type total: int
        """
        self.progbar["value"] = index
        self.PROGRESS.set(f"{index}/{total}")
        # self.update_idletasks()

    def _download_images(self):
        """Called by the Download button. Captures state, spawns worker."""
        # \\ Capture all Tk variable values HERE (main thread) \\
        save_path = self.SAVE_PATH.get()
        img_option = self.img_quality.get()
        custom_name = self.custom_entry.get()
        custom_name_check = self.CUSTOM_NAME.get()
        skip_existing = self.SKIP_EXISTING.get()

        if save_path == "":
            messagebox.showerror(
                "Error", "Please select a directory in which to save your downloads"
            )
            return
        elif not os.path.exists(save_path):
            messagebox.showerror("Error", "Directory does not exist")
            return

        # Capture listbox selection before spawning thread
        selections = self.image_list.curselection()
        selected_images = [self.image_list.get(index) for index in selections]

        if not selected_images:
            return

        # Guard: don't start if already polling
        if self._polling:
            return

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
            on_done=lambda: self._gui_queue.put(("done",)),
        )

        # \\ Reset UI (main thread) \\
        self.PROGRESS.set("")
        self.progbar.config(maximum=len(selected_images))
        self.progbar["value"] = 0
        self.PROGRESS.set(f"0/{len(selected_images)}")

        # \\ Spawn worker \\
        self._download_thread = threading.Thread(
            target=worker.run,
            kwargs={
                "selected_images": selected_images,
                "save_path": save_path,
                "img_option": img_option,
                "custom_name": custom_name,
                "custom_name_check": custom_name_check,
                "skip_existing": skip_existing,
            },
            daemon=True,
        )
        self._download_thread.start()
        if not self._polling:  # Start polling if not already running
            self._polling = True
            self._poll_queue()

    def show_context_menu(self, event):
        # Get the widget that triggered the event (i.e. was right-clicked)
        widget = event.widget

        menu = getattr(widget, "context_menu", None)
        if menu is None:
            logger.warning(f"No context menu assigned to {widget}")
            return
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def copy_filename(self, listbox: tk.Listbox):
        """
        Copy the filename without the file extension from a selected URL in a
        listbox directly to the clipboard.

        :param listbox: tkinter.Listbox widget with selected URL from which
         the filename should be obtained
        :type listbox: tkinter.Listbox
        """
        index = listbox.curselection()
        if not index:
            messagebox.showwarning("Warning", "No download entry selected")
        elif len(index) > 1:
            messagebox.showwarning("Warning", "More than one entry selected")
            return
        else:
            url = listbox.get(index)
            clean_url = url.split("?", 1)[0]
            basename = os.path.basename(clean_url)
            cleaned_name = os.path.splitext(basename)[0]
            self.clipboard_clear()
            self.clipboard_append(cleaned_name)

    def show_on_disk(self, listbox: tk.Listbox):
        index = listbox.curselection()
        save_dir = self.SAVE_PATH.get()
        if not index:
            messagebox.showwarning("Warning", "No download entry selected")
        else:
            element = listbox.get(index)
            if element.startswith(("+", "*", "^")):
                pattern = r'"(.*?)"'
                result = re.search(pattern, element)
                if result:
                    matches = re.findall(pattern, element)
                    if len(matches) > 1:
                        file_path = os.path.join(save_dir, matches[-1])
                        show_in_file_manager(file_path)
                    else:
                        file_path = os.path.join(save_dir, matches[0])
                        show_in_file_manager(file_path)
                else:
                    messagebox.showwarning("Warning", "No file found in selection")
            else:
                messagebox.showwarning("Warning", "Not a valid selection")

    # \\\ Main-thread side \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

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
                        result = dialog_fn(**kwargs)  # Blocks until user responds
                        self._resp_queue.put(result)
                    except Exception as e:
                        self._resp_queue.put(e)
                    finally:
                        result_event.set()

                elif kind == "done":
                    self._polling = False
                    self._set_downloading(False)
                    return  # stop the after-loop

        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    # \\\ Background-thread side \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\

    def _ask_on_main(self, dialog_fn, **kwargs):
        """Show a modal dialog on the main thread, return its result here."""
        event = threading.Event()
        self._gui_queue.put(("dialog", dialog_fn, kwargs, event))
        event.wait()  # Block until main thread is done
        return self._resp_queue.get()  # Grab the user's answer


if __name__ == "__main__":
    # Configure logging
    frozen = getattr(sys, "frozen", False)

    log_dir = (
        os.path.dirname(sys.executable)
        if frozen
        else os.path.dirname(os.path.abspath(__file__))
    )
    log_level = (
        logging.WARNING if frozen else logging.DEBUG
    )  # WARNING in frozen builds, DEBUG from source

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        handlers=[
            logging.FileHandler(
                os.path.join(log_dir, "artstation_artwork_downloader.log")
            ),
            logging.StreamHandler(),  # also to console when running from terminal
        ],
    )

    app = ArtStationArtworkDownloader()
    app.mainloop()
