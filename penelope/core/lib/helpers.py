# -*- coding: utf-8 -*-

import datetime
import operator
import re

SECS_IN_HR = 60.0*60.0
WORK_HOURS_IN_DAY = 8.0


def timedelta_as_work_days(td):
    return (td.days*24.0 + td.seconds/SECS_IN_HR) / WORK_HOURS_IN_DAY


def timedelta_as_work_hours(td):
    return (td.days*24.0 + td.seconds/SECS_IN_HR)


def timedelta_as_human_str(td, seconds=False):
    """
    Formats a timedelta for human consumption. Also used by some reports.
    """
    if td is None:
        return ''
    hh, rem = divmod(td.days*24.0*SECS_IN_HR + td.seconds, SECS_IN_HR)
    mm, ss = divmod(rem, 60)
    if seconds or ss:
        return '%d:%02d:%02d' % (hh, mm, ss)
    else:
        return '%d:%02d' % (hh, mm)


def ticket_url(request, project, ticket_id):
    tracs = list(project.tracs)
    if not tracs:
        return None
    trac_url = tracs[0].application_uri(request)
    return '%s/ticket/%s' % (trac_url, ticket_id)


def timeentry_url(request, time_entry):
    return '/admin/TimeEntry/%s' % time_entry.id


def chunks(seq, num):
    avg = len(seq) / float(num)
    out = []
    last = 0.0
    while last < len(seq):
        out.append(seq[int(last):int(last + avg)])
        last += avg
    return out


def total_seconds(dt):
    """
    datetime.total_seconds is new in python 2.7
    """
    return dt.days*24*60*60 + dt.seconds


def time_chunks(dt, num):
    """
    Splits a datetime without splitting minutes
    """
    chunk_minutes = total_seconds(dt) // 60 // num
    chunk_dt = datetime.timedelta(seconds=chunk_minutes * 60)
    for n in range(num-1):
        yield chunk_dt
        dt -= chunk_dt
    yield dt



def time_parse(text, maximum=None, minimum=None):
    """
    Returns a timedelta object, given a string like HH:MM, HH or :MM
    """
    if not text:
        return None

    m = re.match('^([0-1]?[0-9]|2[0-4]):([0-5][0-9])$', text)
    if not m:
        raise ValueError(u'Cannot parse time (must be HH:MM)')

    hh, mm = m.groups()
    hh = int(hh)
    mm = int(mm)

    ret = datetime.timedelta(seconds=hh*60*60+mm*60)

    if maximum and ret > maximum:
        raise ValueError(u'Time value too big (must be <= %s)' % timedelta_as_human_str(maximum))

    if minimum and ret < minimum:
        raise ValueError(u'Time value too small (must be >= %s)' % timedelta_as_human_str(minimum))

    return ret



# Reverse ordering key for strings, dates or any kind of object.
# From http://stackoverflow.com/questions/11206884/how-to-write-python-sort-key-functions-for-descending-values
# In python 2.7, ReversedOrder can be written as:
#
#import functools
#@functools.total_ordering
#class ReversedOrder(object):
#    def __init__(self, value):
#        self.value = value
#    def __eq__(self, other):
#        return other.value == self.value
#    def __lt__(self, other):
#        return other.value < self.value

class ReversedOrder(object):
    def __init__(self, value):
        self.value = value
for x in ['__lt__', '__le__', '__eq__', '__ne__', '__ge__', '__gt__']:
    op = getattr(operator, x)
    setattr(ReversedOrder, x, lambda self, other, op=op: op(other.value, self.value))


def unicodelower(obj):
    """
    Case insensitive sort key.
    """
    try:
        return unicode(obj, errors='ignore').lower()
    except TypeError:
        return unicode(obj).lower()


def listwrap(obj):
    """
    Always returns a list, converting tuples and sequences, wraps single objects.
    """
    if obj is None:
        return []
    if isinstance(obj, basestring):   # strings are sequence type too
        return [obj]
    if operator.isSequenceType(obj):
        return list(obj)
    return [obj]


