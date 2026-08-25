# PiWatch — Stopwatch with OLED Display & Buzzer

A feature-rich stopwatch built on the **Raspberry Pi Pico 2** with a 128×64 OLED display, tactile button input, passive buzzer feedback, and a hidden glitch easter egg.

---

## Features

| Feature | Description |
|---------|-------------|
| **Stopwatch** | Start/stop timing with centisecond precision (MM:SS.CC format) |
| **OLED Display** | 128×64 SSD1306 display with scaled time text and reactive UI tiles |
| **Button Input** | Start/stop toggle via momentary button on GP16 |
| **Reset** | Hold BOOTSEL button for 1 second to reset (only when stopped) |
| **Buzzer Feedback** | Context-aware tones on start, stop, and reset actions |
| **Glitch Easter Egg** | Triple-tap GP16 within 0.5 seconds to trigger a 3-second screen corruption animation with descending noise sound |
| **Timer Pause** | Time automatically pauses after glitch until user restarts |

---

## Hardware Requirements

### Core Components
| Component | Quantity | Notes |
|-----------|----------|-------|
| Raspberry Pi Pico 2 (RP2350) | 1 | Or Pico 2 W (note: wireless pins unavailable) |
| SSD1306 OLED Display (128×64) | 1 | I2C interface, address 0x3C or 0x3D |
| Momentary push button | 1 | For start/stop toggle |
| Passive buzzer | 1 | Piezo type — requires PWM/toggling signal (NOT active buzzer) |

### Optional Components
| Component | Quantity | Notes |
|-----------|----------|-------|
| 2N222A NPN transistor | 1 | Only needed for magnetic buzzer (>30mA). Piezo buzzers can be driven directly from GPIO |
| 1kΩ resistor | 1 | Base current limiting (if using transistor) |
| LED (any color) | 1 | Optional flyback diode substitute when using transistor |

### Power
- **USB power** via Pico's USB port (recommended for development)
- **Battery** (optional): Single-cell LiPo (3.0–4.2V) connected to **VSYS** (Pin 39), NOT 3V3_OUT

---

## Wiring Guide

### OLED Display (I2C)
| OLED Pin | Pico Physical Pin | Pico GPIO | Function |
|----------|-------------------|-----------|----------|
| VCC      | 36                | 3V3_OUT   | 3.3V power |
| GND      | 38                | GND       | Ground |
| SDA      | 6                 | GP4       | I2C data (I2C0) |
| SCL      | 7                 | GP5       | I2C clock (I2C0) |

### Start/Stop Button
| Button Leg | Pico Physical Pin | Pico GPIO | Notes |
|------------|-------------------|-----------|-------|
| One leg    | 21                | GP16      | Active-low, internal pull-up enabled |
| Other leg  | Any GND           | GND       | Connect to any ground pin (e.g., Pin 38) |

### Passive Buzzer
**For piezo buzzers (recommended):** Drive directly from GPIO — no transistor needed.

| Buzzer Pin | Pico Physical Pin | Pico GPIO | Notes |
|------------|-------------------|-----------|-------|
| (+)        | 20                | GP15      | PWM output pin |
| (−)        | 38                | GND       | Ground |

**For magnetic buzzers (>30mA):** Use transistor switch.

```
GP15 (Pin 20) ──► 1kΩ resistor ──► Transistor Base
Transistor Emitter ───────────────► GND (Pin 38)

3V3_OUT (Pin 36) ──► Buzzer (+)
Buzzer (-) ─────────► Transistor Collector

LED (optional flyback):
  Cathode (short leg) ──► Buzzer (+) / 3V3
  Anode (long leg) ─────► Transistor Collector
```

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

---

## Software Setup

