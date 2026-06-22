#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AC's Switch 2 Emulator 0.1
"""
# import python 3.14. files = off
# pr

import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

BG = "#1e1e1e"
PANEL = "#2d2d2d"
ACCENT = "#00b4ff"
TEXT = "#e0e0e0"
FPS = 60
FRAME_MS = 1000 // FPS
LOGIC_HZ = 240
STEPS_PER_FRAME = max(1, LOGIC_HZ // FPS)
SCALE = 3
SCREEN_W = 320 * SCALE
SCREEN_H = 180 * SCALE


class ACNX2Assembler:
    def assemble(self, source: str) -> bytes:
        program = bytearray()
        for line in source.splitlines():
            line = line.strip().split(";")[0].strip()
            if not line:
                continue
            parts = line.replace(",", " ").split()
            mnem = parts[0].upper()

            if mnem == "NOP":
                program += bytes([0x00, 0, 0, 0])
            elif mnem == "MOV":
                program += bytes([0x01, int(parts[1][1:]) & 0xF, 0, int(parts[2]) & 0xFF])
            elif mnem == "ADD":
                program += bytes([0x02, int(parts[1][1:]) & 0xF, 0, int(parts[2]) & 0xFF])
            elif mnem == "RECT":
                program += bytes([0x07, int(parts[1][1:]) & 0xF, int(parts[2][1:]) & 0xF, int(parts[3]) & 0xFF])
            elif mnem == "JOYCON":
                program += bytes([0x10, 0, 0, 0])
            elif mnem == "DOCK":
                program += bytes([0x20, 0, 0, 0])
            elif mnem == "HALT":
                program += bytes([0xFF, 0, 0, 0])
        return bytes(program)


class ACNX2VM:
    __slots__ = ("x", "y", "halted", "program", "pc", "mode", "dirty")

    def __init__(self):
        self.x = 120
        self.y = 60
        self.halted = False
        self.program = b""
        self.pc = 0
        self.mode = "HANDHELD"
        self.dirty = True

    def load(self, bytecode: bytes):
        self.program = bytecode
        self.pc = 0
        self.halted = False
        self.dirty = True

    def step(self):
        if self.halted or not self.program or self.pc >= len(self.program):
            self.halted = True
            return False
        opcode = self.program[self.pc]
        self.pc += 4
        changed = True

        if opcode == 0x01:
            self.x = self.program[self.pc - 1] * 2
        elif opcode == 0x02:
            self.x = (self.x + self.program[self.pc - 1]) % 280
        elif opcode == 0x07:
            self.x = self.program[self.pc - 3] * 18
            self.y = self.program[self.pc - 2] * 18
        elif opcode == 0x10:
            self.x += 8
        elif opcode == 0x20:
            self.mode = "DOCK"
        elif opcode == 0xFF:
            self.halted = True
        else:
            changed = opcode not in (0x00,)

        if changed:
            self.dirty = True
        return changed

    def set_mode(self, mode):
        if self.mode != mode:
            self.mode = mode
            self.dirty = True


class ScreenCanvas:
    """Persistent canvas items — no delete-all per frame."""

    def __init__(self, canvas: tk.Canvas, scale=SCALE):
        self.canvas = canvas
        self.scale = scale
        self._dock_visible = None
        self._last_xy = None
        s = scale
        c = canvas
        c.create_rectangle(0, 0, SCREEN_W, SCREEN_H, fill="#000000", outline="", tags=("layer",))
        self.dock_frame = c.create_rectangle(
            30, 15, SCREEN_W - 30, SCREEN_H - 15,
            outline="#ffffff", width=18, state="hidden", tags=("layer",),
        )
        self.dock_text = c.create_text(
            SCREEN_W // 2, 35, text="SWITCH 2 DOCK MODE",
            fill=ACCENT, font=("Consolas", 16, "bold"), state="hidden", tags=("layer",),
        )
        self.sprite = c.create_rectangle(
            0, 0, 50 * s, 45 * s, fill=ACCENT, outline="#ffffff", width=5, tags=("layer",),
        )

    def sync(self, vm: ACNX2VM):
        if not vm.dirty and self._dock_visible == (vm.mode == "DOCK") and self._last_xy == (vm.x, vm.y):
            return False

        s = self.scale
        dock = vm.mode == "DOCK"
        if self._dock_visible != dock:
            state = "normal" if dock else "hidden"
            self.canvas.itemconfigure(self.dock_frame, state=state)
            self.canvas.itemconfigure(self.dock_text, state=state)
            self._dock_visible = dock

        xy = (vm.x, vm.y)
        if self._last_xy != xy:
            x1, y1 = vm.x * s, vm.y * s
            self.canvas.coords(self.sprite, x1, y1, x1 + 50 * s, y1 + 45 * s)
            self._last_xy = xy

        vm.dirty = False
        return True


class ACNXEMU:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AC's Switch 2 Emulator 0.1")
        self.root.configure(bg=BG)
        self.root.geometry("1380x820")

        self.vm = ACNX2VM()
        self.assembler = ACNX2Assembler()
        self.running = False
        self._fps_t = time.perf_counter()
        self._fps_frames = 0
        self._fps_display = 0.0
        self._next_tick = time.perf_counter()

        self._build_ui()
        self.screen = ScreenCanvas(self.canvas)
        self.render(force=True)
        self._frame_loop()

    def _build_ui(self):
        top = tk.Frame(self.root, bg="#0078d4", height=55)
        top.pack(fill="x")
        tk.Label(
            top, text="AC's Switch 2 Emulator 0.1",
            bg="#0078d4", fg="white", font=("Consolas", 17, "bold"),
        ).pack(side="left", padx=25, pady=12)

        tb = tk.Frame(self.root, bg=PANEL, height=55)
        tb.pack(fill="x", padx=12, pady=8)

        ttk.Button(tb, text="▶ Run", command=self.toggle_run).pack(side="left", padx=6)
        ttk.Button(tb, text="⏹ Stop", command=self.stop).pack(side="left", padx=6)
        ttk.Button(tb, text="Step", command=self.step).pack(side="left", padx=6)
        ttk.Button(tb, text="Load .nx2", command=self.load).pack(side="left", padx=6)
        ttk.Button(tb, text="Assemble", command=self.assemble).pack(side="left", padx=6)
        ttk.Button(tb, text="Mode", command=self.toggle_mode).pack(side="left", padx=6)

        main = tk.PanedWindow(self.root, orient="horizontal", bg=BG)
        main.pack(fill="both", expand=True, padx=12, pady=5)

        left = tk.Frame(main, bg=PANEL)
        main.add(left, width=550)
        tk.Label(
            left, text="Code Editor", bg=PANEL, fg=ACCENT, font=("Consolas", 13, "bold"),
        ).pack(anchor="w", padx=15, pady=8)
        self.editor = scrolledtext.ScrolledText(left, bg="#1e1e1e", fg=TEXT, font=("Consolas", 11))
        self.editor.pack(fill="both", expand=True, padx=15, pady=5)
        self.editor.insert("1.0", """; Switch 2 Example
