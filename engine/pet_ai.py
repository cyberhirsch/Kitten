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
        
    def is_hungry(self):
        return time.time() - self.last_fed > self.hunger_threshold

    def update(self, delta_ms, virtual_rect, floors):
        """
        Updates physics and AI state.
        virtual_rect: [left, top, right, bottom] of the entire virtual desktop
        floors: list of Y coordinates representing surfaces (window tops + screen bottoms)
        """
        self.anim_timer += delta_ms
        v_left, v_top, v_right, v_bottom = virtual_rect
        
        # Hunger check
        hungry = self.is_hungry()
        speed_mult = 1.5 if hungry else 1.0
        
        # Find current floor (closest below cat)
        current_floor = 100000 
        for f in floors:
            if f >= self.y + 120: # 120 is nearly the bottom of the 128px sprite
                if f < current_floor:
                    current_floor = f
        
        # Gravity
        if self.state != State.CARRY:
            if self.y + 128 < current_floor:
                self.vy += self.gravity
                if self.state != State.JUMP:
                    self.set_state(State.FALL)
            else:
                # Landed
                if self.state == State.FALL or self.state == State.JUMP:
                    self.set_state(State.LANDING, duration=300)
                elif self.state == State.LANDING:
                    if time.time() * 1000 > self.state_end_time:
                        self.set_state(State.IDLE)
                
                self.y = current_floor - 128
                self.vy = 0
        
        # Horizontal Movement
        if self.state == State.WALK:
            self.x += (self.walk_speed * speed_mult) if self.direction == "right" else -(self.walk_speed * speed_mult)
        elif self.state == State.RUN:
            self.x += (self.run_speed * speed_mult) if self.direction == "right" else -(self.run_speed * speed_mult)

        self.y += self.vy

        # --- Clamping and Collisions (AFTER movement) ---
        
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
        
        # Hard clamp Y to virtual desktop bottom (ultimate fallback)
        if self.y > v_bottom - 128:
            self.y = v_bottom - 128
            self.vy = 0
            if self.state == State.FALL or self.state == State.JUMP:
                self.set_state(State.LANDING, duration=300)
        
        # Stop at top of virtual desktop
        if self.y < v_top:
            self.y = v_top
            self.vy = 0

        # AI Behavior transitions
        if time.time() * 1000 > self.state_end_time:
            self.choose_next_state(hungry)

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

    def choose_next_state(self, hungry):
        weights = {
            State.IDLE: 25,
            State.LOOK_SIDE: 15,
            State.WALK: 30,
            State.LICK: 10,
            State.CLEAN: 10,
            State.SLEEP: 10
        }
        
        if hungry:
            weights[State.RUN] = 30
            weights[State.WALK] = 50
            weights[State.SLEEP] = 0
            weights[State.IDLE] = 10
            
        states = list(weights.keys())
        probs = list(weights.values())
        next_s = random.choices(states, weights=probs)[0]
        
        # Determine duration
        duration = random.randint(2000, 5000)
        if next_s == State.SLEEP:
            # Nap can last up to 10 minutes (600,000 ms), minimum 30 seconds
            duration = random.randint(30000, 600000)
        elif next_s in [State.WALK, State.RUN]:
            self.direction = random.choice(["left", "right"])
            
        self.set_state(next_s, duration=duration)
