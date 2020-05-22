def bprint(stream):
    bstring = []
    for i in stream:
        bstring.append(hex(i)[2:])
    print(' '.join(bstring))


class ParsingError(Exception):
    pass
