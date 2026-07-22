import tkinter as tk
from tkinter import ttk, messagebox

from .client import login
from .config import set_token, set_username


def show_login(on_success):

    window = tk.Tk()
    window.title("Trade Copier Login")
    window.geometry("350x250")
    window.resizable(False, False)

    ttk.Label(
        window,
        text="Trade Copier",
        font=("Segoe UI", 18, "bold")
    ).pack(pady=15)

    ttk.Label(window, text="Username").pack()

    username_entry = ttk.Entry(window, width=30)
    username_entry.pack(pady=5)

    ttk.Label(window, text="Password").pack()

    password_entry = ttk.Entry(window, show="*", width=30)
    password_entry.pack(pady=5)

    status = ttk.Label(window, text="")
    status.pack(pady=10)

    def do_login():

        username = username_entry.get().strip()
        password = password_entry.get()

        if not username or not password:
            messagebox.showerror("Error", "Please enter username and password.")
            return

        status.config(text="Connecting...")

        try:

            response = login(username, password)

            if response.status_code == 200:

                data = response.json()

                set_token(data["token"])
                set_username(data["username"])

                window.destroy()

                on_success()

            else:

                messagebox.showerror(
                    "Login Failed",
                    "Invalid username or password."
                )

                status.config(text="")

        except Exception as e:

            messagebox.showerror(
                "Connection Error",
                str(e)
            )

            status.config(text="")

    ttk.Button(
        window,
        text="Login",
        command=do_login
    ).pack(pady=10)

    window.mainloop()