# Device-specific MicroPython images

For most devices you can just use a default image distributed by MicroPython. Don't bother getting images for Lilygo devices, just download the image for your ESP32 board (vanilla or S3) or use the ones provided here.

Unfortunately, sometimes the default provided in the MicroPython website does not work as expected (for example the T3-S3 has a 4MB flash instead of 8MB, and this create issues with the image MicroPython distributes). In this case you need to either use the image we provide here or build your own MicroPython image from source.

In this directory you will find:

**T3-S3** image: modified for 4MB flash. SPIRAM support enabled.
**T3 and T-BEAM** image: this image is good for old T3/T-BEAM devices not based on the S3 chip. This is just the MicroPython ESP32-GENERIC image without any changes, here just for your convenience.
