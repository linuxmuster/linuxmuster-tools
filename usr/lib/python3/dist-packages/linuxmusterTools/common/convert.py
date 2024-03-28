import math


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
