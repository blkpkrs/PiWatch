# PiWatch — What Was Wrong, What Was Fixed, How It Works Now

Replaces the old `help.md`, which contained several incorrect diagnoses and at least
one wiring instruction that likely caused a hardware failure. Everything below is
either verified or explicitly marked as unverified.

**Hardware:** Raspberry Pi Pico 2 (RP2350) · SSD1306 128×64 OLED (I2C) · momentary
button · passive buzzer
**Firmware:** MicroPython · `main.py` + `ssd1306.py`
**Branch:** `feature/buzzer`

---

## Part 1 — Bugs fixed

### 1.1 BOOTSEL polarity was inverted (the big one)

**Symptom:** the display reset to `0:00` about 2 seconds after every stop, and the
serial log printed `RESET (BOOTSEL hold)` on a loop from boot.

**Cause:** `rp2.bootsel_button()` returns **1 when pressed, 0 when released**. The
code had it backwards:

```python
bs = rp2.bootsel_button()   # 1=released, 0=pressed   <-- wrong
if bs == 0:                 # "button held down"      <-- actually "not held"
```

Since the button is released almost always, `bs` was `0` continuously, which the code
read as "held." The 1-second hold timer armed at boot and re-armed after every reset,
firing forever. Resets were gated behind `if not running:`, so while the watch ran the
bogus reset was silently blocked — the moment you stopped, the next timer expiry zeroed
`elapsed_us`. That is the entire "auto-reset on stop" mystery.

**Fix:** `if bs == 1:`, plus corrected comments.

> **The original diagnosis was wrong and cost real time.** An earlier debug pass
> concluded the BOOTSEL line was "stuck low" — a hardware fault — and recommended
> probing GPIO15 with a multimeter. That reading came from *the same inverted
> assumption*: it correctly sampled "released" as `0` and then mislabeled it
> "pressed." Nothing was wrong with the hardware. The suggested probe would also
> have found nothing, because BOOTSEL on RP2350 is wired to the **QSPI_SS** pin,
> not to GPIO15 or any exposed GPIO.

### 1.2 Elapsed time went negative on the frame you pressed START

`now` was sampled at the top of the loop, but `start_us` was sampled later in the
button handler — so on that one iteration `now < start_us` and elapsed was negative.
`format_time()` rendered it as `-1:59.99` for a single frame.

### 1.3 The stopwatch broke after ~8.9 minutes

`time.ticks_us()` wraps at 2³⁰ µs (~17.9 min) and `ticks_diff()` is only valid across
±2²⁹ µs (~8.9 min). Beyond that the result goes negative. Reproduced in CPython:

```
running   500s -> ticks_diff=   500000000 -> 08:20.00
running   540s -> ticks_diff=  -533741824 -> -9:06.25
```

**Fix for 1.2 and 1.3 together:** elapsed time now accumulates from small per-loop
deltas rather than one long span.

```python
now_us = time.ticks_us()
dt_us = time.ticks_diff(now_us, last_tick_us)
last_tick_us = now_us
if running:
    elapsed_us += dt_us
```

Each delta is a few milliseconds, so `ticks_diff` never approaches its limit and the
wrap is handled correctly. It is exact integer microseconds in and out, so it does not
drift — the original "never accumulate per frame" concern applied to floats, not this.

### 1.4 `format_time()` could overflow the display

Past 99 minutes it returned 9 characters, which no longer fits the 128 px row. Now
clamped to `99:59.99`.

### 1.5 Buzzer — two commits that each guaranteed silence

A passive buzzer is a bare piezo element with **no internal oscillator**. It needs an
audio-frequency square wave (roughly 500 Hz–5 kHz). It cannot make a tone from a DC
level. Two commits removed the working drive:

**`f9608fc` "increase buzzer duty cycle to 100% for stronger signal"**

```python
buzzer.duty_u16(32768)   # 50%  -> before
buzzer.duty_u16(65535)   # 100% -> after
```

**100% duty is silence, not maximum volume.** Duty cycle is the fraction of each PWM
period the pin sits high; at 65535 the pin is permanently HIGH and never toggles, so
there is no waveform at all. `0` and `65535` are *both* silent, and 50% is the loudest
a square wave gets. Volume on a passive buzzer comes from drive voltage and current,
not from duty cycle. This change made working PWM look broken.

**`4f9f140` "replace PWM with simple on/off toggling"**

Concluded PWM was at fault and replaced it with GPIO toggling. That could not work
either — `buzz(100, 50, 2)` toggles at about **6.7 Hz**, as its own docstring admitted
(*"at ~1/(on+off) Hz"*). That is infrasound; it produced only a faint mechanical click
on each edge.

**Fix:** restored PWM at 50% duty, with the reasoning written into the constant so the
mistake is not repeated.

