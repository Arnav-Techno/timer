"""
Meditation Interval Timer
--------------------------
Build a sequence of timed meditation segments (e.g. 5 min, then 12 min)
and the app automatically plays a jingle sound at the end of each one.

Quick desktop test (fast iteration, no Android build needed):
    pip install kivy
    python main.py

Package for Android: see README.md
"""

import os
import json
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.core.window import Window
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.metrics import dp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOUNDS_DIR = os.path.join(BASE_DIR, "sounds")
SOUND_EXTENSIONS = (".wav", ".mp3", ".ogg")
PRESETS_FILE = os.path.join(BASE_DIR, "presets.json")


# ---------------- Android wake lock ----------------
# Keeps the CPU running (screen can still turn off / lock) so the timer
# keeps counting and jingles keep playing through the speaker instead of
# the whole app being frozen by the OS.

_wake_lock = None


def acquire_wake_lock():
    global _wake_lock
    if platform != "android" or _wake_lock is not None:
        return
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        PowerManager = autoclass("android.os.PowerManager")

        activity = PythonActivity.mActivity
        power_manager = activity.getSystemService(Context.POWER_SERVICE)
        _wake_lock = power_manager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK, "MeditationTimer:SessionLock"
        )
        _wake_lock.acquire()
    except Exception as e:
        print("Could not acquire wake lock:", e)


def release_wake_lock():
    global _wake_lock
    if _wake_lock is not None:
        try:
            _wake_lock.release()
        except Exception as e:
            print("Could not release wake lock:", e)
        _wake_lock = None


def list_sound_files():
    if not os.path.isdir(SOUNDS_DIR):
        return []
    return [
        f for f in sorted(os.listdir(SOUNDS_DIR))
        if f.lower().endswith(SOUND_EXTENSIONS)
    ]


class SegmentRow(BoxLayout):
    """One row in the segment editor: minutes + which sound plays at the end."""

    def __init__(self, sound_choices, minutes=5, sound=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(48),
                          spacing=dp(8), **kwargs)

        self.minutes_input = TextInput(
            text=str(minutes),
            input_filter="float",
            multiline=False,
            size_hint_x=0.25,
        )

        choices = sound_choices if sound_choices else ["(no sounds found)"]
        default_sound = sound if sound in choices else choices[0]
        self.sound_spinner = Spinner(
            text=default_sound,
            values=choices,
            size_hint_x=0.55,
        )

        remove_btn = Button(text="x", size_hint_x=0.2)
        remove_btn.bind(on_release=self.remove_self)

        self.add_widget(Label(text="min:", size_hint_x=0.1))
        self.add_widget(self.minutes_input)
        self.add_widget(self.sound_spinner)
        self.add_widget(remove_btn)

    def remove_self(self, *_):
        App.get_running_app().remove_segment(self)

    def get_data(self):
        try:
            minutes = float(self.minutes_input.text)
        except ValueError:
            minutes = 0
        return minutes, self.sound_spinner.text


