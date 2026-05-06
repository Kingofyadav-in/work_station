import tkinter as tk
from tkinter import scrolledtext
import platform
import socket
import datetime
import getpass
import subprocess


def get_device_name():
    return socket.gethostname()


def get_os_info():
    return platform.system() + " " + platform.release()


def get_user_name():
    return getpass.getuser()


def get_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def check_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return "Connected"
    except OSError:
        return "Not Connected"


def refresh_info():
    time_value.config(text=get_time())
    internet_value.config(text=check_internet())
    root.after(1000, refresh_info)


def make_row(label_text, value_text):
    row = tk.Frame(info_frame, bg="#101820")
    row.pack(anchor="w", pady=5)

    label = tk.Label(
        row,
        text=label_text,
        font=("Arial", 12, "bold"),
        fg="#00ffaa",
        bg="#101820",
        width=15,
        anchor="w"
    )
    label.pack(side="left")

    value = tk.Label(
        row,
        text=value_text,
        font=("Arial", 12),
        fg="white",
        bg="#101820",
        anchor="w"
    )
    value.pack(side="left")

    return value


def map_intent_to_command(intent: str):
    intent = intent.lower().strip()

    command_map = {
        "show date": ["date"],
        "show calendar": ["cal"],
        "show files": ["ls", "-la"],
        "show uptime": ["uptime"],
        "show whoami": ["whoami"],
        "show pwd": ["pwd"],
        "check network": ["ping", "-c", "1", "8.8.8.8"],
    }

    return command_map.get(intent)


def run_jarvis_command():
    intent = intent_entry.get().strip()

    output_box.delete("1.0", tk.END)

    if not intent:
        output_box.insert(tk.END, "Please enter an intent.\n")
        return

    command = map_intent_to_command(intent)

    # Layer 3: simple intelligence / decision check
    if command is None:
        output_box.insert(
            tk.END,
            f"Unknown intent: {intent}\n\n"
            "Try one of these:\n"
            "- show date\n"
            "- show calendar\n"
            "- show files\n"
            "- show uptime\n"
            "- show whoami\n"
            "- show pwd\n"
            "- check network\n"
        )
        return

    # Layer 4: safe action execution
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )

        output_box.insert(tk.END, f"Intent: {intent}\n")
        output_box.insert(tk.END, f"Command: {' '.join(command)}\n")
        output_box.insert(tk.END, "-" * 50 + "\n")

        if result.stdout:
            output_box.insert(tk.END, result.stdout)

        if result.stderr:
            output_box.insert(tk.END, "\n[stderr]\n" + result.stderr)

        output_box.insert(tk.END, f"\nExit code: {result.returncode}\n")

    except Exception as e:
        output_box.insert(tk.END, f"Execution error: {e}\n")


root = tk.Tk()
root.title("Jarvis Intro App")
root.geometry("700x550")
root.configure(bg="#101820")

title = tk.Label(
    root,
    text="Welcome to Jarvis",
    font=("Arial", 20, "bold"),
    fg="white",
    bg="#101820"
)
title.pack(pady=15)

subtitle = tk.Label(
    root,
    text="Jarvis is not just an assistant. It is a command bridge.",
    font=("Arial", 12),
    fg="#cccccc",
    bg="#101820"
)
subtitle.pack(pady=5)

info_frame = tk.Frame(root, bg="#101820")
info_frame.pack(pady=15)

user_value = make_row("User:", get_user_name())
device_value = make_row("Device:", get_device_name())
os_value = make_row("OS:", get_os_info())
time_value = make_row("Time:", get_time())
internet_value = make_row("Internet:", check_internet())

message = tk.Label(
    root,
    text="Human intent → Jarvis bridge → CLI execution → System feedback",
    font=("Arial", 12),
    fg="#ffffff",
    bg="#101820",
    wraplength=600,
    justify="center"
)
message.pack(pady=15)

input_frame = tk.Frame(root, bg="#101820")
input_frame.pack(pady=10)

intent_label = tk.Label(
    input_frame,
    text="Enter intent:",
    font=("Arial", 12, "bold"),
    fg="#00ffaa",
    bg="#101820"
)
intent_label.pack(side="left", padx=5)

intent_entry = tk.Entry(
    input_frame,
    width=40,
    font=("Arial", 12)
)
intent_entry.pack(side="left", padx=5)

run_button = tk.Button(
    input_frame,
    text="Run",
    font=("Arial", 11, "bold"),
    bg="#00ffaa",
    fg="black",
    command=run_jarvis_command
)
run_button.pack(side="left", padx=5)

output_label = tk.Label(
    root,
    text="Jarvis Output",
    font=("Arial", 12, "bold"),
    fg="#00ffaa",
    bg="#101820"
)
output_label.pack(pady=(15, 5))

output_box = scrolledtext.ScrolledText(
    root,
    width=80,
    height=15,
    font=("Courier", 10),
    bg="#1a1a1a",
    fg="white",
    insertbackground="white"
)
output_box.pack(pady=10)

refresh_info()
root.mainloop()
