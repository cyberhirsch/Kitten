import random
import time
from enum import Enum, auto

class State(Enum):
    IDLE = auto()
    LOOK_SIDE = auto()
    WALK = auto()
    RUN = auto()
    SLEEP = auto()
    JUMP = auto()
    FALL = auto()
    LANDING = auto()
    LICK = auto()
    CLEAN = auto()
    PLAY = auto()
    EMOTE = auto()
    CARRY = auto()

class BehaviorMode(Enum):
    LAZY = auto()      # Always sleepy, never hungry
    STANDARD = auto()  # Gets hungry and reminds user to take breaks (Work Timer)

class PetAI:
    def __init__(self, start_x, start_y):
        self.x = start_x
        self.y = start_y
        self.vx = 0
        self.vy = 0
        self.state = State.IDLE
        self.direction = "right"
        self.last_fed = time.time()
        self.hunger_threshold = 7200 # 2 hours
        
        # Animation state
        self.current_anim = "IDLE"
        self.frame_idx = 0
        self.anim_timer = 0
        
        # Target for movement
        self.target_x = start_x
        self.state_end_time = 0
        
        # Physics constants
        self.gravity = 0.5
        self.walk_speed = 2
        self.run_speed = 4
        self.last_reaction_time = 0
        
        # Motivator system
        self.work_start_time = 0
        self.last_activity_time = 0
        self.is_working = False
        
        # State & Behavior system
        self.awake_until = 0
        self.queued_state = None
        self.mode = BehaviorMode.LAZY
        
    def is_hungry(self):
        if self.mode == BehaviorMode.LAZY:
            return False
        return time.time() - self.last_fed > self.hunger_threshold

    def update(self, delta_ms, virtual_rect, floors, mouse_pos=None, last_input_time_ms=None):
        """
        Updates physics and AI state.
        virtual_rect: [left, top, right, bottom] of the entire virtual desktop
        floors: list of Y coordinates representing surfaces (window tops + screen bottoms)
        mouse_pos: (x, y) tuple of the global mouse position
        last_input_time_ms: timestamp of last system input (mouse/kb)
        """
        self.anim_timer += delta_ms
        v_left, v_top, v_right, v_bottom = virtual_rect
        
        now_ms = time.time() * 1000

        # Motivator Logic Update (Standard mode only)
        if self.mode == BehaviorMode.STANDARD and last_input_time_ms:
            # Check if user is active
            if last_input_time_ms > self.last_activity_time:
                self.last_activity_time = last_input_time_ms
                if not self.is_working:
                    self.is_working = True
                    self.work_start_time = now_ms
            
            # Reset logic: If idle for 5 minutes (300,000ms), stop working
            if now_ms - self.last_activity_time > 300000:
                self.is_working = False
                self.work_start_time = 0

        # Hunger check
        hungry = self.is_hungry()
        speed_mult = 1.5 if hungry else 1.0
        
        # Find current floor (closest below cat)
        current_floor = 100000 
        for f in floors:
            # We check if floor is below the cat's belly (y + 100)
            if f >= self.y + 100: 
                if f < current_floor:
                    current_floor = f
        
        # Gravity
        on_ground = False
        if self.state != State.CARRY:
            # 128 is the bottom of the sprite
            if self.y + 128 < current_floor - 2: # Add small epsilon to avoid jitter
                self.vy += self.gravity
                if self.state != State.JUMP and self.state != State.FALL:
                    self.set_state(State.FALL)
            else:
                # Landed
                on_ground = True
                if self.state == State.FALL or self.state == State.JUMP:
                    self.vx = 0 # Stop jump momentum
                    self.set_state(State.LANDING, duration=300)
                elif self.state == State.LANDING:
                    if time.time() * 1000 > self.state_end_time:
                        self.set_state(State.IDLE)
                
                # Snap to floor
                self.y = current_floor - 128
                self.vy = 0

        # Jump/Play Trigger
        now = time.time() * 1000
        if on_ground and self.state not in [State.SLEEP, State.CARRY, State.JUMP, State.LANDING, State.EMOTE, State.PLAY]:
            if mouse_pos:
                mx, my = mouse_pos
                dx = mx - (self.x + 64)
                dy = my - (self.y + 64)
                dist = (dx**2 + dy**2)**0.5
                
                # Check if mouse is in front and near ground level (dy 20-80)
                in_front = (self.direction == "right" and dx > 0) or (self.direction == "left" and dx < 0)
                near_ground = 20 < dy < 80
                
                if in_front and near_ground:
                    if dist < 40:
                        # Almost touching ground near cat - Play! (No cooldown)
                        self.set_state(State.PLAY, duration=720) # 6 frames * 120ms
                    elif dist < 80:
                        # A bit further out - Jump! (With 10s cooldown)
                        if now - self.last_reaction_time > 10000:
                            self.last_reaction_time = now
                            self.vx = 2.3 if self.direction == "right" else -2.3
                            self.vy = -4.6
                            self.set_state(State.JUMP, duration=1050) # 7 frames * 150ms
        
        # Horizontal Movement
        if self.state == State.WALK:
            self.x += (self.walk_speed * speed_mult) if self.direction == "right" else -(self.walk_speed * speed_mult)
        elif self.state == State.RUN:
            self.x += (self.run_speed * speed_mult) if self.direction == "right" else -(self.run_speed * speed_mult)
        else:
            self.x += self.vx

        self.y += self.vy

        # --- Clamping and Collisions ---
        
        # Virtual Desktop Boundary Clamping (Horizontal)
        if self.x < v_left:
            self.x = v_left
            if self.state in [State.WALK, State.RUN]:
                self.set_state(State.IDLE, duration=2000)
                self.direction = "right"
        elif self.x > v_right - 128:
            self.x = v_right - 128
            if self.state in [State.WALK, State.RUN]:
                self.set_state(State.IDLE, duration=2000)
                self.direction = "left"
        
        # Absolute bottom clamp (safety fallback)
        # Use a 5px buffer to avoid fighting with the floor logic
        if self.y > v_bottom + 5 - 128:
            self.y = v_bottom + 5 - 128
            self.vy = 0
        
        # Stop at top of virtual desktop
        if self.y < v_top:
            self.y = v_top
            self.vy = 0

        # AI Behavior transitions
        if time.time() * 1000 > self.state_end_time:
            self.choose_next_state()

    def wake_up(self, duration_ms=60000):
        """Wakes the cat up and makes it playful for a duration."""
        self.awake_until = time.time() * 1000 + duration_ms
        if self.state == State.SLEEP:
            self.set_state(State.IDLE, duration=1000)

    def set_state(self, new_state, duration=random.randint(2000, 5000)):
        self.state = new_state
        self.state_end_time = time.time() * 1000 + duration
        self.frame_idx = 0
        
        # Map state to animation name
        if self.state == State.FALL:
            self.current_anim = "CARRY_FALL"
        elif self.state == State.CARRY:
            self.current_anim = "CARRY_HELD"
        else:
            self.current_anim = self.state.name

    def choose_next_state(self):
        if self.queued_state:
            next_s = self.queued_state
            self.queued_state = None
            duration = random.randint(30000, 600000) if next_s == State.SLEEP else random.randint(2000, 5000)
            self.set_state(next_s, duration=duration)
            return

        now = time.time() * 1000
        is_awake = now < self.awake_until

        if self.mode == BehaviorMode.LAZY:
            if is_awake:
                # Playful/Active weights
                weights = {
                    State.IDLE: 15,
                    State.LOOK_SIDE: 15,
                    State.WALK: 30,
                    State.RUN: 10,
                    State.LICK: 10,
                    State.CLEAN: 10,
                    State.PLAY: 10
                }
            else:
                # Lazy/Sleepy weights
                weights = {
                    State.IDLE: 20,
                    State.LOOK_SIDE: 5,
                    State.WALK: 5,
                    State.SLEEP: 60,
                    State.LICK: 5,
                    State.CLEAN: 5
                }
        elif self.mode == BehaviorMode.STANDARD:
            hungry = self.is_hungry()
            now = time.time() * 1000
            work_duration = now - self.work_start_time if (self.is_working and self.work_start_time > 0) else 0
            
            # Motivator Phases (Combined with hunger)
            # Phase 2: Running (50m+) or very hungry
            if work_duration > 3000000 or (hungry and random.random() < 0.3): 
                next_s = State.RUN
                duration = random.randint(5000, 10000)
            # Phase 1: Walking (45m+) or generally hungry
            elif work_duration > 2700000 or hungry:
                next_s = State.WALK
                duration = random.randint(3000, 7000)
            else:
                # Normal behavior while working or just hanging out
                weights = {
                    State.IDLE: 25,
                    State.LOOK_SIDE: 15,
                    State.WALK: 30,
                    State.LICK: 10,
                    State.CLEAN: 10,
                    State.SLEEP: 10 # Rare naps in standard mode
                }
                states = list(weights.keys())
                probs = list(weights.values())
                next_s = random.choices(states, weights=probs)[0]
                duration = random.randint(2000, 5000)
                if next_s == State.SLEEP:
                    duration = random.randint(30000, 120000)
        else:
            # Fallback
            weights = {State.IDLE: 100}
            
        states = list(weights.keys())
        probs = list(weights.values())
        next_s = random.choices(states, weights=probs)[0]
        
        # Determine duration
        duration = random.randint(2000, 5000)
        if next_s == State.SLEEP:
            # Nap can last up to 10 minutes (600,000 ms), minimum 1 minute
            duration = random.randint(60000, 600000)
        elif next_s in [State.WALK, State.RUN]:
            self.direction = random.choice(["left", "right"])
            
        self.set_state(next_s, duration=duration)
