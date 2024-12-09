import math
from datetime import datetime


def format_size(num, suffix='B', base=2):
    if num == 0:
        return f'0 {suffix}'

    if base == 2:
        units = ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']
        scale_base = 1024
    elif base == 10:
        units = ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']
        scale_base = 1000
    else:
        raise Exception("Please use 2 or 10 as base")

    scale = int(math.floor(math.log(num, scale_base)))
    value = num / math.pow(scale_base, scale)
    if scale > 7:
        return f'{value:.2f} Yi{suffix}'
    return f'{value:3.2f} {units[scale]}{suffix}'

def convert_sophomorix_time(t):
    """
    Convert sophomorix datetime to readable info.

    :param t: Sophomorix date like 20081030125303.0Z
    :type t: basestring
    :return: Human-readable date like 30 Oct 2008 12:53:30
    :rtype:
    """


    try:
        return  datetime.strptime(t, '%Y%m%d%H%M%S.%fZ').strftime("%d %b %Y %H:%M:%S")
    except Exception:
        return t