# DMX / Art-Net / sACN control via the LumiBand bridge

LumiBand supports standard DMX-over-Ethernet protocols for stage, venue and installation use. A compact Art-Net / sACN → BLE bridge sits on your network, receives DMX from any console or lighting software, and broadcasts to every band in range. From the console's point of view, each bridge looks like a single 32-channel RGB fixture with 8 zones.

The band's BLE GATT API ([README.md](README.md)) continues to work in parallel — zone assignment, battery, status notifications and effect uploads are still done over BLE. The bridge adds the DMX side; it doesn't replace the GATT API.

---

## Architecture

```
┌───────────────┐  Art-Net / sACN   ┌─────────────┐  BLE adv broadcast  ┌─────────┐
│ Lighting      │ ────────────────▶ │ LumiBridge  │ ──────────────────▶ │ LumiBand│
│ console / sw  │   UDP over LAN    │ ESP32 + ETH │   29-byte snapshot  │ (any N) │
└───────────────┘                   └─────────────┘    every ~40 ms     └─────────┘
```

- The bridge is a passive translator: it does not connect to bands, it only broadcasts. There is no pairing, no addressing, no connection limit — any band in BLE range receives the broadcast and renders its own zone's slot.
- Each bridge consumes **32 contiguous DMX channels** from a start address you set via its web UI.
- Bands are assigned to one of **8 zones** via the GATT `0x20 DMX zone` command (see [README.md#dmx-zone](README.md)) or by a long-press gesture on the band itself.

---

## DMX channel map

| Zone | Red       | Green     | Blue      | Brightness |
|:----:|:---------:|:---------:|:---------:|:----------:|
| 0    | start + 0 | start + 1 | start + 2 | start + 3  |
| 1    | start + 4 | start + 5 | start + 6 | start + 7  |
| 2    | start + 8 | start + 9 | start +10 | start +11  |
| 3    | start +12 | start +13 | start +14 | start +15  |
| 4    | start +16 | start +17 | start +18 | start +19  |
| 5    | start +20 | start +21 | start +22 | start +23  |
| 6    | start +24 | start +25 | start +26 | start +27  |
| 7    | start +28 | start +29 | start +30 | start +31  |

Default start address is `1`; configurable `1–481` via the bridge web UI. The Brightness channel is a per-zone master dimmer applied by the bridge before transmission — the final RGB arriving at the band is `(R, G, B) × Brightness / 255`.

> There is no "effect index" channel. The band renders a solid colour per zone under DMX control; chases, fades, strobes, and other time-based effects are produced by your console animating the DMX values exactly like for any other RGB fixture.

---

## Supported protocols

### Art-Net

- **Transport:** UDP, port `6454`
- **Packet type:** standard ArtDmx
- **Universe:** the bridge is universe-agnostic — it accepts any universe. If your console must emit a specific universe, use anything; the bridge does not filter.
- **Addressing:** broadcast to `255.255.255.255` or unicast to the bridge's IP.

### sACN (ANSI E1.31)

- **Transport:** UDP, port `5568`
- **Multicast group:** `239.255.<hi>.<lo>` where `hi` / `lo` are the upper and lower bytes of the universe number. Universe `1` → `239.255.0.1`.
- **Universe:** configurable `1–63999` via the bridge web UI (per ANSI E1.31-2018 §6.7.1).
- **Unicast fallback:** sACN packets sent directly to the bridge's IP on port 5568 are also accepted for consoles that prefer unicast.

### Discovery

The bridge advertises itself on the LAN over mDNS as **`lumibridge.local`** (first bridge on the LAN wins the well-known name; additional bridges fall back to `lumibridge-XXXX.local` where `XXXX` is the last 2 bytes of the ESP32 MAC). Most modern consoles and OSes resolve `.local` names automatically.

---

## Zone assignment — tie-in with the BLE API

Zones are a band-side concept. The bridge broadcasts all 8 zones' RGB in one packet; each band picks out its own zone's 3 bytes. To assign a band to zone `N`, write to the Command characteristic (see [README.md#dmx-zone](README.md)):

```
[0x20, N]        → assign to zone N (0–7)
[0x20, 0xFF]     → unassigned (defaults to zone 0 under DMX)
```

The assignment is persisted in flash, so the band remembers its zone across power cycles.

> When DMX packets arrive, the band renders their colour and pauses its normal (preset / audio-reactive) mode. The band stays in DMX mode for the rest of the session; power-cycle to resume preset playback. The Status characteristic's byte `[4]` reports `dmxActive = 1` while under DMX control — see [README.md](README.md#status-notifications).

---

## Setup

1. Plug the bridge into Ethernet. It gets its IP via DHCP (static reservation also fine).
2. Browse to `http://lumibridge.local/`.
3. Set the DMX start address (1–481). Default `1`.
4. If using sACN: set the universe (1–63999). Default `1` → multicast group `239.255.0.1`.
5. Point your lighting console at the bridge: Art-Net broadcast, or sACN multicast on the configured universe.

### QLC+ example

A ready-made QLC+ workspace with 8 zones pre-wired is in the main repo at `arduino/dmx_ble_bridge/qlc_test_zones.qxw`. Open it in QLC+ 5.x, set the sACN output to your network interface and the configured universe, and the per-zone sliders drive the bands directly.

Additional QLC+ configuration examples live in [`examples/qlcplus/`](examples/qlcplus/) alongside the single-band OSC examples.

---

## Multi-bridge coverage

For larger venues where one bridge's BLE range doesn't cover the whole floor, deploy **2–4 bridges** on the same LAN. All bridges receive identical DMX via sACN multicast, broadcast identical BLE content, and bands render from whichever bridge they hear best. No per-bridge configuration needed beyond the shared start address and universe. Expected BLE range at the bridge's +9 dBm Tx power is roughly 15–30 m indoors depending on obstructions.

---

## BLE wire format — build your own bridge

If you want to drive LumiBands from your own hardware (a custom ESP32
sketch, an nRF52 dongle, a Raspberry Pi with BlueZ, anything that can
emit raw BLE advertising packets) you do **not** need to use the
LumiBridge. The bands listen for a specific manufacturer-data payload
in non-connectable BLE advertising packets and render whatever matches.

**Why broadcast, not GATT?** The GATT path (see [README.md](README.md)
and [BLE_PROTOCOL.md](BLE_PROTOCOL.md)) is one central ↔ one band.
Great for the phone app, useless for lighting a venue of 200 bands.
Broadcast is one-to-many, needs no pairing, has no connection limit,
and a single packet re-transmitted at ~25 Hz keeps every band in
range synchronised.

### Advertising-packet requirements

- **PDU type:** non-connectable (ADV_NONCONN_IND) is fine; connectable
  works too but wastes airtime. 
- **AD type:** `0xFF` (Manufacturer Specific Data).
- **Company ID:** the first two bytes of the manufacturer-data payload
  are `0xFF 0xFF` (little-endian). This is an "unofficial" company ID
  used purely as a tunnel marker — bands filter on it. Not a Bluetooth
  SIG assignment.
- **Marker byte:** `[2] = 0x4C` (ASCII `L`). Bands ignore any
  manufacturer packet without this.
- **Packet type byte:** `[3]` selects which of the three packet
  variants is being sent (see below).
- **Re-send cadence:** the production bridge broadcasts at ~25 Hz
  (40 ms interval). Bands scan at 100 % duty cycle with the scanner
  only paused during their own peripheral advertising, so one packet
  per DMX frame is enough.

### Packet variant 1 — legacy per-zone (9 bytes)

Carries one zone's colour + brightness. Original format, still
supported for backward compatibility with older bridges.

```
Byte  Value   Meaning
[0]   0xFF    Company ID (LE) 0xFFFF
[1]   0xFF
[2]   0x4C    'L' marker
[3]   addr    0x00 = global (every band matches)
              0x01 = zone-specific (match when [4] == band's zoneId)
[4]   zone    Zone id, 0..7 (only when [3] == 0x01)
[5]   R       Red,        0..255
[6]   G       Green,      0..255
[7]   B       Blue,       0..255
[8]   Bright  Brightness, 0..255
```

If you have only one "zone" in your scene, broadcast with
`[3] = 0x00` and every band in range will render your RGB+brightness
regardless of its assigned zone. For per-zone control, send one
packet per zone with `[3] = 0x01` and `[4] = <zoneId>`.

### Packet variant 2 — zone snapshot (29 bytes)

What the production bridge actually emits. Carries **all 8 zones**
of RGB in one packet, so a single 40 ms re-broadcast keeps the whole
venue painted. No per-zone brightness (raw RGB; the band's master
brightness still applies).

```
Byte       Value   Meaning
[0..1]     0xFF 0xFF   Company ID
[2]        0x4C        'L' marker
[3]        0x02        v2 snapshot marker
[4+z*3+0]  R           Zone z's red
[4+z*3+1]  G           Zone z's green
[4+z*3+2]  B           Zone z's blue     (z = 0..7)
```

Total payload: 4 + 24 = 28 bytes of manufacturer data (fits the 29-byte
legacy-advertising cap). Bands with `zoneId <= 7` pick out their three
bytes; bands with `zoneId = 0xFF` (unassigned) render zone 0.

### Packet variant 3 — zone assignment (5 bytes)

Mass-provisioning signal. A band that receives this packet
**unconditionally adopts** the advertised zone, persists it to flash,
and shows a colour-bar zone-number display on its LEDs as an operator
confirmation (display stays on until the band is powered off).

```
Byte  Value   Meaning
[0]   0xFF    Company ID
[1]   0xFF
[2]   0x4C    'L' marker
[3]   0x03    Assignment marker
[4]   zone    Target zone, 0..7
```

Use case: a bridge in "provisioning mode" (operator action) sends only
this packet variant for a brief window; every band powered on near the
bridge during that window receives it and self-assigns to the given
zone. Lets you re-provision a pile of pre-assigned bands without
handling each one individually.

Assignment packets do **NOT** flip the band into DMX-locked mode —
they only write the zone. The band keeps running whatever preset /
Custom / Playlist was previously active. To actually light the band
from DMX, follow up with variant 1 or 2 packets.

### Band-side behaviour after first match

The first packet (variant 1 or 2) that passes filtering latches the
band into **DMX lockout** mode:

- Band stops BLE advertising and force-disconnects any connected phone
  (scanner-only dedicates the radio to listening for the next DMX
  packet).
- Band sets `dmxActive = true`, notifies its Status characteristic (so
  any observer that was previously connected sees byte `[4] = 1`).
- Band **never automatically exits** DMX mode until the next power
  cycle. A brief packet gap doesn't drop the lock — the band keeps
  rendering the last-known RGB/brightness. This is deliberate; ad-hoc
  recovery when packets stop would create flicker on crowded airwaves.
- If no further DMX is heard after 5 s, the Status byte `[4]`
  transitions back to `0` to notify any still-connected GATT observers
  (edge-triggered notification), but the lockout itself persists.

### Minimal reference implementation (Python + bluepy on Linux)

Linux doesn't expose raw BLE advertising through BlueZ's D-Bus layer
cleanly, so most prototypes use a small helper like `bless` or raw
HCI commands. Here's the shape of the advertising payload builder;
drop it into whatever stack you already have:

```python
def make_snapshot_packet(zone_rgbs: list[tuple[int, int, int]]) -> bytes:
    """Build a v2 snapshot payload for zones 0..7. Pad with (0,0,0) for
    unused zones. Returns the manufacturer-data bytes (not the full
    HCI advertising frame — wrap according to your BLE stack)."""
    assert 1 <= len(zone_rgbs) <= 8
    pkt = bytearray([0xFF, 0xFF, 0x4C, 0x02])
    for i in range(8):
        r, g, b = zone_rgbs[i] if i < len(zone_rgbs) else (0, 0, 0)
        pkt += bytes([r & 0xFF, g & 0xFF, b & 0xFF])
    return bytes(pkt)   # 28 bytes
```

Re-broadcast this payload at ~25 Hz with the AD type set to `0xFF`
(Manufacturer Specific Data). Any LumiBand in range will render.

---

## Technical summary

| | |
|---|---|
| Bridge hardware | ESP32-S3 + W5500 Ethernet, USB-C powered |
| Protocols | Art-Net (UDP 6454), sACN E1.31 (UDP 5568) |
| Zones per bridge | 8 |
| DMX channels per bridge | 32 contiguous |
| Discovery | mDNS as `lumibridge.local` |
| Configuration UI | `http://lumibridge.local/` |
| End-to-end latency | ~40 ms (bounded by the BLE re-broadcast cycle at 25 Hz) |
| Bands per bridge | unlimited within radio range |
| Multi-bridge mode | identical DMX content on every bridge; bands render from whichever they hear best |

---

## Known limits

- Hard cap of **8 zones** per bridge (bounded by the BLE legacy advertising payload size, 29 bytes).
- All bands within a zone show identical colour; **per-band or per-LED addressing over DMX is not supported**.
- **One-way broadcast** — bands do not report state back to the bridge or console. For state feedback use the BLE Status characteristic directly against the band.
- When a band locks onto DMX, its **audio-reactive animations are disabled** until the next power cycle.
- **No RS485 wire-level DMX512 input.** Art-Net or sACN only.

---

## Firmware source

Bridge firmware source and build instructions live in the main LumiBand repo. The firmware is open; you can flash your own bridge from a Waveshare ESP32-S3-ETH board (or compatible) and modify the behaviour. The current release is **v2.4.1**.
