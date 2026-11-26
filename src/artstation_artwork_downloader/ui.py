# Copyright (c) 2026 Jérémy Rotzetter

"""UI construction, listbox helpers, and dialogs for ArtStation Artwork Downloader."""

import os
import re
import tkinter as tk
from tkinter import messagebox, ttk

from showinfm import show_in_file_manager

# === Window utility ===========================================================


def center_window(app: tk.Tk, width: int, height: int):
    """
    Function to place the app window in the center of the screen when launching it.
    """
    x = (app.winfo_screenwidth() / 2) - (width / 2)
    y = (app.winfo_screenheight() / 2) - (height / 2)
    app.geometry(f"{width}x{height}+{int(x)}+{int(y)}")


# === Menubar ==================================================================


def build_menubar(
    app: tk.Tk,
    *,
    on_about,
    on_use,
    on_filename_help,
    on_get_json_url,
    on_load_json_clp,
    on_change_theme,
    on_close,
) -> tuple[tk.Menu, int]:
    menubar = tk.Menu(app)
    app.config(menu=menubar)

    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label="About...", command=on_about)
    help_menu.add_command(label="How to use...", command=on_use)
    help_menu.add_command(label="About custom filenames...", command=on_filename_help)

    fallback_menu = tk.Menu(menubar, tearoff=0)
    fallback_menu.add_command(label="Get URL to JSON", command=on_get_json_url)
    fallback_menu.add_command(
        label="Load JSON from clipboard", command=on_load_json_clp
    )

    menubar.add_cascade(label="Help", menu=help_menu)
    menubar.add_cascade(label="Fallback Method", menu=fallback_menu)
    menubar.add_command(label="Switch to Dark Mode ", command=on_change_theme)
    theme_index = menubar.index("Switch to Dark Mode ")
    menubar.add_command(label="Exit", command=on_close)
    return menubar, theme_index


# === Context menus ============================================================


def build_entry_menu(entry: tk.Entry) -> tk.Menu:
    menu = tk.Menu(tearoff=0)
    menu.add_command(
        label="Select All",
        command=lambda: (entry.focus(), entry.select_range(0, tk.END)),
    )
    menu.add_separator()
    menu.add_command(
        label="Copy",
        command=lambda: entry.event_generate("<<Copy>>"),
    )
    menu.add_command(
        label="Paste",
        command=lambda: entry.event_generate("<<Paste>>"),
    )
    menu.add_separator()
    menu.add_command(
        label="Clear",
        command=lambda: (entry.focus(), entry.delete(0, tk.END)),
    )
    entry.bind(
        "<<ContextMenu>>",
        lambda e: (
            str(entry.cget("state")) == "normal" and menu.tk_popup(e.x_root, e.y_root)
        ),
    )
    return menu


def build_image_list_menu(
    app: tk.Tk, on_copy, on_select_all, on_invert, on_clear
) -> tk.Menu:
    menu = tk.Menu(app, tearoff=False)
    menu.add_command(label="Copy filename", command=on_copy)
    menu.add_separator()
    menu.add_command(label="Select all", command=on_select_all)
    menu.add_command(label="Invert selection", command=on_invert)
    menu.add_command(label="Clear selection", command=on_clear)
    return menu


def build_log_menu(app: tk.Tk, on_show_on_disk) -> tk.Menu:
    menu = tk.Menu(app, tearoff=False)
    menu.add_command(label="Show file on disk", command=on_show_on_disk)
    return menu


# === Frame builders ===========================================================
# Each returns a dict of widgets so main.py can hold references.


