import sys
import os
import time
from PyQt6.QtWidgets import QApplication, QMainWindow, QMenu
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect
from PyQt6.QtGui import QPainter, QAction, QCursor
from PyQt6.QtMultimedia import QSoundEffect, QAudioOutput, QMediaPlayer
from PyQt6.QtCore import QUrl
import ctypes

from engine.sprite_engine import SpriteEngine
from engine.pet_ai import PetAI, State, BehaviorMode
from engine.window_helper import get_collidable_windows
import json

ANIMATIONS_CONFIG = {
    "IDLE":       {"row": 0, "frames": 4,  "speed": 200},
    "LOOK_SIDE":  {"row": 1, "frames": 4,  "speed": 200},
    "LICK":       {"row": 2, "frames": 4,  "speed": 150},
    "CLEAN":      {"row": 3, "frames": 4,  "speed": 150},
    "WALK":       {"row": 4, "frames": 8,  "speed": 100}, 
    "RUN":        {"row": 5, "frames": 8,  "speed": 80},  
    "SLEEP":      {"row": 6, "frames": 4,  "speed": 400},
    "PLAY":       {"row": 7, "frames": 6,  "speed": 120},
    "JUMP":       {"row": 8, "frames": 7,  "speed": 150},
    "LANDING":    {"row": 8, "frames": 3,  "col_start": 4, "speed": 100},
    "EMOTE":      {"row": 9, "frames": 8,  "speed": 150},
    "CARRY_HELD": {"row": 8, "frames": 1,  "col_start": 2, "speed": 1000}, 
    "CARRY_FALL": {"row": 8, "frames": 1,  "col_start": 3, "speed": 1000}, 
}

