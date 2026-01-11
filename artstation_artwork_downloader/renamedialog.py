# Copyright (C) 2025 Jérémy Rotzetter. Portions Copyright (C) 1997 by Fredrik Lundh.
#
# This code is partially derived from Python standard library's simpledialog module,
# with modifications made to support additional buttons on the widget which are used to
# modify boolean variables or open the os-specific standard file explorer in the directory
# where a file is located on disk.

# See https://docs.python.org/3/library/dialog.html#module-tkinter.simpledialog for more information about the original module.

import tkinter as tk
from tkinter import simpledialog
from showinfm import show_in_file_manager
import os


class AskRenameDialog(simpledialog.Dialog):
    def __init__(
        self,
        checkvar,
        overwritevar,
        file_path,
        title,
        prompt,
        initialvalue=None,
        size_diff=None,
        download_is_bigger=None,
        parent=None,
    ):
        self.prompt = prompt
        self.checkvar = checkvar
        self.overwritevar = overwritevar
        self.file_path = file_path
        self.initialvalue = initialvalue
        self.size_diff = size_diff
        self.download_is_bigger = download_is_bigger

        simpledialog.Dialog.__init__(self, parent, title)

    def destroy(self):
        self.entry = None
        simpledialog.Dialog.destroy(self)

    def body(self, master):
        file_exists_lbl = tk.Label(
            master,
            text=f'A file named "{self.initialvalue}" already exists.',
            justify=tk.LEFT,
        )
        file_exists_lbl.grid(row=0, padx=5, pady=5)

        if self.download_is_bigger == 0:
            label_text = f"The file on disk is {self.size_diff} larger than the file to be downloaded."
        elif self.download_is_bigger == 1:
            label_text = f"The file to be downloaded is {self.size_diff} larger than the file on disk."
        elif self.download_is_bigger == 2:
            label_text = "Both files are equal in size."
        else:
            label_text = "Difference in file sizes could not be determined."

        size_diff_lbl = tk.Label(master, text=label_text, justify=tk.LEFT)
        size_diff_lbl.grid(row=1, padx=5, pady=5)

        show_btn = tk.Button(
            master, text="Show file on disk", command=self.show_on_disk
        )
        show_btn.grid(row=2, padx=5, pady=5)

        entry_lbl = tk.Label(master, text=self.prompt, justify=tk.LEFT)
        entry_lbl.grid(row=3, padx=5, sticky=tk.W)

        self.entry = tk.Entry(master, width=50)
        self.entry.grid(row=4, padx=5, sticky=tk.W + tk.E)

        if self.initialvalue is not None:
            self.entry.insert(0, self.initialvalue)
            self.entry.select_range(0, tk.END)

        return self.entry

    def buttonbox(self):
        box = tk.Frame(self)
        # Custom buttons
        tk.Button(
            box, text="Rename", width=10, command=self.ok, default=tk.ACTIVE
        ).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(box, text="Skip", width=10, command=self.cancel).pack(
            side=tk.LEFT, padx=5, pady=5
        )
        tk.Button(box, text="Skip all", width=10, command=self.skip_all).pack(
            side=tk.LEFT, padx=5, pady=5
        )
        tk.Button(box, text="Overwrite", width=10, command=self.overwrite).pack(
            side=tk.LEFT, padx=5, pady=5
        )
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def skip_all(self):
        self.checkvar.set(True)
        self.cancel()

    def validate(self):
        result = self.entry.get()
        self.result = result
        return 1

    def show_on_disk(self):
        # Use 'show-in-file-manager' library as it should work for
        # many different OSes
        show_in_file_manager(self.file_path)

    def overwrite(self):
        self.overwritevar.set(True)
        self.cancel()


def ask_rename(
    checkvar: bool,
    overwritevar: bool,
    file_path: str,
    title: str = "File Exists",
    prompt: str = "Please enter a new filename (without extension):",
    initialvalue: str | None = None,
    size_diff: str | None = None,
    download_is_bigger: int | None = None,
    **kw,
) -> str:
    """
    Get a string representing a filename from the user

    :param checkvar: The boolean variable that will be set to True when
      'Skip all' button is pressed
    :type checkvar: bool
    :param overwritevar: The boolean variable that will be set to True when
      'Overwrite' button is pressed
    :type overwritevar: bool
    :param file_path: The path to the already existing file on disk
    :type file_path: str
    :param title: The title of the window
    :type title: str
    :param prompt: The label text
    :type prompt: str
    :param initialvalue: The value that is initially displayed in the entry field,
      usually the filename
    :type initialvalue: str | None
    :param size_diff: The difference in size between the file on disk and the
      file that is to be downloaded
    :type size_diff: str | None
    :param download_is_bigger: Integer value that will determine which message
      regarding file size differences is displayed. 0 means file on disk is
      larger, 1 means the file to be downloaded is larger and 2 means both files
      have the same size
    :type download_is_bigger: int | None
    :param **kw: Keyword arguments that can be passed to simpledialog.Dialog
    :return: Return value is a string
    :rtype: str
    """
    d = AskRenameDialog(
        checkvar,
        overwritevar,
        file_path,
        title,
        prompt,
        initialvalue,
        size_diff,
        download_is_bigger,
        **kw,
    )
    return d.result


if __name__ == "__main__":

    class TestDialog(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("TestDialog")

            self.SKIP_EXISTING = tk.BooleanVar(value=False)
            self.OVERWRITE = tk.BooleanVar()
            dir_path = os.path.dirname(os.path.abspath(__file__))
            self.file_path = f"{dir_path}/existing-file-on-disk.txt"
            self.size_diff = "1.1 MB"

            skip_check = tk.Checkbutton(
                master=self,
                variable=self.SKIP_EXISTING,
                text="Always skip existing files?",
            )
            skip_check.pack()
            test = tk.Button(self, text="Test", command=self.call_test)
            test.pack()
            quit = tk.Button(self, text="Quit", command=self.quit)
            quit.pack()

        def call_test(self):
            filename = "existing-file-on-disk"
            print("checkvar was:", self.SKIP_EXISTING.get())
            print("overwrite was:", self.OVERWRITE.get())
            new_name = ask_rename(
                title="Test Title",
                prompt="Prompt test:",
                checkvar=self.SKIP_EXISTING,
                overwritevar=self.OVERWRITE,
                file_path=self.file_path,
                initialvalue=filename,
                size_diff=self.size_diff,
                download_is_bigger=1,
                parent=self,
            )
            print("The file name is now:", new_name)
            print("checkvar is now:", self.SKIP_EXISTING.get())
            print("overwrite is now:", self.OVERWRITE.get(), "\n")

    app = TestDialog()
    app.mainloop()
