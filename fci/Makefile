all: pngtofci

pngtofci: pngtofci.c
	$(CC) -O3 pngtofci.c `libpng-config --cflags` `libpng-config --L_opts` `libpng-config --libs` -lm -o pngtofci -Wall -W

clean:
	rm -f pngtofci
