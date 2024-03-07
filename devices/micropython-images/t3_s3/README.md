# T3-S3 image modified for 4MB flash

The micropython image for S3 defaults to 8MB flash. To fix it, we need `mp-image-tool-esp32`. This is an utility that can modify MicroPython images avoiding to recompile to just change a little parameter:

    ./mp-image-tool-esp32 ../ESP32_GENERIC_S3-SPIRAM_OCT-20240222-v1.22.2.bin -f 4M --resize vfs=0

We will obtain a new image file this way (the old file will not be overwritten). Now we are ready to install MicroPython flashing the device. Make sure to reboot the T3-S3 while pushing the *boot* button, otherwise you will not be able to flash the device.

First of all, erease the flash memory.

    esptool.py --chip esp32s3 --port /dev/tty.usbmodem1201 erase_flash

Followed by:

    esptool.py --chip esp32s3 --port /dev/tty.usbmodem1201 write_flash -z 0 ESP32_GENERIC_S3-SPIRAM_OCT-20240222-v1.22.2-4MB-resize=vfs.bin
