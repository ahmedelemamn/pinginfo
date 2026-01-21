"""Tkinter GUI for PingInfo."""

from __future__ import annotations

import asyncio
import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from pinginfo.ping import PingResult, ping_hosts


@dataclass(frozen=True)
class PingSettings:
    interval: float
    timeout: float
    count: int


def _format_latency(latency_ms: float | None) -> str:
    if latency_ms is None:
        return "-"
    return f"{latency_ms:.1f} ms"


class PingInfoApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PingInfo")

        self.host_var = tk.StringVar()
        self.interval_var = tk.StringVar(value="1.0")
        self.timeout_var = tk.StringVar(value="1.5")
        self.count_var = tk.StringVar(value="0")

        self._result_queue: queue.Queue[tuple[int, list[PingResult]]] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._iteration = 0
        self._rows: dict[str, str] = {}

        self._build_ui()
        self._poll_results()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        host_frame = ttk.Frame(frame)
        host_frame.pack(fill=tk.X)

        ttk.Label(host_frame, text="Host").pack(side=tk.LEFT)
        host_entry = ttk.Entry(host_frame, textvariable=self.host_var)
        host_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(host_frame, text="Add", command=self._add_host).pack(side=tk.LEFT)

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=False, pady=8)

        self.host_list = tk.Listbox(list_frame, height=5)
        self.host_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(list_frame)
        button_frame.pack(side=tk.LEFT, padx=6)
        ttk.Button(button_frame, text="Remove", command=self._remove_host).pack(fill=tk.X)

        settings_frame = ttk.LabelFrame(frame, text="Settings")
        settings_frame.pack(fill=tk.X, pady=8)

        self._add_setting(settings_frame, "Interval (s)", self.interval_var, 0)
        self._add_setting(settings_frame, "Timeout (s)", self.timeout_var, 1)
        self._add_setting(settings_frame, "Count (0=forever)", self.count_var, 2)

        control_frame = ttk.Frame(frame)
        control_frame.pack(fill=tk.X, pady=6)
        self.start_button = ttk.Button(control_frame, text="Start", command=self._start)
        self.start_button.pack(side=tk.LEFT)
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self._stop, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=6)

        self.status_label = ttk.Label(frame, text="Idle")
        self.status_label.pack(anchor=tk.W)

        self.tree = ttk.Treeview(frame, columns=("status", "latency"))
        self.tree.heading("#0", text="Host")
        self.tree.heading("status", text="Status")
        self.tree.heading("latency", text="Latency")
        self.tree.column("#0", width=200, anchor=tk.W)
        self.tree.column("status", width=120, anchor=tk.W)
        self.tree.column("latency", width=120, anchor=tk.E)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=8)

    def _add_setting(self, parent: ttk.Widget, label: str, variable: tk.StringVar, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=6, pady=4)
        ttk.Entry(parent, textvariable=variable, width=10).grid(row=row, column=1, sticky=tk.W, padx=6)

    def _add_host(self) -> None:
        host = self.host_var.get().strip()
        if not host:
            return
        self.host_list.insert(tk.END, host)
        self.host_var.set("")

    def _remove_host(self) -> None:
        for index in reversed(self.host_list.curselection()):
            self.host_list.delete(index)

    def _get_hosts(self) -> list[str]:
        return list(self.host_list.get(0, tk.END))

    def _get_settings(self) -> PingSettings:
        interval = max(0.1, float(self.interval_var.get() or 1.0))
        timeout = max(0.5, float(self.timeout_var.get() or 1.5))
        count = max(0, int(float(self.count_var.get() or 0)))
        return PingSettings(interval=interval, timeout=timeout, count=count)

    def _start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        hosts = self._get_hosts()
        if not hosts:
            self.status_label.config(text="Add at least one host")
            return
        self._stop_event.clear()
        self._iteration = 0
        self._rows.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.status_label.config(text="Running...")
        settings = self._get_settings()
        self._worker = threading.Thread(
            target=self._run_loop,
            args=(hosts, settings),
            daemon=True,
        )
        self._worker.start()
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

    def _stop(self) -> None:
        self._stop_event.set()
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Stopping...")

    def _run_loop(self, hosts: list[str], settings: PingSettings) -> None:
        while not self._stop_event.is_set():
            self._iteration += 1
            results = asyncio.run(ping_hosts(hosts, settings.timeout))
            self._result_queue.put((self._iteration, results))
            if settings.count and self._iteration >= settings.count:
                break
            time.sleep(settings.interval)
        self._stop_event.set()
        self._result_queue.put((self._iteration, []))

    def _poll_results(self) -> None:
        try:
            while True:
                iteration, results = self._result_queue.get_nowait()
                if results:
                    self.status_label.config(text=f"Iteration {iteration}")
                    self._update_results(results)
                else:
                    if self._stop_event.is_set():
                        self.status_label.config(text="Stopped")
                        self.start_button.config(state=tk.NORMAL)
                        self.stop_button.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        self.root.after(200, self._poll_results)

    def _update_results(self, results: list[PingResult]) -> None:
        for result in results:
            status = "OK" if result.success else "FAIL"
            latency = _format_latency(result.latency_ms)
            if result.host in self._rows:
                self.tree.item(self._rows[result.host], values=(status, latency))
            else:
                item = self.tree.insert("", tk.END, values=(status, latency), text=result.host)
                self._rows[result.host] = item



def main() -> int:
    root = tk.Tk()
    PingInfoApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
