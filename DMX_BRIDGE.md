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
