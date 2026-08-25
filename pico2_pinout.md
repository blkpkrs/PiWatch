# Raspberry Pi Pico 2 / Pico 2 W — Pinout & Protocol Reference

**MCU:** RP2350 · Dual Cortex-M33 @ 150 MHz (or dual RISC-V Hazard3, switchable) · 520 KB SRAM · 4 MB flash
**Wireless (Pico 2 W only):** Infineon CYW43439 — 802.11n Wi-Fi + Bluetooth 5.2
**Logic level:** 3.3 V — **not 5 V tolerant.** Applying 5 V to a GPIO will damage it.

---

## 1. Physical Pinout

Pin 1 is top-left (USB port oriented up). Numbering runs down the left side (1–20), then up the right side (21–40).

### Left side (pins 1–20)

| Pin | Name | SPI | I2C | UART | Notes |
|-----|------|-----|-----|------|-------|
| 1 | GP0 | SPI0 RX | I2C0 SDA | UART0 TX | |
| 2 | GP1 | SPI0 CSn | I2C0 SCL | UART0 RX | |
| 3 | **GND** | | | | |
| 4 | GP2 | SPI0 SCK | I2C1 SDA | | |
| 5 | GP3 | SPI0 TX | I2C1 SCL | | |
| 6 | GP4 | SPI0 RX | I2C0 SDA | UART1 TX | |
| 7 | GP5 | SPI0 CSn | I2C0 SCL | UART1 RX | |
| 8 | **GND** | | | | |
| 9 | GP6 | SPI0 SCK | I2C1 SDA | | |
| 10 | GP7 | SPI0 TX | I2C1 SCL | | |
| 11 | GP8 | SPI1 RX | I2C0 SDA | UART1 TX | |
| 12 | GP9 | SPI1 CSn | I2C0 SCL | UART1 RX | |
| 13 | **GND** | | | | |
| 14 | GP10 | SPI1 SCK | I2C1 SDA | | |
| 15 | GP11 | SPI1 TX | I2C1 SCL | | |
| 16 | GP12 | SPI1 RX | I2C0 SDA | UART0 TX | |
| 17 | GP13 | SPI1 CSn | I2C0 SCL | UART0 RX | |
| 18 | **GND** | | | | |
| 19 | GP14 | SPI1 SCK | I2C1 SDA | | |
| 20 | GP15 | SPI1 TX | I2C1 SCL | | |

### Right side (pins 21–40)

| Pin | Name | SPI | I2C | UART | Notes |
|-----|------|-----|-----|------|-------|
| 21 | GP16 | SPI0 RX | I2C0 SDA | UART0 TX | |
| 22 | GP17 | SPI0 CSn | I2C0 SCL | UART0 RX | |
| 23 | **GND** | | | | |
| 24 | GP18 | SPI0 SCK | I2C1 SDA | | |
| 25 | GP19 | SPI0 TX | I2C1 SCL | | |
| 26 | GP20 | SPI0 RX | I2C0 SDA | UART1 TX | |
| 27 | GP21 | SPI0 CSn | I2C0 SCL | UART1 RX | |
| 28 | **GND** | | | | |
| 29 | GP22 | | | | Plain GPIO |
| 30 | **RUN** | | | | Pull LOW to reset the MCU |
| 31 | GP26 / **ADC0** | SPI1 SCK | I2C1 SDA | | Analog capable |
| 32 | GP27 / **ADC1** | SPI1 TX | I2C1 SCL | | Analog capable |
| 33 | **ADC_GND** | | | | Clean ground return for ADC |
| 34 | GP28 / **ADC2** | SPI1 RX | | | Analog capable |
| 35 | **ADC_VREF** | | | | ADC reference (≈3.3 V) |
| 36 | **3V3_OUT** | | | | Regulated 3.3 V out, ~300 mA budget |
| 37 | **3V3_EN** | | | | Pull LOW to disable the regulator |
| 38 | **GND** | | | | |
| 39 | **VSYS** | | | | Main input, 1.8–5.5 V |
| 40 | **VBUS** | | | | 5 V from USB |

---

## 2. Pico 2 W — Pins You Cannot Use

The wireless module consumes several GPIOs internally. **These are not exposed on the header and must not be driven:**

| GPIO | Function |
|------|----------|
| GP23 | `WL_ON` — wireless chip power control |
| GP24 | `WL_D` — wireless SPI data |
| GP25 | `WL_CS` — wireless SPI chip select |
| GP29 / ADC3 | `WL_CLK` — also VSYS voltage sense divider |

**Onboard LED gotcha:** on the Pico 2 W, the user LED hangs off the CYW43 chip, *not* GP25. Use `Pin("LED")` in MicroPython, not `Pin(25)`.

---

## 3. Peripheral Budget

