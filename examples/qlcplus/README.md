# LumiBand — QLC+ files

[QLC+](https://qlcplus.org) is a free, open-source lighting control application.
These files let you control LumiBand from QLC+ via **OSC** over UDP.

## Files

| File | Purpose |
|------|---------|
| `LumiBand.qxf` | Fixture definition — install once into QLC+ |
| `LumiBand_OSC.qxw` | Ready-to-use workspace with sliders and scene buttons |

---

## Setup

### 1. Install the fixture definition (optional)
Copy `LumiBand.qxf` to your QLC+ user fixtures folder:

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/QLC+/fixtures/` |
| Linux | `~/.qlcplus/fixtures/` |
| Windows | `C:\Users\<you>\QLC+\fixtures\` |

### 2. Open the workspace
Open `LumiBand_OSC.qxw` in QLC+.

### 3. Configure the OSC output address
1. Go to **Inputs/Outputs** → **OSC** tab
2. Set the **Output address** to your phone's IP address (e.g. `192.168.1.42`)
3. Output port: **9000** (default — no change needed)

> Tip: find your phone's IP in Settings → Wi-Fi → tap your network.
> The phone and the computer running QLC+ must be on the same Wi-Fi network.

### 4. Enable the universe and go live
- Toggle the universe output **on**
- Switch to the **Virtual Console** tab
- Use the **Red / Green / Blue / Brightness** sliders or the scene buttons

---

## OSC address format

QLC+ sends one message per channel using the path:
```
/<universe-1>/dmx/<channel-1>
```
with a **float 0.0–1.0** argument.

The LumiBand app maps channels relative to the configured **DMX start address**
(default 1):

| Channel offset | Function |
|---------------|----------|
| +0 | Red |
| +1 | Green |
| +2 | Blue |
| +3 | Brightness |

---

## Alternatives

QLC+ also supports **Art-Net** and **sACN (E1.31)** natively — both work with
LumiBand. OSC is the simplest option if you just want the sliders without
configuring a full DMX universe.