def resource_path(relative_path):
    """ Get absolute path to resource, checking multiple locations """
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
    def __init__(self):
        super().__init__()
        
        # Window attributes
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.Tool # Hide from taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setFixedSize(128, 128)
        
        # Engine setup
        spritesheet_path = resource_path(os.path.join("assets", "spritesheet.png"))
        self.sprite_engine = SpriteEngine(spritesheet_path)
        for name, cfg in ANIMATIONS_CONFIG.items():
            self.sprite_engine.load_animation(name, cfg["row"], cfg["frames"], cfg.get("col_start", 0))
            
        # Audio setup
        self.audio_output = QAudioOutput()
        self.purr_player = QMediaPlayer()
        self.purr_player.setAudioOutput(self.audio_output)
        purr_path = resource_path(os.path.join("assets", "purr.mp3"))
        self.purr_player.setSource(QUrl.fromLocalFile(purr_path))
        self.purr_player.setLoops(QMediaPlayer.Loops.Infinite)
        self.audio_output.setVolume(0) # Start muted for fading
        
        # Petting & Fading state
        self.is_petting = False
        self.should_purr = False
        self.current_volume = 0.0
        self.target_volume = 0.0
        
        # Timer to detect when petting stops (200ms of no wheel activity)
        self.petting_stop_timer = QTimer()
        self.petting_stop_timer.setSingleShot(True)
        self.petting_stop_timer.timeout.connect(self.on_petting_stopped)
        
        # Timer for smooth volume transition (every 50ms)
        self.fade_update_timer = QTimer()
        self.fade_update_timer.timeout.connect(self.update_audio_fade)
        self.fade_update_timer.start(50)
 
        # AI tracking
        self.virtual_geo = QApplication.primaryScreen().virtualGeometry()
        self.ai = PetAI(self.virtual_geo.center().x(), self.virtual_geo.center().y())
        
        # Window tracking
        self.collidable_floors = [self.virtual_geo.bottom()]
        self.last_window_update = 0
        
        # Dragging state
        self.dragging = False
        self.drag_pos = QPoint()
        
        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.game_loop)
        self.timer.start(30) # ~33 FPS
 
        # Load saved settings
        self.load_settings()
        
        # Use a single shot timer to apply macOS-specific fixes after the window is fully realized
        if sys.platform == "darwin":
            QTimer.singleShot(500, self.apply_macos_fixes)
        
        self.show()
        self.raise_()
        self.activateWindow()

    def apply_macos_fixes(self):
        """Apply native macOS window behavior fixes."""
        try:
            import objc
            from AppKit import (
                NSApplication, 
                NSApplicationActivationPolicyAccessory,
                NSWindowCollectionBehaviorCanJoinAllSpaces,
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
                
                # Space Collection Behavior
                # STATIONARY: Don't move with other windows
                # IGNORES_CYCLE: Don't show in Cmd+Tab
                behavior = (
                    NSWindowCollectionBehaviorStationary |
                    NSWindowCollectionBehaviorIgnoresCycle
                )
                window.setCollectionBehavior_(behavior)
                
                # Set a high level (NSStatusWindowLevel = 25)
                # This ensures it's above most apps but below system overlays
                window.setLevel_(25) 
                
        except Exception as e:
            print(f"macOS window customization failed: {e}")

    def update_windows(self):
        # Update window list every 500ms
        if time.time() - self.last_window_update > 0.5:
            # Collect floors from all screens that intersect the cat's X range
            floors = []
            screens = QApplication.screens()
            cat_rect = QRect(int(self.ai.x), int(self.ai.y), 128, 128)
            
            for s in screens:
                s_geo = s.availableGeometry()
                # If cat is horizontally within this screen, its bottom is a valid floor
                if self.ai.x + 100 > s_geo.left() and self.ai.x + 28 < s_geo.right():
                    # Use availableGeometry().bottom() + 1 to treat it as a solid surface
                    # Qt's bottom() is height-1, so height is bottom()+1
                    floors.append(s_geo.bottom() + 1)
            
            rects = get_collidable_windows(exclude_hwnd=int(self.winId()))
            # Extract top edges that intersect with the cat's horizontal range
            for r in rects:
                left, top, right, bottom = r
                if left < self.ai.x + 100 and right > self.ai.x + 28:
                    floors.append(top)

            # Always include the absolute bottom as a safety floor
            floors.append(self.virtual_geo.bottom() + 1)
            self.collidable_floors = floors
            self.last_window_update = time.time()

    def game_loop(self):
        self.update_windows()
        
        # Get mouse position
        m_pos = QCursor.pos()
        mouse_tuple = (m_pos.x(), m_pos.y())
        
        # Update AI
        v_rect = [self.virtual_geo.left(), self.virtual_geo.top(), self.virtual_geo.right(), self.virtual_geo.bottom()]
        last_input_ms = self.get_last_input_time_ms()
        self.ai.update(30, v_rect, self.collidable_floors, mouse_pos=mouse_tuple, last_input_time_ms=last_input_ms)
        
        # Sync window position
        if self.dragging:
            # Position is updated by mouseMoveEvent
            pass
        else:
            self.move(int(self.ai.x), int(self.ai.y))
            
        # Animation frame update
        anim_cfg = ANIMATIONS_CONFIG.get(self.ai.current_anim, ANIMATIONS_CONFIG["IDLE"])
        if self.ai.anim_timer > anim_cfg["speed"]:
            # Special case: Petting EMOTE hold at frame 5
            if self.is_petting and self.ai.current_anim == "EMOTE" and self.ai.frame_idx == 5:
                self.ai.anim_timer = 0
            else:
                next_frame = (self.ai.frame_idx + 1)
                
                # If we reached the end of the EMOTE animation and we're not petting anymore,
                # transition to IDLE immediately to prevent looping back to frame 0.
                if self.ai.current_anim == "EMOTE" and next_frame >= anim_cfg["frames"]:
                    if not self.is_petting:
                        self.ai.set_state(State.IDLE)
                    else:
                        # Fallback for continuous petting if it somehow exceeds frames
                        self.ai.frame_idx = 0
                else:
                    self.ai.frame_idx = next_frame % anim_cfg["frames"]
                    
                self.ai.anim_timer = 0
            
        # Update mask for click-through
        _, mask = self.sprite_engine.get_frame(self.ai.current_anim, self.ai.frame_idx, self.ai.direction)
        if mask:
            self.setMask(mask)
            
        self.update() # Trigger paintEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        frame, _ = self.sprite_engine.get_frame(self.ai.current_anim, self.ai.frame_idx, self.ai.direction)
        if frame:
            painter.drawPixmap(0, 0, frame)

    # Input Events
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
            
            # Update direction based on move
            if new_pos.x() > self.ai.x:
                self.ai.direction = "right"
            elif new_pos.x() < self.ai.x:
                self.ai.direction = "left"
                
            self.ai.x = new_pos.x()
            self.ai.y = new_pos.y()
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.ai.vy = 0 # Drop it
            self.ai.wake_up() # Waking up after being moved
            self.ai.set_state(State.FALL)
            event.accept()

    def wheelEvent(self, event):
        # Petting interaction
        if self.ai.state != State.CARRY:
            # Check if we just started petting
            if not self.is_petting:
                self.is_petting = True
                # Delay the reaction by 500ms as requested
                QTimer.singleShot(500, self.start_petting_reaction)
            else:
                # Continuous petting logic (only active if reaction has already started)
                if self.should_purr:
                    # Keep sleeping! Extend the state end time so it doesn't wake up while petting
                    self.ai.state_end_time = time.time() * 1000 + 3000
                elif self.ai.state == State.EMOTE:
                    # Refresh emote duration
                    self.ai.state_end_time = time.time() * 1000 + 1500
            
            # Reset the stop timer
            self.petting_stop_timer.start(300) 
            event.accept()

    def start_petting_reaction(self):
        """Triggered after a 500ms delay from the start of petting."""
        if not self.is_petting:
            return # Stopped petting before the delay finished
            
        if self.ai.state == State.SLEEP:
            self.should_purr = True
            self.target_volume = 0.5 # Max volume
            self.purr_player.play()
        else:
            self.should_purr = False
            self.ai.wake_up() # Refresh/Trigger playful period
            self.ai.set_state(State.EMOTE, duration=1500)

    def on_petting_stopped(self):
        self.is_petting = False
        # If we were purring, start 5s fade out
        if self.should_purr:
            self.target_volume = 0.0
        
    def update_audio_fade(self):
        # 1s fade in = 0.5 volume change in 1000ms. 
        # With 50ms intervals, that's 20 steps. Step = 0.5 / 20 = 0.025
        # 5s fade out = 0.5 volume change in 5000ms.
        # With 50ms intervals, that's 100 steps. Step = 0.5 / 100 = 0.005
        
        if self.current_volume < self.target_volume:
            # Fade in
            self.current_volume = min(self.target_volume, self.current_volume + 0.025)
        elif self.current_volume > self.target_volume:
            # Fade out
            self.current_volume = max(self.target_volume, self.current_volume - 0.005)
            
        self.audio_output.setVolume(self.current_volume)
        
        # Stop player if faded out completely
        if self.current_volume <= 0 and self.target_volume == 0:
            if self.purr_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.purr_player.stop()
                self.should_purr = False

    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        # Dark mode styling for context menu
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
        close_action = QAction("Close", self)
        close_action.triggered.connect(QApplication.instance().quit)
        
        menu.addAction(feed_action)
        menu.addSeparator()

        # Behavior Submenu
        behavior_menu = menu.addMenu("Behavior")
        
        lazy_action = QAction("Lazy (Always Sleepy)", self)
        lazy_action.setCheckable(True)
        lazy_action.setChecked(self.ai.mode == BehaviorMode.LAZY)
        lazy_action.triggered.connect(lambda checked: self.set_behavior_mode(BehaviorMode.LAZY))
        
        standard_action = QAction("Standard (Hunger & Break Reminders)", self)
        standard_action.setCheckable(True)
        standard_action.setChecked(self.ai.mode == BehaviorMode.STANDARD)
        standard_action.triggered.connect(lambda checked: self.set_behavior_mode(BehaviorMode.STANDARD))
        
        behavior_menu.addAction(lazy_action)
        behavior_menu.addAction(standard_action)

        menu.addSeparator()
        menu.addAction(close_action)
        try:
            menu.exec(pos)
        except Exception as e:
            print(f"Context menu error: {e}")

    def set_behavior_mode(self, mode):
        self.ai.mode = mode
        # If switching to lazy, maybe wake up briefly to show it changed
        if mode == BehaviorMode.LAZY:
            self.ai.wake_up(3000)
        self.save_settings()

    def feed_pet(self):
        self.ai.last_fed = time.time()
        self.ai.work_start_time = time.time() * 1000 # Reset work timer too
        self.ai.awake_until = 0 # No longer want to play if just fed
        # Briefly lick/clean before sleep (2 seconds)
        self.ai.set_state(State.CLEAN, duration=2000)
        self.ai.queued_state = State.SLEEP

    def save_settings(self):
        """Saves current kitten settings to a JSON file."""
        settings = {
            "behavior_mode": self.ai.mode.name
        }
        try:
            settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
            # If running as EXE, we might want to save in the user's local app data instead
            # but for now let's use the folder next to the exe/script for portability.
            with open(settings_path, "w") as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def load_settings(self):
        """Loads kitten settings from a JSON file."""
        try:
            settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    mode_name = settings.get("behavior_mode")
                    if mode_name == "MOTIVATOR":
                        self.ai.mode = BehaviorMode.STANDARD
                    elif mode_name in BehaviorMode.__members__:
                        self.ai.mode = BehaviorMode[mode_name]
        except Exception as e:
            print(f"Failed to load settings: {e}")

    def get_last_input_time_ms(self):
        """Returns the timestamp (ms) of the last user input (keyboard or mouse)."""
        if sys.platform == "win32":
            try:
                import win32api
                # GetTickCount() is roughly time.time() * 1000 but relative to system boot.
                # However, GetLastInputInfo is also relative to system boot.
                # To get a 'now' timestamp comparable to GetLastInputInfo, we use GetTickCount.
                last_input_tick = win32api.GetLastInputInfo()
                # We need to map this back to our current time.time() epoch if possible,
                # but the AI just needs to know if it CHANGED. 
                # Actually, AI uses time.time() for resets.
                # Let's use a trick: 
                import ctypes
                millis = ctypes.windll.kernel32.GetTickCount()
                idle_ms = millis - last_input_tick
                return (time.time() * 1000) - idle_ms
            except Exception:
                return time.time() * 1000
        elif sys.platform == "darwin":
            try:
                from Quartz import CGEventSourceSecondsSinceLastEventType, kCGEventSourceStateCombinedSessionState, kCGAnyInputEventType
                idle_secs = CGEventSourceSecondsSinceLastEventType(kCGEventSourceStateCombinedSessionState, kCGAnyInputEventType)
                return (time.time() - idle_secs) * 1000
            except Exception:
                return time.time() * 1000
        return time.time() * 1000

def log_exception(cls, exception, traceback):
    import traceback as tb
    error_msg = "".join(tb.format_exception(cls, exception, traceback))
    with open("crash_report.txt", "a") as f:
        f.write(f"\n--- Crash at {time.ctime()} ---\n")
        f.write(error_msg)
    print(error_msg)
    sys.__excepthook__(cls, exception, traceback)

sys.excepthook = log_exception

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Hide Dock icon on macOS
    if sys.platform == "darwin":
        try:
            from AppKit import NSBundle
            # This is a cleaner way to do it before the app fully starts
            # Another way is using NSApplication.sharedApplication().setActivationPolicy_(2)
            # but setting LSUIElement in Info.plist is preferred for bundled apps.
            # For development/script running, we can use this:
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            nsapp = NSApplication.sharedApplication()
            nsapp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except ImportError:
            pass

    pet = DesktopPet()
    sys.exit(app.exec())
