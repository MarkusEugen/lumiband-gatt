// LumiBand BLE controller — Kotlin / Android example
// Min SDK: Android 8 (API 26). Uses standard android.bluetooth APIs.
// Required permissions in AndroidManifest.xml:
//   Android 12+ (API 31+): BLUETOOTH_SCAN, BLUETOOTH_CONNECT
//   Android 11 and below:  BLUETOOTH, BLUETOOTH_ADMIN, ACCESS_FINE_LOCATION

package com.example.lumiband

import android.bluetooth.*
import android.bluetooth.le.*
import android.content.Context
import android.os.ParcelUuid
import java.util.UUID

private val SERVICE = UUID.fromString("4fafc201-1fb5-459e-8fcc-c5c9c331914b")
private val CMD     = UUID.fromString("beb54840-36e1-4688-b7f5-ea07361b26a8")
private val BRIGHT  = UUID.fromString("beb5483f-36e1-4688-b7f5-ea07361b26a8")
private val STATUS  = UUID.fromString("beb54842-36e1-4688-b7f5-ea07361b26a8")

private val CCCD    = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb") // notify descriptor

// MARK: - Listener interface

interface LumiBandListener {
    fun onConnected()
    fun onDisconnected()
    fun onStatusUpdate(mode: Int, brightness: Int)
}

// MARK: - Controller

class LumiBandController(private val context: Context) {

    var listener: LumiBandListener? = null

    private val adapter: BluetoothAdapter =
        (context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter

    private var gatt: BluetoothGatt? = null
    private var cmdChar:    BluetoothGattCharacteristic? = null
    private var brightChar: BluetoothGattCharacteristic? = null
    private var scanner:    BluetoothLeScanner? = null

    // MARK: Scanning

    fun startScan() {
        scanner = adapter.bluetoothLeScanner
        val filter   = ScanFilter.Builder()
            .setServiceUuid(ParcelUuid(SERVICE))
            .build()
        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()
        scanner?.startScan(listOf(filter), settings, scanCallback)
    }

    fun stopScan() {
        scanner?.stopScan(scanCallback)
        scanner = null
    }

    fun disconnect() {
        gatt?.disconnect()
    }

    // MARK: Commands

    /** Set solid colour. r/g/b/brightness: 0–255. strobe: 0=steady, 1–255=speed (1≈1Hz→255≈25Hz). */
    fun setColor(r: Int, g: Int, b: Int, brightness: Int = 255, strobe: Int = 0) {
        write(byteArrayOf(0x03, r.toByte(), g.toByte(), b.toByte(), brightness.toByte(), strobe.toByte()),
              withResponse = false)
    }

    /** Set master brightness (0–255) without changing colour. */
    fun setBrightness(value: Int) {
        val char = brightChar ?: return
        writeChar(char, byteArrayOf(value.toByte()), withResponse = true)
    }

    /**
     * Activate a built-in preset.
     * 0 = Classic, 1 = Static, 2 = Party, 3 = Lava, 4 = Dim
     */
    fun setPreset(index: Int) {
        write(byteArrayOf(0x02, index.toByte()), withResponse = true)
    }

    /** Release any override and resume the band's saved mode. */
    fun exitOverride() {
        write(byteArrayOf(0x08, 0x00), withResponse = true)
    }

    // MARK: Private helpers

    private fun write(bytes: ByteArray, withResponse: Boolean) {
        writeChar(cmdChar ?: return, bytes, withResponse)
    }

    @Suppress("DEPRECATION")
    private fun writeChar(char: BluetoothGattCharacteristic, bytes: ByteArray, withResponse: Boolean) {
        val g = gatt ?: return
        val writeType = if (withResponse)
            BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
        else
            BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE

        // API 33+ uses the non-deprecated overload; older builds use the deprecated field setter
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            g.writeCharacteristic(char, bytes, writeType)
        } else {
            char.writeType = writeType
            char.value = bytes
            g.writeCharacteristic(char)
        }
    }

    // MARK: Scan callback

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            if (result.device.name?.contains("LumiBand") == true) {
                stopScan()
                gatt = result.device.connectGatt(context, false, gattCallback,
                    BluetoothDevice.TRANSPORT_LE)
            }
        }
    }

    // MARK: GATT callback

    private val gattCallback = object : BluetoothGattCallback() {

        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                g.requestMtu(512)      // improves effect upload speed
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                cmdChar = null
                brightChar = null
                gatt = null
                listener?.onDisconnected()
            }
        }

        override fun onMtuChanged(g: BluetoothGatt, mtu: Int, status: Int) {
            g.discoverServices()
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            val service = g.getService(SERVICE) ?: return
            cmdChar    = service.getCharacteristic(CMD)
            brightChar = service.getCharacteristic(BRIGHT)

            // Enable status notifications
            val statusChar = service.getCharacteristic(STATUS) ?: return
            g.setCharacteristicNotification(statusChar, true)
            val descriptor = statusChar.getDescriptor(CCCD)
            if (android.os.Build.VERSION.SDK_INT >= 33) {
                g.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
            } else {
                @Suppress("DEPRECATION")
                descriptor.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                @Suppress("DEPRECATION")
                g.writeDescriptor(descriptor)
            }

            listener?.onConnected()
        }

        @Suppress("DEPRECATION", "OVERRIDE_DEPRECATION")
        override fun onCharacteristicChanged(
            g: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic
        ) {
            if (characteristic.uuid != STATUS) return
            val data = characteristic.value ?: return
            if (data.size < 2) return
            listener?.onStatusUpdate(data[0].toInt() and 0xFF, data[1].toInt() and 0xFF)
        }

        // API 33+ callback — delegates to the pre-33 override above for shared handling
        override fun onCharacteristicChanged(
            g: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            value: ByteArray
        ) {
            if (characteristic.uuid != STATUS || value.size < 2) return
            listener?.onStatusUpdate(value[0].toInt() and 0xFF, value[1].toInt() and 0xFF)
        }
    }
}
