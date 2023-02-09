import asyncio
from ble_serial.scan import main as scanner


async def main():
    ADAPTER = "hci0"
    SCAN_TIME = 5  # seconds
    SERVICE_UUID = None  # optional filtering

    devices = await scanner.scan(ADAPTER, SCAN_TIME, SERVICE_UUID)

    print()  # newline
    scanner.print_list(devices)

    # manual indexing
    print(devices[0].name, devices[0].address)

    # ### deep scan get's services/characteristics
    # DEVICE = "4C:75:25:D7:41:06"
    DEVICE = "0C:8B:95:AA:77:F6"
    services = await scanner.deep_scan(DEVICE, devices)
    #
    scanner.print_details(services)
    print()  # newline
    #
    # # manual indexing by uuid
    # print(services.get_service("0000ffe0-0000-1000-8000-00805f9b34fb"))
    # print(services.get_characteristic("0000ffe1-0000-1000-8000-00805f9b34fb"))
    # # or by handle
    # print(services.services[16])
    # print(services.characteristics[17])


if __name__ == "__main__":
    asyncio.run(main())
