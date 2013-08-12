# -*- coding: utf-8 -*-

TEMPLATE = """<div class="alert alert-%(type)s fade in"><a class="close" href="#" data-dismiss="alert">x</a><p>%(message)s</p></div>"""
STATUSMESSAGEKEY = 'PENELOPE_MESSAGE'


class Message(object):
    """A single status message."""

    def __init__(self, message, type):
        self.message = message
        self.type = type


class Messages(list):
    def __init__(self, *args, **kwargs):
        list.__init__(self, *args, **kwargs)
        self.template = TEMPLATE

    def show(self):
        return u''.join([self.template % a.__dict__ for a in self])

    def add(self, text, type='info'):
        message = Message(text, type)
        self.append(message)
