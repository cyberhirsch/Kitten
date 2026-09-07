"""
Species definitions.

Each PetDefinition describes everything that differs between pets: the
spritesheet layout, which direction the source art faces, movement speeds,
which behaviours the art can actually depict, and where its settings live.
The window, physics and AI code is shared.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from engine.pet_ai import State


@dataclass(frozen=True)
class Variant:
    """A colour/skin swap: same animation layout, different sheet."""
    id: str
    label: str
    spritesheet: str


@dataclass(frozen=True)
class PetDefinition:
    id: str
    display_name: str
    variants: Tuple[Variant, ...]
    animations: Dict[str, dict]
    settings_filename: str
    sprite_size: int = 32
    scale: int = 4
    purr_sound: Optional[str] = None  # None -> this pet is silent
    disabled_states: frozenset = field(default_factory=frozenset)
    walk_speed: float = 2.0
    run_speed: float = 4.0
    gravity: float = 0.5

    @property
    def frame_size(self) -> int:
        return self.sprite_size * self.scale

    @property
    def allowed_states(self) -> frozenset:
        return frozenset(State) - self.disabled_states

    @property
    def default_variant(self) -> Variant:
        return self.variants[0]

    def variant(self, variant_id) -> Variant:
        for v in self.variants:
            if v.id == variant_id:
                return v
        return self.default_variant


KITTEN = PetDefinition(
    id="kitten",
    display_name="Desktop Kitten",
    settings_filename="settings.json",
    variants=(Variant("default", "Kitten", "assets/spritesheet.png"),),
    purr_sound="assets/purr.mp3",
    animations={
        "IDLE":       {"row": 0, "frames": 4, "speed": 200},
        "LOOK_SIDE":  {"row": 1, "frames": 4, "speed": 200},
        "LICK":       {"row": 2, "frames": 4, "speed": 150},
        "CLEAN":      {"row": 3, "frames": 4, "speed": 150},
        "WALK":       {"row": 4, "frames": 8, "speed": 100},
        "RUN":        {"row": 5, "frames": 8, "speed": 80},
        "SLEEP":      {"row": 6, "frames": 4, "speed": 400},
        "PLAY":       {"row": 7, "frames": 6, "speed": 120},
        "JUMP":       {"row": 8, "frames": 7, "speed": 150},
        "LANDING":    {"row": 8, "frames": 3, "col_start": 4, "speed": 100},
        "EMOTE":      {"row": 9, "frames": 8, "speed": 150},
        "CARRY_HELD": {"row": 8, "frames": 1, "col_start": 2, "speed": 1000},
        "CARRY_FALL": {"row": 8, "frames": 1, "col_start": 3, "speed": 1000},
    },
)


# The PixelSnakes sheets are a single 7-frame slither cycle (224x32) facing
# right, same as the kitten sheet. There are no lick/clean/play/jump/look-side
# poses, so those states are disabled and the remaining ones are built from
# slices of the walk cycle: frames 0-1 read as a resting sway, frames 5-6 as
# slow breathing.
_SNAKE_ANIMATIONS = {
    "IDLE":       {"row": 0, "frames": 2, "speed": 450},
    "WALK":       {"row": 0, "frames": 7, "speed": 110},
    "RUN":        {"row": 0, "frames": 7, "speed": 65},
    "SLEEP":      {"row": 0, "frames": 2, "col_start": 5, "speed": 700},
    "EMOTE":      {"row": 0, "frames": 7, "speed": 55},   # happy wiggle when petted
    "LANDING":    {"row": 0, "frames": 1, "speed": 100},
    "CARRY_HELD": {"row": 0, "frames": 1, "col_start": 3, "speed": 1000},
    "CARRY_FALL": {"row": 0, "frames": 1, "col_start": 2, "speed": 1000},
}

SNAKE = PetDefinition(
    id="snake",
    display_name="Desktop Snake",
    settings_filename="settings-snake.json",
    purr_sound=None,
    walk_speed=1.6,
    run_speed=3.4,
    disabled_states=frozenset({
        State.LOOK_SIDE, State.LICK, State.CLEAN, State.PLAY, State.JUMP,
    }),
    animations=_SNAKE_ANIMATIONS,
    variants=(
        Variant("green",  "Green",  "assets/snakes/SnakeGreen-Walk.png"),
        Variant("red",    "Red",    "assets/snakes/SnakeRed-Walk.png"),
        Variant("blue",   "Blue",   "assets/snakes/SnakeBlue-Walk.png"),
        Variant("brown",  "Brown",  "assets/snakes/SnakeBrown-Walk.png"),
        Variant("corn",   "Corn",   "assets/snakes/SnakeCorn-Walk.png"),
        Variant("albino", "Albino", "assets/snakes/SnakeAlbino-Walk.png"),
    ),
)


PETS = {p.id: p for p in (KITTEN, SNAKE)}
