# Desktop Pets 🐱🐍
> **Tiny companions for your digital desktop.**

Lightweight desktop pet applications built with Python and PyQt6. They live on your screen, walk on top of your windows, and react to your interactions with animations and sounds.

Two pets ship as **separate applications**, sharing one engine:

| Pet | Description |
| :--- | :--- |
| **Desktop Kitten** 🐱 | The original. Full animation set, purrs when you pet it while it sleeps. |
| **Desktop Snake** 🐍 | Slithers along your window edges in six colours. Wiggles happily when petted. |

Run whichever you like — or both at once, since they're independent executables with independent settings.

## ✨ Features
- **Cross-Platform**: Works on both Windows and macOS.
- **Two pets**: A kitten and a snake, each built as its own standalone app.
- **Window Awareness**: The kitten can detect the top edges of your open windows and use them as platforms to walk or sit on.
- **Physics-Based Movement**: Includes gravity, jumping, and falling logic.
- **Rich Animations**: 10+ distinct animation states including walking, running, sleeping, licking, and "being carried."
- **Interactive**:
  - **Drag & Drop**: Pick up the kitten and move it anywhere.
  - **Petting**: Use your mouse wheel over the kitten to pet it and hear it purr.
  - **Feeding**: Right-click to open a context menu and feed the pet.
- **Colour variants**: The snake comes in Green, Red, Blue, Brown, Corn and Albino, switchable from its right-click menu.
- **Standalone Executable**: No Python installation required to run the final version.

### A note on the snake's animations
The snake's sprite pack contains a single seven-frame slither cycle and nothing
else — no lick, clean, play or jump poses. Rather than fake them, those
behaviours are switched off for the snake, and its idle and sleep animations are
built from slices of the walk cycle. It has no sound of its own, so petting a
sleeping snake wakes it into a happy wiggle instead of purring.

## 🎮 How to Use

### Running the Executable
If you don't want to build the project from source, you can buy the pre-built, ready-to-run version on itch.io:

👉 **[Download on itch.io](https://cyberhirsch.itch.io/desktop-kitten-pet)**

Otherwise, simply run the `dist/DesktopKitten.exe` (Windows) or the app bundle (macOS) after building it.

### Building from source
Both pets have their own PyInstaller spec. From the project root:

```bash
pip install -r requirements.txt
pyinstaller --noconfirm --clean "Desktop Kitten.spec"
pyinstaller --noconfirm --clean "Desktop Snake.spec"
```

Results land in `dist/` — a `.app` bundle on macOS, a folder containing the
`.exe` on Windows.

### Automated builds
The `Build` GitHub Actions workflow builds both pets for Windows and macOS on
every push and pull request, and attaches the zipped results as run artifacts.
Pushing a `v*` tag additionally publishes them to a GitHub Release.

### Auto-Start on Login (macOS)
1.  Open **System Settings** > **General** > **Login Items**.
2.  Click the **+** button under **Open at Login**.
3.  Select your `Desktop Kitten.app` or `Desktop Snake.app`.

### Controls
| Action | Control |
| :--- | :--- |
| **Pick up / Move** | Left-click and Drag |
| **Pet / Purr** | Scroll Mouse Wheel |
| **Menu (Feed / Behavior / Color / Quit)** | Right-click |

### Development Setup
If you want to run from source, ensure you have Python installed and install dependencies:

```bash
pip install -r requirements.txt
python main.py    # the kitten
python snake.py   # the snake
```

Run the headless smoke test (no display required) with:

```bash
python tests/smoke_test.py
```

## 🛠️ Technical Details
- **Structure**: `app.py` holds the shared window, physics and interaction code. `engine/pets.py` defines each species — spritesheet layout, colour variants, movement speeds, sound, and which behaviours its artwork can depict. `main.py` and `snake.py` are one-line entry points.
- **Frontend**: PyQt6 (Frameless, transparent, always-on-top window).
- **Collision Engine**: 
  - **Windows**: `win32gui` integration to find window rectangles.
  - **macOS**: `Quartz` (CoreGraphics) integration via `pyobjc`.
- **Animation System**: Custom sprite engine handling 32x32 frames with nearest-neighbor scaling.
- **Audio**: Python `QMediaPlayer` for MP3 playback.
- **Settings**: Stored per-pet in the user's application data directory (`%APPDATA%`, `~/Library/Application Support`, or `$XDG_CONFIG_HOME`), so they survive updates.

## 🎨 Credits
- Snake sprites: **PixelSnakes (Free)** by **Carysaurus** — see `assets/snakes/CREDITS.md`.

---
*Created with ❤️ for Cat Lovers.*
