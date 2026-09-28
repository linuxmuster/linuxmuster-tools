"""
Tests for the natural sort helpers: natural_key, sort_naturally.
"""

import pytest

from linuxmusterTools.common.sorting import natural_key, sort_naturally


# --- natural_key -------------------------------------------------------

@pytest.mark.parametrize("names, expected", [
    # The case a plain sorted() gets wrong
    (['m10', 'm5', 'm1'], ['m1', 'm5', 'm10']),
    # Every segment counts, not only the first number
    (['r100-pc10', 'r100-pc5'], ['r100-pc5', 'r100-pc10']),
    # Schoolclasses, as the webui and the ldap reader sort them
    (['10a', '5a', '5b', '9c'], ['5a', '5b', '9c', '10a']),
    # A name without any digit is ordered alphabetically, not pushed away
    (['10a', 'kurs', '5a'], ['5a', '10a', 'kurs']),
    # Each octet of an IP address is a segment of its own
    (['10.0.0.10', '10.0.0.2', '10.0.1.1'], ['10.0.0.2', '10.0.0.10', '10.0.1.1']),
    # Rooms, groups, images
    (['raum2-pc1', 'raum10-pc1', 'raum2-pc10'], ['raum2-pc1', 'raum2-pc10', 'raum10-pc1']),
])
def test_natural_key_sorts_numbers_as_numbers(names, expected):
    assert sorted(names, key=natural_key) == expected

def test_natural_key_is_case_insensitive():
    assert sorted(['b1', 'A2', 'a1'], key=natural_key) == ['a1', 'A2', 'b1']

def test_natural_key_breaks_ties_on_the_original_string():
    # 'PC1' and 'pc1' hold the same segments once the text is case folded:
    # without the tie-break their keys would be equal and their order would
    # depend on the input order.
    assert sorted(['pc1', 'PC1'], key=natural_key) == ['PC1', 'pc1']
    assert sorted(['PC1', 'pc1'], key=natural_key) == ['PC1', 'pc1']
    assert natural_key('m5') != natural_key('M5')


# --- padded numbers ----------------------------------------------------

@pytest.mark.parametrize("names, expected", [
    # A padded number comes before an unpadded one whatever its value
    (['m1', 'm05'], ['m05', 'm1']),
    (['m1', 'm2', 'm3', 'm4', 'm05', 'm06'], ['m05', 'm06', 'm1', 'm2', 'm3', 'm4']),
    # ... and the unpadded ones keep their numeric order
    (['m10', 'm5', 'm05'], ['m05', 'm5', 'm10']),
    # Between two padded numbers the value decides again
    (['m09', 'm05', 'm10', 'm1'], ['m05', 'm09', 'm1', 'm10']),
    # The rule applies per segment, not once per name
    (['r1-pc05', 'r1-pc1', 'r01-pc1'], ['r01-pc1', 'r1-pc05', 'r1-pc1']),
    # Padding depth ranks before the value: two zeros before one, one before none
    (['m05', 'm0020'], ['m0020', 'm05']),
    (['pc01', 'pc001'], ['pc001', 'pc01']),
    # One block per depth, each block in numeric order
    (['m1', 'm05', 'm0020', 'm010', 'm5'], ['m0020', 'm05', 'm010', 'm1', 'm5']),
    (['m012', 'm09', 'm0020', 'm010', 'm05'], ['m0020', 'm05', 'm09', 'm010', 'm012']),
])
def test_natural_key_sorts_padded_numbers_first(names, expected):
    assert sorted(names, key=natural_key) == expected

def test_natural_key_reads_a_bare_zero_as_a_value_not_as_padding():
    assert natural_key('m0') == natural_key('m0')
    assert sorted(['m1', 'm0'], key=natural_key) == ['m0', 'm1']
    # '00' is padding, '0' is not, so they are not the same name, and '000'
    # is padded one level deeper than '00'
    assert sorted(['m0', 'm00'], key=natural_key) == ['m00', 'm0']
    assert sorted(['m0', 'm00', 'm000'], key=natural_key) == ['m000', 'm00', 'm0']

def test_natural_key_padding_does_not_leak_between_segments():
    # The padded '01' is in the first segment of one name and in the second of
    # the other: each segment is judged on its own.
    assert sorted(['r01-pc1', 'r1-pc01'], key=natural_key) == ['r01-pc1', 'r1-pc01']

def test_natural_key_handles_leading_digits_and_empty_strings():
    assert sorted(['2a', '', '10a'], key=natural_key) == ['', '2a', '10a']

def test_natural_key_sorts_none_last():
    assert sorted(['b', None, 'a'], key=natural_key) == ['a', 'b', None]

def test_natural_key_accepts_non_strings():
    # A caller reading an attribute which is not always a string must not get
    # a TypeError out of the sort.
    assert sorted([10, 5, 'm1'], key=natural_key) == [5, 10, 'm1']

def test_natural_key_reads_a_hyphen_as_a_separator_not_a_sign():
    assert sorted(['pc-2', 'pc-10'], key=natural_key) == ['pc-2', 'pc-10']

def test_natural_key_does_not_overflow_on_long_digit_runs():
    # Segments are compared as Python ints, not as fixed-width numbers.
    assert sorted(['a' + '9' * 30, 'a' + '9' * 29], key=natural_key) == [
        'a' + '9' * 29,
        'a' + '9' * 30,
    ]


# --- sort_naturally ----------------------------------------------------

def test_sort_naturally_without_key():
    assert sort_naturally(['m10', 'm5']) == ['m5', 'm10']

def test_sort_naturally_returns_a_new_list():
    names = ['m10', 'm5']
    assert sort_naturally(names) is not names
    assert names == ['m10', 'm5']

def test_sort_naturally_accepts_any_iterable():
    assert sort_naturally({'m10', 'm5', 'm1'}) == ['m1', 'm5', 'm10']

def test_sort_naturally_with_a_key_on_dicts():
    hosts = [{'hostname': 'm10'}, {'hostname': 'm5'}]
    assert sort_naturally(hosts, key=lambda host: host['hostname']) == [
        {'hostname': 'm5'},
        {'hostname': 'm10'},
    ]

def test_sort_naturally_reverse():
    assert sort_naturally(['m5', 'm10', 'm1'], reverse=True) == ['m10', 'm5', 'm1']

def test_sort_naturally_is_stable_on_equal_keys():
    first = {'hostname': 'm1', 'ip': '10.0.0.1'}
    second = {'hostname': 'm1', 'ip': '10.0.0.2'}
    hosts = [first, second]
    result = sort_naturally(hosts, key=lambda host: host['hostname'])
    assert result[0] is first
    assert result[1] is second


# --- public API ----------------------------------------------------------

def test_helpers_are_reexported_by_common():
    # Callers import them from linuxmusterTools.common, not from the sorting
    # module: this checks the re-export in common/__init__.py.
    from linuxmusterTools import common

    assert common.natural_key is natural_key
    assert common.sort_naturally is sort_naturally
