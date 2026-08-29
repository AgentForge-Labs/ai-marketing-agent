# demo.py — Wassim Sayah
# Visual demo: red targets appear on screen, mouse moves and clicks them biometrically.
# Uses tkinter (built-in) for the target window. No browser needed.

import sys
import time
import random
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_mouse.human_mouse import HumanMouse

try:
    from pynput.mouse import Controller, Button
except ImportError:
    print("[!] pip install pynput")
    sys.exit(1)

try:
    import tkinter as tk
except ImportError:
    print("[!] tkinter not available")
    sys.exit(1)

PROFILE = Path(__file__).parent.parent / "profile" / "mouse_profile.json"
if not PROFILE.exists():
    print("[!] No profile found. Run record_mouse.py + train_mouse_model.py first.")
    sys.exit(1)

mouse_ctrl = Controller()
model      = HumanMouse.load_profile(PROFILE)
session    = model.new_session(variance=0.08)

TARGET_RADIUS = 25
TARGETS_TO_HIT = 12


class DemoWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI Mouse Demo — W. Sayah")
        self.root.attributes("-topmost", True)

        # get screen size and make the window large
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = int(sw * 0.75), int(sh * 0.75)
        x, y = (sw - w) // 2, (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.canvas = tk.Canvas(self.root, bg="#0a0b0f", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.w = w
        self.h = h
        self.win_x = x
        self.win_y = y
        self.hits = 0
        self.target_id = None
        self.target_cx = 0
        self.target_cy = 0
        self.running = True

        # status text
        self.status = self.canvas.create_text(
            w // 2, 30, text="Starting in 2 seconds...",
            fill="#e8eaf6", font=("Consolas", 14)
        )
        self.counter = self.canvas.create_text(
            w // 2, h - 30,
            text=f"Targets hit: 0 / {TARGETS_TO_HIT}",
            fill="#6b7280", font=("Consolas", 11)
        )

        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        self.root.after(100, self._update_position)

    def _update_position(self):
        """Track window position in case user moves it."""
        if self.running:
            try:
                self.win_x = self.root.winfo_rootx()
                self.win_y = self.root.winfo_rooty()
                self.w = self.root.winfo_width()
                self.h = self.root.winfo_height()
            except:
                pass
            self.root.after(200, self._update_position)

    def spawn_target(self):
        if self.target_id:
            self.canvas.delete(self.target_id)

        pad = 80
        cx = random.randint(pad, self.w - pad)
        cy = random.randint(pad + 50, self.h - pad - 50)
        self.target_cx = cx
        self.target_cy = cy

        r = TARGET_RADIUS
        self.target_id = self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill="#e53935", outline="#ff8a80", width=2
        )
        self.canvas.itemconfig(self.status, text=f"Target #{self.hits + 1}")
        self.canvas.update()

    def screen_pos(self):
        """Convert canvas target to screen coordinates."""
        return self.win_x + self.target_cx, self.win_y + self.target_cy

    def mark_hit(self):
        self.hits += 1
        if self.target_id:
            self.canvas.itemconfig(self.target_id, fill="#1b5e20", outline="#66bb6a")
        self.canvas.itemconfig(
            self.counter,
            text=f"Targets hit: {self.hits} / {TARGETS_TO_HIT}"
        )
        self.canvas.update()

    def set_status(self, text):
        self.canvas.itemconfig(self.status, text=text)
        self.canvas.update()

    def stop(self):
        self.running = False
        self.root.destroy()


def run_demo(win):
    time.sleep(2)

    pos = mouse_ctrl.position
    current = (pos[0], pos[1])

    for i in range(TARGETS_TO_HIT):
        if not win.running:
            break

        # spawn a new red target
        win.root.after(0, win.spawn_target)
        time.sleep(0.3)  # let tkinter render

        # get screen position of the target
        tx, ty = win.screen_pos()

        # add slight randomness inside the target circle (don't always hit dead center)
        offset_x = random.randint(-TARGET_RADIUS // 3, TARGET_RADIUS // 3)
        offset_y = random.randint(-TARGET_RADIUS // 3, TARGET_RADIUS // 3)
        target = (tx + offset_x, ty + offset_y)

        # generate biometric path
        path = session.path_to(current, target)

        # move the cursor
        for x, y, delay_ms in path:
            if not win.running:
                return
            mouse_ctrl.position = (x, y)
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

        # click
        mouse_ctrl.click(Button.left)
        current = target

        # visual feedback
        win.root.after(0, win.mark_hit)

        # human pause before next target
        pause = random.uniform(0.5, 1.5)
        time.sleep(pause)

    if win.running:
        win.root.after(0, lambda: win.set_status("Done! Close the window."))


if __name__ == "__main__":
    print("[*] AI Mouse visual demo")
    print(f"[*] Profile: {PROFILE.name}")
    print("[*] Watch your cursor move to the red targets.\n")

    win = DemoWindow()

    t = threading.Thread(target=run_demo, args=(win,), daemon=True)
    t.start()

    win.root.mainloop()
    print("[*] Demo finished.")
