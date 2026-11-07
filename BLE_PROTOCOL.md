# LumiBand BLE protocol — reference

A formal byte-level specification of every GATT characteristic and
every command opcode exposed by LumiBand firmware. Target audience:
a developer implementing LumiBand support from scratch. For
tutorial-style docs with copy-paste examples, see [README.md](README.md).

Current spec version: **firmware 1.2.x**. Older-firmware differences
are called out inline and summarised in §10.

---

> **Not what you want?** This document covers the **GATT-connected**
> protocol (one central ↔ one band, pair + write characteristics).
> If you want to drive many bands at once without any connection —
> the way the LumiBridge does — you want the BLE advertising
> broadcast protocol instead. That is a separate wire format; see
> the "**BLE wire format**" section of
> [DMX_BRIDGE.md](DMX_BRIDGE.md) for the byte layout of all three
> packet variants (legacy per-zone, v2 snapshot, assignment).

## 1. Overview

| Property | Value |
|----------|-------|
| Advertising name | `LumiBand` |
| Advertised service UUID | `4fafc201-1fb5-459e-8fcc-c5c9c331914b` |
| Pairing / bonding | None required |
| Concurrency | One central at a time |
| MTU | Negotiate the largest supported (nRF52840 band accepts 512); matters for Effect Upload throughput |
| Endianness | All multi-byte integers are **big-endian** unless noted |
| BLE sleep | Band stops advertising after ~5 min of no central activity; wake via power cycle or opcode `0x04` keep-alive before timeout |

---

## 2. Service + characteristic table

**Service:** `4fafc201-1fb5-459e-8fcc-c5c9c331914b`

| Char | UUID | Properties | Size | Notify |
|------|------|------------|------|--------|
| Command       | `beb54840-36e1-4688-b7f5-ea07361b26a8` | Write           | 1–7+ B   | — |
| Brightness    | `beb5483f-36e1-4688-b7f5-ea07361b26a8` | Write           | 1 B      | — |
| Status        | `beb54842-36e1-4688-b7f5-ea07361b26a8` | Read / Notify   | **7 B**  | ✓ |
| Effect Upload | `beb54841-36e1-4688-b7f5-ea07361b26a8` | Write           | 1–20 B   | — |
| Sync          | `beb54843-36e1-4688-b7f5-ea07361b26a8` | Write           | 4 B      | — |
| Battery Level | `00002a19-0000-1000-8000-00805f9b34fb` | Read            | 1 B      | — |

The Battery Level characteristic sits inside the standard
**Bluetooth Battery Service `0x180F`**, not inside the LumiBand service.
Generic BLE tools (nRF Connect, LightBlue) will show it automatically.

---

## 3. Command characteristic — opcode reference

Every command is `[opcode, payload…]` written to the Command
characteristic with response.

Legend:
- **Persist** = Flash means the band saves to flash and reapplies on
  power-cycle. RAM means change is lost on reboot. Mixed means parts
  of the state are flashed (e.g. `buttonPressCount`) and parts aren't
  (e.g. Classic sub-effect override).
- **Status-notify** = opcode triggers a Status notification once the
  new state takes effect.

| Op | Name                               | Bytes | Persist | Status-notify |
|----|------------------------------------|-------|---------|----------------|
| `0x02` | Activate mode / sub-command    | 2–20+ | Flash   | ✓ |
| `0x03` | Solid colour override          | 5 or 6 | RAM    | — |
| `0x04` | Keep-alive toggle              | 2     | RAM     | — |
| `0x05` | Alarm on/off                   | 2     | RAM     | ✓ |
| `0x06` | Update effect timing in-place  | 5 or 6 | Flash  | — |
| `0x07` | Classic colour + button count  | 3     | Flash   | ✓ (next tick) |
| `0x08` | Exit override                  | 1 or 2 | RAM    | — |
| `0x10` | Super saver                    | 2     | Flash   | — |
| `0x11` | Night mode                     | 3     | Flash   | — |
| `0x12` | Sub-effect picker              | 2     | Mixed   | ✓ |
| `0x20` | DMX zone                       | 2     | Flash   | ✓ |

### 0x02 — Activate mode / sub-command

The 0x02 opcode is overloaded. Second byte is the sub-command selector.

