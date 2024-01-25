# SMX small messages compression algorithm

LoRa networks have an extremely limited bandwidth and requires a long
channel time in order to send even small messages. When LoRa is used
to send messages between humans, a form of compression improves the
channel utilization in a sensible way.

This compression scheme is designed to compress small messages in extremely
memory constrained devices, like ESP32 devices running MicroPython.
The basic idea is to use a pre-computed bigrams and words tables to encode
short messages more efficiently, for a total RAM usage of less than
2kbytes.

The words table is composed of 256 words. Short words (len less than 4 bytes)
are not present because they are better encoded with bigrams.
This is the full list of the 256 words:

*"that this with from your have more will home about page search free other information time they site what which their news there only when contact here business also help view online first been would were services some these click like service than find price date back people list name just over state year into email health world next used work last most products music data make them should product system post city policy number such please available copyright support message after best software then good video well where info rights public books high school through each links review years order very privacy book items company read group need many user said does under general research university january mail full reviews program life know games days management part could great united hotel real item international center ebay must store travel comments made development report member details line terms before hotels send right type because local those using results office education national design take posted internet address community within states area want phone shipping reserved subject between forum family long based code show even black check special prices website index being women much sign file link open today technology south case project same pages version section found sports house related security both county american photo game members power while care network down computer systems three total place following download without access think north resources current posts media control water history pictures size personal since including guide shop directory board location change white text small rating rate government"*

If a word match is not found, the bigram table is used. The table is composed of the most common 128 bigrams by frequency, for a total of 256 bytes:

*"intherreheanonesorteattistenntartondalitseediseangoulecomeneriroderaioicliofasetvetasihamaecomceelllcaurlachhidihofonsotacnarssoprrtsassusnoiltsemctgeloeebetrnipeiepancpooldaadviunamutwimoshyoaiewowosfiepttmiopiaweagsuiddoooirspplscaywaigeirylytuulivimabty"*

When not even a matching bigram is found, bytes with value 0 or in the range
from 9 to 127 can be encoded with a single byte (this happens for instance for
all the ASCII uppercase letters, symbols, numbers...). The byte value can be
left as it is.

For bytes in the range from 1 to 8 and from 128 to 255, an escape sequence
is generated and from 1 to 5 verbatim bytes are emitted. Bytes with values
6, 7, 8 are used as special escapes to emit a word from the table. The
value of 6 is used.

So this is how the encoding works:

* A byte with value from 128 to 255 encodes a bigram with ID from 0 to 127.
* A byte with value 0 or from 9 to 127 is just what it is.
* A byte with value of 6 is followed by a byte representing the word ID to emit.
* A byte with value 7 is like 6, but after the word a space is emitted.
* A byte with value 8 is like 6, but before the word a space is emitted.
* A byte with a value from 1 to 5 means that from 1 to 5 verbatim bytes follow.

This means that this compression scheme will use more space than the input
string only when emtting verbatim bytes, that is when the string contains
special or unicode characters.

As long as the messages are latin letters natural language messages with common statistical properties, the program will only seldom use more space than needed and will often be able to compress words to less bytes. However programs using this scheme should have a one bit flag in the header in order to signal if the message is compressed or not, so that every time the result would be larger than the uncompressed message, no compression is used in order to trasmit the message.

## Real world compression achieved

./smax c "The program is designed to work well with English text"
Compressed length: 44.44%

./smax c "As long as the messages are latin letters natural language messages with common statistical properties, the program will only seldom use more space than needed"
Compressed length: 54.72%

./smax c "Anche se in maniera meno efficiente, questo algoritmo di compressione è in grado di comprimere testi in altre lingue."
Compressed length: 66.95%
