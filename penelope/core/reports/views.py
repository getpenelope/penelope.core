# -*- coding: utf-8 -*-

from zope.interface import implements

from penelope.core import fanstatic_resources
from penelope.core.interfaces import IReportView
from penelope.core.views import DefaultContext


class ReportContext(DefaultContext):
    """
    Default context factory for Report views.
    """

    implements(IReportView)

    def __init__(self, request):
        super(ReportContext, self).__init__(request)
        fanstatic_resources.project_filter.need()
        fanstatic_resources.saved_queries.need()