```python
BUZZER_DUTY = 32768   # 50% duty = loudest. 0 and 65535 are BOTH silent:
                      # at 100% the pin never toggles, so there is no waveform.
```

`buzz(on_ms, off_ms, cycles)` was replaced by `tone(freq_hz, ms, gap_ms)`, and the
three cues now use distinguishable pitches instead of clicks.

---

## Part 2 — Performance work

`oled.show()` pushes the whole 1024-byte framebuffer over I2C — about **23 ms at
400 kHz**, and by far the most expensive thing in the loop.

| Change | Effect |
|---|---|
| Skip the redraw when the displayed value is unchanged | Largest win. Idle now costs **zero** I2C traffic; previously it pushed a full frame ~30×/sec at a static screen. |
| `fill_rect` over the text box instead of full-screen `fill(0)` | Cuts CPU-side clearing ~8×. Does **not** reduce I2C — `show()` always sends the full buffer, as this driver has no partial-page update. |
| Per-character diffing in `draw_time()` | Only repaints digits that actually changed — usually 1–2 of 8. |
| f-string instead of `"...".format()` | Avoids reparsing the format mini-language every call. |
| Poll interval 10 ms → 5 ms | Short taps are no longer missed while rendering. |

Simulated loop verification: **0** pushes while idle, ~20/sec while running, 13 across
a full BOOTSEL hold, and reset correctly blocked while running.

---

## Part 3 — Features added

**2× scaled time text.** 16×16 px per character. Eight characters × 16 px = exactly
128 px, so `MM:SS.CC` fills the display width. `framebuf` has no scaling, so
`draw_char_scaled()` rasterises each glyph into an 8×8 scratch buffer and expands every
set pixel into a 2×2 block. **2× is the ceiling** for this format — 3× would need
192 px and overflow the panel.

**Two reactive UI tiles.** A divider at y=30, then START/STOP left and RESET right:

- Left tile reads **START** when stopped, **STOP** when running, and inverts (filled
  box, knocked-out label) while GP16 is held.
- Right tile grows a **progress bar** as BOOTSEL is held, filling over the 1 s window,
  then flashes solid for 250 ms when the reset fires.
- The progress bar appears **only while stopped**. Since reset is gated to the stopped
  state, holding BOOTSEL while running deliberately shows nothing — that is the
  "unavailable right now" signal.

**Reset hold time** reduced from 2 s to 1 s (`BOOTSEL_HOLD_MS = 1000`).

Verified layout geometry — nothing out of bounds, label and progress bar do not collide:

| Element | x range | y range |
|---|---|---|
| Time row (8 chars) | 0–127 | 6–21 |
| Divider | 0–127 | 30 |
| Left tile | 1–62 | 36–61 |
| Right tile | 65–126 | 36–61 |
| Tile label | centred | 41–48 |
| Progress bar | inset 4 px | 53–58 |

---

## Part 4 — The hardware failure

**The first Pico 2 was destroyed by a battery wiring mistake.**

Pin 36 measured **4.777 V** and the board stopped enumerating over USB. That number is
diagnostic: 4.777 V is USB VBUS (5 V) minus the drop across the Pico's onboard Schottky
D1 — in other words, the 3.3 V rail was sitting at **VSYS potential**.

**Cause:** the LiPo was connected to **pin 36 (3V3 OUT)** instead of **pin 39 (VSYS)**.
Pin 36 is the regulator's *output*. Back-driving it with 4.2 V destroyed the buck-boost
converter, which then failed short and passed VSYS straight through to the 3.3 V rail —
well past the RP2350's ~3.6 V absolute maximum.

This is unrecoverable: with the regulator shorted, every power-up re-applies 4.7 V to
the chip. The board cannot be made safe.

### Correct battery wiring

```
LiPo RED  (+) ──────────────► Pin 39  (VSYS)
LiPo BLACK(−) ──────────────► Pin 38  (GND)
```

VSYS feeds a **buck-boost** regulator accepting **1.8 V–5.5 V**, so a LiPo swinging
4.2 V → 3.0 V sits entirely inside range and yields nearly full cell capacity. No boost
converter needed.

**Three pins that will destroy the board:**

| Pin | Why |
|---|---|
| **36 — 3V3 OUT** | Regulator output. This is what killed the first board. |
| **40 — VBUS** | USB 5 V rail, wired to the USB connector. |
| Reversed polarity | Kills the Pico and possibly vents the cell. |

**If you want USB and battery both connected,** add a Schottky (1N5817 / SS14 / BAT43)
from battery + to VSYS, stripe toward the Pico. This ORs the two sources so the higher
one wins and neither can backfeed the other. Costs ~0.3 V, which is irrelevant against
a 1.8 V floor. Without it, USB holds VSYS at 4.7 V while the cell sits directly on that
rail — an uncontrolled path to push current into a lithium cell.

