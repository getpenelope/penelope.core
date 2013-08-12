# -*- coding: utf-8 -*-

import datetime
import re
import unittest2

from penelope.core.lib.helpers import time_chunks, time_parse



class TestTimeChunks(unittest2.TestCase):

    def test_onepiece(self):
        dt = datetime.timedelta(seconds=7000)
        tc = list(time_chunks(dt, 1))
        self.assertSequenceEqual(tc, [datetime.timedelta(seconds=7000)])

    def test_fifteen(self):
        dt = datetime.timedelta(seconds=15*60)
        tc = list(time_chunks(dt, 2))
        self.assertSequenceEqual(tc,
                                 [
                                     datetime.timedelta(seconds=7*60),
                                     datetime.timedelta(seconds=8*60)
                                ])

    def test_pi(self):
        dt = datetime.timedelta(seconds=3.1415926*60*60)
        tc = list(time_chunks(dt, 7))
        self.assertSequenceEqual(tc,
                                 [
                                     datetime.timedelta(seconds=26*60),
                                     datetime.timedelta(seconds=26*60),
                                     datetime.timedelta(seconds=26*60),
                                     datetime.timedelta(seconds=26*60),
                                     datetime.timedelta(seconds=26*60),
                                     datetime.timedelta(seconds=26*60),
                                     datetime.timedelta(0, 1949, 733360),
                                ])


HH = 60*60
MM = 60

class TestTimeParse(unittest2.TestCase):

    def test_hours(self):
        self.assertRaisesRegexp(ValueError, re.escape(u'Cannot parse time (must be HH:MM)'),
                                time_parse, '3')

    def test_minutes(self):
        self.assertRaisesRegexp(ValueError, re.escape(u'Cannot parse time (must be HH:MM)'),
                                time_parse, ':30')

    def test_gibberish(self):
        self.assertRaisesRegexp(ValueError, re.escape(u'Cannot parse time (must be HH:MM)'),
                                time_parse, 'blablabla')

    def test_hhmm(self):
        self.assertEquals(time_parse('2:27'),
                          datetime.timedelta(seconds=2*HH+27*MM) )

    def test_minimum(self):
        self.assertRaisesRegexp(ValueError, re.escape(u'Time value too small (must be >= 0:01'),
                                time_parse, '0:00', minimum=datetime.timedelta(seconds=1*60))

    def test_maximum(self):
        self.assertRaisesRegexp(ValueError, re.escape(u'Time value too big (must be <= 8:00'),
                                time_parse, '8:01', maximum=datetime.timedelta(seconds=8*HH))

    def test_empty(self):
        self.assertIsNone(time_parse(''))






if __name__ == '__main__':
    unittest2.main()

