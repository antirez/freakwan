#include <stdio.h>
#include <string.h>
#include <ctype.h>
#include <stdlib.h>

/* 128 common bigrams. */
const char *bigrams = "intherreheanonesorteattistenntartondalitseediseangoulecomeneriroderaioicliofasetvetasihamaecomceelllcaurlachhidihofonsotacnarssoprrtsassusnoiltsemctgeloeebetrnipeiepancpooldaadviunamutwimoshyoaiewowosfiepttmiopiaweagsuiddoooirspplscaywaigeirylytuulivimabty";

/* 256 common trigrams. */
const char *trigrams = "theingandiontioentforatiterateersresherestcomproereallintmenyouonsourconarethaveressthireastatinhatistectortearineagehistedontncestoithntesintororeliniveitewitnotnthtraomeicaperartstectioftothiceoutillideethiesoneserecoerastrevedinratonacesediitieriransanityounnaluseurerinameactigheseavestintshessitderfthlesmanantindnewprireebleastntaturporghtainancchaeasparovenderomrecertlancalsofcanormtesostcatsonticendheainaredworberlichanmattathinnespreshoreneinemericustfrorthinceatasentiardrchndileatanssininminailompinscouellervtalencasstthlleelemoreansthtemsearmaalsundplapleealrieemaalindaackhenialordanaarcorichethoeoflisdiseencarngtireeadetoeneattntoommposabllatndsdatlitgramesheckinesavieotedthernsioonoesiinfmernfohavmarchitenuniimenatdeshourittimdenscoanshelnstrtirep";

/* Compress the string 's' of 'len' bytes and stores the compression
 * result in 'dst' for a maximum of 'dstlen' bytes. Returns the
 * amount of bytes written. */
unsigned long smaz_compress(unsigned char *dst, unsigned long dstlen, unsigned char *s, unsigned long len)
{

    int verblen = 0;     /* Length of the emitted verbatim sequence, 0 if
                          * no verbating sequence was emitted last time,
                          * otherwise 1...7, it never reaches 8 even if we have
                          * vertabim len of 8, since as we emit a verbatim
                          * sequence of 8 bytes we reset verblen to 0 to
                          * star emitting a new verbatim sequence. */
    unsigned long y = 0; // Index of next byte to set in 'dst'.

    while(len && y < dstlen) {
        /* Try to emit a bigram. */
        if (len >= 2) {
            int i;
            for (i = 0; i < 128; i++) {
                const char *t = bigrams + i*2;
                if (s[0] == t[0] && s[1] == t[1]) break;
            }

            /* Emit bigram if a match was found. */
            if (i != 128) {
                int x = 1;
                if (y < dstlen) dst[y++] = x<<7 | i;
                
                /* Consume. */
                s += 2;
                len -= 2;
                verblen = 0;
                continue;
            }
        }
        
        /* No bigram match. Let's try if we can represent this
         * byte with a single output byte without escaping. We can
         * for all the bytes values but 1, 2, 3, 4, 5, 6, 7, 8. */
        if (!(s[0] > 0 && s[0] < 9)) {
            if (y < dstlen) dst[y++] = s[0];

            /* Consume. */
            s++;
            len--;
            verblen = 0;
            continue;
        }

        /* If we are here, we got no match nor in the bigram nor
         * with the single byte. We have to emit 'varbatim' bytes
         * with the escape sequence. */
        verblen++;
        if (verblen == 1) {
            if (y+1 == dstlen) break; /* No room for 2 bytes. */
            dst[y++] = verblen;
            dst[y++] = s[0];
        } else {
            dst[y++] = s[0];
            dst[y-(verblen+1)] = verblen; // Fix the verbatim bytes length.
            if (verblen == 8) verblen = 0; // Start to emit a new sequence.
        }

        /* Consume. */
        s++;
        len--;
    }
    return y;
}

/* Decompress the string 'c' of 'len' bytes and stores the compression
 * result in 'dst' for a maximum of 'dstlen' bytes. Returns the
 * amount of bytes written. */
unsigned long smaz_decompress(unsigned char *dst, unsigned long dstlen, unsigned char *c, unsigned long len)
{
    (void) dst;
    (void) dstlen;
    (void) c;
    (void) len;
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr,
        "Usage: %s c|d 'string to c=compress, d=decompress'\n", argv[0]);
        exit(1);
    }

    unsigned char buf[256];
    unsigned long olen;

    if (argv[1][0] == 'c') {
        olen = smaz_compress(buf,sizeof(buf),(unsigned char*)argv[2],strlen(argv[2]));
    } else if (argv[1][0] == 'd') {
        olen = smaz_decompress(buf,sizeof(buf),(unsigned char*)argv[2],strlen(argv[2]));
    } else {
        fprintf(stderr,"Operation should be 'c' or 'd'\n");
        exit(1);
    }

    printf("Compressed bytes: %lu\n", olen);
}
