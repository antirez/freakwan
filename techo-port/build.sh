arduino-cli compile --fqbn adafruit:nrf52:pca10056 . || exit
arduino-cli upload -p /dev/tty.usbmodem11201 --fqbn adafruit:nrf52:pca10056 .