| `d[1]` | Payload tail | Behaviour |
|--------|--------------|-----------|
| `0..4, 6, 7` | — (or custom-count byte for `6`) | Activate built-in mode. Index 0 = Classic, 1 = Static, 2 = Party, 3 = Flame, 4 = Dim, 6 = Custom, 7 = Playlist. Index 5 (Alarm) is reserved — use opcode 0x05 instead. |
| `6` | `[count]` | Activate Custom effect mode, cycling `count` uploaded slots (1–8). |
| `7` | `[count, idx0, idx1, …, idxN]` | Activate Playlist mode with the given sub-effect indices. `count` = length of indices; indices are firmware playlist-table positions (0–48). |
| `8` | `[secHi, secLo]` | Set Playlist slot interval, 1–3600 s (big-endian uint16). |
| `9` | `[secHi, secLo]` | Set Custom slot interval, 1–3600 s. |
| `10`| `[count]` | Re-sync Custom: reset to slot 0 at the current moment without flash save. Use after a Sync-characteristic write. |
| `11`| `[t3, t2, t1, t0]` | Set the Custom effect start-tick to a big-endian uint32 ms value. Advanced sync use. |

### 0x03 — Solid colour override

```
[0x03, R, G, B, Brightness, Strobe?]
```

| Byte | Meaning |
|------|---------|
| R, G, B | Pixel colour, 0–255 each |
| Brightness | Hardware brightness 0 (off) – 255 (full). Bypasses any app-level brightness cap. |
| Strobe *(optional)* | 0 = steady, 1–255 = speed (logarithmic: 1 ≈ 0.25 Hz, 255 ≈ 25 Hz) |

Entering the override pauses the running mode. Exit via opcode 0x08 to
resume the saved mode without having to re-send it.

### 0x04 — Keep-alive toggle

```
[0x04, 0x01]   — disable BLE sleep (band keeps advertising)
[0x04, 0x00]   — re-enable BLE sleep (default)
```

### 0x05 — Alarm on/off

```
[0x05, 0x01]   — Alarm ON  (overrides current mode)
[0x05, 0x00]   — Alarm OFF (restores previous mode + brightness)
```

Alarm captures the current mode / brightness / custom-count on entry
so the OFF transition is lossless.

### 0x06 — Update effect timing in-place

```
[0x06, slot, settings, rowMsHi, rowMsLo, refBpm?]
```

| Byte | Meaning |
|------|---------|
| `slot` | Effect slot 0–7 (must be `effectLoaded`) |
| `settings` | Settings bitmask (see [EFFECT_UPLOAD.md](EFFECT_UPLOAD.md)) |
| `rowMsHi/Lo` | Row-advance interval, big-endian uint16, 20–1000 ms |
| `refBpm` *(optional)* | Reference BPM for BPM-locked mode. 0 = unused. |

Lets a client tweak an already-uploaded effect's cadence without
re-sending pixel data.

### 0x07 — Classic colour + button count

```
[0x07, classicColorIdx, buttonPressCount]
```

| Byte | Meaning |
|------|---------|
| `classicColorIdx` | 0 = auto-hue; 1–8 = pinned to that colour scheme (value modulo 9) |
| `buttonPressCount` | 8-bit press counter — drives Static palette cycling and Party sub-effect cycling. |

Both bytes are flashed. Mirrored in Status bytes `[2]` and `[3]`.
Added in firmware 1.0.

### 0x08 — Exit override

```
[0x08]         — exit colour / strobe override
[0x08, 0x00]   — same, with an unused trailing byte for round-tripping
```

Restores the pre-override brightness and resumes the saved mode. No-op
if no override is active.

### 0x10 — Super saver

```
[0x10, 0x01]   — Super Saver ON  (blanks every other LED, ~50 % power)
[0x10, 0x00]   — Super Saver OFF
```

Persisted in flash. Does not take effect when DMX is streaming (DMX
packets bypass the super-saver gate for full-brightness venue use).

### 0x11 — Night mode

```
[0x11, on, dimBits]
```

| Byte | Meaning |
|------|---------|
| `on` | `1` = enable, `0` = disable |
| `dimBits` | Bit-clamp applied to every channel: `3` = dim, `1` = super dim. Ignored when `on = 0`. |

Locks master brightness to 5 % and clamps channels for near-dark
ambient use. Persisted in flash.

### 0x12 — Sub-effect picker (NEW in 1.2)

```
[0x12, subIdx]
```

Dispatch depends on the currently-active mode:

| Active mode | Effect |
|-------------|--------|
| Classic (0) | `subIdx = 255` resumes the auto-rotating story pointer; any other value pins Classic to sub-effect `subIdx % 15` (STORY_COUNT). Pin is **RAM-only** — reverts to auto on power-cycle. |
| Static  (1) | `subIdx % 20` selects the palette entry. Writes `buttonPressCount` — flashed. |
| Party   (2) | `subIdx % 12` selects the party sub-effect. Writes `buttonPressCount` — flashed. |
| Other       | Ignored; no state change and no Status notification. |

Status byte `[6]` mirrors the new value on the subsequent notify.

### 0x20 — DMX zone

```
[0x20, zoneId]
```

| Value | Meaning |
|-------|---------|
| `0xFF` | Unassigned — band only responds to DMX broadcasts marked as global (DMX addr type `0x00`). |
| `0..7` | Zone number. Band responds to DMX packets addressed to its zone *and* to global broadcasts. |

