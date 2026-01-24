# Kitten Python 🐱
> **A tiny feline companion for your digital desktop.**

Kitten Python is a lightweight desktop pet application built with Python and PyQt6. This little kitten lives on your screen, walks on top of your windows, and reacts to your interactions with animations and sounds.

## ✨ Features
- **Window Awareness**: The kitten can detect the top edges of your open windows and use them as platforms to walk or sit on.
- **Physics-Based Movement**: Includes gravity, jumping, and falling logic.
- **Rich Animations**: 10+ distinct animation states including walking, running, sleeping, licking, and "being carried."
- **Interactive**:
  - **Drag & Drop**: Pick up the kitten and move it anywhere.
  - **Petting**: Use your mouse wheel over the kitten to pet it and hear it purr.
  - **Feeding**: Right-click to open a context menu and feed the pet.
- **Standalone Executable**: No Python installation required to run the final version.

## 🎮 How to Use

### Running the Executable
If you don't want to build the project from source, you can buy the pre-built, ready-to-run version on itch.io:

👉 **[Download on itch.io](https://cyberhirsch.itch.io/desktop-kitten-pet)**

Otherwise, simply run the `dist/KittenPet.exe` after building it.

### Controls
| Action | Control |
| :--- | :--- |
| **Pick up / Move** | Left-click and Drag |
| **Pet / Purr** | Scroll Mouse Wheel |
| **Menu (Feed/Quit)** | Right-click |

### Development Setup
If you want to run from source, ensure you have Python installed and install dependencies:
```bash
pip install PyQt6 pywin32 Pillow
python main.py
```

## 🛠️ Technical Details
- **Frontend**: PyQt6 (Frameless, transparent, always-on-top window).
- **Collision Engine**: Custom `win32gui` integration to find window rectangles.
- **Animation System**: Custom sprite engine handling 32x32 frames with nearest-neighbor scaling.
- **Audio**: Python `QMediaPlayer` for MP3 playback.

---
*Created with ❤️ for Cat Lovers.*
