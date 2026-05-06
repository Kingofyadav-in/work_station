#!/usr/bin/env python3

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from bridge import process_intent
from context import read_recent_logs
from profile_manager import get_session, load_profiles
from system_info import get_system_info
from voice_input import get_voice_status

BG = "#08141f"
PANEL = "#102636"
CARD = "#153246"
TEXT = "#ecf7ff"
MUTED = "#9cc3d5"
ACCENT = "#4de2c5"
WARN = "#f6c85f"


class JarvisApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Jarvis Human Interface Bridge")
        self.root.geometry("920x680")
        self.root.configure(bg=BG)

        self.identity_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.voice_var = tk.StringVar()
        self.time_var = tk.StringVar()
        self.connectivity_var = tk.StringVar()
        self.profile_var = tk.StringVar()
        self.session_var = tk.StringVar()
        self.intent_var = tk.StringVar(value="status")
        self.name_var = tk.StringVar()
        self.language_var = tk.StringVar()
        self.domain_var = tk.StringVar()
        self.intro_mode_var = tk.StringVar()
        self.response_mode_var = tk.StringVar()

        self._build_layout()
        self.refresh()

    def _build_layout(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(24, 12))

        tk.Label(
            header,
            text="JARVIS",
            font=("Helvetica", 28, "bold"),
            fg=ACCENT,
            bg=BG,
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Human decides. Jarvis interprets. CLI executes. System responds. Human confirms.",
            font=("Helvetica", 11),
            fg=MUTED,
            bg=BG,
        ).pack(anchor="w", pady=(4, 0))

        grid = tk.Frame(self.root, bg=BG)
        grid.pack(fill="both", expand=True, padx=24, pady=12)
        grid.columnconfigure(0, weight=3)
        grid.columnconfigure(1, weight=2)

        left = tk.Frame(grid, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        right = tk.Frame(grid, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self._make_card(left, "Identity Bridge", self.identity_var, height=10)
        self._make_card(left, "Bridge Output", self.output_var, height=12)
        self._make_card(right, "Live Signals", None, metrics=True)
        self._make_card(right, "Profile State", self.profile_var, height=9)
        self._make_card(right, "Session State", self.session_var, height=7)

        controls = tk.Frame(self.root, bg=BG)
        controls.pack(fill="x", padx=24, pady=(0, 24))

        entry = ttk.Entry(controls, textvariable=self.intent_var, width=52)
        entry.pack(side="left", padx=(0, 12))
        entry.bind("<Return>", self._run_intent)

        ttk.Button(controls, text="Run Intent", command=self._run_intent).pack(side="left")
        ttk.Button(controls, text="Refresh Context", command=self.refresh).pack(side="left", padx=(12, 0))
        ttk.Button(controls, text="Show Logs", command=self._show_logs).pack(side="left", padx=(12, 0))

        prefs = tk.Frame(self.root, bg=BG)
        prefs.pack(fill="x", padx=24, pady=(0, 24))

        ttk.Entry(prefs, textvariable=self.name_var, width=22).pack(side="left", padx=(0, 8))
        ttk.Entry(prefs, textvariable=self.language_var, width=10).pack(side="left", padx=(0, 8))
        ttk.Entry(prefs, textvariable=self.domain_var, width=20).pack(side="left", padx=(0, 8))
        ttk.Combobox(
            prefs,
            textvariable=self.intro_mode_var,
            values=("short", "normal", "formal"),
            state="readonly",
            width=10,
        ).pack(side="left", padx=(0, 8))
        ttk.Combobox(
            prefs,
            textvariable=self.response_mode_var,
            values=("adaptive", "concise", "detailed"),
            state="readonly",
            width=10,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(prefs, text="Save Preferences", command=self._save_preferences).pack(side="left")

    def _make_card(
        self,
        parent: tk.Widget,
        title: str,
        variable: tk.StringVar | None,
        *,
        height: int = 8,
        metrics: bool = False,
    ) -> None:
        card = tk.Frame(parent, bg=PANEL, bd=0, highlightthickness=0)
        card.pack(fill="both", expand=True, pady=10)

        tk.Label(
            card,
            text=title,
            font=("Helvetica", 14, "bold"),
            fg=TEXT,
            bg=PANEL,
        ).pack(anchor="w", padx=16, pady=(16, 10))

        if metrics:
            metrics_frame = tk.Frame(card, bg=PANEL)
            metrics_frame.pack(fill="x", padx=16, pady=(0, 16))
            self._metric(metrics_frame, "Local Time", self.time_var, ACCENT)
            self._metric(metrics_frame, "Connectivity", self.connectivity_var, WARN)
            self._metric(metrics_frame, "Voice Layer", self.voice_var, ACCENT)
            return

        if variable is None:
            variable = tk.StringVar(value="")

        text = tk.Label(
            card,
            textvariable=variable,
            font=("Courier", 11),
            fg=TEXT,
            bg=CARD,
            justify="left",
            anchor="nw",
            padx=14,
            pady=14,
            height=height,
        )
        text.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def _metric(self, parent: tk.Widget, label: str, variable: tk.StringVar, color: str) -> None:
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=6)
        tk.Label(row, text=label, font=("Helvetica", 11, "bold"), fg=MUTED, bg=CARD).pack(
            anchor="w", padx=12, pady=(10, 2)
        )
        tk.Label(row, textvariable=variable, font=("Helvetica", 12), fg=color, bg=CARD).pack(
            anchor="w", padx=12, pady=(0, 10)
        )

    def refresh(self) -> None:
        info = get_system_info()
        voice = get_voice_status()
        profiles = load_profiles()
        hi_profile = profiles["HI"]
        session = get_session()
        identity_result = process_intent("identity")
        status_result = process_intent("status")

        self.identity_var.set(identity_result["result"] or identity_result["error"] or "Unavailable")
        self.output_var.set(status_result["result"] or status_result["error"] or "Unavailable")
        self.time_var.set(info["local_time"])
        self.connectivity_var.set(f"{info['connectivity']} | {info['local_ip']}")
        self.voice_var.set(voice["message"])
        self.profile_var.set(
            f"Name: {hi_profile.get('name', 'unknown')}\n"
            f"Domain: {hi_profile.get('domain', 'unknown')}\n"
            f"Language: {hi_profile.get('language', 'unknown')}\n"
            f"Intro Mode: {hi_profile.get('preferred_intro_mode', 'unknown')}\n"
            f"Response Mode: {hi_profile.get('preferred_response_mode', 'unknown')}\n"
            f"Mic Device: {hi_profile.get('preferred_mic_device', 'unknown')}\n"
            f"Wake Phrase: {hi_profile.get('wake_phrase', 'unknown')}"
        )
        self.session_var.set(
            f"Last Command: {session.get('last_command', 'unknown')}\n"
            f"Last Action: {session.get('last_action', 'unknown')}\n"
            f"Last Success: {session.get('last_successful_action', 'unknown')}\n"
            f"Pending: {session.get('pending_action', '') or '(none)'}"
        )

        self.name_var.set(hi_profile.get("name", ""))
        self.language_var.set(hi_profile.get("language", ""))
        self.domain_var.set(hi_profile.get("domain", ""))
        self.intro_mode_var.set(hi_profile.get("preferred_intro_mode", "normal"))
        self.response_mode_var.set(hi_profile.get("preferred_response_mode", "adaptive"))

        self.root.after(5000, self.refresh)

    def _run_intent(self, _event: object | None = None) -> None:
        intent = self.intent_var.get().strip()
        if not intent:
            messagebox.showinfo("Jarvis", "Enter an intent first.")
            return

        result = process_intent(intent)
        behavior = result.get("behavior", {})
        output_text = result["result"] or result["error"] or "No output."
        if behavior:
            output_text = (
                f"{output_text}\n\n"
                f"Risk Tier: {behavior.get('risk_tier', 'unknown')}\n"
                f"Response Mode: {behavior.get('response_mode', 'unknown')}"
            )
        self.output_var.set(output_text)
        self.session_var.set(
            f"Last Command: {get_session().get('last_command', 'unknown')}\n"
            f"Last Action: {get_session().get('last_action', 'unknown')}\n"
            f"Last Success: {get_session().get('last_successful_action', 'unknown')}\n"
            f"Pending: {get_session().get('pending_action', '') or '(none)'}"
        )

    def _save_preferences(self) -> None:
        commands = [
            f"set my name {self.name_var.get().strip()}",
            f"set my language {self.language_var.get().strip()}",
            f"set my domain {self.domain_var.get().strip()}",
            f"set intro mode {self.intro_mode_var.get().strip()}",
            f"set response mode {self.response_mode_var.get().strip()}",
        ]
        for command in commands:
            if command.split()[-1]:
                process_intent(command)
        self.refresh()
        messagebox.showinfo("Jarvis", "Preferences saved.")

    def _show_logs(self) -> None:
        self.output_var.set(read_recent_logs(12) or "No logs yet.")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    JarvisApp().run()