Persisted in flash. Status byte `[5]` mirrors the current value.

---

## 4. Status characteristic — 7-byte layout

Subscribe to notifications to track the band's state. The band also
pushes a notification on every mode / brightness / DMX / zone / sub-
effect change so a client can stay in sync without polling.

```
[modeIndex, brightness, classicColorIdx, buttonPressCount, dmxActive, zoneId, subIdx]
```

| Byte | Field | Meaning |
|------|-------|---------|
| `[0]` | modeIndex        | 0 = Classic, 1 = Static, 2 = Party, 3 = Flame, 4 = Dim, 5 = Alarm, 6 = Custom, 7 = Playlist |
| `[1]` | brightness       | 0–255 master brightness |
| `[2]` | classicColorIdx  | Active Classic colour-scheme pointer; value modulo 9 picks one of 9 schemes |
| `[3]` | buttonPressCount | 8-bit press counter (wraps at 255). Drives Static palette + Party sub-effect cycling |
| `[4]` | dmxActive        | `1` while DMX-over-BLE is driving the band, `0` otherwise. Edge-triggered: one notification on entry, one on exit (5 s after DMX silence). |
| `[5]` | zoneId           | DMX zone, `0..7` or `0xFF` unassigned. Mirrors opcode `0x20`. |
| `[6]` | subIdx           | Current sub-effect index for the active mode. Classic: `255` = auto, else 0..14. Static / Party: `buttonPressCount % N`. Other modes: `255`. Written by opcode `0x12` or physical button. |

**Backward compatibility.** Clients that read only the first N bytes
(for N < 7) still see valid earlier fields. Firmware < 1.1 doesn't
emit bytes `[5..6]`; firmware < 1.0+ doesn't emit byte `[4]`.
Read defensively: `len = min(available, 7)` and treat missing bytes
as "unknown".

---

## 5. Brightness characteristic

Single-byte write, no opcode.

```
[brightness]      // 0..255
```

Changes the master brightness immediately. Flashed. Does NOT change
colour or active mode. Mirrored in Status byte `[1]`.

---

## 6. Sync characteristic

Four-byte big-endian uint32 — a shared `groupTime` in milliseconds.
Each band sets `syncOffset = groupTime − millis()` and uses that
offset whenever it needs the current position in a repeating
animation cycle. All bands that received the same `groupTime` will
be at the same cycle position regardless of when each one booted.

```
[T3, T2, T1, T0]   // big-endian uint32 ms
```

Has no persistence — a band that reboots loses its `syncOffset` and
needs a fresh Sync write. See README.md §Multi-device Sync for a
Python example driving many bands concurrently.

---

## 7. Effect Upload characteristic

Three-opcode chunked protocol for sending custom LED animations (up
to 8 slots × up to 16 rows × 15 LEDs × RGB565 per slot):

```
[0x00, slot, numRows]      // begin upload
[0x01, ...payload bytes]   // one or more chunks (20 B each over MTU 23)
[0x02]                     // commit — triggers flash write + reload
```

See [EFFECT_UPLOAD.md](EFFECT_UPLOAD.md) for the full byte-level
protocol, chunking rules, settings bitmask, and reference Python
implementation.

---

## 8. Battery Level characteristic

Standard Bluetooth SIG Battery Service `0x180F`, characteristic
`0x2A19`.

```
read → [percent]   // 0..100
```

The nRF52840 ADC path uses the Seed XIAO VBAT divider + a 2.4 V
internal reference. Reads are taken on-demand (band only consumes
the divider current while the characteristic is being read).

No notifications on this characteristic — poll on a schedule if
you want a live gauge. Battery percent is computed against a
resting-cell SoC lookup, so the first read within ~1 min of
unplugging USB will read higher than the eventual resting value.

---

## 9. Firmware version compatibility

| Firmware | Added |
|----------|-------|
| 1.0  | Base protocol: opcodes `0x02` / `0x03` / `0x04` / `0x05` / `0x06` / `0x07` / `0x08`, Status payload 4 bytes `[mode, bright, classicColorIdx, buttonPressCount]` |
| 1.0+ | Opcodes `0x10` (super saver), `0x11` (night mode) |
| 1.1  | Opcode `0x20` (DMX zone), Status byte `[4]` (dmxActive), Status byte `[5]` (zoneId) |
| 1.2  | Opcode `0x12` (sub-effect picker), Status byte `[6]` (subIdx), `Lava` renamed to `Flame` (byte value 3 unchanged) |

Clients implementing graceful degradation should prefer a "read what
is there, ignore what is not" pattern: write newer opcodes
unconditionally (older firmware ignores unknown bytes), read Status
with `min(available, 7)`, and never assume fields beyond the
firmware version you targeted.
