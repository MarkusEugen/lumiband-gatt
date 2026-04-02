# LumiBand GATT API

LumiBand is a wearable LED band controlled over BLE.
This document is everything a developer needs to control it from any platform.

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
| **Battery Level** | `00002a19-0000-1000-8000-00805f9b34fb` | Read | Standard BLE Battery Service (0x180F) |

---

## Command Reference

All commands are written to the **Command** characteristic.

### Set solid colour
```
[0x03,  R,  G,  B,  Brightness]
```
| Byte | Value |
|------|-------|
| `0x03` | command type |
| `R` | red 0–255 |
| `G` | green 0–255 |
| `B` | blue 0–255 |
| `Brightness` | 0 = off, 255 = full |

Example — pure red at 50 % brightness:
```
[0x03, 255, 0, 0, 128]
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

**Payload: 2 bytes**
```
[modeIndex, brightness]
```

| modeIndex | Mode |
|-----------|------|
| `0` | Solid colour |
| `1` | Preset |
| `2` | Custom effect |

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
| React Native | [react-native-ble-plx](https://github.com/dotintent/react-native-ble-plx) | [examples/react-native/LumiBandBLE.js](examples/react-native/LumiBandBLE.js) |
| Web | [Web Bluetooth API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API) | [examples/web/lumiband.html](examples/web/lumiband.html) |
| Swift | CoreBluetooth | [examples/swift/LumiBandController.swift](examples/swift/LumiBandController.swift) |

---

## Advanced — Custom Effect Upload

Custom animations are stored in up to 8 slots on the band. Each effect is a grid of up to 8 rows × 15 LEDs with timing and sound-reactive settings.

See [EFFECT_UPLOAD.md](EFFECT_UPLOAD.md) for the full protocol.

---

## Contributing

Found a bug in this spec, or built something cool with LumiBand? PRs welcome.
If you've built a controller app, open an issue and we'll link it here.

---

## Licence

MIT