| Peripheral | Count | Notes |
|-----------|-------|-------|
| UART | 2 | UART0, UART1 |
| I2C | 2 | I2C0, I2C1 |
| SPI | 2 | SPI0, SPI1 |
| PWM | 12 slices × 2 channels = 24 outputs | Any GPIO can be routed |
| ADC | 3 external (GP26–28) + internal temp sensor | 12-bit, ~500 kS/s |
| PIO | 3 blocks × 4 state machines = 12 | For custom/bit-banged protocols |

**Key constraint:** only *one* peripheral instance can be active per bus at a time. You can't run two separate I2C0 buses on different pin pairs simultaneously — pick one pin pair per instance. If you need more buses than the hardware provides, use PIO.

---

## 4. Communication Protocols

### 4.1 UART — Point-to-Point Serial

**Use for:** GPS modules, serial LCDs, XBee radios, debug consoles, board-to-board links.

**Wiring:** TX → RX (crossed), RX → TX, common GND. No clock line — both ends must agree on baud rate.

| Bus | Common pin pairs (TX / RX) |
|-----|---------------------------|
| UART0 | GP0/GP1, GP12/GP13, GP16/GP17 |
| UART1 | GP4/GP5, GP8/GP9, GP20/GP21 |

```python
from machine import UART, Pin

uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))

uart.write(b"AT\r\n")

if uart.any():
    data = uart.readline()
    print(data)
```

**Practical notes:**
- Standard baud rates: 9600, 19200, 38400, 57600, 115200. Higher rates need shorter, cleaner wiring.
- Talking to a 5 V device (many Arduino peripherals) requires a level shifter on the Pico's RX line. The Pico's 3.3 V TX is usually read fine by a 5 V device, but 5 V into the Pico's RX will damage it.
- For long runs or noisy environments (motor drivers, industrial sensors), convert to RS-485 with a transceiver like the MAX485.

---

### 4.2 I2C — Multi-Device Two-Wire Bus

**Use for:** IMUs (MPU6050, BNO055), OLED displays, temperature/pressure sensors (BME280), real-time clocks, EEPROM.

**Wiring:** SDA and SCL shared across all devices, common GND. **Pull-up resistors required** — typically 4.7 kΩ to 3.3 V on each line. Many breakout boards include them; if you chain several boards, you may need to remove some to avoid over-stiffening the bus.

| Bus | Common pin pairs (SDA / SCL) |
|-----|-----------------------------|
| I2C0 | GP0/GP1, GP4/GP5, GP8/GP9, GP12/GP13, GP16/GP17, GP20/GP21 |
| I2C1 | GP2/GP3, GP6/GP7, GP10/GP11, GP14/GP15, GP18/GP19, GP26/GP27 |

```python
from machine import I2C, Pin

i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400_000)

# Always scan first when bringing up new hardware
print([hex(addr) for addr in i2c.scan()])

# Read 6 bytes starting at register 0x3B from device 0x68
data = i2c.readfrom_mem(0x68, 0x3B, 6)

# Write a config byte
i2c.writeto_mem(0x68, 0x6B, bytes([0x00]))
```

**Practical notes:**
- Speeds: 100 kHz (standard), 400 kHz (fast), 1 MHz (fast-plus, if the device supports it).
- Each device needs a unique 7-bit address. Address collisions are the most common I2C failure — many sensors have an `ADDR` pin to shift between two addresses. Beyond that, use a TCA9548A multiplexer or put devices on the second bus.
- `i2c.scan()` returning an empty list almost always means missing pull-ups, swapped SDA/SCL, or no power to the device.
- Keep total bus capacitance low: under ~30 cm of wiring at 400 kHz is a reasonable rule of thumb.

---

### 4.3 SPI — High-Speed Synchronous Bus

**Use for:** SD cards, TFT displays, high-rate ADCs/DACs, NRF24L01 radios, flash memory.

**Wiring:** SCK (clock), TX/MOSI (Pico → device), RX/MISO (device → Pico), plus one CS line per device. CS is active-low and is normally driven as a plain GPIO, not by the SPI peripheral, so you can address many devices from one bus.

| Bus | SCK | TX (MOSI) | RX (MISO) |
|-----|-----|-----------|-----------|
| SPI0 | GP2, GP6, GP18 | GP3, GP7, GP19 | GP0, GP4, GP16, GP20 |
| SPI1 | GP10, GP14, GP26 | GP11, GP15, GP27 | GP8, GP12, GP28 |

```python
from machine import SPI, Pin

spi = SPI(0,
          baudrate=1_000_000,
          polarity=0,
          phase=0,
          sck=Pin(2),
          mosi=Pin(3),
          miso=Pin(4))

cs = Pin(5, Pin.OUT, value=1)   # idle high

cs.value(0)                      # select device
spi.write(bytes([0x9F]))         # send command
resp = spi.read(3)               # clock in 3 bytes
cs.value(1)                      # deselect
```

**Practical notes:**
- `polarity` and `phase` define the SPI mode (0–3). Check the device datasheet — wrong mode produces garbage data, not silence.
- SPI is much faster than I2C (tens of MHz) but costs more pins. Use it when throughput matters: displays, SD logging, fast sampling.
- Only pull one CS low at a time. Two selected devices will both drive MISO and corrupt the bus.
- No pull-ups needed, unlike I2C.

