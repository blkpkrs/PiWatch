# PiWatch — Help & Troubleshooting Guide

## Overview

PiWatch is a stopwatch built on the **Raspberry Pi Pico 2 (RP2350)** with an **SSD1306 OLED display** and a **passive buzzer**. It features:

- Start/Stop toggle via GP16 button
- Reset via BOOTSEL hold (1 second)
- Glitch Easter egg: triple-tap GP16 within 0.5 seconds
- Context-aware buzzer feedback on button presses

---

## Hardware Setup

### Components Required

| Component | Quantity | Notes |
|-----------|----------|-------|
| Raspberry Pi Pico 2 / Pico 2 W | 1 | RP2350 MCU |
| SSD1306 OLED Display (128×64) | 1 | I2C interface, address 0x3C or 0x3D |
| Passive Buzzer | 1 | Requires PWM/toggling signal (NOT active buzzer) |
| 2N222A NPN Transistor | 1 | Switches buzzer current (TO-92 package) |
| 1kΩ Resistor | 1 | Base current limiting for transistor (brown-black-red) |
| LED (any color) | 1 | Optional flyback diode substitute |

### Pinout Reference

#### OLED Display (I2C)
| OLED Pin | Pico Physical Pin | Pico GPIO | Function |
|----------|-------------------|-----------|----------|
| VCC      | 36                | 3V3_OUT   | 3.3V power |
| GND      | 38                | GND       | Ground |
| SDA      | 6                 | GP4       | I2C data (I2C0) |
| SCL      | 7                 | GP5       | I2C clock (I2C0) |

#### Start/Stop Button
| Button Leg | Pico Physical Pin | Pico GPIO | Notes |
|------------|-------------------|-----------|-------|
| One leg    | 21                | GP16      | Active-low, internal pull-up enabled |
| Other leg  | Any GND           | GND       | Connect to any ground pin (e.g., Pin 38) |

#### Passive Buzzer
| Component     | Pico Physical Pin | Pico GPIO | Notes |
|---------------|-------------------|-----------|-------|
| Buzzer (+)    | 36                | 3V3_OUT   | Connected to positive supply |
| Buzzer (-)    | —                 | —         | Connects to transistor collector |
| Transistor Collector (middle pin) | Buzzer (-) | — | Switches buzzer to ground |
| Transistor Emitter (right pin) | GND | Pin 38 | Ground connection |
| Transistor Base (left pin) | ← 1kΩ resistor → GP15 | Pin 20 | Control signal |
| LED (optional flyback) | Cathode → Buzzer(+)/3V3, Anode → Collector | — | Protects transistor from back-EMF |

### Transistor Pin Identification (2N222A)
Hold the transistor with the **flat side facing you**, legs pointing down:

```
    Flat side facing you
   ┌──────────────┐
   │  2N222A      │
   │              │
   └──┬───┬───┬───┘
      │   │   │
     Base Collector Emitter
```

- **Base (left):** Connects to 1kΩ resistor → GP15
- **Collector (middle):** Connects to buzzer (-) and LED anode
- **Emitter (right):** Connects directly to GND

### Wiring Diagram

```
3V3_OUT (Pin 36) ───────────────► Buzzer (+)
                                   │
                                 Diode (cathode/short leg)
                                   │
Buzzer (-) ───────────────────────► Transistor Collector (middle)
                                     │
                                   LED Anode (long leg)
                                     │
                                   Transistor Emitter ──► GND (Pin 38)

GP15 (Pin 20) ──► 1kΩ Resistor ──► Transistor Base (left)
```

