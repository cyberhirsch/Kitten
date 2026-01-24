import sys
import os
import time
from PyQt6.QtWidgets import QApplication, QMainWindow, QMenu
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect
from PyQt6.QtGui import QPainter, QAction
from PyQt6.QtMultimedia import QSoundEffect, QAudioOutput, QMediaPlayer
from PyQt6.QtCore import QUrl

from engine.sprite_engine import SpriteEngine
from engine.pet_ai import PetAI, State
from engine.window_helper import get_collidable_windows

ANIMATIONS_CONFIG = {
    "IDLE":       {"row": 0, "frames": 4,  "speed": 200},
    "LOOK_SIDE":  {"row": 1, "frames": 4,  "speed": 200},
    "LICK":       {"row": 2, "frames": 4,  "speed": 150},
    "CLEAN":      {"row": 3, "frames": 4,  "speed": 150},
    "WALK":       {"row": 4, "frames": 8,  "speed": 100}, 
    "RUN":        {"row": 5, "frames": 8,  "speed": 80},  
    "SLEEP":      {"row": 6, "frames": 4,  "speed": 400},
    "PLAY":       {"row": 7, "frames": 6,  "speed": 120},
    "JUMP":       {"row": 8, "frames": 2,  "speed": 150},
    "LANDING":    {"row": 8, "frames": 3,  "col_start": 4, "speed": 100},
    "EMOTE":      {"row": 9, "frames": 8,  "speed": 150},
    "CARRY_HELD": {"row": 8, "frames": 1,  "col_start": 2, "speed": 1000}, 
    "CARRY_FALL": {"row": 8, "frames": 1,  "col_start": 3, "speed": 1000}, 
}

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

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

        self.show()

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
                    floors.append(s_geo.bottom())

            rects = get_collidable_windows(exclude_hwnd=int(self.winId()))
            
            # Extract top edges that intersect with the cat's horizontal range
            for r in rects:
                left, top, right, bottom = r
                if left < self.ai.x + 100 and right > self.ai.x + 28:
                    floors.append(top)
            
            self.collidable_floors = floors if floors else [self.virtual_geo.bottom()]
            self.last_window_update = time.time()

    def game_loop(self):
        self.update_windows()
        
        # Update AI
        v_rect = [self.virtual_geo.left(), self.virtual_geo.top(), self.virtual_geo.right(), self.virtual_geo.bottom()]
        self.ai.update(30, v_rect, self.collidable_floors)
        
        # Sync window position
        if self.dragging:
            # Position is updated by mouseMoveEvent
            pass
        else:
            self.move(int(self.ai.x), int(self.ai.y))
            
        # Animation frame update
        anim_cfg = ANIMATIONS_CONFIG.get(self.ai.current_anim, ANIMATIONS_CONFIG["IDLE"])
        if self.ai.anim_timer > anim_cfg["speed"]:
            self.ai.frame_idx = (self.ai.frame_idx + 1) % anim_cfg["frames"]
            self.ai.anim_timer = 0
            
        self.update() # Trigger paintEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        frame = self.sprite_engine.get_frame(self.ai.current_anim, self.ai.frame_idx, self.ai.direction)
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
            self.ai.set_state(State.FALL)
            event.accept()

    def wheelEvent(self, event):
        # Petting interaction
        if self.ai.state != State.CARRY:
            # Check if we just started petting
            if not self.is_petting:
                self.is_petting = True
                if self.ai.state == State.SLEEP:
                    self.should_purr = True
                    self.target_volume = 0.5 # Max volume
                    self.purr_player.play()
                else:
                    self.should_purr = False
                    self.ai.set_state(State.EMOTE, duration=1500)
            else:
                # Continuous petting
                if self.should_purr:
                    # Keep sleeping! Extend the state end time so it doesn't wake up while petting
                    self.ai.state_end_time = time.time() * 1000 + 3000
                else:
                    # Refresh emote
                    self.ai.set_state(State.EMOTE, duration=1500)
            
            # Reset the stop timer
            self.petting_stop_timer.start(300) 
            event.accept()

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
        feed_action = QAction("Feed", self)
        feed_action.triggered.connect(self.feed_pet)
        close_action = QAction("Close", self)
        close_action.triggered.connect(QApplication.instance().quit)
        
        menu.addAction(feed_action)
        menu.addSeparator()
        menu.addAction(close_action)
        menu.exec(pos)

    def feed_pet(self):
        self.ai.last_fed = time.time()
        # Food coma nap: 5 minutes
        self.ai.set_state(State.SLEEP, duration=300000)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = DesktopPet()
    sys.exit(app.exec())
