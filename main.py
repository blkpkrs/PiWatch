# main.py — stopwatch, GME12864-11 / SSD1306 128x64
from machine import Pin, I2C, PWM
from ssd1306 import SSD1306_I2C
import framebuf
import rp2
import time

# --- config ---
I2C_ID, SDA_PIN, SCL_PIN = 0, 4, 5
I2C_FREQ = 400_000          # 400 kHz: ~23 ms to push a full 1024-byte frame
BOOTSEL_HOLD_MS = 1000      # 1-second hold to reset
TARGET_FPS = 20
FRAME_MS = 1000 // TARGET_FPS
RESET_FLASH_MS = 250        # how long the RESET tile stays lit after firing
BUZZER_PIN = 15             # PWM pin for passive buzzer (Pin 20)
BUZZER_ENABLED = True       # set False to mute buzzer

# --- layout (128x64) ---
TIME_SCALE = 2              # 8x8 font scaled 2x -> 16x16 per char
TIME_X, TIME_Y = 0, 6       # 8 chars * 16 px = 128 px, exactly the full width
CHAR_W = 8 * TIME_SCALE
CHAR_H = 8 * TIME_SCALE

SEP_Y = 30                  # divider between the time and the two tiles
BTN_Y, BTN_H = 36, 26
BTN_L_X, BTN_L_W = 1, 62    # start/stop tile
BTN_R_X, BTN_R_W = 65, 62   # reset tile

# --- hardware ---
print("Initializing I2C at 400 kHz...")
i2c = I2C(I2C_ID, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=I2C_FREQ)
print(f"I2C scan: {i2c.scan()}")

oled = SSD1306_I2C(128, 64, i2c, addr=0x3C)

# Button on GP16 to GND — start/stop toggle
btn = Pin(16, Pin.IN, Pin.PULL_UP)

# Passive buzzer on GP15 (PWM) — transistor switch to GND
buzzer = PWM(Pin(BUZZER_PIN))
buzzer.freq(2000)
buzzer.duty_u16(0)  # start silent

# --- state ---
running      = False
elapsed_us   = 0
last_tick_us = time.ticks_us()   # delta accumulator: wrap-safe, no drift
btn_released = True              # only count a press after seeing release (debounce)
bootsel_press_time = 0
reset_flash_until  = 0
last_draw_ms = 0

# cached render state, so we only repaint what actually changed
prev_time_chars = [None] * 8
prev_left  = None                # (label, inverted)
prev_right = None                # (inverted, progress_bucket)


# --- buzzer: context-aware beep tones ---
def beep(freq, duration_ms):
    """Play a tone at `freq` Hz for `duration_ms`. Non-blocking if buzzer already on."""
    if not BUZZER_ENABLED:
        return
    buzzer.freq(freq)
    buzzer.duty_u16(65535)  # 100% duty cycle for max current
    time.sleep_ms(duration_ms)
    buzzer.duty_u16(0)      # stop

def beep_start():
    """Medium ascending beep — action confirmed."""
    beep(2000, 150)

def beep_stop():
    """Short descending beep — pause acknowledged."""
    beep(1500, 80)

def beep_reset():
    """Distinct double-beep — different action."""
    beep(1000, 80)
    time.sleep_ms(50)
    beep(1200, 80)


def format_time(us):
    """us -> 'MM:SS.CC' (8 chars), clamped at 99:59.99."""
    cs = us // 10_000                       # centiseconds
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    if m > 99:                              # keep it 8 chars wide
        return "99:59.99"
    return f"{m:02d}:{s:02d}.{cs:02d}"


# --- scaled text: render one 8x8 glyph into a scratch buffer, blow it up ---
_glyph_buf = bytearray(8)                   # 8x8 MONO_VLSB == 8 bytes
_glyph = framebuf.FrameBuffer(_glyph_buf, 8, 8, framebuf.MONO_VLSB)


def draw_char_scaled(ch, x, y, scale):
    """Draw one character at `scale`x size. framebuf has no scaling, so we
    rasterise the glyph at 1x and expand each set pixel into a scale x scale block."""
    _glyph.fill(0)
    _glyph.text(ch, 0, 0, 1)
    oled.fill_rect(x, y, 8 * scale, 8 * scale, 0)
    for cy in range(8):
        for cx in range(8):
            if _glyph.pixel(cx, cy):
                oled.fill_rect(x + cx * scale, y + cy * scale, scale, scale, 1)