### Breadboard Layout Tips
- Ensure the transistor straddles the center groove correctly (pins on opposite sides won't connect)
- Verify each jumper wire is fully seated in both the breadboard and Pico header
- Check for accidental shorts between adjacent rows near the transistor

---

## Code Implementation

### File Structure
```
main.py          — Main application code
ssd1306.py       — SSD1306 OLED driver (from micropython-ssd1306)
```

### Key Configuration Constants

| Constant | Default | Description |
|----------|---------|-------------|
| `I2C_ID` | 0 | I2C bus number (I2C0) |
| `SDA_PIN` | 4 | GPIO for I2C data line |
| `SCL_PIN` | 5 | GPIO for I2C clock line |
| `I2C_FREQ` | 400,000 | I2C clock speed (fast mode) |
| `BOOTSEL_HOLD_MS` | 1000 | Hold time for reset (1 second) |
| `TARGET_FPS` | 20 | Display refresh rate |
| `RESET_FLASH_MS` | 250 | Duration of reset confirmation flash |
| `TRIPLE_TAP_WINDOW_MS` | 500 | Window to detect triple-tap for glitch (0.5 seconds) |
| `GLITCH_RUN_MS` | 1500 | Duration of glitch animation (1.5 seconds) |
| `BUZZER_PIN` | 15 | GPIO for buzzer control (Pin 20) |
| `BUZZER_ENABLED` | True | Enable/disable buzzer output |

### Buzzer Implementation

The buzzer uses **simple GPIO toggling** (not PWM) to produce click sounds:

```python
buzzer_pin = Pin(BUZZER_PIN, Pin.OUT, value=0)

def buzz(on_ms, off_ms, cycles):
    """Click buzzer on/off for specified repetitions."""
    if not BUZZER_ENABLED:
        return
    for _ in range(cycles):
        buzzer_pin.value(1)   # Turn on (transistor conducts, buzzer sounds)
        time.sleep_ms(on_ms)
        buzzer_pin.value(0)   # Turn off (transistor stops, buzzer silent)
        if off_ms > 0:
            time.sleep_ms(off_ms)
```

#### Beep Patterns

| Action | Pattern | Timing | Description |
|--------|---------|--------|-------------|
| **START** | `click-click` | 100ms on, 50ms off × 2 | Medium double-click |
| **STOP** | `click` | 60ms on × 1 | Short single click |
| **RESET** | `click...click` | 50ms on, 80ms pause × 2 | Distinct double-click with gap |

### Glitch Easter Egg

Triggered by **triple-tapping the GP16 button within 0.5 seconds**:

```python
tap_times.append(now_ms)
# Remove taps older than the window
while tap_times and time.ticks_diff(now_ms, tap_times[0]) > TRIPLE_TAP_WINDOW_MS:
    tap_times.pop(0)
if len(tap_times) >= 3:
    # Trigger glitch animation
```

The glitch animation runs for 1.5 seconds, corrupting the display with row tears and static blocks, then restores cleanly. **All button processing is frozen during glitch** to prevent unintended state changes.

### State Machine Flow

```
┌─────────────┐     tap      ┌─────────────┐
│   STOPPED   │ ◄──────────► │   RUNNING   │
│  (elapsed=0)│              │ (counting)  │
└──────┬──────┘              └─────────────┘
       │ BOOTSEL hold 1s
       ▼
  (reset to 0)

┌──────────────────┐
│ Triple-tap GP16  │ ──► Glitch animation (1.5s)
│ within 0.5s      │     Buttons frozen during glitch
└──────────────────┘
```

---

## Troubleshooting

### OLED Display Not Working

#### Symptom: `I2C scan: []` or `OSError: [Errno 5] EIO`

**Checklist:**
1. **Power:** Is VCC connected to Pin 36 (3V3_OUT)? Does the OLED flash when first powered?
2. **Ground:** Is GND connected to Pin 38 (or any GND pin)?
3. **SDA/SCL pins:** Are they on Pico Pins 6 (GP4) and 7 (GP5)?
   - SDA → Pin 6, SCL → Pin 7
4. **Wiring:** Reseat all jumper wires. Try different breadboard rows.
5. **I2C address:** Some OLEDs use 0x3D instead of 0x3C.
6. **Frequency:** Try lowering I2C_FREQ to 100,000 if wiring is long.

**Diagnostic command (run in Thonny REPL):**
```python
from machine import Pin, I2C
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
print([hex(a) for a in i2c.scan()])
```

### Buzzer Not Working

#### Symptom: No sound when pressing buttons

**Step 1 — Verify buzzer works:**
Disconnect the transistor. Connect directly:
```
3V3_OUT (Pin 36) ──► Buzzer (+)
Buzzer (-) ──► 1kΩ resistor ──► GP15 (Pin 20)
```
Run the code. If it clicks, the buzzer is fine and the issue is in the transistor circuit.

**Step 2 — Check transistor wiring:**
- **Flat side facing you, legs down:** Base (left), Collector (middle), Emitter (right)
- **Base** → 1kΩ resistor → GP15 (Pin 20)
- **Collector** → Buzzer (-) + LED anode
- **Emitter** → GND (Pin 38)

**Step 3 — Verify transistor is not dead:**
Try a different 2N222A if available. Transistors can fail with a shorted collector-emitter junction (stuck ON).

**Step 4 — Check base resistor:**
- Verify it's actually 1kΩ (brown-black-red color bands)
- Ensure the resistor is firmly connected to GP15 on one end and transistor base on the other
- Check for breadboard shorts between adjacent rows

**Step 5 — Measure voltage at base:**
- With multimeter on DC voltage mode, probe the transistor base pin
- When code runs and buzzer should sound, voltage should spike to ~0.6–1.2V
- If it reads 0V constantly, the resistor or GP15 connection is bad

**Step 6 — Check for stuck transistor:**
- Unplug USB. If buzzer clicks when unplugged, the transistor is likely shorted (C-E junction failed)
- Replace with a known-good transistor

#### Symptom: Buzzer stuck ON (always sounding)

This means the transistor is always conducting. Causes:
1. **Transistor is dead** (C-E shorted) — replace it
2. **Base resistor connected to 3V3 instead of GP15** — verify wiring
3. **Breadboard short** between base and collector or base and 3V3

#### Symptom: Buzzer clicks when tapped to ground but not from code
- The buzzer itself works, but the transistor isn't switching properly
- Check base resistor connection to GP15
- Try a different transistor

### Button Not Responding

**Checklist:**
1. Is the button wired to GP16 (Pin 21) and GND?
2. Is the button fully seated in the breadboard?
3. Try a different button or jumper wire — buttons can fail internally

### Glitch Not Triggering

1. **Triple-tap speed:** You must tap GP16 three times within 0.5 seconds
2. **Timing:** Wait for the display to settle before attempting triple-tap
3. **Console output:** Check Thonny REPL for `"GLITCH (triple-tap)"` message

### General Tips

- **Reseat all wires** — breadboard connections can become loose over time
- **Try different jumper wires** — they can fail internally even if they look fine
- **Check breadboard rows** — rows can have internal breaks; try moving wires to different rows
- **Power cycle the Pico** — unplug USB, wait 5 seconds, replug
- **Verify MicroPython firmware** — if issues persist, reflash the Pico with latest firmware

---

## Pin Reference Card

### RP2350 (Pico 2) Quick Reference

| Physical Pin | GPIO | Function(s) |
|:------------:|------|-------------|
| 1 | GP0 | I2C0 SDA, UART0 TX |
| 2 | GP1 | I2C0 SCL, UART0 RX |
| 3 | GND | Ground |
| 4 | GP2 | I2C1 SDA |
| 5 | GP3 | I2C1 SCL |
| 6 | GP4 | **I2C0 SDA (OLED)** |
| 7 | GP5 | **I2C0 SCL (OLED)** |
| 8 | GND | Ground |
| 9 | GP6 | I2C1 SDA |
| 10 | GP7 | I2C1 SCL |
| ... | ... | ... |
| 20 | GP15 | **Buzzer control** |
| 21 | GP16 | **Start/Stop button** |
| ... | ... | ... |
| 36 | 3V3_OUT | Regulated 3.3V output (~300mA) |
| 38 | GND | Ground |
| 40 | VBUS | 5V from USB |

### I2C Pin Pairs (RP2350)

| Bus | Valid SDA / SCL Combinations |
|-----|------------------------------|
| I2C0 | GP0/GP1, **GP4/GP5**, GP8/GP9, GP12/GP13, GP16/GP17, GP20/GP21 |
| I2C1 | GP2/GP3, GP6/GP7, GP10/GP11, GP14/GP15, GP18/GP19, GP26/GP27 |

---

## Git Branches

| Branch | Purpose |
|--------|---------|
| `main` | Stable, working code |
| `feature/glitch-easter-egg` | Triple-tap glitch animation |
| `feature/buzzer` | Buzzer feedback integration |

---

## Credits & References

- **OLED Driver:** [micropython-ssd1306](https://github.com/mcauser/micropython-ssd1306)
- **RP2350 Pinout:** See `pico2_pinout.md` in project directory
- **MicroPython Docs:** https://docs.micropython.org/
