# -*- coding: utf-8 -*-

"""
FormAlchemy widgets for penelope.core
"""

from formalchemy.fields import FieldRenderer
from formalchemy import helpers as h


class BigTextAreaFieldRenderer(FieldRenderer):
    """
    A textarea with a bigger default size
    """
    def render(self, size=(60, 8), **kwargs):
        if isinstance(size, tuple):
            kwargs['size'] = 'x'.join(map(str, size))
        return h.text_area(self.name, content=self.value, **kwargs)


