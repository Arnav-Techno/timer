# Meditation Timer

A Kivy app where you build a sequence of meditation segments (e.g. "5 min,
then 12 min") and it automatically plays a jingle at the end of each one.

## How it works

- Each row in the editor is one segment: a duration in minutes + a sound
  that plays when that segment ends.
- Add as many segments as you like. The sound on the *last* row acts as
  your "session end" jingle.
- "Save preset" / "Load preset" let you store named sequences (e.g.
  "Morning 20+20", "Quick 5+12") so you don't have to rebuild them each time.
  These are stored in `presets.json` next to the app.
- Sounds are auto-detected from the `sounds/` folder — just drop your own
  `.wav`, `.mp3`, or `.ogg` files in there and they'll show up in the
  dropdown next time you open the app (or after you add a new segment row).

Three placeholder chime tones are included so you can test the app right
away. Replace them with your real jingles by adding files to `sounds/`
(you can delete the placeholders once you have your own).

## 1. Fast local testing (recommended before every Android build)

Android builds are slow (10-30+ min), so iterate on desktop first:

```bash
pip install kivy
cd meditation_timer
python main.py
```

This opens the app in a window on your computer, behaving exactly like it
will on your phone.

## 2. Building and installing the APK on your phone

Buildozer itself only runs on Linux, so if you're on Windows/macOS the
easiest path is **Option A** (no Linux setup needed at all). If you already
have Linux/WSL, **Option B** is simpler.

### Option A — Build in the cloud with GitHub Actions (recommended)

This repo already includes `.github/workflows/build.yml`, which builds the
APK for you on GitHub's servers.

1. Create a new repo on GitHub and push this project to it:
   ```bash
   cd meditation_timer
   git init
   git add .
   git commit -m "Meditation timer app"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```
2. On GitHub, go to your repo's **Actions** tab. The "Build Android APK"
   workflow will run automatically (takes ~15-20 min the first time).
3. When it finishes, open the workflow run and download the
   **meditation-timer-apk** artifact (a zip containing the `.apk`).
4. Transfer the `.apk` to your phone any way you like (email it to
   yourself, Google Drive, USB cable, etc.), then tap it on your phone to
   install. Android will ask you to allow "install unknown apps" for
   whichever app you opened it from (Files, Chrome, Gmail...) — approve
   that, then install.

### Option B — Build locally (Linux or WSL2 on Windows)

```bash
pip install buildozer cython
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf \
    libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
    libtinfo5 cmake libffi-dev libssl-dev

cd meditation_timer
buildozer -v android debug
```

The first run downloads the Android SDK/NDK automatically (can take a
while). Your APK ends up at `bin/meditationtimer-0.1-debug.apk`.

**Install via USB** (enable Developer Options → USB debugging on your
phone first):
```bash
buildozer android deploy run logcat
# or manually:
adb install bin/meditationtimer-0.1-debug.apk
```

## 3. Working with the screen off / locked

The app now:
- Acquires a partial **wake lock** while a session is running, so the CPU
  keeps running (and your jingles keep playing) even though the screen is
  off or the phone is locked. The screen itself is still allowed to turn
  off/lock as normal — you don't need to keep it lit.
- Times everything off the actual clock rather than counting app "ticks",
  so if the OS ever briefly delays the app, the countdown and jingle timing
  self-correct instead of drifting.
- Won't be killed just because the screen turns off (`on_pause` returns
  `True`), and re-syncs its display the moment you unlock your phone again.

**One real limitation to know about:** this works reliably as long as the
meditation app stays the *active* app (screen off/locked is fine — that's
the normal way phones behave). If you fully switch to a different app for
an extended period, Android's battery-saving (Doze/App Standby) can still
suspend background apps regardless of the wake lock. For a typical
20-40 minute sit where you lock your phone and set it down, this setup
should hold up fine. If you specifically want jingles to keep playing
while you're actively using another app, that needs turning this into a
proper Android foreground service (like how music apps work) — a bigger
change, let me know if you want that instead.

## 4. Other things you might want later

- **Vibration on jingle**: easy to add via `plyer.vibrator` for silent
  environments.
- **Notification showing time remaining**: possible via `plyer.notification`
  or a foreground-service notification.

## File structure

```
meditation_timer/
├── main.py            # app logic and UI
├── buildozer.spec      # Android packaging config
├── presets.json         # created automatically once you save a preset
├── sounds/              # drop your jingle files here (.wav/.mp3/.ogg)
└── README.md
```
