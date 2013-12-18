from zope.interface import Interface
from zope.schema import Object, TextLine
from penelope.core.interfaces import IManageView


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
    "marker interfaces for dublincore models"


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
