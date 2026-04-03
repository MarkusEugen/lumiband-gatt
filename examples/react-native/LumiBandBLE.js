/**
 * LumiBand BLE controller — React Native example
 * Requires: react-native-ble-plx
 *   npm install react-native-ble-plx
 *   npx pod-install  (iOS)
 */

import { BleManager } from 'react-native-ble-plx';
import { Buffer } from 'buffer';

const SERVICE = '4fafc201-1fb5-459e-8fcc-c5c9c331914b';
const CMD     = 'beb54840-36e1-4688-b7f5-ea07361b26a8';
const BRIGHT  = 'beb5483f-36e1-4688-b7f5-ea07361b26a8';
const STATUS  = 'beb54842-36e1-4688-b7f5-ea07361b26a8';

const manager = new BleManager();

// ── Discovery ─────────────────────────────────────────────────────────────────

export function scanForLumiBand(onFound) {
  manager.startDeviceScan([SERVICE], null, (error, device) => {
    if (error) { console.error(error); return; }
    if (device?.name?.includes('LumiBand')) {
      manager.stopDeviceScan();
      onFound(device);
    }
  });
}

// ── Connection ────────────────────────────────────────────────────────────────

export async function connect(device) {
  const connected = await device.connect({ requestMTU: 512 });
  await connected.discoverAllServicesAndCharacteristics();
  return connected;
}

// ── Commands ──────────────────────────────────────────────────────────────────

/** Set solid colour. r/g/b/brightness: 0–255. strobe: 0=steady, 1–255=speed (1≈0.25Hz→255≈25Hz). */
export async function setColor(device, r, g, b, brightness = 255, strobe = 0) {
  const bytes = Buffer.from([0x03, r, g, b, brightness, strobe]);
  await device.writeCharacteristicWithoutResponseForService(SERVICE, CMD, bytes.toString('base64'));
}

/** Set master brightness (0–255) without changing colour. */
export async function setBrightness(device, brightness) {
  const bytes = Buffer.from([brightness]);
  await device.writeCharacteristicWithResponseForService(SERVICE, BRIGHT, bytes.toString('base64'));
}

/** Activate a built-in preset (0=Classic, 1=Static, 2=Party, 3=Lava, 4=Dim). */
export async function setPreset(device, index) {
  const bytes = Buffer.from([0x02, index]);
  await device.writeCharacteristicWithResponseForService(SERVICE, CMD, bytes.toString('base64'));
}

/** Release any override and resume the band's saved mode. */
export async function exitOverride(device) {
  const bytes = Buffer.from([0x08, 0x00]);
  await device.writeCharacteristicWithResponseForService(SERVICE, CMD, bytes.toString('base64'));
}

// ── Status notifications ──────────────────────────────────────────────────────

/**
 * Subscribe to status updates.
 * callback receives { mode: number, brightness: number }
 * Returns a subscription — call subscription.remove() to stop.
 */
export function subscribeStatus(device, callback) {
  return device.monitorCharacteristicForService(SERVICE, STATUS, (error, char) => {
    if (error || !char?.value) return;
    const bytes = Buffer.from(char.value, 'base64');
    callback({ mode: bytes[0], brightness: bytes[1] });
  });
}

// ── Example usage ─────────────────────────────────────────────────────────────

/*
scanForLumiBand(async (device) => {
  const connected = await connect(device);

  const sub = subscribeStatus(connected, ({ mode, brightness }) => {
    console.log(`mode=${mode}  brightness=${brightness}`);
  });

  await setColor(connected, 255, 0, 0);      // red
  await new Promise(r => setTimeout(r, 1000));

  await setColor(connected, 0, 255, 0);      // green
  await new Promise(r => setTimeout(r, 1000));

  await setPreset(connected, 0);             // Classic
  await new Promise(r => setTimeout(r, 3000));

  await exitOverride(connected);
  sub.remove();
});
*/
