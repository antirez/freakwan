#!/bin/sh
btecli:	main.m SerialBTE.m SerialBTE.h
	clang -framework Foundation -framework CoreBluetooth main.m SerialBTE.m linenoise.c -g -ggdb -o btecli

clean:
	rm -f btecli
