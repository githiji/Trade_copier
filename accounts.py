# gui.py
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from database import add_account, get_accounts, init_db, remove_account, toggle_account

# Ensure current dir is in path for local imports to work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

APP_ICON = "trade_copier.ico"

COLORS = {
    "bg": "#101418",
    "panel": "#171c22",
    "panel_alt": "#1f2630",
    "field": "#0f141a",
    "border": "#2d3743",
    "text": "#eef3f8",
    "muted": "#97a4b3",
    "accent": "#4f8cff",
    "accent_hover": "#6aa0ff",
    "danger": "#b93d48",
}

FONT = ("Segoe UI", 10)
FONT_HEADER = ("Segoe UI Semibold", 13)


def configure_dark_theme(window):
    window.configure(bg=COLORS["bg"])
    style = ttk.Style(window)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", font=FONT)
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Panel.TFrame", background=COLORS["panel"])
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("Header.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONT_HEADER)
    style.configure(
        "TEntry",
        fieldbackground=COLORS["field"],
        background=COLORS["field"],
        foreground=COLORS["text"],
        insertcolor=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=(8, 6),
        relief="flat",
    )
    style.configure(
        "TButton",
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        borderwidth=0,
        focusthickness=0,
        padding=(10, 8),
        relief="flat",
    )
    style.map(
        "TButton",
        background=[("active", COLORS["border"]), ("pressed", COLORS["border"])],
        foreground=[("disabled", COLORS["muted"])],
    )
    style.configure("Accent.TButton", background=COLORS["accent"], foreground="white")
    style.map("Accent.TButton", background=[("active", COLORS["accent_hover"]), ("pressed", COLORS["accent"])])
    style.configure("Danger.TButton", background=COLORS["danger"], foreground="white")
    style.configure(
        "Treeview",
        background=COLORS["field"],
        fieldbackground=COLORS["field"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        rowheight=28,
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["accent"])],
        foreground=[("selected", "white")],
    )


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def set_window_icon(window):
    icon_path = resource_path(APP_ICON)
    if os.path.exists(icon_path):
        try:
            window.iconbitmap(icon_path)
        except tk.TclError:
            pass


class WindowsFileDrop:
    def __init__(self, widget, callback):
        if sys.platform != "win32":
            raise RuntimeError("Native file drag/drop is only available on Windows.")

        import ctypes

        self.widget = widget
        self.callback = callback
        self.ctypes = ctypes
        self.user32 = ctypes.windll.user32
        self.shell32 = ctypes.windll.shell32
        self.WM_DROPFILES = 0x0233
        self.GWLP_WNDPROC = -4
        self.WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )
        self.shell32.DragAcceptFiles.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.shell32.DragQueryFileW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_wchar_p,
            ctypes.c_uint,
        ]
        self.shell32.DragQueryFileW.restype = ctypes.c_uint
        self.shell32.DragFinish.argtypes = [ctypes.c_void_p]
        self.user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        self.user32.SetWindowLongPtrW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        self.user32.CallWindowProcW.restype = ctypes.c_void_p
        self.user32.CallWindowProcW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self._new_proc = self.WNDPROC(self._window_proc)
        self.old_proc = None
        self.hwnd = None

    def enable(self):
        self.widget.update_idletasks()
        self.hwnd = self.ctypes.c_void_p(self.widget.winfo_id())

        self.shell32.DragAcceptFiles(self.hwnd, True)
        self.old_proc = self.user32.SetWindowLongPtrW(
            self.hwnd,
            self.GWLP_WNDPROC,
            self.ctypes.cast(self._new_proc, self.ctypes.c_void_p),
        )

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == self.WM_DROPFILES:
            path = self._get_first_dropped_file(wparam)
            self.shell32.DragFinish(wparam)
            if path:
                self.callback(path)
            return 0

        return self.user32.CallWindowProcW(
            self.old_proc,
            hwnd,
            msg,
            wparam,
            lparam,
        )

    def _get_first_dropped_file(self, drop_handle):
        count = self.shell32.DragQueryFileW(drop_handle, 0xFFFFFFFF, None, 0)
        if count == 0:
            return None

        length = self.shell32.DragQueryFileW(drop_handle, 0, None, 0) + 1
        buffer = self.ctypes.create_unicode_buffer(length)
        self.shell32.DragQueryFileW(drop_handle, 0, buffer, length)
        return buffer.value


class AccountManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Trade Copier Account Manager")
        self.root.geometry("820x560")
        self.root.minsize(740, 500)
        configure_dark_theme(self.root)
        self.drop_handlers = []

        main = ttk.Frame(root, padding=14)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 12))

        ttk.Label(header, text="Account Manager", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Manage the MetaTrader terminals used by the copier.",
            foreground=COLORS["muted"],
        ).pack(anchor="w", pady=(2, 0))

        form = ttk.Frame(main, style="Panel.TFrame", padding=12)
        form.pack(fill="x", pady=(0, 10))

        self.login_entry = self.create_entry(form, "Login")
        self.server_entry = self.create_entry(form, "Server")
        self.password_entry = self.create_entry(form, "Password", show="*")
        self.path_entry = self.create_entry(form, "Terminal Path")

        path_buttons = ttk.Frame(form, style="Panel.TFrame")
        path_buttons.pack(fill="x", pady=(8, 0))

        ttk.Button(path_buttons, text="Browse Terminal", command=self.browse_terminal).pack(
            side="left",
            expand=True,
            fill="x",
            padx=(0, 4),
        )
        ttk.Button(path_buttons, text="Add Account", style="Accent.TButton", command=self.add_account).pack(
            side="right",
            expand=True,
            fill="x",
            padx=(4, 0),
        )

        self.drop_label = tk.Label(
            main,
            text="Drag terminal64.exe here",
            relief="groove",
            height=3,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            activebackground=COLORS["panel_alt"],
            font=("Segoe UI Semibold", 10),
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        self.drop_label.pack(fill="x", pady=(0, 10))

        self.account_table = ttk.Treeview(
            main,
            columns=("id", "login", "server", "status", "path"),
            show="headings",
            selectmode="extended",
            height=10,
        )
        self.account_table.heading("id", text="ID")
        self.account_table.heading("login", text="Login")
        self.account_table.heading("server", text="Server")
        self.account_table.heading("status", text="Status")
        self.account_table.heading("path", text="Terminal")
        self.account_table.column("id", width=45, anchor="center")
        self.account_table.column("login", width=120)
        self.account_table.column("server", width=150)
        self.account_table.column("status", width=90, anchor="center")
        self.account_table.column("path", width=330)
        self.account_table.pack(fill="both", expand=True, pady=(0, 10))

        action_row = ttk.Frame(main)
        action_row.pack(fill="x")

        ttk.Button(action_row, text="Enable Selected", command=lambda: self.set_selected_enabled(1)).pack(
            side="left",
            expand=True,
            fill="x",
            padx=(0, 4),
        )
        ttk.Button(action_row, text="Disable Selected", command=lambda: self.set_selected_enabled(0)).pack(
            side="left",
            expand=True,
            fill="x",
            padx=4,
        )
        ttk.Button(action_row, text="Remove Selected", style="Danger.TButton", command=self.remove_selected).pack(
            side="right",
            expand=True,
            fill="x",
            padx=(4, 0),
        )

        self.refresh()
        self.root.after(100, self.enable_file_drop)

    def create_entry(self, parent, label, show=None):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.pack(fill="x", pady=4)

        ttk.Label(frame, text=label, width=16, background=COLORS["panel"], foreground=COLORS["muted"]).pack(side="left")
        entry = ttk.Entry(frame, show=show)
        entry.pack(side="right", fill="x", expand=True)
        return entry

    def browse_terminal(self):
        path = filedialog.askopenfilename(
            title="Select MetaTrader terminal",
            filetypes=[("MetaTrader terminal", "terminal*.exe"), ("Executable files", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.set_terminal_path(path)

    def enable_file_drop(self):
        if sys.platform != "win32":
            self.drop_label.config(text="Use Browse Terminal to select terminal64.exe")
            return

        try:
            for widget in (self.root, self.drop_label, self.path_entry):
                handler = WindowsFileDrop(widget, self.set_terminal_path)
                handler.enable()
                self.drop_handlers.append(handler)
        except Exception as exc:
            self.drop_label.config(text=f"Drag/drop unavailable. Use Browse Terminal. ({exc})")

    def set_terminal_path(self, path):
        path = path.strip().strip("{}")
        if path.lower().endswith(".lnk"):
            messagebox.showwarning(
                "Shortcut dropped",
                "Please drag the actual terminal64.exe file, not a desktop shortcut.",
            )
            return

        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, path)

    def add_account(self):
        login = self.login_entry.get().strip()
        server = self.server_entry.get().strip()
        password = self.password_entry.get().strip()
        path = self.path_entry.get().strip().strip("{}")

        if not login or not server or not password or not path:
            messagebox.showerror("Missing Info", "Login, server, password, and terminal path are required.")
            return

        if not os.path.isfile(path):
            messagebox.showerror("Invalid Path", "Choose or drag the actual terminal .exe file.")
            return

        add_account(login, server, password, path)
        self.refresh()

    def selected_account_ids(self):
        ids = []
        for item_id in self.account_table.selection():
            values = self.account_table.item(item_id, "values")
            ids.append(int(values[0]))
        return ids

    def remove_selected(self):
        account_ids = self.selected_account_ids()
        if not account_ids:
            return

        if not messagebox.askyesno("Remove Accounts", f"Remove {len(account_ids)} selected account(s)?"):
            return

        for account_id in account_ids:
            remove_account(account_id)
        self.refresh()

    def set_selected_enabled(self, enabled):
        account_ids = self.selected_account_ids()
        if not account_ids:
            return

        for account_id in account_ids:
            toggle_account(account_id, enabled)
        self.refresh()

    def refresh(self):
        self.account_table.delete(*self.account_table.get_children())

        for acc in get_accounts():
            account_id, login, server, password, path, enabled = acc
            status = "Enabled" if enabled == 1 else "Disabled"
            self.account_table.insert(
                "",
                tk.END,
                values=(account_id, login, server, status, path),
            )


if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    set_window_icon(root)
    configure_dark_theme(root)
    app = AccountManager(root)
    root.mainloop()
