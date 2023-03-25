arduino-cli compile --fqbn adafruit:nrf52:pca10056 . || exit
arduino-cli upload -p /dev/tty.usbmodem1* --fqbn adafruit:nrf52:pca10056 .
