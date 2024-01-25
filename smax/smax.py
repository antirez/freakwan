# Define common bigrams and words
bigrams = "intherreheanonesorteattistenntartondalitseediseangoulecomeneriroderaioicliofasetvetasihamaecomceelllcaurlachhidihofonsotacnarssoprrtsassusnoiltsemctgeloeebetrnipeiepancpooldaadviunamutwimoshyoaiewowosfiepttmiopiaweagsuiddoooirspplscaywaigeirylytuulivimabty"
words = [
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
"rating", "rate", "government"]

# SMAX compression function
def smax_compress(s):
    dst = bytearray()
    verblen = 0

    while len(s) > 0:
        if len(s) >= 4:
            for i, w in enumerate(words):
                wordlen = len(w)
                space = s[0] == ' '

                if len(s) >= wordlen + space and s[space:wordlen+space] == w.encode():
                    break
            else:
                i = False

            if i:
                if s[0] == ' ':
                    dst.extend([8,i])
                    s = s[1:]
                elif len(s) > wordlen and s[wordlen] == ' ':
                    dst.extend([7,i])
                    s = s[1:]
                else:
                    dst.extend([6,i])

                s = s[wordlen:]
                verblen = 0
                continue

        if len(s) >= 2:
            for i in range(0, len(bigrams), 2):
                if s[:2] == bigrams[i:i+2].encode():
                    break
            else:
                i = False

            if i:
                dst.append(1 << 7 | i // 2)
                s = s[2:]
                verblen = 0
                continue

        if not (0 < s[0] < 9):
            dst.append(s[0])
            s = s[1:]
            verblen = 0
            continue

        verblen += 1
        if verblen == 1:
            dst.extend([verblen,s[0]])
        else:
            dst.append(s[0])
            dst[-(verblen + 1)] = verblen
            if verblen == 5:
                verblen = 0

        s = s[1:]

    return bytes(dst)

# SMAX decompression function (stub)
def smax_decompress(c):
    pass  # Decompression logic goes here

# Main function for command-line interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        sys.exit("Usage: {} c|d 'string to c=compress, d=decompress'".format(sys.argv[0]))

    if sys.argv[1] == 'c':
        compressed = smax_compress(sys.argv[2].encode())
        print("Compressed length: {:.02f}%".format(len(compressed) / len(sys.argv[2].encode()) * 100))
        print(compressed)
    elif sys.argv[1] == 'd':
        decompressed = smax_decompress(sys.argv[2].encode())
        # Print decompression results here
    else:
        sys.exit("Operation should be 'c' or 'd'")

