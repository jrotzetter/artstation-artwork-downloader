# Copyright (c) 2026 Jérémy Rotzetter

import tkinter as tk
from tkinter import ttk

# Define themes
light_theme = {
    "TFrame": {"configure": {"background": "#f0f0f0"}},
    "TButton": {
        "configure": {
            "background": "#e0e0e0",
            "foreground": "black",
            "anchor": "center",
            "bordercolor": "#9e9a91",
            "lightcolor": "#eeebe7",
            "darkcolor": "#cfcdc8",
            "borderwidth": 3,
            "relief": "raised",
        },
        "map": {
            "background": [
                ("active", "#c0c0c0")
            ],  # Hover effect only; 'relief' handles click
            "foreground": [("active", "black")],
        },
    },
    "TLabel": {"configure": {"background": "#f0f0f0", "foreground": "black"}},
    "TLabelframe": {"configure": {"background": "#f0f0f0", "borderwidth": 2}},
    "TLabelframe.Label": {
        "configure": {
            "background": "#f0f0f0",
            "foreground": "black",
            "borderwidth": 2,
        }
    },
    "TCombobox": {
        "configure": {
            "fieldbackground": "white",
            "foreground": "black",
            "arrowcolor": "black",
            "selectbackground": "white",  # Override default focus color
            "selectforeground": "black",
        }
    },
    "TEntry": {
        "configure": {
            "fieldbackground": "white",
            "foreground": "black",
            "insertcolor": "black",
        },
        "map": {
            "fieldbackground": [("readonly", "lightgray"), ("disabled", "darkgray")],
            "foreground": [("readonly", "black"), ("disabled", "gray")],
        },
    },
    "TCheckbutton": {
        "configure": {
            "background": "#f0f0f0",
            "foreground": "black",
            "indicatorbackground": "white",
            "indicatorsize": 11,
        }
    },
    "TProgressbar": {
        "configure": {
            "background": "#007acc",
            "bordercolor": "#d0d0d0",
            "troughcolor": "#e0e0e0",
        }
    },
    "TScrollbar": {
        "configure": {
            "troughcolor": "#dcdad5",  # Light gray from clam theme's "-frame"
            "background": "#eeeeee",  # For the slider
            "darkcolor": "#d0cecb",  # Lower border of slider for 3D effect
            "lightcolor": "#ffffff",  # Upper border of slider for 3D effect
            "bordercolor": "#c0bebb",
        },
        "map": {
            "background": [("active", "darkgray")],
        },
    },
}
dark_theme = {
    "TFrame": {"configure": {"background": "#171717"}},
    "TButton": {
        "configure": {
            "background": "#3c3f41",
            "foreground": "#f5f5f5",
            "anchor": "center",
            "bordercolor": "#444444",
            "lightcolor": "#333333",
            "darkcolor": "#555555",
            "borderwidth": 3,
            "relief": "raised",
        },
        "map": {
            "background": [("active", "#5c5f61")],
            "foreground": [("active", "white")],
        },
    },
    "TLabel": {"configure": {"background": "#171717", "foreground": "#a1a1a1"}},
    "TLabelframe": {"configure": {"background": "#171717", "borderwidth": 2}},
    "TLabelframe.Label": {
        "configure": {
            "background": "#171717",
            "foreground": "#a1a1a1",
            "borderwidth": 2,
        }
    },
    "TCombobox": {
        "configure": {
            "fieldbackground": "#3c3f41",
            "foreground": "#f5f5f5",
            "arrowcolor": "black",
            "selectbackground": "#3c3f41",  # Only affects the field, not the dropdown list
            "selectforeground": "white",
        }
    },
    "TEntry": {
        "configure": {
            "fieldbackground": "#3c3f41",
            "foreground": "white",
            "insertcolor": "white",
        },
        "map": {
            # Distinct colors for states to improve visibility in dark mode
            "fieldbackground": [
                ("readonly", "#555555"),
                ("disabled", "#444444"),
                ("active", "#4c4f51"),  # Lighter background on focus
            ],
            "foreground": [
                ("readonly", "lightgray"),  # Softer text for non-editable text
                ("disabled", "#888888"),  # Faded for disabled
            ],
        },
    },
    "TCheckbutton": {
        "configure": {
            "background": "#171717",
            "foreground": "white",
            "indicatorbackground": "#3c3f41",
            "indicatorsize": 11,
            "indicatorforeground": "white",
        }
    },
    "TProgressbar": {
        "configure": {
            "background": "#007acc",
            "bordercolor": "#444444",
            "troughcolor": "#3c3f41",
        }
    },
    "TScrollbar": {
        "configure": {
            "troughcolor": "#3c3f41",
            "background": "#555555",
            "darkcolor": "#222222",
            "lightcolor": "#444444",
            "bordercolor": "#444444",
        },
        "map": {
            "background": [("active", "#777777")],
        },
    },
}

# For default values of clam theme see here:
# https://github.com/coapp-packages/tk/blob/master/library/ttk/clamTheme.tcl

# Test themes
# \\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
if __name__ == "__main__":

    class ThemeApp:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("Custom Themed Light/Dark Mode")
            self.root.geometry("400x300")

            self.style = ttk.Style(self.root)
            self.style.theme_create("light", parent="alt", settings=light_theme)
            self.style.theme_create("dark", parent="alt", settings=dark_theme)
            self.style.theme_use("light")

            self.current_theme = "light"
            self.create_widgets()

        def create_widgets(self):
            main_frame = ttk.Frame(self.root)
            main_frame.pack(fill="both", expand=True, padx=20, pady=20)

            self.label = ttk.Label(main_frame, text="Try out Custom Themes!")
            self.label.pack(pady=20)

            self.toggle_btn = ttk.Button(main_frame, text="Switch to Dark Mode")
            self.toggle_btn.pack(pady=10)
            self.toggle_btn.config(command=self.change_theme)

        def change_theme(self):
            if self.current_theme == "light":
                self.style.theme_use("dark")
                self.root.configure(bg="#2d2d2d")
                self.current_theme = "dark"
                self.toggle_btn.config(text="Switch to Light Mode")
            else:
                self.style.theme_use("light")
                self.root.configure(bg="white")
                self.current_theme = "light"
                self.toggle_btn.config(text="Switch to Dark Mode")

        def run(self):
            self.root.mainloop()

    app = ThemeApp()
    app.run()