MOV R0, 90
MOV R1, 55
RECT R0, R1, 45
JOYCON
DOCK
HALT
""")

        right = tk.Frame(main, bg=BG)
        main.add(right, stretch="always")
        tk.Label(
            right, text="Switch 2 Screen", bg=BG, fg=ACCENT, font=("Consolas", 13, "bold"),
        ).pack(anchor="w", padx=15, pady=8)
        self.canvas = tk.Canvas(
            right, width=SCREEN_W, height=SCREEN_H,
            bg="#000000", highlightthickness=12, highlightbackground=ACCENT,
        )
        self.canvas.pack(pady=12)

        self.status = tk.Label(self.root, text="Ready | 60 FPS target", bg=PANEL, fg=TEXT, anchor="w", padx=15)
        self.status.pack(fill="x", side="bottom")

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("NX2", "*.nx2 *.txt")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", code)
            self.assemble()

    def assemble(self):
        code = self.editor.get("1.0", "end").strip()
        try:
            bytecode = self.assembler.assemble(code)
            self.vm.load(bytecode)
            self.render(force=True)
            self.status.config(text=f"Assembled {len(bytecode)} bytes | 60 FPS")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def toggle_run(self):
        self.running = not self.running
        self._next_tick = time.perf_counter()
        self._set_status()

    def stop(self):
        self.running = False
        self._set_status()

    def step(self):
        self.vm.step()
        self.render(force=True)

    def toggle_mode(self):
        self.vm.set_mode("DOCK" if self.vm.mode == "HANDHELD" else "HANDHELD")
        self.render(force=True)

    def render(self, force=False):
        if force or self.vm.dirty:
            self.screen.sync(self.vm)

    def _set_status(self):
        base = "RUNNING" if self.running else ("HALTED" if self.vm.halted else "PAUSED")
        self.status.config(text=f"{base} | {self._fps_display:.0f} FPS | PC={self.vm.pc} | {self.vm.mode}")

    def _frame_loop(self):
        now = time.perf_counter()
        self._fps_frames += 1
        if now - self._fps_t >= 0.5:
            self._fps_display = self._fps_frames / (now - self._fps_t)
            self._fps_frames = 0
            self._fps_t = now

        if self.running and now >= self._next_tick:
            missed = min(4, int((now - self._next_tick) / (1.0 / FPS)) + 1)
            for _ in range(missed):
                for _ in range(STEPS_PER_FRAME):
                    if not self.vm.step():
                        break
                self._next_tick += 1.0 / FPS
            self.render()

        if self.running or self.vm.dirty:
            self._set_status()

        self.root.after(FRAME_MS, self._frame_loop)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    ACNXEMU().run()
