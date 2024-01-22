install: axp192.mpy bt.mpy clictrl.mpy dutycycle.mpy fci.mpy font4x6.mpy freakwan.mpy history.mpy icons.mpy keychain.mpy message.mpy networking.mpy scroller.mpy splash.mpy sx1276.mpy sensor.mpy
	talk32 /dev/tty.wchusbserial* put *.mpy main.py

%.mpy: %.py
	mpy-cross $<