---

### 4.4 ADC — Analog Input

**Use for:** potentiometers, load cells (via amplifier), thermistors, analog pressure sensors, strain gauges.

| Channel | Pin | Header |
|---------|-----|--------|
| ADC0 | GP26 | 31 |
| ADC1 | GP27 | 32 |
| ADC2 | GP28 | 34 |
| ADC4 | — | Internal temperature sensor |

```python
from machine import ADC, Pin

pot = ADC(Pin(26))

raw = pot.read_u16()             # 0–65535 (12-bit value left-shifted)
volts = raw * 3.3 / 65535
print(f"{volts:.3f} V")
```

**Practical notes:**
- Input range is 0–3.3 V. For higher voltages, use a resistor divider; for sub-millivolt signals (thermocouples, strain gauges), use an external instrumentation amplifier or a dedicated 24-bit ADC like the HX711.
- Tie **ADC_GND (pin 33)** to your sensor's ground return, not a random digital ground pin. This matters for low-noise measurements.
- The RP2350's ADC has known DNL non-linearity. For precision work, oversample and average, or use an external ADC over SPI/I2C.
- **ADC3 is unavailable on Pico 2 W** — it's consumed by the wireless module's VSYS sense.

---

### 4.5 PWM — Motor & Servo Control

**Use for:** hobby servos, DC motor speed via H-bridge, LED dimming, buzzers.

Any GPIO can output PWM. The 12 slices each drive 2 channels; GPIOs sharing a slice share a frequency but can have independent duty cycles.

```python
from machine import Pin, PWM

# Standard hobby servo: 50 Hz, 1.0–2.0 ms pulse
servo = PWM(Pin(15))
servo.freq(50)

def angle(deg):
    us = 1000 + (deg / 180) * 1000        # 1000–2000 µs
    duty = int(us / 20000 * 65535)        # 20 ms period
    servo.duty_u16(duty)

angle(90)
```

**Practical note:** never power servos or motors from **3V3_OUT (pin 36)** — it's limited to roughly 300 mA and motor inrush will brown out the MCU. Use a separate supply with grounds tied together.

---

### 4.6 PIO — When the Hardware Peripherals Aren't Enough

The RP2350 has 3 PIO blocks (12 state machines total) that run small programs independently of the CPU. Use them for:
- More UART/I2C/SPI buses than the 2 hardware instances allow
- Timing-critical protocols like WS2812/NeoPixel, DHT22, or quadrature encoder decoding
- Precise pulse generation or capture without CPU jitter

For a mechanical engineering context, PIO is particularly useful for **reading quadrature encoders** on motors — it handles the edge counting in hardware, so you don't drop counts at high RPM.

---

## 5. Power

| Pin | Function |
|-----|----------|
| **VBUS (40)** | 5 V from USB. Absent when USB is disconnected. |
| **VSYS (39)** | Main system input, **1.8–5.5 V**. Feeds the onboard buck-boost regulator. |
| **3V3_OUT (36)** | Regulated 3.3 V output for peripherals. ~300 mA budget. |
| **3V3_EN (37)** | Pull LOW to shut down the 3.3 V rail (useful for low-power modes). |

**Battery operation:** feed 1.8–5.5 V into VSYS. A 2S LiPo (7.4 V) is too high — regulate down first. A single-cell LiPo (3.0–4.2 V) works directly into VSYS thanks to the buck-boost.

**Do not** back-feed 5 V into VBUS while USB is connected without a Schottky diode in series.

---

## 6. Known Gotcha: RP2350 Input Pull-Down Erratum (E9)

On RP2350 silicon, a GPIO configured as an **input with the internal pull-down enabled** can latch at roughly 2.1–2.2 V after an external voltage is applied and removed, instead of returning cleanly to 0 V. This makes it read as a stuck HIGH.

**Practical impact:** active-high buttons wired against internal pull-downs may not release correctly.

**Workarounds:**
1. Wire buttons **active-low** — connect to GND, use internal pull-*ups*. This is the standard approach anyway and sidesteps the issue entirely.
2. If you must use pull-downs, add an **external resistor of 8.2 kΩ or lower** to GND.

```python
# Preferred: active-low button
btn = Pin(14, Pin.IN, Pin.PULL_UP)
pressed = not btn.value()
```

---

## 7. Quick Bring-Up Checklist

1. Confirm the device's logic level — 3.3 V or level-shifted.
2. Tie all grounds together before applying power.
3. I2C: verify pull-ups, then run `i2c.scan()` — no addresses means wiring or power, not code.
4. SPI: confirm the mode (polarity/phase) from the datasheet before debugging data.
5. UART: confirm baud rate and that TX/RX are crossed.
6. Anything drawing more than ~200 mA gets its own supply, not 3V3_OUT.
7. On Pico 2 W, remember GP23/24/25/29 are off-limits and the LED is `Pin("LED")`.
