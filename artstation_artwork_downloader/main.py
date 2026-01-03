# Copyright (C) 2025 Jérémy Rotzetter

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import simpledialog
import json
import os
import requests
import secrets
import cloudscraper
from humanize import naturalsize


class ArtStationArtworkDownloader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ArtStation Artwork Project Downloader")
        self.center_window(900, 820)
        self.resizable(width=False, height=False)
        self.style = ttk.Style(self)
        # self.style.theme_use("clam") # the 'focus' color of the combobox's selection is a part of the 'clam' style
        # print(ttk.Style().theme_names())
        # print(ttk.Style().lookup("TButton", "font"))

        ###/// GLOBAL VARIABLES \\\###
        self.STORE_PATH = tk.StringVar()
        self.LOADED_JSON = tk.StringVar()
        self.JSON = tk.StringVar()
        self.CUSTOM_NAME = tk.BooleanVar()
        self.PROGRESS = tk.StringVar()
        BUTTON_WIDTH = 25
        self.SKIP_EXISTING = tk.BooleanVar(value=True)

        ###/// TOPMENU \\\###
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About...", command=self._show_about)
        help_menu.add_command(label="How to use...", command=self._show_use)

        menubar.add_cascade(label="Help", menu=help_menu)
        menubar.add_command(label="Exit", command=self.destroy)

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
        self.store_path_lbl = ttk.Label(
            master=self.options_frm, text=" Downloads will be saved to:"
        )
        self.store_path_ent = ttk.Entry(
            master=self.options_frm,
            textvariable=self.STORE_PATH,
            state="readonly",
        )

        self.options_frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.options_frm.grid_columnconfigure(2, weight=1)
        self.options_frm.grid_rowconfigure((0, 1), weight=1)

        self.img_quality_lbl.grid(row=0, column=0, padx=5, pady=(5, 0))
        self.img_quality.grid(row=1, column=0, padx=10, pady=(0, 10))
        self.select_path_btn.grid(row=1, column=1, padx=10, pady=(0, 10))
        self.store_path_lbl.grid(row=0, column=2, padx=5, pady=(5, 0), sticky="W")
        self.store_path_ent.grid(row=1, column=2, padx=10, pady=(0, 10), sticky="EW")

        ###/// JSON FRAME \\\###
        # Container frame for the two methods to load the image urls from the project json
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
        self.loaded_json_lbl.grid(row=2, column=0, padx=5, pady=(5, 0))
        self.loaded_json_ent.grid(row=3, column=0, padx=10, pady=(0, 10))
        self.clear_json_btn.grid(row=3, column=1, padx=10, pady=(0, 10))

        ###/// GET JSON FRAME (FALLBACK FRAME) \\\###
        self.get_json_frm = ttk.LabelFrame(
            master=self.json_frm, relief="groove", text="Fallback Method"
        )

        self.get_json_btn = ttk.Button(
            master=self.get_json_frm,
            text="Get URL to JSON",
            width=BUTTON_WIDTH,
            command=self.get_json_url,
        )
        self.load_json_btn = ttk.Button(
            master=self.get_json_frm,
            text="Load JSON from clipboard",
            width=BUTTON_WIDTH,
            command=self.load_json_clp,
        )

        self.get_json_frm.pack(
            fill=tk.BOTH, expand=True, padx=(50, 10), pady=10, side="right"
        )
        self.get_json_frm.grid_rowconfigure((0, 1), weight=1)
        self.get_json_frm.grid_columnconfigure(0, weight=1)

        self.get_json_btn.grid(row=0, column=0, padx=10, pady=10)
        self.load_json_btn.grid(row=1, column=0, padx=10, pady=10)

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
            text="Use custom file name with sequential numbers?",
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
            "ArtStation Artwork Project Downloader\n \nAuthor: jrotzetter \nVersion: 1.0.0 \nLicense: MIT",
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
        selected_directory = filedialog.askdirectory()
        self.STORE_PATH.set(selected_directory)

    def get_json_url(self):
        hashid = self.project_ent.get()
        url = f"https://www.artstation.com/projects/{hashid}.json"
        self.clipboard_clear()
        self.clipboard_append(url)

    @staticmethod
    def load_json(json_string: str):
        try:
            data = json.loads(json_string)
            return data
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Invalid JSON: {e}")

    def load_json_clp(self):
        try:
            # Retrieve text from the clipboard
            clipboard_text = self.clipboard_get()

            json_content = self.load_json(clipboard_text)
            if json_content is None:
                return
            self._populate_image_list(json_content)
        except tk.TclError:
            messagebox.showerror("Error", "Clipboard is empty!")
            return

    def load_json_url(self):
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
        # Clear all items from the listbox
        self.image_list.delete(0, tk.END)
        try:
            id = json_content["hash_id"]
        except KeyError:
            messagebox.showwarning("Warning", "hash ID not found!")
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

    def _clear_json(self):
        self.LOADED_JSON.set("")
        self.image_list.delete(0, tk.END)

    def show_entry(self, var, ent):
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

        Reference:
        [1] https://github.com/r888888888/danbooru/issues/3528
        [2] https://pwmon.org/p/5470/cloudflare-discolors-web/
        [3] https://blog.cloudflare.com/introducing-polish-automatic-image-optimizati/
        """
        dummy_param = secrets.token_hex(16)
        # dummy_param = secrets.token_urlsafe(16)
        return f"{url}&{dummy_param}"

    def update_progress(self, index: int, total: int):
        """
        Update the progressbar

        :param index: current item
        :param total: total number of items/ max value of progressbar
        """
        self.progbar["value"] = index
        self.PROGRESS.set(f"{index}/{total}")
        self.update_idletasks()

    @staticmethod
    def get_filename(url: str) -> str:
        """
        Get the filename from a URL without the file extension

        :param url: URL to file
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
        is not in the dictionary of the allowed extensions

        :param url: URL to file
        :param resp: Server's response to HTTP request for file
        :param allowed_extn: file extension to look for from Content-Type in server's response
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

    def _get_new_name(self, filename: str, ext: str, store_path: str):
        """
        Allow user to enter a new name for a file should one with the same name
        already exist in the target directory "store_path" or skip the renaming

        :param filename: name of the file
        :param ext: extension of the file
        :param store_path: path to target directory
        """
        new_filename = simpledialog.askstring(
            "A file with the same name already exists",
            "Please enter a new filename (without extension):",
            parent=self,
            initialvalue=filename,
        )
        if new_filename is None or new_filename == "":
            return
        new_file = f"{new_filename}{ext}"
        file_path = os.path.join(store_path, new_file)
        if os.path.isfile(file_path):
            new_file = self._get_new_name(filename, ext, store_path)
            return new_file
        else:
            return new_file

    def download_image(
        self,
        url: str,
        filename: str,
        store_path: str,
        session: requests.Session,
        headers: dict[str, str],
        allowed_extn: dict[str, str],
    ) -> str:
        try:
            url_no_cache = self._no_cache(url)
            with session.get(
                url_no_cache, timeout=15, stream=True, headers=headers
            ) as resp:
                resp.raise_for_status()
                content_length = int(resp.headers.get("Content-Length", 0))
                ext = self.get_extension(url_no_cache, resp, allowed_extn)
                file = f"{filename}{ext}"
                file_path = os.path.join(store_path, file)
                new_name = None

                if os.path.isfile(file_path):
                    if not self.SKIP_EXISTING.get():
                        new_name = self._get_new_name(filename, ext, store_path)

                    if new_name is None:
                        self.SKIPS += 1
                        return f'^ Skipped "{file}" as it already exists'

                    file_path = os.path.join(store_path, new_name)

                with open(file_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if not chunk:
                            continue  # filters out keep-alive packets so only real file data is written
                        f.write(chunk)

            file_size = os.path.getsize(file_path)
            human_size = naturalsize(file_size)
            if not content_length == 0 and not content_length == file_size:
                # Check if there is a size difference between reported size
                # found in the response.header (if present) and downloaded file
                # if there is, that could mean there was a cache HIT and a
                # compressed file was downloaded
                self.WARNINGS += 1
                diff = naturalsize(abs(content_length - file_size))
                return f'* Saved: "{file}" with {human_size} - Warning: File size mismatch between local copy and ArtStation by {diff}'
            if new_name is not None:
                return f'+ Saved "{file}" as: "{new_name}" with {human_size}'
            return f'+ Saved: "{file}" with {human_size}'

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

    def _download_images(self):
        store_path = self.STORE_PATH.get()
        img_option = self.img_quality.get()
        custom_name = self.custom_entry.get()
        custom_name_check = self.CUSTOM_NAME.get()
        self.PROGRESS.set("")
        self.progbar["value"] = 0
        self.progbar.update()
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

        if store_path == "":
            messagebox.showerror(
                "Error", "Please select a directory to store the downloads"
            )
            return
        elif not os.path.exists(store_path):
            messagebox.showerror("Error", "Directory does not exist!")
            return

        # Get the indices of current selection from the listbox
        selections = self.image_list.curselection()

        all_items = self.image_list.get(0, tk.END)
        selected_images = [
            item for index, item in enumerate(all_items) if index not in selections
        ]
        progbar_max = len(selected_images)
        self.progbar.config(maximum=progbar_max)
        self.PROGRESS.set(f"0/{progbar_max}")

        with requests.Session() as sess:
            if custom_name_check and not custom_name == "":
                counter = 1
                for image in selected_images:
                    image_url = image.replace("/large/", f"/{img_option}/")
                    filename = f"{custom_name}{counter}"
                    download_result = self.download_image(
                        image_url,
                        filename,
                        store_path,
                        sess,
                        HEADERS,
                        EXTN_FROM_CONTENT_TYPE,
                    )
                    if download_result == "429":
                        messagebox.showwarning(
                            "Warning: 429 Too Many Requests",
                            "Rate limit exceeded. Best take a break and try again later.",
                        )
                        break
                    self.log_lb.insert(tk.END, download_result)
                    self.update_progress(counter, progbar_max)
                    counter += 1
            else:
                counter = 1
                for image in selected_images:
                    filename = self.get_filename(image)
                    image_url = image.replace("/large/", f"/{img_option}/")
                    download_result = self.download_image(
                        image_url,
                        filename,
                        store_path,
                        sess,
                        HEADERS,
                        EXTN_FROM_CONTENT_TYPE,
                    )
                    if download_result == "429":
                        messagebox.showwarning(
                            "Warning: 429 Too Many Requests",
                            "Rate limit exceeded. Best take a break and try again later.",
                        )
                        break
                    self.log_lb.insert(tk.END, download_result)
                    self.update_progress(counter, progbar_max)
                    counter += 1

        self.log_lb.insert(
            tk.END,
            f">>> {progbar_max} Files - Skipped: {self.SKIPS}, Errors: {self.ERRORS}, Warnings: {self.WARNINGS}",
        )
        self.log_lb.insert(tk.END, "")


if __name__ == "__main__":
    app = ArtStationArtworkDownloader()
    app.mainloop()