def draw_time(tstr):
    """Repaint only the digits that changed. Returns True if anything was drawn."""
    dirty = False
    for i in range(8):
        if tstr[i] != prev_time_chars[i]:
            draw_char_scaled(tstr[i], TIME_X + i * CHAR_W, TIME_Y, TIME_SCALE)
            prev_time_chars[i] = tstr[i]
            dirty = True
    return dirty


def draw_tile(x, w, label, inverted, progress):
    """One UI tile: outlined box, centred label, optional hold-progress bar.
    `inverted` fills the tile and flips the label — that is the 'pressed' look."""
    fg = 0 if inverted else 1
    oled.fill_rect(x, BTN_Y, w, BTN_H, 1 if inverted else 0)
    oled.rect(x, BTN_Y, w, BTN_H, 1)
    oled.text(label, x + (w - len(label) * 8) // 2, BTN_Y + 5, fg)
    if progress > 0:                        # hold-to-reset fill, drawn under the label
        bx, by = x + 4, BTN_Y + BTN_H - 9
        bw, bh = w - 8, 6
        oled.rect(bx, by, bw, bh, fg)
        fw = int((bw - 2) * progress)
        if fw > 0:
            oled.fill_rect(bx + 1, by + 1, fw, bh - 2, fg)


# --- first paint ---
oled.fill(0)
oled.hline(0, SEP_Y, 128, 1)
draw_time(format_time(0))
draw_tile(BTN_L_X, BTN_L_W, "START", False, 0)
draw_tile(BTN_R_X, BTN_R_W, "RESET", False, 0)
oled.show()
prev_left  = ("START", False)
prev_right = (False, 0)

print("=" * 50)
print("STOPWATCH READY")
print("  - GP16 button tap: start/stop")
print("  - BOOTSEL hold 1s: reset time (only when stopped)")
print("=" * 50)

while True:
    now_ms = time.ticks_ms()

    # --- accumulate elapsed time from per-loop deltas ---
    # Each delta is a few ms, so ticks_diff never approaches its +/-2^29 us limit
    # and the 2^30 us wrap of ticks_us() is handled correctly. Integer us in,
    # integer us out, so this accumulates exactly — no drift.
    now_us = time.ticks_us()
    dt_us = time.ticks_diff(now_us, last_tick_us)
    last_tick_us = now_us
    if running:
        elapsed_us += dt_us

    # --- GP16 button: start/stop toggle (active low, one trigger per press) ---
    btn_val = btn.value()
    gp16_down = (btn_val == 0)
    if gp16_down and btn_released:      # pressed, and we saw a release first
        running = not running
        if running:
            beep_start()
        else:
            beep_stop()
        print(f"{'START' if running else 'STOP'}: {format_time(elapsed_us)}")
    btn_released = not gp16_down

    # --- BOOTSEL: reset only (1-second hold, only while stopped) ---
    bs = rp2.bootsel_button()           # 1=pressed, 0=released
    hold_ms = 0
    if bs == 1:
        if bootsel_press_time == 0:
            bootsel_press_time = now_ms
        hold_ms = time.ticks_diff(now_ms, bootsel_press_time)
        if hold_ms >= BOOTSEL_HOLD_MS:
            if not running:
                elapsed_us = 0
                reset_flash_until = time.ticks_add(now_ms, RESET_FLASH_MS)
                beep_reset()
                print("RESET (BOOTSEL hold)")
            bootsel_press_time = 0      # clear so the next press can trigger again
            hold_ms = 0
    else:
        bootsel_press_time = 0          # released, clear timer

    # --- render at a fixed rate, pushing to I2C only when something changed ---
    if time.ticks_diff(now_ms, last_draw_ms) >= FRAME_MS:
        last_draw_ms = now_ms
        dirty = draw_time(format_time(elapsed_us))

        left = ("STOP" if running else "START", gp16_down)
        if left != prev_left:
            draw_tile(BTN_L_X, BTN_L_W, left[0], left[1], 0)
            prev_left = left
            dirty = True

        # reset tile: fills as BOOTSEL is held, then flashes solid when it fires
        flashing = time.ticks_diff(reset_flash_until, now_ms) > 0
        progress = 0.0
        if not running and hold_ms > 0:
            progress = hold_ms / BOOTSEL_HOLD_MS
            if progress > 1.0:
                progress = 1.0
        # bucket the bar so we only repaint on a visible step, not every frame
        right = (flashing, int(progress * 12))
        if right != prev_right:
            draw_tile(BTN_R_X, BTN_R_W, "RESET", flashing, progress)
            prev_right = right
            dirty = True

        if dirty:
            oled.show()

    time.sleep_ms(5)    # short poll so button taps are not missed
