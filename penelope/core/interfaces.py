from zope.interface import Interface, classImplements
from zope.schema import Object, TextLine


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


class IPorModel(Interface):
    "marker interface for all por models"


class IWorkflowEnabled(IPorModel):
    "marker interface for all workflowenabled objects"


class IContract(IPorModel):
    "marker interface for contract model"


class ICustomerRequest(IPorModel):
    "marker interface for customer request model"


class ICustomer(IPorModel):
    "marker interface for customer model"


class ITimeEntry(IPorModel):
    "marker interface for timeentry model"


class IDublinCore(IPorModel):
    "marker interfaces for dublinmodels"


class IKanbanBoard(IPorModel):
    "Marker interface for kanbanboard"


class IProject(IPorModel):
    "interface that provides get_tickets method"

    def get_tickets(self, limit):
        """ """


class IRoleable(IPorModel):
    "Marker interface for models that have role mapping"


class IProjectRelated(IPorModel):
    "Object that implement this inteface need to know their project"

    project = Object(schema=IProject,
                     title=u"Related project",
                     required=True) 

    project_related_label = TextLine(title=u'Project related label')
    project_related_id = TextLine(title=u'Project related id (path)')


class ITicketStore(Interface):
    " marker interface "

    def get_tickets_for_project(self, project, request, query=None, limit=None):
        """ """

    def get_requests_from_tickets(self, project, ticket_ids, request=None):
        """ """

    def get_tickets_for_request(self, customer_request, limit=None):
        """ """

class IUser(IPorModel, IManageView):
    "Marker interface for user objects"


class IRole(IPorModel, IManageView):
    "Marker interface for role objects"


class IApplication(IProjectRelated):
    "Marker interface for applications"


class ITrac(IApplication):
    "Only for trac applications"


class ITracReport(IApplication):
    "Only for trac reports applications"


class IGoogleDocs(IApplication):
    "Only for google docs applications"


class ISVN(IApplication):
    "Only for svn applications"


class IGenericApp(IApplication):
    "Only for generic applications"


def register():
    """
    External interface declaration. This way we can remove penelope.core dependency
    from penelope.models
    """
    from penelope.models import TimeEntry, Workflow, DublinCore, TicketStore
    from penelope.models import GlobalConfig, Principal, Role, OpenId, Cost
    from penelope.models import User, Customer, Project, Application
    from penelope.models import GenericApp, Trac, TracReport, Subversion, GoogleDoc
    from penelope.models import Contract, CustomerRequest, Group, SavedQuery, KanbanBoard

    classImplements(TimeEntry, IProjectRelated, ITimeEntry)
    classImplements(Workflow, IWorkflowEnabled)
    classImplements(DublinCore, IDublinCore)
    classImplements(TicketStore, ITicketStore)
    classImplements(GlobalConfig, IPorModel)
    classImplements(Principal, IPorModel)
    classImplements(Role, IRole)
    classImplements(User, IRoleable, IUser)
    classImplements(OpenId, IPorModel)
    classImplements(Cost, IPorModel)
    classImplements(Customer, ICustomer)
    classImplements(Project, IProject, IProjectRelated)
    classImplements(Application, IProjectRelated, IApplication)
    classImplements(GenericApp, IGenericApp)
    classImplements(Trac, ITrac)
    classImplements(TracReport, ITracReport)
    classImplements(Subversion, ISVN)
    classImplements(GoogleDoc, IGoogleDocs)
    classImplements(Contract, IContract, IProjectRelated)
    classImplements(CustomerRequest, ICustomerRequest, IProjectRelated)
    classImplements(Group, IRoleable, IProjectRelated)
    classImplements(SavedQuery, IPorModel)
    classImplements(KanbanBoard, IKanbanBoard)