**The Pico cannot charge the battery.** There is no charging circuit. Use a TP4056
module (load-sharing variant if you want to run while charging), an Adafruit Micro-Lipo,
or a Pimoroni LiPo SHIM for Pico.

**Runtime estimate** (350 mAh cell): ~45–60 mA total draw → **≈ 6 h theoretical,
realistically 4.5–5.5 h**. Discharge rate is a non-issue at ~0.16C. To extend it:
`oled.contrast(0x01)` (OLED current scales hard with brightness; init currently sets
`0xFF`), then `machine.freq(48_000_000)`, then `oled.poweroff()` on idle timeout.

### Verify before applying power

With the board out of circuit, in continuity mode:

- Battery + ↔ 3V3 wire → **must be open**
- VSYS wire ↔ 3V3 wire → **must be open**
- Battery + ↔ battery − → **must be open**

Then confirm by **silkscreen on the underside**, not by counting pins. The numbering
wraps: pin 1 is top-left, down the left edge to pin 20, then pin 21 is bottom-**right**
counting *upward* to pin 40. Counting the right side downward lands you on VSYS while
you think you are on 3V3 OUT.

With USB connected, a healthy board reads:

| Pin | Label | Expected |
|---|---|---|
| 40 | VBUS | ~5.0 V |
| 39 | VSYS | ~4.7 V — *normal, this is the Schottky drop* |
| 37 | 3V3_EN | ~4.7 V (pulled up to VSYS) |
| 36 | 3V3(OUT) | **3.3 V** |

Note that 3V3_EN also sits near 4.7 V, so being one pin off in *either* direction shows
roughly that number.

---

## Part 5 — Errors in the old `help.md`

Recorded so they are not reintroduced.

**Transistor pinout — almost certainly wrong.** It claimed *"Base (left), Collector
(middle), Emitter (right)."* On essentially every TO-92 bipolar transistor the **base is
the centre pin**; for a 2N2222A/PN2222A with the flat face toward you and legs down it
is normally **E, B, C** left to right. Wiring per the old doc puts the 1 kΩ resistor on
the emitter and GND on the collector, so the transistor never switches — which matches
the reported symptom.

*This is still unverified on your actual part.* TO-92 pinouts genuinely differ between
families (a BC547 is the mirror of a 2N3904), so trust a meter over any diagram
including this one. In **diode mode**:

- Red probe on the **base**, black on either other leg → both read ~0.6–0.7 V
- Red on either other leg, black on base → both read OL

The leg reading ~0.65 V to *both* others is the base.

**"LED as flyback diode" — wrong.** A piezo buzzer is capacitive, has no back-EMF, and
needs no flyback diode at all. An LED is a poor one regardless (~2 V forward drop,
reverse breakdown around 5 V, poor recovery). The old doc also contradicted itself: its
table said cathode→3V3 while its ASCII diagram drew the LED across collector–emitter.
Leave it out. Only if the buzzer turns out to be a **magnetic** type does it need a real
1N4148 across the buzzer, cathode to 3V3.

**Documented a feature that is not on this branch.** It described the triple-tap glitch
easter egg and `TRIPLE_TAP_WINDOW_MS`; `grep` finds zero glitch code in `main.py` on
`feature/buzzer`. That work lives on `feature/glitch-easter-egg`.

**BOOTSEL described as GPIO15.** It is QSPI_SS on RP2350 — not an exposed GPIO, and
unrelated to GP15.

---

## Part 6 — How it is set up now

### Wiring

| Component | Pico GPIO | Physical pin |
|---|---|---|
| OLED VCC | 3V3 OUT | 36 |
| OLED GND | GND | 38 |
| OLED SDA | GP4 (I2C0 SDA) | 6 |
| OLED SCL | GP5 (I2C0 SCL) | 7 |
| Button leg A | GP16 (internal pull-up) | 21 |
| Button leg B | GND | any GND |
| Buzzer | GP15 (PWM) | 20 |
| Reset button | BOOTSEL (on-board) | — |

Full pin reference lives in [pico2_pinout.md](pico2_pinout.md).

**Buzzer — consider dropping the transistor.** A passive *piezo* buzzer draws only a
few mA and a GPIO can drive it directly:

```
GP15 (Pin 20) ──► Buzzer (+)
GND  (Pin 38) ──► Buzzer (−)
```

That removes the transistor, the resistor, and the entire pinout question from the
circuit. Keep the transistor only for a *magnetic* buzzer drawing 30–80 mA.

### Controls

| Input | Action |
|---|---|
| GP16 tap | Start / stop toggle |
| BOOTSEL hold 1 s (stopped only) | Reset to zero |

### Audio cues

