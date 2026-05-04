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

Up to **16 rows**, **15 LEDs** per row, stored in up to **8 slots** (0–7).

---

## Upload Protocol

All packets are written to the **Effect Upload** characteristic with response.

### Phase 1 — Begin
```
[0x00,  slot,  numRows]
```
Resets the upload buffer. `slot` = 0–7, `numRows` = 2–16.

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

Total size: `numRows × 15 × 2 + 4` bytes

```
numRows × 15 × 2 bytes   LED colours, row-major, big-endian RGB565
1 byte                   settings  (see below)
2 bytes                  rowMs, big-endian uint16 (10–1000 ms per row)
1 byte                   refBpm (reference BPM for BPM-locked mode, 0 = unused)
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
bit 0  (0x01)  SOUND_ORGEL       Scale each LED's brightness by audio level every tick
bit 1  (0x02)  SOUND_FLASH_BEAT  Flash entire row white for one tick on every beat
bit 2  (0x04)  SOUND_NEXT_BEAT   Advance row on beat instead of on the row timer
bit 3  (0x08)  SOUND_PEGEL       Select row by audio level (overrides row timer)
bit 4  (0x10)  SOUND_BPM         Scale rowMs to live BPM (requires loop-forward)
bit 5  (0x20)  LOOP_BOUNCE       Reverse direction at end instead of wrapping
bit 6  (0x40)  LOOP_REVERSE      Play rows in reverse order
bit 7  (0x80)  POV_MODE          Persistence-of-Vision: R/G/B channels strobed
                                 sequentially at 5 ms each for streak photography
```

Multiple sound mode bits can be set simultaneously.
`SOUND_PEGEL` overrides the row timer entirely — rows are selected by audio level.
`POV_MODE` disables all sound modes; use with Loop or Bounce for sweep effects.

---

## Example — Python

```python
import struct, asyncio
from bleak import BleakClient

SERVICE  = '4fafc201-1fb5-459e-8fcc-c5c9c331914b'
FX_CHAR  = 'beb54841-36e1-4688-b7f5-ea07361b26a8'

def build_payload(rows, row_ms=100, settings=0x00, ref_bpm=0):
    """rows: list of lists of (r, g, b) tuples, 15 LEDs each"""
    data = bytearray()
    for row in rows:
        for (r, g, b) in row:
            px = ((r >> 3) << 11) | ((g >> 3) << 5) | (b >> 3)
            data += struct.pack('>H', px)
    data.append(settings)
    data += struct.pack('>H', row_ms)
    data.append(ref_bpm)
    return bytes(data)

async def upload_effect(address, slot, rows, row_ms=100, settings=0x00):
    async with BleakClient(address) as client:
        payload = build_payload(rows, row_ms, settings)
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
