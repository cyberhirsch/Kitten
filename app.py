"""
Shared desktop-pet application.

main.py and snake.py are thin entry points that hand a PetDefinition to
run(); everything below is species-agnostic.
"""

import ctypes
import json
import os
import sys
import time

from PyQt6.QtWidgets import QApplication, QMainWindow, QMenu
from PyQt6.QtCore import Qt, QTimer, QPoint, QUrl
from PyQt6.QtGui import QPainter, QAction, QCursor, QActionGroup
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

from engine.sprite_engine import SpriteEngine
from engine.pet_ai import PetAI, State, BehaviorMode
from engine.window_helper import get_collidable_windows
from engine.paths import user_data_file, legacy_settings_path

# How far in from the window edges the sprite body is assumed to sit, used when
# deciding which floors the pet overlaps horizontally.
BODY_INSET = 28


def resource_path(relative_path):
    """ Get absolute path to resource, checking multiple locations """
    relative_path = os.path.join(*relative_path.split("/")) if "/" in relative_path else relative_path
    paths_to_check = []

    # 1. PyInstaller _MEIPASS
    if hasattr(sys, '_MEIPASS'):
        paths_to_check.append(os.path.join(sys._MEIPASS, relative_path))

    # 2. macOS App Bundle Resources (relative to executable)
    bundle_path = os.path.join(os.path.dirname(sys.executable), "..", "Resources", relative_path)
    paths_to_check.append(os.path.abspath(bundle_path))

    # 3. Current Working Directory (Dev)
    paths_to_check.append(os.path.abspath(os.path.join(".", relative_path)))

    for path in paths_to_check:
        if os.path.exists(path):
            return path

    return paths_to_check[0] if paths_to_check else relative_path


