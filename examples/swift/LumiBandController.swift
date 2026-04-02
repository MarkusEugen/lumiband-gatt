// LumiBand BLE controller — Swift / CoreBluetooth example
// Works on iOS 13+ and macOS 10.15+
// Add CoreBluetooth.framework to your target.

import CoreBluetooth

private let kService  = CBUUID(string: "4fafc201-1fb5-459e-8fcc-c5c9c331914b")
private let kCmd      = CBUUID(string: "beb54840-36e1-4688-b7f5-ea07361b26a8")
private let kBright   = CBUUID(string: "beb5483f-36e1-4688-b7f5-ea07361b26a8")
private let kStatus   = CBUUID(string: "beb54842-36e1-4688-b7f5-ea07361b26a8")

// MARK: - Delegate protocol

protocol LumiBandDelegate: AnyObject {
    func lumiBandDidConnect()
    func lumiBandDidDisconnect()
    func lumiBandStatusDidUpdate(mode: UInt8, brightness: UInt8)
}

// MARK: - Controller

final class LumiBandController: NSObject {

    weak var delegate: LumiBandDelegate?

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var cmdChar:    CBCharacteristic?
    private var brightChar: CBCharacteristic?

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: nil)
    }

    // MARK: Scanning

    func startScan() {
        guard central.state == .poweredOn else { return }
        central.scanForPeripherals(withServices: [kService])
    }

    func stopScan() { central.stopScan() }

    // MARK: Commands

    /// Set solid colour. Values 0–255.
    func setColor(r: UInt8, g: UInt8, b: UInt8, brightness: UInt8 = 255) {
        write(bytes: [0x03, r, g, b, brightness], withResponse: false)
    }

    /// Set master brightness (0–255) without changing colour.
    func setBrightness(_ value: UInt8) {
        guard let char = brightChar, let p = peripheral else { return }
        p.writeValue(Data([value]), for: char, type: .withResponse)
    }

    /// Activate a built-in preset.
    /// 0 = Classic, 1 = Static, 2 = Party, 3 = Lava, 4 = Dim
    func setPreset(_ index: UInt8) {
        write(bytes: [0x02, index], withResponse: true)
    }

    /// Release any override and resume the band's saved mode.
    func exitOverride() {
        write(bytes: [0x08, 0x00], withResponse: true)
    }

    // MARK: Private

    private func write(bytes: [UInt8], withResponse: Bool) {
        guard let char = cmdChar, let p = peripheral else { return }
        let type: CBCharacteristicWriteType = withResponse ? .withResponse : .withoutResponse
        p.writeValue(Data(bytes), for: char, type: type)
    }
}

// MARK: - CBCentralManagerDelegate

extension LumiBandController: CBCentralManagerDelegate {

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn { startScan() }
    }

    func centralManager(_ central: CBCentralManager,
                        didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any], rssi: NSNumber) {
        guard peripheral.name?.contains("LumiBand") == true else { return }
        self.peripheral = peripheral
        central.stopScan()
        central.connect(peripheral)
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.delegate = self
        peripheral.discoverServices([kService])
    }

    func centralManager(_ central: CBCentralManager,
                        didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        cmdChar = nil; brightChar = nil
        self.peripheral = nil
        delegate?.lumiBandDidDisconnect()
    }
}

// MARK: - CBPeripheralDelegate

extension LumiBandController: CBPeripheralDelegate {

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard let service = peripheral.services?.first(where: { $0.uuid == kService }) else { return }
        peripheral.discoverCharacteristics([kCmd, kBright, kStatus], for: service)
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        for char in service.characteristics ?? [] {
            switch char.uuid {
            case kCmd:    cmdChar    = char
            case kBright: brightChar = char
            case kStatus:
                peripheral.setNotifyValue(true, for: char)
            default: break
            }
        }
        delegate?.lumiBandDidConnect()
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard characteristic.uuid == kStatus,
              let data = characteristic.value, data.count >= 2 else { return }
        delegate?.lumiBandStatusDidUpdate(mode: data[0], brightness: data[1])
    }
}