def build_options_frame(parent, save_path_var: tk.StringVar) -> dict:
    frm = ttk.LabelFrame(master=parent, text="Options", relief="groove")
    BUTTON_WIDTH = 25

    img_quality_lbl = ttk.Label(master=frm, text="Select image dimensions:")
    img_quality = ttk.Combobox(
        master=frm,
        values=["small", "medium", "large", "4k", "8k"],
        state="readonly",
        justify="center",
    )
    img_quality.set("8k")

    select_path_btn = ttk.Button(
        master=frm,
        text="Select save location",
        width=BUTTON_WIDTH,
    )
    save_path_lbl = ttk.Label(master=frm, text=" Downloads will be saved to:")
    save_path_ent = ttk.Entry(master=frm, textvariable=save_path_var, state="readonly")
    open_dir_btn = ttk.Button(
        master=frm,
        text="Open download directory",
        width=BUTTON_WIDTH,
    )

    frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    frm.grid_columnconfigure(2, weight=1)
    frm.grid_rowconfigure((0, 1), weight=1)

    img_quality_lbl.grid(row=0, column=0, padx=5, pady=(5, 0))
    img_quality.grid(row=1, column=0, padx=10, pady=(0, 10))
    select_path_btn.grid(row=1, column=1, padx=10, pady=(0, 10))
    save_path_lbl.grid(row=0, column=2, padx=5, pady=(5, 0), sticky="W")
    save_path_ent.grid(row=1, column=2, padx=10, pady=(0, 10), sticky="EW")
    open_dir_btn.grid(row=0, column=2, padx=10, pady=0, sticky="E")

    return {
        "frame": frm,
        "img_quality": img_quality,
        "select_path_btn": select_path_btn,
        "save_path_ent": save_path_ent,
        "open_dir_btn": open_dir_btn,
    }


def build_source_frame(parent, loaded_json_var: tk.StringVar) -> dict:
    container = ttk.Frame(master=parent, relief="flat")
    container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
    BUTTON_WIDTH = 25

    # Left: load project JSON
    load_frm = ttk.Frame(master=container, relief="groove")
    project_lbl = ttk.Label(master=load_frm, text="Project URL or ID:")
    project_ent = ttk.Entry(master=load_frm, width=BUTTON_WIDTH)
    load_btn = ttk.Button(
        master=load_frm,
        text="Load project",
        width=BUTTON_WIDTH,
    )
    loaded_lbl = ttk.Label(master=load_frm, text="Loaded project hash ID:")
    loaded_ent = ttk.Entry(
        master=load_frm,
        width=BUTTON_WIDTH,
        textvariable=loaded_json_var,
        state="readonly",
        justify=tk.CENTER,
    )
    clear_btn = ttk.Button(
        master=load_frm,
        text="Clear image list",
        width=BUTTON_WIDTH,
    )

    load_frm.pack(fill=tk.BOTH, expand=True, padx=(10, 50), pady=10, side="left")
    # Center widgets vertically/horizontally by giving them equal weight
    load_frm.grid_rowconfigure((0, 1, 2, 3), weight=1)
    load_frm.grid_columnconfigure((0, 1), weight=1)

    project_lbl.grid(row=0, column=0, padx=5, pady=(5, 0))
    project_ent.grid(row=1, column=0, padx=10, pady=(0, 10))
    load_btn.grid(row=1, column=1, padx=10, pady=(0, 10))
    loaded_lbl.grid(row=2, column=0, padx=5, pady=0)
    loaded_ent.grid(row=3, column=0, padx=10, pady=(0, 10))
    clear_btn.grid(row=3, column=1, padx=10, pady=(0, 10))

    build_entry_menu(project_ent)

    # Right: handle individual artworks
    art_frm = ttk.Frame(master=container, relief="groove")
    add_btn = ttk.Button(
        master=art_frm,
        text="(+) Add individual artwork URL",
        width=30,
    )
    remove_btn = ttk.Button(
        master=art_frm,
        text="(-) Remove selected artwork(s)",
        width=30,
    )
    art_frm.pack(fill=tk.BOTH, expand=True, padx=(50, 10), pady=10, side="right")
    art_frm.grid_rowconfigure((0, 1), weight=1)
    art_frm.grid_columnconfigure(0, weight=1)
    add_btn.grid(row=0, column=0, padx=10, pady=10)
    remove_btn.grid(row=1, column=0, padx=10)

    return {
        "container": container,
        "project_ent": project_ent,
        "load_btn": load_btn,
        "loaded_ent": loaded_ent,
        "clear_btn": clear_btn,
        "add_btn": add_btn,
        "remove_btn": remove_btn,
    }