class DesktopPet(QMainWindow):
    def __init__(self, pet):
        super().__init__()

        self.pet = pet
        self.frame_size = pet.frame_size
        self.variant = pet.default_variant

        # Window attributes
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.Tool  # Hide from taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.frame_size, self.frame_size)

        # Audio setup (a pet with no purr_sound stays silent)
        self.audio_output = None
        self.purr_player = None
        if pet.purr_sound:
            self.audio_output = QAudioOutput()
            self.purr_player = QMediaPlayer()
            self.purr_player.setAudioOutput(self.audio_output)
            self.purr_player.setSource(QUrl.fromLocalFile(resource_path(pet.purr_sound)))
            self.purr_player.setLoops(QMediaPlayer.Loops.Infinite)
            self.audio_output.setVolume(0)  # Start muted for fading

        # Petting & Fading state
        self.is_petting = False
        self.should_purr = False
        self.current_volume = 0.0
        self.target_volume = 0.0

        # Timer to detect when petting stops
        self.petting_stop_timer = QTimer()
        self.petting_stop_timer.setSingleShot(True)
        self.petting_stop_timer.timeout.connect(self.on_petting_stopped)

        # Timer for smooth volume transition (every 50ms)
        if self.purr_player:
            self.fade_update_timer = QTimer()
            self.fade_update_timer.timeout.connect(self.update_audio_fade)
            self.fade_update_timer.start(50)

        # AI tracking
        self.virtual_geo = QApplication.primaryScreen().virtualGeometry()
        self.ai = PetAI(self.virtual_geo.center().x(), self.virtual_geo.center().y(), pet=pet)

        # Window tracking
        self.collidable_floors = [self.virtual_geo.bottom()]
        self.last_window_update = 0

        # Dragging state
        self.dragging = False
        self.drag_pos = QPoint()

        # Sprites (load_settings may swap the variant, so load them first)
        self.sprite_engine = None
        self.load_settings()
        self.load_variant(self.variant)

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.game_loop)
        self.timer.start(30)  # ~33 FPS

        # Apply macOS-specific fixes once the window is fully realized
        if sys.platform == "darwin":
            QTimer.singleShot(500, self.apply_macos_fixes)

        self.show()
        self.raise_()
        self.activateWindow()

    def load_variant(self, variant):
        """(Re)builds the sprite engine for a colour variant."""
        engine = SpriteEngine(
            resource_path(variant.spritesheet),
            sprite_size=self.pet.sprite_size,
            scale=self.pet.scale,
        )
        for name, cfg in self.pet.animations.items():
            engine.load_animation(name, cfg["row"], cfg["frames"], cfg.get("col_start", 0))

        self.sprite_engine = engine
        self.variant = variant

    def set_variant(self, variant):
        if variant.id == self.variant.id:
            return
        self.load_variant(variant)
        self.ai.frame_idx = 0
        self.save_settings()

    def apply_macos_fixes(self):
        """Apply native macOS window behavior fixes."""
        try:
            import objc
            from AppKit import (
                NSApplication,
                NSApplicationActivationPolicyAccessory,
                NSWindowCollectionBehaviorStationary,
                NSWindowCollectionBehaviorIgnoresCycle
            )

            # 1. Hide Dock Icon (if not already handled)
            nsapp = NSApplication.sharedApplication()
            nsapp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

            # 2. Get Native Window
            view_ptr = int(self.winId())
            view = objc.objc_object(c_void_p=ctypes.c_void_p(view_ptr))
            window = view.window()

            if window:
                # Remove Shadow (Outline)
                window.setHasShadow_(False)

                # Keep Visible on Deactivate
                window.setHidesOnDeactivate_(False)

                # STATIONARY: Don't move with other windows
                # IGNORES_CYCLE: Don't show in Cmd+Tab
                window.setCollectionBehavior_(
                    NSWindowCollectionBehaviorStationary |
                    NSWindowCollectionBehaviorIgnoresCycle
                )

                # NSStatusWindowLevel = 25: above most apps, below system overlays
                window.setLevel_(25)

        except Exception as e:
            print(f"macOS window customization failed: {e}")

    def update_windows(self):
        # Update window list every 500ms
        if time.time() - self.last_window_update > 0.5:
            floors = []
            body_left = self.ai.x + BODY_INSET
            body_right = self.ai.x + self.frame_size - BODY_INSET

            for s in QApplication.screens():
                s_geo = s.availableGeometry()
                # If the pet is horizontally within this screen, its bottom is a valid floor
                if body_right > s_geo.left() and body_left < s_geo.right():
                    # Qt's bottom() is height-1, so +1 makes it a solid surface
                    floors.append(s_geo.bottom() + 1)

            rects = get_collidable_windows(exclude_hwnd=int(self.winId()))
            # Extract top edges that intersect the pet's horizontal range
            for left, top, right, bottom in rects:
                if left < body_right and right > body_left:
                    floors.append(top)

            # Always include the absolute bottom as a safety floor
            floors.append(self.virtual_geo.bottom() + 1)
            self.collidable_floors = floors
            self.last_window_update = time.time()

    def game_loop(self):
        self.update_windows()

        m_pos = QCursor.pos()
        mouse_tuple = (m_pos.x(), m_pos.y())

        v_rect = [self.virtual_geo.left(), self.virtual_geo.top(),
                  self.virtual_geo.right(), self.virtual_geo.bottom()]
        self.ai.update(30, v_rect, self.collidable_floors,
                       mouse_pos=mouse_tuple,
                       last_input_time_ms=self.get_last_input_time_ms())

        # Sync window position (while dragging, mouseMoveEvent owns the position)
        if not self.dragging:
            self.move(int(self.ai.x), int(self.ai.y))

        # Animation frame update
        anim_cfg = self.pet.animations.get(self.ai.current_anim, self.pet.animations["IDLE"])
        hold_frame = anim_cfg["frames"] - 3  # EMOTE holds near the end while petting
        if self.ai.anim_timer > anim_cfg["speed"]:
            # Special case: hold the petting EMOTE on its peak frame
            if self.is_petting and self.ai.current_anim == "EMOTE" and self.ai.frame_idx == hold_frame:
                self.ai.anim_timer = 0
            else:
                next_frame = self.ai.frame_idx + 1

                # At the end of EMOTE, drop to IDLE rather than looping back to frame 0
                if self.ai.current_anim == "EMOTE" and next_frame >= anim_cfg["frames"]:
                    if not self.is_petting:
                        self.ai.set_state(State.IDLE)
                    else:
                        self.ai.frame_idx = 0
                else:
                    self.ai.frame_idx = next_frame % anim_cfg["frames"]

                self.ai.anim_timer = 0

        # Update mask for click-through
        _, mask = self.sprite_engine.get_frame(self.ai.current_anim, self.ai.frame_idx, self.ai.direction)
        if mask:
            self.setMask(mask)

        self.update()  # Trigger paintEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        frame, _ = self.sprite_engine.get_frame(self.ai.current_anim, self.ai.frame_idx, self.ai.direction)
        if frame:
            painter.drawPixmap(0, 0, frame)

    # ---- Input events ----

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.ai.set_state(State.CARRY)
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if self.dragging:
            new_pos = event.globalPosition().toPoint() - self.drag_pos

            if new_pos.x() > self.ai.x:
                self.ai.direction = "right"
            elif new_pos.x() < self.ai.x:
                self.ai.direction = "left"

            self.ai.x = new_pos.x()
            self.ai.y = new_pos.y()
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.dragging:
            self.dragging = False
            self.ai.vy = 0  # Drop it
            self.ai.wake_up()  # Waking up after being moved
            self.ai.set_state(State.FALL)
            event.accept()

    def wheelEvent(self, event):
        # Petting interaction
        if self.ai.state != State.CARRY:
            if not self.is_petting:
                self.is_petting = True
                # Delay the reaction so a stray scroll doesn't trigger it
                QTimer.singleShot(500, self.start_petting_reaction)
            else:
                if self.should_purr:
                    # Keep sleeping - extend the state so it doesn't wake mid-purr
                    self.ai.state_end_time = time.time() * 1000 + 3000
                elif self.ai.state == State.EMOTE:
                    self.ai.state_end_time = time.time() * 1000 + 1500

            self.petting_stop_timer.start(300)
            event.accept()

    def start_petting_reaction(self):
        """Triggered after a 500ms delay from the start of petting."""
        if not self.is_petting:
            return  # Stopped petting before the delay finished

        # A sleeping pet with a sound purrs and stays asleep; a silent one
        # (or an awake one) wakes up and does its happy animation instead.
        if self.ai.state == State.SLEEP and self.purr_player:
            self.should_purr = True
            self.target_volume = 0.5
            self.purr_player.play()
        else:
            self.should_purr = False
            self.ai.wake_up()
            self.ai.set_state(State.EMOTE, duration=1500)

    def on_petting_stopped(self):
        self.is_petting = False
        if self.should_purr:
            self.target_volume = 0.0  # Begin the slow fade out

    def update_audio_fade(self):
        # Fade in over ~1s (0.025/step), fade out over ~5s (0.005/step), at 50ms steps
        if self.current_volume < self.target_volume:
            self.current_volume = min(self.target_volume, self.current_volume + 0.025)
        elif self.current_volume > self.target_volume:
            self.current_volume = max(self.target_volume, self.current_volume - 0.005)

        self.audio_output.setVolume(self.current_volume)

        if self.current_volume <= 0 and self.target_volume == 0:
            if self.purr_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.purr_player.stop()
                self.should_purr = False

    # ---- Menu ----

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #4a4a4a;
            }
            QMenu::separator {
                height: 1px;
                background: #3d3d3d;
                margin: 4px 10px;
            }
        """)

        feed_action = QAction("Feed", self)
        feed_action.triggered.connect(self.feed_pet)
        menu.addAction(feed_action)
        menu.addSeparator()

        # Behavior submenu
        behavior_menu = menu.addMenu("Behavior")
        behavior_group = QActionGroup(self)
        behavior_group.setExclusive(True)
        for mode, label in ((BehaviorMode.LAZY, "Lazy (Always Sleepy)"),
                            (BehaviorMode.STANDARD, "Standard (Hunger & Break Reminders)")):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(self.ai.mode == mode)
            action.triggered.connect(lambda checked, m=mode: self.set_behavior_mode(m))
            behavior_group.addAction(action)
            behavior_menu.addAction(action)

        # Colour submenu, only for pets that ship more than one sheet
        if len(self.pet.variants) > 1:
            color_menu = menu.addMenu("Color")
            color_group = QActionGroup(self)
            color_group.setExclusive(True)
            for variant in self.pet.variants:
                action = QAction(variant.label, self)
                action.setCheckable(True)
                action.setChecked(variant.id == self.variant.id)
                action.triggered.connect(lambda checked, v=variant: self.set_variant(v))
                color_group.addAction(action)
                color_menu.addAction(action)

        menu.addSeparator()
        close_action = QAction("Close", self)
        close_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(close_action)

        try:
            menu.exec(pos)
        except Exception as e:
            print(f"Context menu error: {e}")

    def set_behavior_mode(self, mode):
        self.ai.mode = mode
        if mode == BehaviorMode.LAZY:
            self.ai.wake_up(3000)
        self.save_settings()

    def feed_pet(self):
        self.ai.last_fed = time.time()
        self.ai.work_start_time = time.time() * 1000  # Reset work timer too
        self.ai.awake_until = 0  # No longer wants to play if just fed
        food_coma_intro = State.CLEAN if State.CLEAN in self.ai.allowed_states else State.IDLE
        self.ai.set_state(food_coma_intro, duration=2000)
        self.ai.queued_state = State.SLEEP

    # ---- Settings ----

    def save_settings(self):
        settings = {
            "behavior_mode": self.ai.mode.name,
            "variant": self.variant.id,
        }
        try:
            with open(user_data_file(self.pet.settings_filename), "w") as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def load_settings(self):
        try:
            settings_path = user_data_file(self.pet.settings_filename)
            if not os.path.exists(settings_path):
                # Migrate settings written by older builds next to the script
                legacy = legacy_settings_path(self.pet.settings_filename)
                if os.path.exists(legacy):
                    settings_path = legacy
            if not os.path.exists(settings_path):
                return

            with open(settings_path, "r") as f:
                settings = json.load(f)

            mode_name = settings.get("behavior_mode")
            if mode_name == "MOTIVATOR":  # Renamed in an earlier release
                self.ai.mode = BehaviorMode.STANDARD
            elif mode_name in BehaviorMode.__members__:
                self.ai.mode = BehaviorMode[mode_name]

            self.variant = self.pet.variant(settings.get("variant"))
        except Exception as e:
            print(f"Failed to load settings: {e}")

    def get_last_input_time_ms(self):
        """Returns the timestamp (ms) of the last user input (keyboard or mouse)."""
        if sys.platform == "win32":
            try:
                import win32api
                # GetLastInputInfo and GetTickCount share the since-boot epoch,
                # so the difference is idle time we can subtract from wall clock.
                last_input_tick = win32api.GetLastInputInfo()
                millis = ctypes.windll.kernel32.GetTickCount()
                idle_ms = millis - last_input_tick
                return (time.time() * 1000) - idle_ms
            except Exception:
                return time.time() * 1000
        elif sys.platform == "darwin":
            try:
                from Quartz import (CGEventSourceSecondsSinceLastEventType,
                                    kCGEventSourceStateCombinedSessionState,
                                    kCGAnyInputEventType)
                idle_secs = CGEventSourceSecondsSinceLastEventType(
                    kCGEventSourceStateCombinedSessionState, kCGAnyInputEventType)
                return (time.time() - idle_secs) * 1000
            except Exception:
                return time.time() * 1000
        return time.time() * 1000


def _install_crash_handler():
    def log_exception(cls, exception, traceback):
        import traceback as tb
        error_msg = "".join(tb.format_exception(cls, exception, traceback))
        try:
            with open(user_data_file("crash_report.txt"), "a") as f:
                f.write(f"\n--- Crash at {time.ctime()} ---\n")
                f.write(error_msg)
        except Exception:
            pass
        print(error_msg)
        sys.__excepthook__(cls, exception, traceback)

    sys.excepthook = log_exception


def run(pet):
    """Boots a QApplication for one pet definition and blocks until it quits."""
    _install_crash_handler()

    app = QApplication(sys.argv)
    app.setApplicationName(pet.display_name)

    # Hide the Dock icon on macOS (LSUIElement covers the bundled build)
    if sys.platform == "darwin":
        try:
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            NSApplication.sharedApplication().setActivationPolicy_(
                NSApplicationActivationPolicyAccessory)
        except ImportError:
            pass

    window = DesktopPet(pet)
    return app.exec()
