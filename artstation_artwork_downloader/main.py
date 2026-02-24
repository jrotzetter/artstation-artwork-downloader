# Copyright (C) 2025 Jérémy Rotzetter

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
import json
import os
import requests
import secrets
import cloudscraper
from humanize import naturalsize
import renamedialog
import pymage_size
from showinfm import show_in_file_manager
import re
from decimal import Decimal


class ArtStationArtworkDownloader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ArtStation Artwork Project Downloader")
        self.center_window(900, 820)
        # self.resizable(width=False, height=False)
        self.minsize(width=900, height=820)
        self.style = ttk.Style(self)
        # self.style.theme_use("clam") # the 'focus' color of the combobox's selection is a part of the 'clam' style
        # print(ttk.Style().theme_names())
        # print(ttk.Style().lookup("TButton", "font"))

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
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About...", command=self._show_about)
        help_menu.add_command(label="How to use...", command=self._show_use)

        fallback_menu = tk.Menu(menubar, tearoff=0)
        fallback_menu.add_command(label="Get URL to JSON", command=self.get_json_url)
        fallback_menu.add_command(
            label="Load JSON from clipboard", command=self.load_json_clp
        )

        menubar.add_cascade(label="Help", menu=help_menu)
        menubar.add_cascade(label="Fallback Method", menu=fallback_menu)
        menubar.add_command(label="Exit", command=self.destroy)

        ###/// LOG FRAME CONTEXT MENU \\\###
        self.log_lb_menu = tk.Menu(self, tearoff=False)
        self.log_lb_menu.add_command(
            label="Show file on disk", command=self.show_on_disk
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
            master=self.load_json_frm, text="Paste project hash ID:"
        )
        self.project_ent = ttk.Entry(
            master=self.load_json_frm,
            width=BUTTON_WIDTH,
        )

        self.load_json_url_btn = ttk.Button(
            master=self.load_json_frm,
            text="Load JSON from URL",
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
            text="Choose images to exclude (optional)",
        )

        img_y_scrollbar = tk.Scrollbar(self.output_frm, orient="vertical")
        img_x_scrollbar = tk.Scrollbar(self.output_frm, orient="horizontal")
        self.image_list = tk.Listbox(
            master=self.output_frm,
            selectmode="multiple",
            yscrollcommand=img_y_scrollbar.set,
            xscrollcommand=img_x_scrollbar.set,
        )
        img_y_scrollbar.config(command=self.image_list.yview)
        img_x_scrollbar.config(command=self.image_list.xview)

        self.output_frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        self.output_frm.grid_rowconfigure(0, weight=1)
        self.output_frm.grid_columnconfigure(0, weight=1)

        self.image_list.grid(row=0, column=0, padx=5, pady=5, sticky="EW")
        img_y_scrollbar.grid(row=0, column=1, sticky="NS")
        img_x_scrollbar.grid(row=1, column=0, sticky="EW")

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

        log_y_scrollbar = tk.Scrollbar(self.log_frm, orient="vertical")
        log_x_scrollbar = tk.Scrollbar(self.log_frm, orient="horizontal")
        self.log_lb = tk.Listbox(
            master=self.log_frm,
            selectmode="browse",
            activestyle="none",
            yscrollcommand=log_y_scrollbar.set,
            xscrollcommand=log_x_scrollbar.set,
        )
        log_y_scrollbar.config(command=self.log_lb.yview)
        log_x_scrollbar.config(command=self.log_lb.xview)

        self.log_lb.bind("<Button-3>", self.show_context_menu)

        self.log_frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.log_frm.grid_rowconfigure(0, weight=1)
        self.log_frm.grid_columnconfigure(0, weight=1)

        self.log_lb.grid(row=0, column=0, padx=5, pady=5, sticky="EW")
        log_y_scrollbar.grid(row=0, column=1, sticky="NS")
        log_x_scrollbar.grid(row=1, column=0, sticky="EW")

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

    @staticmethod
    def _show_about():
        messagebox.showinfo(
            "About",
            "ArtStation Artwork Project Downloader\n \nAuthor: jrotzetter \nVersion: 2.1.2 \nLicense: MIT",
        )

    @staticmethod
    def _show_use():
        messagebox.showinfo(
            "How to use",
            "1. Select a save location and image dimensions\n"
            "2. Paste hash ID (found after artstation.com/artwork/)\n"
            "3. Load JSON from URL (if error use Fallback Method)\n"
            "4. Select images that are to be excluded from download\n"
            "5. Download images",
        )

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

    def get_json_url(self):
        """
        Returns the URL to a project's JSON data on ArtStation and copies it to the clipboard.
        """
        hashid = self.project_ent.get()
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
        Load a project's data from ArtStation and populate a tkinter listbox with an URL image list.
        """
        try:
            hashid = self.project_ent.get()
            url = f"https://www.artstation.com/projects/{hashid}.json"
            scraper = cloudscraper.create_scraper()
            response = scraper.get(url, timeout=15)
            response.raise_for_status()
            json_data = response.json()
            self._populate_image_list(json_data)
        except Exception as e:
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
        if not len(urls) == 0:
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
                    "Error", "Clipboard does not contain URL to an image artwork"
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

    @staticmethod
    def _no_cache(url: str):
        """
        Prevent a cache hit to circumvent Cloudflare's 'optimizations'

        Artstation will send different images depending on whether an image
        is a cache hit or miss due to Cloudflare's 'Polish' image optimization [1].
        This feature removes image metadata, including color profiles, which can
        distort the colors [2], and may even recompress an image which might lead to
        image quality loss [3]. Adding a random dummy query parameter should cause a
        cache miss and prevent this from happening [1].

        Reference:\n
        [1] https://github.com/r888888888/danbooru/issues/3528\n
        [2] https://pwmon.org/p/5470/cloudflare-discolors-web/\n
        [3] https://blog.cloudflare.com/introducing-polish-automatic-image-optimizati/

        :param url: URL to an artwork image on ArtStation
        :type url: str
        """
        dummy_param = secrets.token_hex(16)
        # dummy_param = secrets.token_urlsafe(16)
        return f"{url}&{dummy_param}"

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
        self.update_idletasks()

    @staticmethod
    def _get_decimal_places(num1, num2):
        def count_decimal_places(d):
            d = Decimal(str(d))  # Convert via string to avoid float inaccuracies
            return abs(d.as_tuple().exponent)

        decimal_places_num1 = count_decimal_places(num1)
        decimal_places_num2 = count_decimal_places(num2)
        decimal_places = max(decimal_places_num1, decimal_places_num2)
        return decimal_places

    @staticmethod
    def get_filename(url: str) -> str:
        """
        Get the filename from a URL without the file extension.

        :param url: URL to file
        :type url: str
        """
        clean_url = url.split("?", 1)[0]
        basename = os.path.basename(clean_url)
        cleaned_name = os.path.splitext(basename)[0]
        return cleaned_name

    @staticmethod
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
        content_type = (
            resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        )
        extn = allowed_extn.get(content_type)

        # ...else fallback to URL suffix if not known Content-Type
        # (sometimes files have the wrong extension)
        if not extn:
            clean_url = url.split("?", 1)[0]
            extn = os.path.splitext(clean_url)[1]
        return extn

    def _get_new_name(
        self,
        filename: str,
        ext: str,
        save_path: str,
        download_size: int | None = None,
    ) -> str | None:
        """
        Allow user to enter a new name for a file should one with the same name
        already exist in the target directory or skip the renaming process.

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
        :return: A new filename if `filename` was changed, `None` otherwise
        :rtype: str | None
        """
        self.OVERWRITE.set(False)
        file_path = os.path.join(save_path, f"{filename}{ext}")

        if download_size is not None:
            on_disk = os.path.getsize(file_path)
            # Check whether the reported download size matches file size on disk
            if download_size == on_disk:
                download_is_bigger = 2
            elif download_size > on_disk:
                download_is_bigger = 1
            elif download_size < on_disk:
                download_is_bigger = 0
            else:
                download_is_bigger = None
            size_diff = naturalsize(abs(download_size - on_disk))
        else:
            download_is_bigger = None
            size_diff = None

        new_filename = renamedialog.ask_rename(
            checkvar=self.SKIP_EXISTING,
            overwritevar=self.OVERWRITE,
            file_path=file_path,
            initialvalue=filename,
            size_diff=size_diff,
            download_is_bigger=download_is_bigger,
            parent=self,
        )
        # If the user clicked on the overwrite button, use the original name
        if new_filename is None and self.OVERWRITE.get():
            return f"{filename}{ext}"

        # If the user clicked on skip button or entered an empty string,
        # exit function and skip download of this file
        if new_filename is None or new_filename == "":
            return

        # Check whether a file with this new name exists
        if "$N" in new_filename:
            new_filename = new_filename.replace("$N", filename)
        new_file = f"{new_filename}{ext}"
        new_file_path = os.path.join(save_path, new_file)

        if os.path.isfile(new_file_path):
            if download_size is None:
                new_file = self._get_new_name(new_filename, ext, save_path)
            else:
                new_file = self._get_new_name(
                    new_filename, ext, save_path, download_size
                )
        return new_file

    def download_image(
        self,
        url: str,
        filename: str,
        save_path: str,
        session: requests.Session,
        headers: dict[str, str],
        allowed_extn: dict[str, str],
    ) -> str:
        """
        This function downloads an image from a provided URL, ensuring that it
        is handled correctly according to the users wishes if a file with the
        same name already exists.

        :param url: The URL to download the image from
        :type url: str
        :param filename: The name for the downloaded image (without extension)
        :type filename: str
        :param save_path: The path where the downloaded image will be saved
        :type save_path: str
        :param session: A session object to handle requests
        :type session: requests.Session
        :param headers: Headers for the request
        :type headers: dict[str, str]
        :param allowed_extn: Dictionary of allowed content-type extensions to look for in the server's response
        :type allowed_extn: dict[str, str]
        :return: Information about the downloads outcome
        :rtype: str
        """
        try:
            # Construct URL to file with added dummy query cache-busting parameter to bypass possible cache hit
            url_no_cache = self._no_cache(url)

            with session.get(
                url_no_cache, timeout=15, stream=True, headers=headers
            ) as resp:
                # Check if response was successful else raise error
                resp.raise_for_status()
                # Get the expected content length (i.e. file size) from response header
                content_length = int(resp.headers.get("Content-Length", 0))
                ext = self.get_extension(url_no_cache, resp, allowed_extn)
                file = f"{filename}{ext}"
                file_path = os.path.join(save_path, file)
                new_name = None

                # Check if a file with the same name already exists
                if os.path.isfile(file_path):
                    # If SKIP_EXISTING is not checked, prompt user how to handle
                    # this situation
                    if not self.SKIP_EXISTING.get():
                        if not content_length == 0:
                            new_name = self._get_new_name(
                                filename, ext, save_path, content_length
                            )
                        else:
                            new_name = self._get_new_name(
                                filename,
                                ext,
                                save_path,
                            )

                    # Skip download
                    if new_name is None:
                        self.SKIPS += 1
                        return f'^ Skipped "{file}" as it already exists'

                    file_path = os.path.join(save_path, new_name)

                with open(file_path, "wb") as f:
                    # Download the image in chunks instead of loading the entire
                    # file into memory to avoid memory issues
                    for chunk in resp.iter_content(chunk_size=8192):
                        if not chunk:
                            continue  # filters out keep-alive packets so only real file data is written
                        f.write(chunk)

            self.SAVED += 1
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
                width, height = "?", "?"

            if not content_length == 0 and not content_length == file_size:
                # Check if there is a size difference between reported size
                # found in the response.header (if present) and downloaded file
                # if there is, that could mean there was a cache HIT and a
                # compressed file was downloaded
                self.WARNINGS += 1
                diff = naturalsize(abs(content_length - file_size))
                return f'* Saved: "{file}" ({width}x{height}, {human_size}) - Warning: File size mismatch between local copy and ArtStation by {diff}'
            if new_name is not None:
                if self.OVERWRITE.get():
                    self.WARNINGS += 1
                    return f'* Saved: "{new_name}" ({width}x{height}, {human_size}) - Warning: The original file was overwritten'
                return f'+ Saved: "{file}" as "{new_name}" ({width}x{height}, {human_size})'
            return f'+ Saved: "{file}" ({width}x{height}, {human_size})'

        except requests.HTTPError as e:
            if e.response.status_code == 429:
                self.ERRORS += 1
                # print(e.response.headers["Retry-After"])
                self.log_lb.insert(tk.END, f"! {e}")
                return "429"
            else:
                self.ERRORS += 1
                return f'! HTTP error while downloading "{url}": {e}'
        except requests.Timeout:
            self.ERRORS += 1
            return f'! Timeout reached while fetching "{url}"'
        except requests.RequestException as e:
            self.ERRORS += 1
            return f'! Failed "{url}": {e}'

    @staticmethod
    def _determine_img_dimension(url: str, img_dim: str, filename: str) -> str:
        """
        Determines the dimension in the URL at which the image should be
        downloaded, updating the URL accordingly. GIF's will always be
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
            answer = messagebox.askquestion(
                "Download original image?",
                f'The original image is available. Would you like to download "{filename}" in it\'s original dimension instead of the selected dimension?',
            )
            if answer == "yes":
                return url
            else:
                parts = url.rsplit("/", 2)
                new_url = f"{parts[0]}/{img_dim}/{parts[2]}"
                return new_url
        else:
            parts = url.rsplit("/", 2)
            new_url = f"{parts[0]}/{img_dim}/{parts[2]}"
            return new_url

    def _download_images(self):
        """
        This function downloads all unselected image URLs from a listbox.
        """
        save_path = self.SAVE_PATH.get()
        img_option = self.img_quality.get()
        custom_name = self.custom_entry.get()
        custom_name_check = self.CUSTOM_NAME.get()
        starting_counter = 1
        increment = 1
        digits = 1
        self.PROGRESS.set("")
        self.progbar["value"] = 0
        self.progbar.update()
        self.SAVED = 0
        self.ERRORS = 0
        self.SKIPS = 0
        self.WARNINGS = 0
        HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Cache-Control": "max-age=0, no-cache, no-store, must-revalidate",
        }
        # Most common image extensions
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

        if save_path == "":
            messagebox.showerror(
                "Error", "Please select a directory in which to save your downloads"
            )
            return
        elif not os.path.exists(save_path):
            messagebox.showerror("Error", "Directory does not exist")
            return

        # Get the indices of current selection from the listbox
        selections = self.image_list.curselection()

        all_items = self.image_list.get(0, tk.END)
        # Get all unselected items, which are the ones that will be downloaded
        selected_images = [
            item for index, item in enumerate(all_items) if index not in selections
        ]
        progbar_max = len(selected_images)
        self.progbar.config(maximum=progbar_max)
        self.PROGRESS.set(f"0/{progbar_max}")

        with requests.Session() as sess:
            if custom_name_check and not custom_name == "":
                counter = starting_counter

                if isinstance(counter, float) or isinstance(increment, float):
                    decimal_places = self._get_decimal_places(counter, increment)

                for index, image in enumerate(selected_images, start=1):
                    filename = custom_name
                    if "$N" in filename:
                        original_filename = self.get_filename(image)
                        filename = filename.replace("$N", original_filename)
                    if len(selected_images) > 1:
                        if "$#" in filename:
                            if isinstance(counter, float) or isinstance(
                                increment, float
                            ):
                                num_formatted = f"{counter:0{digits}.{decimal_places}f}"
                            else:
                                num_formatted = f"{counter:0{digits}d}"
                            filename = filename.replace("$#", num_formatted)
                        else:
                            filename = f"{custom_name}{counter}"
                    else:
                        filename = custom_name

                    image_url = self._determine_img_dimension(
                        image, img_option, filename
                    )

                    download_result = self.download_image(
                        image_url,
                        filename,
                        save_path,
                        sess,
                        HEADERS,
                        EXTN_FROM_CONTENT_TYPE,
                    )
                    if download_result == "429":
                        # Since the download of all remaining files will now be
                        # cancelled, ensure they are also counted as skipped
                        self.SKIPS += progbar_max - (
                            self.SAVED + self.ERRORS + self.SKIPS
                        )
                        messagebox.showwarning(
                            "Warning: 429 Too Many Requests",
                            "Rate limit exceeded. Best take a break and try again later.",
                        )
                        self.log_lb.insert(
                            tk.END,
                            "< Rate limit exceeded, cancelling download of remaining files...",
                        )
                        break

                    self.log_lb.insert(tk.END, download_result)
                    self.update_progress(index, progbar_max)
                    counter += increment
            else:
                for index, image in enumerate(selected_images, start=1):
                    filename = self.get_filename(image)

                    image_url = self._determine_img_dimension(
                        image, img_option, filename
                    )

                    download_result = self.download_image(
                        image_url,
                        filename,
                        save_path,
                        sess,
                        HEADERS,
                        EXTN_FROM_CONTENT_TYPE,
                    )
                    if download_result == "429":
                        # Cancel the remaining downloads
                        self.SKIPS += progbar_max - (
                            self.SAVED + self.ERRORS + self.SKIPS
                        )
                        messagebox.showwarning(
                            "Warning: 429 Too Many Requests",
                            "Rate limit exceeded. Best take a break and try again later.",
                        )
                        self.log_lb.insert(
                            tk.END,
                            "< Rate limit exceeded, cancelling download of remaining files...",
                        )
                        break

                    self.log_lb.insert(tk.END, download_result)
                    self.update_progress(index, progbar_max)

        self.log_lb.insert(
            tk.END,
            f">>> {progbar_max} Files - Saved: {self.SAVED}, Skipped: {self.SKIPS}, Warnings: {self.WARNINGS}, Errors: {self.ERRORS}",
        )
        self.log_lb.insert(tk.END, "")

    def show_context_menu(self, event):
        try:
            self.log_lb_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.log_lb_menu.grab_release()

    def show_on_disk(self):
        index = self.log_lb.curselection()
        save_dir = self.SAVE_PATH.get()
        if not index:
            messagebox.showwarning("Warning", "No download entry selected")
        else:
            element = self.log_lb.get(index)
            if (
                element.startswith("+")
                or element.startswith("*")
                or element.startswith("^")
            ):
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


if __name__ == "__main__":
    app = ArtStationArtworkDownloader()
    app.mainloop()