### 1. Flash MicroPython Firmware
Download the latest RP2350 MicroPython firmware from [micropython.org](https://micropython.org/download/).

1. Hold the **BOOTSEL** button on the Pico
2. Connect USB to your computer
3. A drive named `RPI-RP2` will appear
4. Drag the `.uf2` firmware file onto it
5. The Pico will reboot with MicroPython

### 2. Upload Project Files
Using **Thonny IDE** (recommended):

1. Open Thonny → Preferences → Interpreter → Select "MicroPython (Raspberry Pi Pico)"
2. Connect to the Pico
3. Click **STOP** (to release the REPL)
4. Open **View → Files**
5. Upload these files to `/` (root of Pico):
   - `main.py` — Main application code
   - `ssd1306.py` — OLED driver (from `/micropython-ssd1306/`)

### 3. Run the Project
The Pico will auto-run `main.py` on boot. If Thonny captures the REPL:
- Click **STOP** to halt execution
- Or hold `Ctrl+C` while connecting

---

## Usage Instructions

### Normal Operation
| Action | How to Trigger | Feedback |
|--------|---------------|----------|
| **Start/Stop** | Tap the button on GP16 once | Single 1800 Hz beep (start) or 1200 Hz beep (stop) |
| **Reset** | Hold BOOTSEL button for 1 second (only when stopped) | Double chirp at 2600 Hz, progress bar on display |

### Glitch Easter Egg
| Action | How to Trigger | Effect |
|--------|---------------|--------|
| **Triple-tap** | Tap GP16 button 3 times within 0.5 seconds | Screen corruption animation for 3 seconds with descending noise sound (3000→2000→1200→600 Hz). Timer pauses until user restarts. |

### Display Layout
```
┌──────────────────────────────┐
│  MM:SS.CC   (scaled time)    │
│                              │
│──────────────────────────────│  ← Divider line
│                              │
│  ┌────────┐  ┌──────────┐   │
│  │ START  │  │ RESET    │   │  ← UI tiles (inverts when held)
│  └────────┘  └──────────┘   │
│                    [████]    │     ← Progress bar (reset hold)
└──────────────────────────────┘
```

---

## Configuration

Edit `main.py` to customize behavior:

| Constant | Default | Description |
|----------|---------|-------------|
| `I2C_FREQ` | 400,000 | I2C clock speed (Hz) |
| `BOOTSEL_HOLD_MS` | 1000 | Hold time for reset (ms) |
| `TARGET_FPS` | 20 | Display refresh rate |
| `RESET_FLASH_MS` | 250 | Duration of reset confirmation flash (ms) |
| `TRIPLE_TAP_WINDOW_MS` | 500 | Window to detect triple-tap for glitch (ms) |
| `GLITCH_RUN_MS` | 3000 | Duration of glitch animation (ms) |
| `BUZZER_PIN` | 15 | GPIO pin for buzzer control |
| `BUZZER_ENABLED` | True | Enable/disable buzzer output |
| `BUZZER_DUTY` | 16384 | PWM duty cycle (0=silent, 32768=50%, 65535=silent) |

---

## Troubleshooting

### OLED Not Displaying
1. **I2C scan returns empty:** Check SDA/SCL wiring (Pins 6/7), verify OLED power, try address 0x3D
2. **Display shows garbage:** Lower `I2C_FREQ` to 100,000
3. **No power:** Verify OLED VCC is connected to Pin 36 (3V3_OUT), not Pin 40 (VBUS)

### Buzzer Not Working
1. **No sound:** Verify buzzer is passive (not active). Try direct GPIO drive: GP15 → buzzer (+), GND → buzzer (−)
2. **Stuck on:** Transistor may be shorted — replace it or bypass with direct GPIO
3. **Too quiet:** Increase `BUZZER_DUTY` (try 24576 for ~37.5%)
4. **Too loud:** Decrease `BUZZER_DUTY` (try 8192 for ~12.5%)

### Button Not Responding
- Verify button is wired to GP16 (Pin 21) and GND
- Check for loose breadboard connections
- Try a different button or jumper wire

### Glitch Not Triggering
- You must tap GP16 three times within 0.5 seconds
- Wait for display to settle before attempting triple-tap
- Check Thonny console for `"GLITCH (triple-tap)"` message

### General Tips
- **Reseat all wires** — breadboard connections can become loose
- **Try different jumper wires** — they can fail internally
- **Check breadboard rows** — rows can have internal breaks; try moving wires to different rows
- **Power cycle the Pico** — unplug USB, wait 5 seconds, replug
- **Verify MicroPython firmware** — if issues persist, reflash the Pico

---

## Battery Operation (Optional)

### Wiring
```
LiPo RED (+)  ──────────────► Pin 39 (VSYS)
LiPo BLACK (−) ─────────────► Pin 38 (GND)
```

### Important Warnings
- **NEVER connect battery to Pin 36 (3V3_OUT)** — this will destroy the Pico
- **NEVER connect battery to Pin 40 (VBUS)** — this can damage the USB port
- The Pico **cannot charge** the battery — use a TP4056 module or similar charger
- Add a Schottky diode (1N5817/SS14/BAT43) from battery to VSYS for safe USB+battery operation

### Runtime Estimate
- **~4.5–5.5 hours** on a 350 mAh LiPo cell
- To extend: reduce OLED contrast with `oled.contrast(0x01)` or power off display on idle timeout

---

## Technical Details

### Timing Architecture
- Elapsed time accumulates from per-loop integer-microsecond deltas using `time.ticks_diff()`
- Wrap-safe: handles the 2³⁰ µs wrap of `ticks_us()` correctly
- Drift-free: exact integer microseconds in and out

### Rendering Optimization
- Fixed ~20 FPS gate, but `oled.show()` only fires when something changed
- Per-character diffing in time display — only repaints digits that actually changed
- Tile state caching prevents redundant redraws

### Input Handling
- GP16 is active-low with internal pull-up, edge-detected via `btn_released`
- BOOTSEL is polled via `rp2.bootsel_button()` (1 = pressed, 0 = released)
- Triple-tap detection uses a sliding window of recent tap timestamps

### Buzzer Implementation
- Passive piezo buzzer driven by PWM at 50% duty cycle (loudest square wave)
- Context-aware tones: different frequencies and patterns for each action
- Non-blocking glitch sound using state-machine approach during animation

---

## Credits & AI Attribution

This project was developed with assistance from multiple AI models:

| Model | Contribution |
|-------|-------------|
| **Qwen 3.82-27B** | Core stopwatch functionality, I2C OLED integration, time accumulation logic, display rendering, button handling, and initial architecture |
| **Qwen 3.6-35B-A3B** | Buzzer implementation, glitch easter egg mechanics, triple-tap detection, non-blocking sound system, and UI tile rendering |
| **Claude Opus 5** (High Effort) | Major bug fixes including BOOTSEL polarity correction, I2C pinout resolution, PWM duty cycle understanding, time accumulation wrap handling, and comprehensive troubleshooting guidance |

### References
- **OLED Driver:** [micropython-ssd1306](https://github.com/mcauser/micropython-ssd1306)
- **RP2350 Pinout:** See `pico2_pinout.md` in project directory
- **MicroPython Documentation:** https://docs.micropython.org/

---

## License

This project is provided as-is for educational and personal use. Modify and distribute freely.

---

## Support

For issues or questions:
1. Check the **Troubleshooting** section above
2. Review `pico2_pinout.md` for pin reference
3. Open an issue on the GitHub repository
