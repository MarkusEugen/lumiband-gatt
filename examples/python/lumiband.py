"""
LumiBand BLE controller — Python example
Requires: pip install bleak
"""

import asyncio
from bleak import BleakScanner, BleakClient

SERVICE  = '4fafc201-1fb5-459e-8fcc-c5c9c331914b'
CMD      = 'beb54840-36e1-4688-b7f5-ea07361b26a8'
BRIGHT   = 'beb5483f-36e1-4688-b7f5-ea07361b26a8'
STATUS   = 'beb54842-36e1-4688-b7f5-ea07361b26a8'
BATTERY  = '00002a19-0000-1000-8000-00805f9b34fb'


async def find_lumiband():
    """Scan and return the first LumiBand device found."""
    print('Scanning...')
    device = await BleakScanner.find_device_by_filter(
        lambda d, _: d.name and 'LumiBand' in d.name,
        timeout=10.0,
    )
    if device is None:
        raise RuntimeError('No LumiBand found')
    print(f'Found: {device.name}  {device.address}')
    return device


async def set_color(client, r, g, b, brightness=255, strobe=0):
    """Set solid colour. r/g/b/brightness: 0–255. strobe: 0=steady, 1-255=speed (1≈1Hz→255≈25Hz)."""
    await client.write_gatt_char(CMD, bytes([0x03, r, g, b, brightness, strobe]))


async def set_brightness(client, brightness):
    """Set master brightness (0–255) without changing colour."""
    await client.write_gatt_char(BRIGHT, bytes([brightness]))


async def set_preset(client, index):
    """Activate a built-in preset (0=Classic, 1=Static, 2=Party, 3=Lava, 4=Dim)."""
    await client.write_gatt_char(CMD, bytes([0x02, index]))


async def exit_override(client):
    """Release any override and resume the band's saved mode."""
    await client.write_gatt_char(CMD, bytes([0x08, 0x00]))


async def read_battery(client):
    """Read battery level. Returns 0–100 (percent)."""
    val = await client.read_gatt_char(BATTERY)
    return val[0]


def on_status(_, data):
    mode, bright = data[0], data[1]
    print(f'Status — mode={mode}  brightness={bright}')


async def main():
    device = await find_lumiband()

    async with BleakClient(device) as client:
        # MTU is negotiated automatically on macOS/CoreBluetooth.
        # On Linux/BlueZ you can request it: await client.request_mtu(512)
        if hasattr(client, 'request_mtu'):
            await client.request_mtu(512)

        # Read battery level
        battery = await read_battery(client)
        print(f'Battery: {battery} %')

        # Subscribe to status notifications
        await client.start_notify(STATUS, on_status)

        # Red
        await set_color(client, 255, 0, 0)
        await asyncio.sleep(1)

        # Green
        await set_color(client, 0, 255, 0)
        await asyncio.sleep(1)

        # Blue
        await set_color(client, 0, 0, 255)
        await asyncio.sleep(1)

        # Classic sound-reactive preset
        await set_preset(client, 0)
        await asyncio.sleep(3)

        # Return to saved mode
        await exit_override(client)


if __name__ == '__main__':
    asyncio.run(main())