def build_selection_frame(parent, image_list_menu: tk.Menu) -> dict:
    frm = ttk.LabelFrame(
        master=parent,
        relief="groove",
        text="Choose which artworks to download:",
    )
    y_scroll = ttk.Scrollbar(frm, orient="vertical")
    x_scroll = ttk.Scrollbar(frm, orient="horizontal")
    image_list = tk.Listbox(
        master=frm,
        selectmode="multiple",
        yscrollcommand=y_scroll.set,
        xscrollcommand=x_scroll.set,
    )
    y_scroll.config(command=image_list.yview)
    x_scroll.config(command=image_list.xview)
    image_list.context_menu = image_list_menu  # Attach menu to widget
    image_list.bind(
        "<<ContextMenu>>", show_context_menu
    )  # Bind the virtual event instead of a raw button

    frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
    frm.grid_rowconfigure(0, weight=1)
    frm.grid_columnconfigure(0, weight=1)
    image_list.grid(row=0, column=0, padx=5, pady=5, sticky="EW")
    y_scroll.grid(row=0, column=1, sticky="NS")
    x_scroll.grid(row=1, column=0, sticky="EW")

    return {"frame": frm, "image_list": image_list}


def build_download_frame(
    parent,
    skip_var: tk.BooleanVar,
    custom_name_var: tk.BooleanVar,
) -> dict:
    frm = ttk.Frame(master=parent, relief="groove")
    BUTTON_WIDTH = 25

    skip_check = ttk.Checkbutton(
        master=frm,
        variable=skip_var,
        onvalue=True,
        offvalue=False,
        text="Always skip existing files?",
    )
    custom_entry = ttk.Entry(master=frm, width=BUTTON_WIDTH, state="disabled")
    custom_check = ttk.Checkbutton(
        master=frm,
        variable=custom_name_var,
        onvalue=True,
        offvalue=False,
        text="Use custom file name?",
    )
    stop_btn = ttk.Button(
        master=frm,
        text="\u25a0 Stop",
        width=BUTTON_WIDTH,
        state="disabled",
    )
    run_btn = ttk.Button(
        master=frm,
        text="\u25b6 Download artworks",
        width=BUTTON_WIDTH,
    )

    frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    frm.grid_rowconfigure(0, weight=1)
    frm.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

    skip_check.grid(row=0, column=0, padx=10, pady=10)
    custom_entry.grid(row=0, column=2, padx=10, pady=10)
    custom_check.grid(row=0, column=1, padx=10, pady=10)
    stop_btn.grid(row=0, column=3, padx=10, pady=10)
    run_btn.grid(row=0, column=4, padx=10, pady=10)

    build_entry_menu(custom_entry)

    return {
        "frame": frm,
        "skip_check": skip_check,
        "custom_entry": custom_entry,
        "custom_check": custom_check,
        "stop_btn": stop_btn,
        "run_btn": run_btn,
    }


def build_progressbar_frame(parent, progress_var: tk.StringVar) -> dict:
    frm = ttk.Frame(master=parent)
    progbar = ttk.Progressbar(master=frm, mode="determinate")
    progbar_lbl = ttk.Label(
        master=frm,
        textvariable=progress_var,
        anchor="center",
        width=5,
        font=("TkDefaultFont", 10, "bold"),
    )
    frm.pack(fill=tk.BOTH, expand=True)
    frm.grid_columnconfigure(0, weight=1)
    progbar.grid(row=0, column=0, padx=10, sticky="EW")
    progbar_lbl.grid(row=0, column=0, padx=10, pady=10)
    return {"frame": frm, "progbar": progbar, "progbar_lbl": progbar_lbl}


