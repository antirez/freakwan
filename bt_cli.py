import asyncio, logging
from ble_serial.bluetooth.ble_interface import BLE_interface

def receive_callback(value: bytes):
    print("Received:", value)

async def hello_sender(ble: BLE_interface):
    while True:
        await asyncio.sleep(3.0)
        print("Sending...")
        ble.queue_send(b"Hello world\n")

async def main():
    # None uses default/autodetection, insert values if needed
    ADAPTER = "hci0"
    SERVICE_UUID = None
    WRITE_UUID = None
    READ_UUID = None
    DEVICE = "E370F27B-8DDB-62A6-FFE2-896822B786DE"

    ble = BLE_interface(ADAPTER, SERVICE_UUID)
    ble.set_receiver(receive_callback)

    try:
        await ble.connect(DEVICE, "public", 10.0)
        await ble.setup_chars(WRITE_UUID, READ_UUID, "rw")

        await asyncio.gather(ble.send_loop(), hello_sender(ble))
    finally:
        await ble.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