class MeditationApp(App):
    title = "Meditation Timer"

    def build(self):
        Window.clearcolor = (0.07, 0.09, 0.09, 1)

        self.sound_choices = list_sound_files()
        self.segment_rows = []
        self.queue = []
        self.current_index = 0
        self.remaining = 0
        self.clock_event = None
        self.paused = False

        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))

        # ---------------- Editor screen ----------------
        self.editor = BoxLayout(orientation="vertical", spacing=dp(8))
        self.editor.add_widget(Label(
            text="Build your session", size_hint_y=None, height=dp(30),
            font_size="18sp", bold=True
        ))

        scroll = ScrollView(size_hint=(1, 1))
        self.segments_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.segments_box.bind(minimum_height=self.segments_box.setter("height"))
        scroll.add_widget(self.segments_box)
        self.editor.add_widget(scroll)

        add_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        add_btn = Button(text="+ Add segment")
        add_btn.bind(on_release=lambda *_: self.add_segment())
        save_btn = Button(text="Save preset")
        save_btn.bind(on_release=lambda *_: self.show_save_popup())
        load_btn = Button(text="Load preset")
        load_btn.bind(on_release=lambda *_: self.show_load_popup())
        add_row.add_widget(add_btn)
        add_row.add_widget(save_btn)
        add_row.add_widget(load_btn)
        self.editor.add_widget(add_row)

        start_btn = Button(text="Start Session", size_hint_y=None, height=dp(56),
                            font_size="18sp", background_color=(0.2, 0.6, 0.4, 1))
        start_btn.bind(on_release=lambda *_: self.start_session())
        self.editor.add_widget(start_btn)

        # seed with two example segments, like "5 min, then 12 min, then end"
        self.add_segment(minutes=5)
        self.add_segment(minutes=12)

        # ---------------- Running screen ----------------
        self.runner = BoxLayout(orientation="vertical", spacing=dp(14))
        self.segment_label = Label(text="", font_size="20sp")
        self.countdown_label = Label(text="00:00", font_size="64sp", bold=True)
        self.progress_label = Label(text="", font_size="16sp")

        controls = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self.pause_btn = Button(text="Pause")
        self.pause_btn.bind(on_release=lambda *_: self.toggle_pause())
        stop_btn = Button(text="Stop")
        stop_btn.bind(on_release=lambda *_: self.stop_session())
        controls.add_widget(self.pause_btn)
        controls.add_widget(stop_btn)

        self.runner.add_widget(Label())
        self.runner.add_widget(self.segment_label)
        self.runner.add_widget(self.countdown_label)
        self.runner.add_widget(self.progress_label)
        self.runner.add_widget(controls)
        self.runner.add_widget(Label())

        root.add_widget(self.editor)
        self._root = root
        return root

    # ---------------- segment editor ----------------

    def add_segment(self, minutes=5):
        row = SegmentRow(self.sound_choices, minutes=minutes)
        self.segment_rows.append(row)
        self.segments_box.add_widget(row)

    def remove_segment(self, row):
        if row in self.segment_rows:
            self.segment_rows.remove(row)
            self.segments_box.remove_widget(row)

    def current_segments_data(self):
        return [row.get_data() for row in self.segment_rows]

    # ---------------- presets (save/load a named sequence) ----------------

    def _load_presets(self):
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_presets(self, presets):
        with open(PRESETS_FILE, "w") as f:
            json.dump(presets, f, indent=2)

    def show_save_popup(self):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
        name_input = TextInput(hint_text="Preset name", multiline=False,
                                size_hint_y=None, height=dp(40))
        save_btn = Button(text="Save", size_hint_y=None, height=dp(44))
        box.add_widget(name_input)
        box.add_widget(save_btn)
        popup = Popup(title="Save preset", content=box, size_hint=(0.8, 0.4))

        def do_save(*_):
            name = name_input.text.strip()
            if not name:
                return
            presets = self._load_presets()
            presets[name] = self.current_segments_data()
            self._save_presets(presets)
            popup.dismiss()

        save_btn.bind(on_release=do_save)
        popup.open()

    def show_load_popup(self):
        presets = self._load_presets()
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        if not presets:
            box.add_widget(Label(text="No saved presets yet."))
        for name in presets:
            btn = Button(text=name, size_hint_y=None, height=dp(44))

            def make_cb(n=name):
                def cb(*_):
                    self.load_preset(presets[n])
                    popup.dismiss()
                return cb

            btn.bind(on_release=make_cb())
            box.add_widget(btn)
        popup = Popup(title="Load preset", content=box, size_hint=(0.8, 0.6))
        popup.open()

    def load_preset(self, data):
        for row in list(self.segment_rows):
            self.remove_segment(row)
        for minutes, sound in data:
            row = SegmentRow(self.sound_choices, minutes=minutes, sound=sound)
            self.segment_rows.append(row)
            self.segments_box.add_widget(row)

    # ---------------- session runner ----------------

    def start_session(self):
        data = self.current_segments_data()
        self.queue = [
            {"seconds": int(round(minutes * 60)), "sound": sound}
            for minutes, sound in data if minutes > 0
        ]
        if not self.queue:
            return

        # cumulative end-of-segment offsets, e.g. 5min+12min -> [300, 1020]
        self.segment_ends = []
        total = 0
        for seg in self.queue:
            total += seg["seconds"]
            self.segment_ends.append(total)

        self._root.clear_widgets()
        self._root.add_widget(self.runner)

        self.current_index = 0
        self.session_start = time.time()
        self.paused = False
        self.paused_at = None
        self.total_paused = 0.0
        self.pause_btn.text = "Pause"

        acquire_wake_lock()
        self._refresh_labels(elapsed=0)
        # tick often enough for a smooth countdown; correctness doesn't
        # depend on this interval since we always compute from wall-clock time
        self.clock_event = Clock.schedule_interval(self.tick, 1)

    def _elapsed(self):
        now = time.time()
        paused_total = self.total_paused
        if self.paused and self.paused_at is not None:
            paused_total += now - self.paused_at
        return now - self.session_start - paused_total

    def tick(self, dt):
        if self.paused:
            return
        elapsed = self._elapsed()

        # figure out how many segments should have completed by now, and
        # play a jingle for each one we haven't already played (handles
        # the case where the app was suspended past more than one boundary)
        new_index = self.current_index
        while new_index < len(self.segment_ends) and elapsed >= self.segment_ends[new_index]:
            self.play_sound(self.queue[new_index]["sound"])
            new_index += 1
        self.current_index = new_index

        if self.current_index >= len(self.queue):
            self.finish_session()
            return

        self._refresh_labels(elapsed)

    def _refresh_labels(self, elapsed):
        seg_start = self.segment_ends[self.current_index - 1] if self.current_index > 0 else 0
        seg_end = self.segment_ends[self.current_index]
        remaining = max(0, int(round(seg_end - elapsed)))
        mins, secs = divmod(remaining, 60)
        self.countdown_label.text = f"{mins:02d}:{secs:02d}"
        self.segment_label.text = f"Segment {self.current_index + 1} of {len(self.queue)}"
        self.progress_label.text = f"Next sound: {self.queue[self.current_index]['sound']}"

    def toggle_pause(self):
        now = time.time()
        if self.paused:
            self.total_paused += now - self.paused_at
            self.paused_at = None
            self.paused = False
            self.pause_btn.text = "Pause"
        else:
            self.paused = True
            self.paused_at = now
            self.pause_btn.text = "Resume"

    def play_sound(self, filename):
        if not filename or filename == "(no sounds found)":
            return
        path = os.path.join(SOUNDS_DIR, filename)
        sound = SoundLoader.load(path)
        if sound:
            sound.play()

    def finish_session(self):
        if self.clock_event:
            self.clock_event.cancel()
            self.clock_event = None
        release_wake_lock()
        self.segment_label.text = "Session complete"
        self.countdown_label.text = "00:00"
        self.progress_label.text = "Well done."
        Clock.schedule_once(lambda dt: self.stop_session(), 3)

    def stop_session(self):
        if self.clock_event:
            self.clock_event.cancel()
            self.clock_event = None
        release_wake_lock()
        self._root.clear_widgets()
        self._root.add_widget(self.editor)

    # ---------------- app lifecycle ----------------
    # Make sure Android doesn't tear the app down just because the screen
    # turned off or the user switched apps briefly.

    def on_pause(self):
        return True

    def on_resume(self):
        # catch up the countdown/labels immediately in case time passed
        # while we were paused/backgrounded
        if self.clock_event and not self.paused:
            self.tick(0)


if __name__ == "__main__":
    MeditationApp().run()
