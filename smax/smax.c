#include <stdio.h>
#include <string.h>
#include <ctype.h>
#include <stdlib.h>

/* 128 common bigrams. */
const char *bigrams = "intherreheanonesorteattistenntartondalitseediseangoulecomeneriroderaioicliofasetvetasihamaecomceelllcaurlachhidihofonsotacnarssoprrtsassusnoiltsemctgeloeebetrnipeiepancpooldaadviunamutwimoshyoaiewowosfiepttmiopiaweagsuiddoooirspplscaywaigeirylytuulivimabty";

/* 256 common English words of length four letters or more. */
char *words[256] = {
"that", "this", "with", "from", "your", "have", "more", "will", "home",
"about", "page", "search", "free", "other", "information", "time", "they",
"site", "what", "which", "their", "news", "there", "only", "when", "contact",
"here", "business", "also", "help", "view", "online", "first", "been", "would",
"were", "services", "some", "these", "click", "like", "service", "than", "find",
"price", "date", "back", "people", "list", "name", "just", "over", "state",
"year", "into", "email", "health", "world", "next", "used", "work", "last",
"most", "products", "music", "data", "make", "them", "should", "product",
"system", "post", "city", "policy", "number", "such", "please", "available",
"copyright", "support", "message", "after", "best", "software", "then", "good",
"video", "well", "where", "info", "rights", "public", "books", "high", "school",
"through", "each", "links", "review", "years", "order", "very", "privacy",
"book", "items", "company", "read", "group", "need", "many", "user", "said",
"does", "under", "general", "research", "university", "january", "mail", "full",
"reviews", "program", "life", "know", "games", "days", "management", "part",
"could", "great", "united", "hotel", "real", "item", "international", "center",
"ebay", "must", "store", "travel", "comments", "made", "development", "report",
"member", "details", "line", "terms", "before", "hotels", "send", "right",
"type", "because", "local", "those", "using", "results", "office", "education",
"national", "design", "take", "posted", "internet", "address", "community",
"within", "states", "area", "want", "phone", "shipping", "reserved", "subject",
"between", "forum", "family", "long", "based", "code", "show", "even", "black",
"check", "special", "prices", "website", "index", "being", "women", "much",
"sign", "file", "link", "open", "today", "technology", "south", "case",
"project", "same", "pages", "version", "section", "found", "sports", "house",
"related", "security", "both", "county", "american", "photo", "game", "members",
"power", "while", "care", "network", "down", "computer", "systems", "three",
"total", "place", "following", "download", "without", "access", "think",
"north", "resources", "current", "posts", "media", "control", "water",
"history", "pictures", "size", "personal", "since", "including", "guide",
"shop", "directory", "board", "location", "change", "white", "text", "small",
"rating", "rate", "government"};

/* Compress the string 's' of 'len' bytes and stores the compression
 * result in 'dst' for a maximum of 'dstlen' bytes. Returns the
 * amount of bytes written. */
unsigned long smax_compress(unsigned char *dst, unsigned long dstlen, unsigned char *s, unsigned long len)
{

    int debug = 0;       // Log debugging messages.
    int verblen = 0;     /* Length of the emitted verbatim sequence, 0 if
                          * no verbating sequence was emitted last time,
                          * otherwise 1...5, it never reaches 8 even if we have
                          * vertabim len of 8, since as we emit a verbatim
                          * sequence of 8 bytes we reset verblen to 0 to
                          * star emitting a new verbatim sequence. */
    unsigned long y = 0; // Index of next byte to set in 'dst'.

    while(len && y < dstlen) {
        /* Try to emit a word. */
        if (len >= 4) {
            unsigned int i, wordlen;
            for (i = 0; i < 256; i++) {
                const char *w = words[i];
                wordlen = strlen(w);
                unsigned int space = s[0] == ' ';

                if (len >= wordlen+space &&
                    memcmp(w,s+space,wordlen) == 0) break; // Match.
            }

            /* Emit word if a match was found.
             * The escapes are:
             * byte value 6: simple word.
             * byte value 7: word + space.
             * byte value 8: space + word. */
            if (i != 256) {
                if (s[0] == ' ') {
                    if (debug) printf("( %s)", words[i]);
                    if (y < dstlen) dst[y++] = 8; // Space + word.
                    if (y < dstlen) dst[y++] = i; // Word ID.
                    s++; len--; // Account for the space.
                } else if (len > wordlen && s[wordlen] == ' ') {
                    if (debug) printf("(%s )", words[i]);
                    if (y < dstlen) dst[y++] = 7; // Word + space.
                    if (y < dstlen) dst[y++] = i; // Word ID.
                    s++; len--; // Account for the space.
                } else {
                    if (debug) printf("(%s)", words[i]);
                    if (y < dstlen) dst[y++] = 6; // Simple word.
                    if (y < dstlen) dst[y++] = i; // Word ID.
                }
                
                /* Consume. */
                s += wordlen;
                len -= wordlen;
                verblen = 0;
                continue;
            }
        }

        /* Try to emit a bigram. */
        if (len >= 2) {
            int i;
            for (i = 0; i < 128; i++) {
                const char *b = bigrams + i*2;
                if (s[0] == b[0] && s[1] == b[1]) break;
            }

            /* Emit bigram if a match was found. */
            if (i != 128) {
                int x = 1;
                if (y < dstlen) dst[y++] = x<<7 | i;
                
                /* Consume. */
                s += 2;
                len -= 2;
                verblen = 0;
                if (debug) printf("[%c%c]", bigrams[i*2], bigrams[i*2+1]);
                continue;
            }
        }

        /* No word/bigram match. Let's try if we can represent this
         * byte with a single output byte without escaping. We can
         * for all the bytes values but 1, 2, 3, 4, 5, 6, 7, 8. */
        if (!(s[0] > 0 && s[0] < 9)) {
            if (y < dstlen) dst[y++] = s[0];

            /* Consume. */
            if (debug) printf("{%c}", s[0]);
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
            if (debug) printf("_%c", s[0]);
            if (y+1 == dstlen) break; /* No room for 2 bytes. */
            dst[y++] = verblen;
            dst[y++] = s[0];
        } else {
            if (debug) printf("%c", s[0]);
            dst[y++] = s[0];
            dst[y-(verblen+1)] = verblen; // Fix the verbatim bytes length.
            if (verblen == 5) verblen = 0; // Start to emit a new sequence.
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
unsigned long smax_decompress(unsigned char *dst, unsigned long dstlen, unsigned char *c, unsigned long len)
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
        olen = smax_compress(buf,sizeof(buf),(unsigned char*)argv[2],strlen(argv[2]));
    } else if (argv[1][0] == 'd') {
        olen = smax_decompress(buf,sizeof(buf),(unsigned char*)argv[2],strlen(argv[2]));
    } else {
        fprintf(stderr,"Operation should be 'c' or 'd'\n");
        exit(1);
    }

    printf("Compressed length (%lu): %.02f%%\n", olen, (float)olen/strlen(argv[2])*100);
}