def build_log_frame(parent, log_menu: tk.Menu) -> dict:
    frm = ttk.LabelFrame(master=parent, text="Download Status:")
    y_scroll = ttk.Scrollbar(frm, orient="vertical")
    x_scroll = ttk.Scrollbar(frm, orient="horizontal")
    log_lb = tk.Listbox(
        master=frm,
        selectmode="browse",
        activestyle="none",
        yscrollcommand=y_scroll.set,
        xscrollcommand=x_scroll.set,
    )
    y_scroll.config(command=log_lb.yview)
    x_scroll.config(command=log_lb.xview)
    log_lb.context_menu = log_menu  # Attach menu to widget
    log_lb.bind("<<ContextMenu>>", show_context_menu)

    frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
    frm.grid_rowconfigure(0, weight=1)
    frm.grid_columnconfigure(0, weight=1)
    log_lb.grid(row=0, column=0, padx=5, pady=5, sticky="EW")
    y_scroll.grid(row=0, column=1, sticky="NS")
    x_scroll.grid(row=1, column=0, sticky="EW")

    clear_btn = ttk.Button(master=parent, text="Clear download log", width=25)
    clear_btn.pack(anchor="e", padx=32, pady=(0, 5))

    return {"frame": frm, "log_lb": log_lb, "clear_btn": clear_btn}


# === Listbox helpers (module-level, take widgets as args) =====================


def show_context_menu(event):
    widget = event.widget
    menu = getattr(widget, "context_menu", None)
    if menu is None:
        return
    menu.tk_popup(event.x_root, event.y_root)


def copy_filename(app: tk.Tk, listbox: tk.Listbox):
    index = listbox.curselection()
    if not index:
        messagebox.showwarning("Warning", "No download entry selected")
    elif len(index) > 1:
        messagebox.showwarning("Warning", "More than one entry selected")
    else:
        url = listbox.get(index)
        clean_url = url.split("?", 1)[0]
        basename = os.path.basename(clean_url)
        cleaned_name = os.path.splitext(basename)[0]
        app.clipboard_clear()
        app.clipboard_append(cleaned_name)


def invert_selection(listbox: tk.Listbox):
    selection = listbox.curselection()
    listbox.selection_set(0, tk.END)
    for item in selection:
        listbox.selection_clear(item)


def show_on_disk(app: tk.Tk, listbox: tk.Listbox):
    index = listbox.curselection()
    save_dir = app.SAVE_PATH.get()
    if not index:
        messagebox.showwarning("Warning", "No download entry selected")
        return
    element = listbox.get(index)
    if not element.startswith(("+", "*", "^")):
        messagebox.showwarning("Warning", "Not a valid selection")
        return
    matches = re.findall(r'"(.*?)"', element)
    if not matches:
        messagebox.showwarning("Warning", "No file found in selection")
        return
    filename = matches[-1] if len(matches) > 1 else matches[0]
    file_path = os.path.join(save_dir, filename)
    if not os.path.isfile(file_path):
        messagebox.showwarning(
            "Warning",
            f'File:\n"{filename}"\n\nnot found in save directory:\n"{os.path.basename(save_dir)}"',
        )
        return
    show_in_file_manager(file_path)


# === Dialogs ==================================================================


def show_about(version: str):
    messagebox.showinfo(
        "About",
        f"ArtStation Artwork Downloader\n \nAuthor: jrotzetter \nVersion: {version} \nLicense: MIT",
    )


def show_use():
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


def show_filename_help():
    messagebox.showinfo(
        "Custom File Naming Options",
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
        "Example: img_$#{5}  becomes  img_5.jpg, img_6.jpg...\n\n"
        "Note: Sequential numbering is applied automatically when downloading "
        "multiple images. For single-image downloads, no number is added.",
    )