| Event | Pattern |
|---|---|
| START | Rising two-tone — 1800 Hz 70 ms, 30 ms gap, 2600 Hz 90 ms |
| STOP | Single lower tone — 1200 Hz 120 ms |
| RESET | Two identical chirps — 2600 Hz 60 ms, 70 ms gap, 2600 Hz 60 ms |

Set `BUZZER_ENABLED = False` to mute.

### Code architecture

- **Timing** — `elapsed_us` accumulates per-loop integer-microsecond deltas. Wrap-safe,
  drift-free, unaffected by blocking calls (a blocking beep is simply absorbed into the
  next delta, and that time genuinely did pass).
- **Rendering** — fixed ~20 FPS gate, but `oled.show()` only fires when something
  actually changed. `draw_time()` diffs per character; tiles diff on
  `(label, inverted)` and `(flashing, progress_bucket)`.
- **Input** — GP16 is active-low with an internal pull-up, edge-detected via
  `btn_released` so one press yields one toggle. BOOTSEL is polled via
  `rp2.bootsel_button()` (1 = pressed).
- **Scaled text** — `draw_char_scaled()` rasterises an 8×8 glyph into a scratch
  `framebuf` and expands set pixels into `scale × scale` blocks.

### Files

```
main.py                        Application
micropython-ssd1306/ssd1306.py OLED driver — must be uploaded to the device root or /lib
pico2_pinout.md                Pin and protocol reference
fixed.md                       This document
```

**Both `main.py` and `ssd1306.py` must be on the device.** A freshly flashed board has
neither. `main.py` line 3 does `from ssd1306 import SSD1306_I2C` and will fail without it.

### Connecting with Thonny (macOS)

1. Confirm the board enumerates: `ls -1 /dev/cu.*` should show a new `/dev/cu.usbmodem…`
   entry. If it does not, **try a different USB cable first** — many are charge-only.
2. Thonny ▸ Preferences (`⌘,`) ▸ **Interpreter** ▸ *MicroPython (Raspberry Pi Pico)*,
   then select the port.
3. **View ▸ Files** to upload. Right-click → *Upload to /*.

`main.py` autoruns at boot and never exits, so Thonny often cannot grab the REPL. Click
**STOP**, or hold `Ctrl+C` while connecting. Last resort: hold BOOTSEL, re-drag the
`.uf2` — this wipes the filesystem, so keep files in the repo.

---

## Part 7 — Open items

**Verify the buzzer on hardware.** The code fix is correct in principle but has not
been confirmed audible. Run this in the REPL — it also finds the resonant frequency,
where piezos are dramatically louder (usually 2–4 kHz):

```python
from machine import Pin, PWM
import time
b = PWM(Pin(15))
for f in range(500, 5001, 250):
    b.freq(f); b.duty_u16(32768); print(f, "Hz"); time.sleep_ms(300)
b.duty_u16(0)
```

Set `buzzer.freq()` and the `tone()` calls to whichever is loudest. **Silence across the
whole sweep means the fault is in the wiring** — start with the transistor pinout.

**Confirm the transistor pinout with a meter** (Part 5), or bypass it with direct GPIO
drive.

**Beeps block the loop** for up to ~190 ms, pausing the display and button polling.
Elapsed time is unaffected. A non-blocking state machine driven off the render tick
would fix it.

**Branches are unmerged.** `feature/buzzer` and `feature/glitch-easter-egg` both carry
work not on `main`.

### Verification status

| Item | Status |
|---|---|
| All firmware changes | `py_compile` clean |
| Layout geometry, loop state machine, timing arithmetic | Verified by simulation |
| Buzzer audible output | **Not verified** — needs hardware |
| Transistor pinout | **Not verified** — needs meter |
| Anything on real hardware | **Not verified** — no device access |

---

## Part 8 — If you move to a Pico 2 W

The CYW43439 **takes over four GPIOs** that are free on the non-W board:

| GPIO | Pico 2 | Pico 2 W |
|---|---|---|
| GP23 | SMPS power-save | `WL_ON` |
| GP24 | VBUS sense | `WL_D` |
| GP25 | Onboard LED | `WL_CS` |
| GP29 | ADC3 → VSYS/3 monitor | `WL_CLK` |

Consequences: the LED moves to `Pin("LED", Pin.OUT)`; VBUS detect moves to
`Pin('WL_GPIO2', Pin.IN)`; and **battery voltage monitoring via ADC3 becomes awkward**,
since that pin doubles as the wireless SPI clock — an external divider into a spare ADC
pin is cleaner.

**Your stopwatch code runs unchanged** — I2C on GP4/GP5, the GP16 button, GP15 PWM, and
`rp2.bootsel_button()` are all untouched by the wireless chip.

**Battery runtime drops sharply** with the radio active: ~5 h with the radio never
initialised (it stays powered down until you call `network.WLAN`), very roughly
2.5–3 h associated and idle, considerably less while transmitting.
