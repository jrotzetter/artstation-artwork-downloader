# Copyright (C) 2025 Jérémy Rotzetter. Portions Copyright (C) 1997 by Fredrik Lundh.
#
# This code is partially derived from Python standard library's simpledialog module,
# with modifications made to support a third button on the widget which is used to
# modify a boolean variable.

# See https://docs.python.org/3/library/dialog.html#module-tkinter.simpledialog for more information about the original module.

import tkinter as tk
from tkinter import simpledialog


class AskRenameDialog(simpledialog.Dialog):
    def __init__(
        self,
        title,
        prompt,
        checkvar,
        initialvalue=None,
        parent=None,
    ):
        self.prompt = prompt
        self.checkvar = checkvar
        self.initialvalue = initialvalue

        simpledialog.Dialog.__init__(self, parent, title)

    def destroy(self):
        self.entry = None
        simpledialog.Dialog.destroy(self)

    def body(self, master):
        w = tk.Label(master, text=self.prompt, justify=tk.LEFT)
        w.grid(row=0, padx=5, sticky=tk.W)

        self.entry = tk.Entry(master, width=50)
        self.entry.grid(row=1, padx=5, sticky=tk.W + tk.E)

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


def ask_rename(title: str, prompt: str, checkvar: bool, **kw) -> str:
    """
    Get a string representing a filename from the user

    :param title: The title of the widget
    :param prompt: The label text
    :param checkvar: the boolean variable that will be set to True when 'Skip all' button is pressed
    :param **kw: Keyword arguments that can be passed to simpledialog.Dialog
    :return: Return value is a string
    """
    d = AskRenameDialog(title, prompt, checkvar, **kw)
    return d.result


if __name__ == "__main__":

    class TestDialog(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("TestDialog")

            self.SKIP_EXISTING = tk.BooleanVar(value=False)

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
            filename = "this-file-already-exists"
            print("checkvar was:", self.SKIP_EXISTING.get())
            new_name = ask_rename(
                "A file with the same name already exists",
                "Please enter a new filename (without extension):",
                self.SKIP_EXISTING,
                parent=self,
                initialvalue=filename,
            )
            print("The file name is now:", new_name)
            print("checkvar is now:", self.SKIP_EXISTING.get())

    app = TestDialog()
    app.mainloop()
