# LumiBand — Custom Effect Upload Protocol

Custom animations are uploaded to the band's **Effect Upload** characteristic
(`beb54841-36e1-4688-b7f5-ea07361b26a8`) using a simple 3-phase protocol.

---

## Overview

An effect is a grid of LED colours played row-by-row:

```
Row 0: [LED0 LED1 LED2 ... LED14]   ← displayed for rowMs milliseconds
Row 1: [LED0 LED1 LED2 ... LED14]
...
Row N: [LED0 LED1 LED2 ... LED14]
```

Up to **8 rows**, **15 LEDs** per row, stored in up to **8 slots** (0–7).

---

## Upload Protocol

All packets are written to the **Effect Upload** characteristic with response.

### Phase 1 — Begin
```
[0x00,  slot,  numRows]
```
Resets the upload buffer. `slot` = 0–7, `numRows` = 1–8.

### Phase 2 — Data chunks
```
[0x01,  d0, d1, ..., d18]   (up to 19 bytes of payload per packet)
```
Send the serialised payload in 19-byte chunks until exhausted.

### Phase 3 — Commit
```
[0x02,  slot]
```
The band parses the buffer, stores the effect, and persists it to flash.

---

## Payload Format

Total size: `numRows × 15 × 2 + 3` bytes

```
numRows × 15 × 2 bytes   LED colours, row-major, big-endian RGB565
1 byte                   settings  (see below)
2 bytes                  rowMs, big-endian uint16 (20–1000 ms per row)
```

### RGB565 encoding
```
bits 15–11   red   (5 bits)
bits 10–5    green (5 bits, note: 6 bits in true 565, here 5 are used)
bits  4–0    blue  (5 bits)
```

```python
def rgb_to_565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 3) << 5) | (b >> 3)
```

### Settings byte
```
bit 0   SoundMode: Beat
bit 1   SoundMode: Level
bit 2   SoundMode: Envelope
bit 3   SoundMode: Always
bit 4   LoopMode: Bounce   (reverse at end instead of wrapping)
bit 5   LoopMode: LoopReverse  (play forward then backward continuously)
```

Set multiple SoundMode bits to enable multiple triggers.
`0x08` (bit 3 = Always) plays continuously regardless of sound input.

---

## Example — Python

```python
import struct, asyncio
from bleak import BleakClient

SERVICE  = '4fafc201-1fb5-459e-8fcc-c5c9c331914b'
FX_CHAR  = 'beb54841-36e1-4688-b7f5-ea07361b26a8'

def build_payload(rows, row_ms=100, sound_mode=0x08):
    """rows: list of lists of (r, g, b) tuples, 15 LEDs each"""
    data = bytearray()
    for row in rows:
        for (r, g, b) in row:
            px = ((r >> 3) << 11) | ((g >> 3) << 5) | (b >> 3)
            data += struct.pack('>H', px)
    data.append(sound_mode)
    data += struct.pack('>H', row_ms)
    return bytes(data)

async def upload_effect(address, slot, rows, row_ms=100):
    async with BleakClient(address) as client:
        payload = build_payload(rows, row_ms)
        num_rows = len(rows)

        # Begin
        await client.write_gatt_char(FX_CHAR, bytes([0x00, slot, num_rows]))

        # Chunks
        for i in range(0, len(payload), 19):
            chunk = payload[i:i+19]
            await client.write_gatt_char(FX_CHAR, bytes([0x01]) + chunk)

        # Commit
        await client.write_gatt_char(FX_CHAR, bytes([0x02, slot]))
        print(f'Effect uploaded to slot {slot}')
```
