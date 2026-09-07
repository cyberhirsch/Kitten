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
    def __init__(self, start_x, start_y, pet=None):
        # `pet` is an engine.pets.PetDefinition. It supplies the sprite footprint,
        # the movement speeds and which states this species is actually able to
        # perform (the snake sheet, for example, has no lick or jump frames).
        self.pet = pet
        self.frame_size = pet.frame_size if pet else 128
        self.allowed_states = set(pet.allowed_states) if pet else set(State)

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
        self.gravity = pet.gravity if pet else 0.5
        self.walk_speed = pet.walk_speed if pet else 2
        self.run_speed = pet.run_speed if pet else 4
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
            # We check if the floor is below the pet's belly
            if f >= self.y + self.frame_size - 28:
                if f < current_floor:
                    current_floor = f
        
        # Gravity
        on_ground = False
        if self.state != State.CARRY:
            # Bottom edge of the sprite
            if self.y + self.frame_size < current_floor - 2: # Add small epsilon to avoid jitter
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
                self.y = current_floor - self.frame_size
                self.vy = 0

        # Jump/Play Trigger
        now = time.time() * 1000
        if on_ground and self.state not in [State.SLEEP, State.CARRY, State.JUMP, State.LANDING, State.EMOTE, State.PLAY]:
            if mouse_pos:
                mx, my = mouse_pos
                half = self.frame_size // 2
                dx = mx - (self.x + half)
                dy = my - (self.y + half)
                dist = (dx**2 + dy**2)**0.5
                
                # Check if mouse is in front and near ground level (dy 20-80)
                in_front = (self.direction == "right" and dx > 0) or (self.direction == "left" and dx < 0)
                near_ground = 20 < dy < 80
                
                if in_front and near_ground:
                    if dist < 40 and State.PLAY in self.allowed_states:
                        # Almost touching ground near the pet - Play! (No cooldown)
                        self.set_state(State.PLAY, duration=720) # 6 frames * 120ms
                    elif dist < 80 and State.JUMP in self.allowed_states:
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
        elif self.x > v_right - self.frame_size:
            self.x = v_right - self.frame_size
            if self.state in [State.WALK, State.RUN]:
                self.set_state(State.IDLE, duration=2000)
                self.direction = "left"
        
        # Absolute bottom clamp (safety fallback)
        # Use a 5px buffer to avoid fighting with the floor logic
        if self.y > v_bottom + 5 - self.frame_size:
            self.y = v_bottom + 5 - self.frame_size
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


    def set_state(self, new_state, duration=None):
        # NOTE: duration must default to None, not random.randint(...). A call-time
        # default is evaluated once at import, which would freeze every "random"
        # state duration to a single value for the whole process lifetime.
        if duration is None:
            duration = random.randint(2000, 5000)

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

    def _idle_weights(self, is_awake):
        """Weighted state table for the current mode. Never returns an empty dict."""
        if self.mode == BehaviorMode.STANDARD:
            weights = {
                State.IDLE: 25,
                State.LOOK_SIDE: 15,
                State.WALK: 30,
                State.LICK: 10,
                State.CLEAN: 10,
                State.SLEEP: 10,  # Rare naps in standard mode
            }
        elif is_awake:
            # Lazy, but recently petted/moved -> playful
            weights = {
                State.IDLE: 15,
                State.LOOK_SIDE: 15,
                State.WALK: 30,
                State.RUN: 10,
                State.LICK: 10,
                State.CLEAN: 10,
                State.PLAY: 10,
            }
        else:
            # Lazy default
            weights = {
                State.IDLE: 20,
                State.LOOK_SIDE: 5,
                State.WALK: 5,
                State.SLEEP: 60,
                State.LICK: 5,
                State.CLEAN: 5,
            }

        weights = {s: w for s, w in weights.items() if s in self.allowed_states}
        return weights or {State.IDLE: 1}

    def _sleep_duration(self):
        if self.mode == BehaviorMode.STANDARD:
            # Short power naps while the work timer matters
            return random.randint(30000, 120000)
        # Lazy naps run from 1 to 10 minutes
        return random.randint(60000, 600000)

    def choose_next_state(self):
        if self.queued_state:
            next_s = self.queued_state
            self.queued_state = None
            duration = self._sleep_duration() if next_s == State.SLEEP else random.randint(2000, 5000)
            self.set_state(next_s, duration=duration)
            return

        now = time.time() * 1000
        is_awake = now < self.awake_until

        next_s = None
        duration = None

        # Motivator nudges take priority over the random weight table.
        if self.mode == BehaviorMode.STANDARD:
            hungry = self.is_hungry()
            work_duration = now - self.work_start_time if (self.is_working and self.work_start_time > 0) else 0

            # Phase 2: 50m+ at the desk, or very hungry -> run around
            if work_duration > 3000000 or (hungry and random.random() < 0.3):
                next_s = State.RUN
                duration = random.randint(5000, 10000)
            # Phase 1: 45m+ at the desk, or generally hungry -> pace about
            elif work_duration > 2700000 or hungry:
                next_s = State.WALK
                duration = random.randint(3000, 7000)

        if next_s is None:
            weights = self._idle_weights(is_awake)
            next_s = random.choices(list(weights.keys()), weights=list(weights.values()))[0]
            duration = self._sleep_duration() if next_s == State.SLEEP else random.randint(2000, 5000)

        if next_s in (State.WALK, State.RUN):
            self.direction = random.choice(["left", "right"])

        self.set_state(next_s, duration=duration)
