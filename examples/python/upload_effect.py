"""
LumiBand — custom effect uploader
Requires: pip install bleak

Usage:
    python upload_effect.py               # upload all built-in examples
    python upload_effect.py --slot 0      # upload rainbow to slot 0 only
    python upload_effect.py --list        # print available built-in effects
"""

import asyncio
import struct
import argparse
from bleak import BleakScanner, BleakClient

SERVICE = '4fafc201-1fb5-459e-8fcc-c5c9c331914b'
FX_CHAR = 'beb54841-36e1-4688-b7f5-ea07361b26a8'
CMD     = 'beb54840-36e1-4688-b7f5-ea07361b26a8'

NUM_LEDS = 15

# ── Payload helpers ───────────────────────────────────────────────────────────

def rgb565(r: int, g: int, b: int) -> int:
    return ((r >> 3) << 11) | ((g >> 3) << 5) | (b >> 3)


def build_payload(rows: list, row_ms: int = 120, settings: int = 0x08) -> bytes:
    """
    rows     : list of rows, each row is a list of 15 (r, g, b) tuples
    row_ms   : milliseconds to display each row (20–1000)
    settings : bitmask
                 bit 0  SoundMode Beat
                 bit 1  SoundMode Level
                 bit 2  SoundMode Envelope
                 bit 3  SoundMode Always (play regardless of sound)
                 bit 4  LoopMode Bounce
                 bit 5  LoopMode LoopReverse
    """
    data = bytearray()
    for row in rows:
        for (r, g, b) in row[:NUM_LEDS]:
            data += struct.pack('>H', rgb565(r, g, b))
    data.append(settings & 0xFF)
    data += struct.pack('>H', max(20, min(1000, row_ms)))
    return bytes(data)


# ── Built-in effect definitions ───────────────────────────────────────────────

def _solid_row(r: int, g: int, b: int):
    return [(r, g, b)] * NUM_LEDS


def _wheel(pos: int):
    """Simple HSV-style colour wheel, pos 0–255 → (r, g, b)."""
    pos = pos % 256
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)


def effect_rainbow(num_rows: int = 8) -> list:
    """Each row is a full rainbow sweep, shifted across rows."""
    rows = []
    for r in range(num_rows):
        row = [_wheel((i * 256 // NUM_LEDS + r * 32) % 256) for i in range(NUM_LEDS)]
        rows.append(row)
    return rows


def effect_chase(color=(0, 128, 255), num_rows: int = 8) -> list:
    """Single lit pixel chasing across the band."""
    rows = []
    for r in range(num_rows):
        row = [(0, 0, 0)] * NUM_LEDS
        row[r % NUM_LEDS] = color
        rows.append(row)
    return rows


def effect_strobe(color=(255, 255, 255), num_rows: int = 8) -> list:
    """Alternating full-on / full-off rows."""
    on_row  = _solid_row(*color)
    off_row = _solid_row(0, 0, 0)
    return [on_row if r % 2 == 0 else off_row for r in range(num_rows)]


def effect_comet(color=(255, 80, 0), num_rows: int = 8) -> list:
    """Bright head with fading tail moving across the band."""
    rows = []
    for r in range(num_rows):
        row = []
        head = r % NUM_LEDS
        for i in range(NUM_LEDS):
            dist = (head - i) % NUM_LEDS
            if dist == 0:
                row.append(color)
            elif dist <= 4:
                fade = 1.0 - dist / 5.0
                row.append(tuple(int(c * fade) for c in color))
            else:
                row.append((0, 0, 0))
        rows.append(row)
    return rows


BUILT_IN_EFFECTS = {
    #  slot  name          rows-fn               row_ms  settings
    0: ('Rainbow',  effect_rainbow,              80,     0x08),  # Always
    1: ('Chase',    effect_chase,                60,     0x08),
    2: ('Strobe',   effect_strobe,               50,     0x01),  # Beat-sync
    3: ('Comet',    effect_comet,                70,     0x08),
}


# ── Upload logic ──────────────────────────────────────────────────────────────

async def upload_effect(client: BleakClient, slot: int, rows: list,
                        row_ms: int = 120, settings: int = 0x08):
    payload  = build_payload(rows, row_ms, settings)
    num_rows = len(rows)

    # Phase 1 — Begin
    await client.write_gatt_char(FX_CHAR, bytes([0x00, slot, num_rows]))

    # Phase 2 — Data chunks (19 bytes of payload per packet)
    for i in range(0, len(payload), 19):
        chunk = payload[i:i + 19]
        await client.write_gatt_char(FX_CHAR, bytes([0x01]) + chunk)

    # Phase 3 — Commit
    await client.write_gatt_char(FX_CHAR, bytes([0x02, slot]))
    print(f'  ✓ slot {slot} — {num_rows} rows, {len(payload)} bytes')


async def activate_effect(client: BleakClient, slot: int):
    """Send command 0x01 to play a custom effect slot."""
    await client.write_gatt_char(CMD, bytes([0x01, slot]))


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(slots_to_upload: list[int], activate: int | None):
    print('Scanning for LumiBand...')
    device = await BleakScanner.find_device_by_filter(
        lambda d, _: d.name and 'LumiBand' in d.name,
        timeout=10.0,
    )
    if device is None:
        raise RuntimeError('No LumiBand found')
    print(f'Found: {device.name}  {device.address}')

    async with BleakClient(device) as client:
        await client.request_mtu(512)
        print('Connected. Uploading effects...')

        for slot in slots_to_upload:
            name, rows_fn, row_ms, settings = BUILT_IN_EFFECTS[slot]
            print(f'  Uploading slot {slot}: {name}')
            rows = rows_fn()
            await upload_effect(client, slot, rows, row_ms, settings)

        if activate is not None:
            await activate_effect(client, activate)
            print(f'Activated slot {activate}')

        print('Done.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Upload custom effects to LumiBand')
    parser.add_argument('--slot', type=int, choices=list(BUILT_IN_EFFECTS),
                        help='Upload a single slot (default: all)')
    parser.add_argument('--activate', type=int, choices=list(BUILT_IN_EFFECTS),
                        help='Activate a slot after uploading')
    parser.add_argument('--list', action='store_true',
                        help='List available built-in effects and exit')
    args = parser.parse_args()

    if args.list:
        print('Available built-in effects:')
        for slot, (name, *_) in BUILT_IN_EFFECTS.items():
            print(f'  slot {slot}  {name}')
    else:
        slots = [args.slot] if args.slot is not None else list(BUILT_IN_EFFECTS)
        asyncio.run(main(slots, args.activate))
