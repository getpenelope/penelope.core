from zope.interface import Interface

class IApplicationView(Interface):
    pass


class IReportView(Interface):
    "Marker interface for all report views"


class IManageView(Interface):
    "Marker interface for all manage views"


class IBreadcrumbs(Interface):
    "Render my breadcrumbs"


class ISidebar(Interface):
    "Render my sidebar"


class IPorRequest(Interface):
    "Our request marker"


class IRoleFinder(Interface):
    "Adapter that returns roles for context"
