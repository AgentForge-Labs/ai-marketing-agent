# playwright_integration.py — Wassim Sayah
# Playwright wrapper for biometric mouse injection.

import time
import asyncio
import random
from pathlib import Path
from ai_mouse.human_mouse import HumanMouse

class PlaywrightHumanMouse:
    def __init__(self, page, profile_path="profile/mouse_profile.json", rotation_minutes=30):
        self.page = page
        self.profile_path = Path(profile_path)
        self.rotation_interval = rotation_minutes * 60

        self.base_mouse = HumanMouse.load_profile(self.profile_path)

        # extract hardware click profile if it was recorded
        _click = self.base_mouse._profile.get("hardware_click", {})
        self._has_click_data = _click.get("count", 0) > 0
        self._click_mean_s   = _click.get("mean_ms", 85.0) / 1000.0
        self._click_std_s    = _click.get("std_ms",  20.0) / 1000.0
        self._click_p25_s    = _click.get("p25_ms",  65.0) / 1000.0
        self._click_p75_s    = _click.get("p75_ms", 105.0) / 1000.0

        self._current_session    = None
        self._session_start_time = 0
        self.current_x = 960
        self.current_y = 540

        self._rotate_if_needed()

    def _rotate_if_needed(self):
        """Applies mathematical variance every X minutes to evade fingerprinting."""
        now = time.time()
        if self._current_session is None or (now - self._session_start_time) > self.rotation_interval:
            variance = 0.08
            self._current_session = self.base_mouse.new_session(variance=variance)
            self._session_start_time = now
            print(f"[*] Session rotated (variance={variance*100:.0f}%)")

    async def move_to(self, target_x, target_y):
        """Move the mouse to an absolute screen coordinate using human paths"""
        self._rotate_if_needed()
        
        start = (self.current_x, self.current_y)
        end = (target_x, target_y)
        
        # Generate the biometric path
        path = self._current_session.path_to(start, end)
        
        # Execute the path in Playwright
        for x, y, delay_ms in path:
            await self.page.mouse.move(x, y)
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000.0)
            
            # Update our internal tracker
            self.current_x = x
            self.current_y = y

    async def click(self, x=None, y=None, **kwargs):
        """Biometric click if hardware data exists, otherwise falls back to random timing."""
        if x is not None and y is not None:
            await self.move_to(x, y)

        await self.page.mouse.down(**kwargs)

        if self._has_click_data:
            # sample from the real distribution, clamped to [p25, p75] range
            hold = random.gauss(self._click_mean_s, self._click_std_s)
            hold = max(self._click_p25_s, min(hold, self._click_p75_s))
        else:
            hold = random.uniform(0.05, 0.15)

        await asyncio.sleep(hold)
        await self.page.mouse.up(**kwargs)

    async def click_element(self, locator):
        """Moves to a random pixel within an element's bounding box and clicks."""
        await locator.wait_for(state="visible")
        
        box = await locator.bounding_box()
        if not box:
            raise Exception("Could not get bounding box for element (is it visible?)")
            
        # Padding ensures we don't click on the absolute edge of the button
        pad_x = max(1, box["width"] * 0.1)
        pad_y = max(1, box["height"] * 0.1)
        
        # Pick a random target inside the padded box
        target_x = box["x"] + random.uniform(pad_x, box["width"] - pad_x)
        target_y = box["y"] + random.uniform(pad_y, box["height"] - pad_y)
        
        await self.move_to(target_x, target_y)
        await self.click()
        
    async def scroll(self, delta_y):
        """Human-like scroll with mouse wheel (Playwright wheel support)"""
        # A simple natural scroll wrapper just for completeness
        self._rotate_if_needed()
        await self.page.mouse.wheel(delta_x=0, delta_y=delta_y)
        await asyncio.sleep(random.uniform(0.1, 0.3))
