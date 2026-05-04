# LumiBand GATT API

LumiBand is a wearable LED band controlled over BLE.
This document is everything a developer needs to control it from any platform.

**LumiBand is currently in Kickstarter funding**, see this [link](https://lumicense.com)

---

## Quick start

1. Scan for BLE devices advertising the LumiBand service UUID
2. Connect and discover characteristics
3. Write to the **Command** characteristic to change colour or mode

```python
# Python — full red, full brightness
await client.write_gatt_char(CMD, bytes([0x03, 255, 0, 0, 255]))
```

---

## Service & Characteristics

**Service UUID**
```
4fafc201-1fb5-459e-8fcc-c5c9c331914b
```

| Characteristic | UUID | Properties | Description |
|---|---|---|---|
| **Command** | `beb54840-36e1-4688-b7f5-ea07361b26a8` | Write | Main control — colour, presets, modes |
| **Brightness** | `beb5483f-36e1-4688-b7f5-ea07361b26a8` | Write | Master brightness (0–255) |
| **Status** | `beb54842-36e1-4688-b7f5-ea07361b26a8` | Read, Notify | Current mode and brightness |
| **Effect Upload** | `beb54841-36e1-4688-b7f5-ea07361b26a8` | Write | Upload custom LED animations |
| **Sync** | `beb54843-36e1-4688-b7f5-ea07361b26a8` | Write | Multi-device clock synchronisation |
| **Battery Level** | `00002a19-0000-1000-8000-00805f9b34fb` | Read | Standard BLE Battery Service (0x180F) |

---

## Command Reference

All commands are written to the **Command** characteristic.

### Set solid colour
```
[0x03,  R,  G,  B,  Brightness,  Strobe(opt)]
```
| Byte | Value |
|------|-------|
| `0x03` | command type |
| `R` | red 0–255 |
| `G` | green 0–255 |
| `B` | blue 0–255 |
| `Brightness` | 0 = off, 255 = full |
| `Strobe` *(optional)* | 0 = steady, 1–255 = speed (1 ≈ 0.25 Hz slow → 255 ≈ 25 Hz fast, logarithmic) |

Example — pure red at 50 % brightness, no strobe:
```
[0x03, 255, 0, 0, 128]
```

Example — white strobe at ~10 Hz:
```
[0x03, 255, 255, 255, 200, 180]
```

> **Note:** the Brightness byte is applied directly to the hardware. It is not
> capped by any brightness limit set in the LumiBand app — you have full
> control from 0 (off) to 255 (maximum hardware output). Usually the bracelet
> is only set between **5-20%** brightness. Exceeding this range will drain the
> battery a lot faster.

---

### Set brightness only
Write a single byte to the **Brightness** characteristic (does not change colour):
```
[128]   →  50 % brightness
[255]   →  full
[0]     →  off
```

---

### Set colour only (preserve current brightness)

Read the current brightness from the **Status** characteristic first, then
include it in the colour command.

```python
# Python (bleak)
STATUS = 'beb54842-36e1-4688-b7f5-ea07361b26a8'
CMD    = 'beb54840-36e1-4688-b7f5-ea07361b26a8'

status     = await client.read_gatt_char(STATUS)
brightness = status[1]
await client.write_gatt_char(CMD, bytes([0x03, 255, 0, 0, brightness]))
```

```javascript
// Web Bluetooth
const status     = await statusChar.readValue();
const brightness = status.getUint8(1);
await cmdChar.writeValue(new Uint8Array([0x03, 255, 0, 0, brightness]));
```

```swift
// Swift — call inside didUpdateValueFor statusCharacteristic
let brightness = data[1]
let payload: [UInt8] = [0x03, 255, 0, 0, brightness]
peripheral.writeValue(Data(payload), for: cmdCharacteristic, type: .withResponse)
```

```kotlin
// Android (Kotlin)
val brightness = statusValue[1]
val payload = byteArrayOf(0x03, 255.toByte(), 0, 0, brightness)
cmdCharacteristic.value = payload
gatt.writeCharacteristic(cmdCharacteristic)
```

> **Note:** If preserving brightness is not important, skip the Status read
> and pass a brightness value directly:
> ```
> [0x03, 255, 0, 0, 128]   →  red at 50 % brightness
> ```

---

### Activate a built-in preset
```
[0x02,  presetIndex]
```

| Index | Preset |
|-------|--------|
| `0` | Classic — sound-reactive with beat detection |
| `1` | Static |
| `2` | Party |
| `3` | Lava |
| `4` | Dim |

---

### Exit override / return to saved mode
```
[0x08, 0x00]
```
Releases any override and resumes the mode last saved on the band.

---

## Status Notifications

Subscribe to the **Status** characteristic to receive updates whenever the band's state changes.

**Payload: 4 bytes**
```
[modeIndex, brightness, classicColorIdx, buttonPressCount]
```

| Byte | Field | Notes |
|------|-------|-------|
| `[0]` | modeIndex | See table below |
| `[1]` | brightness | 0–255 master brightness |
| `[2]` | classicColorIdx | Active Classic colour scheme (0–10, wraps at 9 for built-in schemes) |
| `[3]` | buttonPressCount | Total button press counter (wraps at 255) |

| modeIndex | Mode |
|-----------|------|
| `0` | Classic (sound-reactive) |
| `1` | Static |
| `2` | Party |
| `3` | Lava |
| `4` | Dim |
| `5` | Alarm |
| `6` | Custom effect |
| `7` | Playlist |

---

## Battery Level

LumiBand exposes the standard **Bluetooth Battery Service (0x180F)**.

| | |
|---|---|
| Service | `0000180f-0000-1000-8000-00805f9b34fb` |
| Characteristic | `00002a19-0000-1000-8000-00805f9b34fb` |
| Properties | Read |
| Value | 1 byte — battery percentage 0–100 |

```python
# Python
level = await client.read_gatt_char('00002a19-0000-1000-8000-00805f9b34fb')
print(f'Battery: {level[0]} %')
```

```javascript
// Web Bluetooth
const battService = await device.gatt.getPrimaryService('battery_service');
const battChar    = await battService.getCharacteristic('battery_level');
const value       = await battChar.readValue();
console.log(`Battery: ${value.getUint8(0)} %`);
```

Because it uses the standard 16-bit UUID, most generic BLE tools (nRF Connect,
LightBlue, etc.) will display the battery level automatically without any
configuration.

---

## Connection notes

- **MTU**: request 512 bytes after connecting — the band (nRF52840) supports it and improves effect upload speed
- **One connection at a time**: only one central can be connected simultaneously
- **No bonding required**: the band does not require pairing or encryption
- **Advertising name**: `LumiBand`

---

## Examples

| Language | Library | File |
|----------|---------|------|
| Python | [bleak](https://github.com/hbldh/bleak) | [examples/python/lumiband.py](examples/python/lumiband.py) |
| Python — effect uploader | [bleak](https://github.com/hbldh/bleak) | [examples/python/upload_effect.py](examples/python/upload_effect.py) |
| React Native | [react-native-ble-plx](https://github.com/dotintent/react-native-ble-plx) | [examples/react-native/LumiBandBLE.js](examples/react-native/LumiBandBLE.js) |
| Web | [Web Bluetooth API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API) | [examples/web/lumiband.html](examples/web/lumiband.html) |
| Swift | CoreBluetooth | [examples/swift/LumiBandController.swift](examples/swift/LumiBandController.swift) |
| Android (Kotlin) | android.bluetooth | [examples/android/LumiBandController.kt](examples/android/LumiBandController.kt) |
| QLC+ (OSC) | [QLC+](https://qlcplus.org) | [examples/qlcplus/](examples/qlcplus/) |

---

## Multi-device Sync

The **Sync** characteristic lets you lock multiple LumiBands to the same animation clock, so every band flashes, pulses, or cycles in perfect unison regardless of when each device connected.

### How it works

Each band maintains an internal `syncOffset` value:

```
syncOffset = groupTime − millis()
```

Once set, the band adds `syncOffset` to its local `millis()` counter whenever it needs the current position in a repeating animation cycle. All bands that received the same `groupTime` will therefore be at the same position in the cycle, even if their own clocks started at different times.

### Payload

Write **4 bytes** (big-endian uint32) to the Sync characteristic:

```
[T3, T2, T1, T0]   →  groupTime in milliseconds
```

| Byte | Value |
|------|-------|
| `T3` | most-significant byte of groupTime |
| `T2` | — |
| `T1` | — |
| `T0` | least-significant byte of groupTime |

`groupTime` is an arbitrary shared timestamp in milliseconds. The simplest choice is the Unix time in ms modulo 2³²; what matters is that every band receives the **same value** at approximately the same moment.

### Python example (bridge node)

```python
import asyncio, struct, time
from bleak import BleakClient

SERVICE  = '4fafc201-1fb5-459e-8fcc-c5c9c331914b'
SYNC     = 'beb54843-36e1-4688-b7f5-ea07361b26a8'

async def sync_bands(addresses: list[str]) -> None:
    group_time = int(time.monotonic() * 1000) & 0xFFFFFFFF
    payload    = struct.pack('>I', group_time)   # big-endian uint32

    async def send(addr):
        async with BleakClient(addr) as client:
            await client.write_gatt_char(SYNC, payload)

    await asyncio.gather(*[send(a) for a in addresses])

asyncio.run(sync_bands([
    'AA:BB:CC:DD:EE:01',
    'AA:BB:CC:DD:EE:02',
    'AA:BB:CC:DD:EE:03',
]))
```

`asyncio.gather` sends the payload to all bands concurrently — typical BLE write latency is <10 ms per device, so hundreds of bands stay within a single animation frame.

### Deployment pattern

```
                ┌──────────────┐
                │  Controller  │  (laptop / Raspberry Pi / phone)
                │  QLC+ / OSC  │  sends R G B Brightness via Art-Net or OSC
                └──────┬───────┘
                       │ UDP broadcast
          ┌────────────┴────────────┐
          │                         │
    ┌─────▼─────┐             ┌─────▼─────┐
    │  ESP32 #1 │  BLE        │  ESP32 #2 │  BLE
    │  bridge   ├──────┐      │  bridge   ├──────┐
    └───────────┘      │      └───────────┘      │
                  bands 1–50                 bands 51–100
```

1. At startup each ESP32 bridge writes the same `groupTime` to every band in its zone.
2. The controller streams colour commands over Art-Net/OSC broadcast — one packet reaches all ESP32s simultaneously.
3. Each ESP32 relays the colour command to its connected bands via BLE.
4. Because every band shares the same `syncOffset`, animations stay in phase across the whole venue.

### Notes

- Re-sync anytime: just write a new `groupTime` to all bands. A drift of ±1 frame (16–20 ms) is imperceptible; re-syncing once per minute is more than sufficient.
- The sync offset only affects time-based effects (presets, custom effects). Solid-colour commands (`0x03`) are instantaneous and need no sync.
- BLE connection latency is the main source of phase error. Keeping each bridge node to ≤50 bands ensures all writes complete within a single animation frame.

---

## Advanced — Custom Effect Upload

Custom animations are stored in up to 8 slots on the band. Each effect is a grid of up to 16 rows × 15 LEDs with timing and sound-reactive settings.

See [EFFECT_UPLOAD.md](EFFECT_UPLOAD.md) for the full protocol.

---

## Contributing

Found a bug in this spec, or built something cool with LumiBand? PRs welcome.
If you've built a controller app, open an issue and we'll link it here.

---

## Licence

MIT
