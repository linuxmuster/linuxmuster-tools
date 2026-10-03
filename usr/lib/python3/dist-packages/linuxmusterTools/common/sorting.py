import re


# Split on digit runs, keeping them: 'r100-pc5' -> ['r', '100', '-pc', '5', ''].
# re.split() always alternates text and digits, starting with text (possibly
# empty), so the odd indices of the result are the numbers and nothing else.
_DIGITS = re.compile(r'(\d+)')


def _number_segment(digits):
    # Leading zeros rank before the value: a digit run padded with two zeros is
    # ordered before one padded with a single zero, itself ordered before an
    # unpadded one, whatever the values are. A run made of zeros only ('0',
    # '00') keeps its last zero as its value, so a bare '0' is not padding.
    zeros = len(digits) - len(digits.lstrip('0'))
    if zeros == len(digits):
        zeros -= 1
    return (-zeros, int(digits))


def natural_key(value):
    """
    Sort key ordering names the way a human reads them: m5 before m10.

    A plain sorted() compares strings character by character, which puts m10
    before m5 as soon as the numbers have a different number of digits. This
    key splits the string into text and number segments and compares the
    numbers as numbers, the text case-insensitively:

    >>> sorted(['m10', 'm5', 'm1'], key=natural_key)
    ['m1', 'm5', 'm10']

    Every segment is used, not only the first number, so hostnames sharing a
    prefix are ordered on the part that actually differs:

    >>> sorted(['r100-pc10', 'r100-pc5'], key=natural_key)
    ['r100-pc5', 'r100-pc10']

    IP addresses come out in numeric order too, each octet being a segment of
    its own ('10.0.0.2' before '10.0.0.10').

    Leading zeros are read as a naming convention of their own, not as noise.
    Numbers are grouped by how deep their padding is, deepest first, and the
    values are compared only inside a group. A site numbering its machines
    'm0020', 'm05' to 'm012' and 'm1' to 'm5' therefore gets one block per
    padding depth, each block in numeric order:

    >>> sorted(['m1', 'm05', 'm0020', 'm010', 'm5'], key=natural_key)
    ['m0020', 'm05', 'm010', 'm1', 'm5']

    A run made of zeros only keeps its last zero as its value, so a bare '0' is
    not padding. This is deliberate and diverges from `sort -V`, from `ls -v`
    and from JavaScript's Intl.Collator, which all read 'm05' as the plain
    number 5.

    Two names differing only in case ('m5' and 'M5') produce the same segments;
    the original string is kept as the last part of the key to break the tie,
    so the order is total and stable. The comparison is pure Unicode case
    folding, without any locale-dependent collation: 'ä' sorts after 'z', and
    the result does not depend on the caller's locale.

    A '-' is a separator, never a sign: '-1' sorts as the text '-' followed by
    the number 1.

    :param value: Value to build a key for. Anything which is not a string is
                  sorted on its str() representation, None comes last.
    :type value: str or None or any
    :return: Comparable key, to pass as sorted()'s key argument
    :rtype: tuple
    """


    if value is None:
        # Nothing to read, and no reason to fail on a missing attribute: an
        # empty name sorts first, a missing one last.
        return (1, (), '')

    text = value if isinstance(value, str) else str(value)

    segments = tuple(
        _number_segment(part) if index % 2 else (0, part.casefold())
        for index, part in enumerate(_DIGITS.split(text))
    )

    return (0, segments, text)

def sort_naturally(items, key=None, reverse=False, digitless_last=False):
    """
    Sort a list of names, or of objects holding a name, in human order.

    >>> sort_naturally(['m10', 'm5'])
    ['m5', 'm10']
    >>> sort_naturally(hosts, key=lambda host: host['hostname'])
    >>> sort_naturally(['abitur', '10b', '5a'], digitless_last=True)
    ['5a', '10b', 'abitur']

    :param items: Values to sort
    :type items: iterable
    :param key: Callable returning the value to sort an item on, like sorted()'s
                own key. Without it the items are sorted on themselves.
    :type key: callable or None
    :param reverse: Sort in descending order. None values, sorted last by
                    natural_key(), then come first.
    :type reverse: bool
    :param digitless_last: Move the values holding no digit at all after the
                           others, each group in natural order. Schoolclasses
                           are listed this way: '5a', '10b', then 'abitur'.
                           With reverse, these values come first.
    :type digitless_last: bool
    :return: Sorted list
    :rtype: list
    """


    if key is None:
        key = lambda item: item

    if digitless_last:
        def sort_key(item):
            value = key(item)
            # None holds no digit either: it stays last, behind the digitless
            # names, as natural_key() orders it.
            digitless = value is None or not _DIGITS.search(str(value))
            return (digitless, natural_key(value))
    else:
        def sort_key(item):
            return natural_key(key(item))

    return sorted(items, key=sort_key, reverse=reverse)
