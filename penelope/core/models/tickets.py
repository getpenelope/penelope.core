# -*- coding: utf-8 -*-
from pyramid.threadlocal import get_current_registry, get_current_request
from zope.interface import implements
from penelope.core.models.interfaces import ITicketStore
from penelope.core.models import DBSession
from penelope.trac.api import TracXmlProxy


class TicketStore(object):
    implements(ITicketStore)

    def get_ticket(self, request, project_id, ticket_id):
        from penelope.core.models.dashboard import Project
        project = DBSession().query(Project).get(project_id)
        if request and project:
            for trac in project.tracs:
                proxy = TracXmlProxy(trac.application_uri(request), request=request)
                return proxy.ticket.get(ticket_id)

    def get_tickets_for_project(self, project, request, query=None, limit=None, not_invoiced=False):
        tickets = []
        for trac in project.tracs:
            proxy = TracXmlProxy(trac.application_uri(request), request=request)
            if not query:
                query = [
                    # 'modified=1weekago',
                ]
            if limit:
                query.append('max=%s' % limit)
            else:
                query.append('max=0')
            tickets.extend(proxy.ticket.queryWithDetails('&'.join(query)))

        if not_invoiced:
            cr_ids = [cr.id for cr in project.customer_requests if cr.workflow_state in ['created', 'estimated']]
            tickets = [t for t in tickets if t['cr'] in cr_ids]

        return tickets

    def get_tickets_for_request(self, customer_request, limit=None, request=None):
        cr = customer_request
        return self.get_tickets_for_project(project=cr.project,
                                            query=['customerrequest=%s' % (cr.id)],
                                            limit=limit,
                                            request=request)

    def get_all_ticket_crs(self, project, request):
        """
        returns a mapping of {ticket.id: cr_id}
        """
        import xmlrpclib
        ret = {}

        for trac in project.tracs:
            proxy = TracXmlProxy(trac.application_uri(request), request=request)
            try:
                for ticket_id, cr_id in proxy.ticket.queryAllCustomerRequests():
                    ret[ticket_id] = cr_id
            except xmlrpclib.ProtocolError:
                pass

        return ret

    def get_requests_from_tickets(self, project, ticket_ids, request=None):
        ticket_cr = []
        for trac in project.tracs:
            proxy = TracXmlProxy(trac.application_uri(request), request=request)
            ticket_cr.extend(proxy.ticket.queryCustomerRequestsByTicktes(ticket_ids))
        return ticket_cr

    def add_tickets(self, project, customerrequest, tickets, reporter, notify=False):
        from trac.env import Environment
        from trac.ticket.notification import TicketNotifyEmail
        from trac.ticket.model import Ticket
        from trac.util.text import exception_to_unicode
        from penelope.core.models.dashboard import User

        settings = get_current_registry().settings
        tracenvs = settings.get('penelope.trac.envs')
        request = get_current_request()

        for trac in project.tracs:
            for t in tickets:
                owner = DBSession.query(User).get(t['owner'])
                ticket = {'summary': t['summary'],
                        'description': t['description'],
                        'customerrequest': customerrequest.id,
                        'reporter': reporter.email,
                        'type': 'task',
                        'priority': 'major',
                        'milestone': 'Backlog',
                        'owner': owner.email,
                        'status': 'new'}
                tracenv = Environment('%s/%s' % (tracenvs, trac.trac_name))
                tracenv.abs_href.base = trac.api_uri
                t = Ticket(tracenv)
                t.populate(ticket)
                t.insert()
                if notify:
                    try:
                        tn = TicketNotifyEmail(tracenv)
                        tn.notify(t, newticket=True)
                    except Exception, e:
                        request.add_message('Failure sending notification on creation '
                        'of a ticket #%s: %s' % (t.id, exception_to_unicode(e)), 'error')

ticket_store = TicketStore()
