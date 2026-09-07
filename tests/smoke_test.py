"""
Headless smoke test for every pet definition.

Runs Qt with the offscreen platform plugin, so it works on a CI runner with no
display. Exercises sprite loading, the game loop, interactions and settings
persistence for each species. Run with:

    python tests/smoke_test.py
"""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from app import DesktopPet  # noqa: E402
from engine.pets import PETS  # noqa: E402
from engine.pet_ai import State, BehaviorMode  # noqa: E402

TICKS_PER_MODE = 4000


def check_pet(pet, failures):
    window = DesktopPet(pet)
    print(f"\n=== {pet.display_name} ({pet.id}) ===")
    print(f"  window {window.width()}x{window.height()}  variant={window.variant.id}")

    # Every declared animation loads with the frame count it advertises.
    for name, cfg in pet.animations.items():
        anim = window.sprite_engine.animations.get(name)
        if not anim or len(anim["right"]) != cfg["frames"]:
            failures.append(f"{pet.id}: animation {name} did not load {cfg['frames']} frames")
    print(f"  animations loaded: {len(window.sprite_engine.animations)}/{len(pet.animations)}")

    # Every state the AI may enter has artwork behind it.
    for state in pet.allowed_states:
        anim_name = {State.FALL: "CARRY_FALL", State.CARRY: "CARRY_HELD"}.get(state, state.name)
        if anim_name not in pet.animations:
            failures.append(f"{pet.id}: state {state.name} has no {anim_name} animation")

    # Every colour variant loads.
    for variant in pet.variants:
        window.load_variant(variant)
        if not window.sprite_engine.animations:
            failures.append(f"{pet.id}: variant {variant.id} failed to load")
    print(f"  variants loaded: {len(pet.variants)}")

    # Drive the loop hard in both behaviour modes, hungry and past the work timer,
    # forcing frequent state transitions.
    for mode in (BehaviorMode.LAZY, BehaviorMode.STANDARD):
        window.ai.mode = mode
        window.ai.last_fed = time.time() - 99999
        window.ai.is_working = True
        window.ai.work_start_time = time.time() * 1000 - 3_100_000
        seen = set()
        for i in range(TICKS_PER_MODE):
            if i % 40 == 0:
                window.ai.state_end_time = 0
            window.game_loop()
            seen.add(window.ai.state)
        illegal = sorted(s.name for s in seen if s not in pet.allowed_states)
        print(f"  {mode.name}: reached {len(seen)} states; illegal={illegal or 'none'}")
        if illegal:
            failures.append(f"{pet.id}: {mode.name} entered disabled states {illegal}")

    # Interactions.
    window.ai.set_state(State.SLEEP, duration=99999)
    window.is_petting = True
    window.start_petting_reaction()
    print(f"  pet while asleep -> state={window.ai.state.name} purring={window.should_purr}")
    if pet.purr_sound and not window.should_purr:
        failures.append(f"{pet.id}: petting a sleeping pet with a sound did not purr")
    if not pet.purr_sound and window.ai.state != State.EMOTE:
        failures.append(f"{pet.id}: petting a sleeping silent pet did not wake it into EMOTE")
    window.on_petting_stopped()

    window.feed_pet()
    print(f"  feed -> state={window.ai.state.name} queued={window.ai.queued_state.name}")
    for _ in range(200):
        window.game_loop()

    # Settings round-trip through a fresh window.
    window.save_settings()
    reloaded = DesktopPet(pet)
    print(f"  settings round-trip -> mode={reloaded.ai.mode.name} variant={reloaded.variant.id}")
    if reloaded.variant.id != window.variant.id or reloaded.ai.mode != window.ai.mode:
        failures.append(f"{pet.id}: settings did not round-trip")

    window.close()
    reloaded.close()


def main():
    app = QApplication(sys.argv)  # noqa: F841 - must outlive the widgets below
    failures = []
    for pet in PETS.values():
        check_pet(pet, failures)

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
