# -*- coding: utf-8 -*-
import re
from trac.core import TracError
from trac.ticket.query import Query
from trac.ticket.model import Ticket
from trac.env import Environment
from pyramid.threadlocal import get_current_registry, get_current_request
from zope.interface import implements
from penelope.core.models.interfaces import ITicketStore
from penelope.core.models import DBSession


class TicketStore(object):
    implements(ITicketStore)

    def get_ticket(self, project_id, ticket_id):
        from penelope.core.models.dashboard import Project
        project = DBSession().query(Project).get(project_id)
        if project:
            settings = get_current_registry().settings
            tracenvs = settings.get('penelope.trac.envs')
            for trac in project.tracs:
                tracenv = Environment('%s/%s' % (tracenvs, trac.trac_name))
                tracenv.abs_href.base = trac.api_uri
                try:
                    t = Ticket(tracenv, ticket_id)
                    return (t.id, t.time_created, t.time_changed, t.values)
                except TracError:
                    return None

    def get_raw_ticket(self, project_id, ticket_id):
        from penelope.core.models.dashboard import Project
        project = DBSession().query(Project).get(project_id)
        if project:
            settings = get_current_registry().settings
            tracenvs = settings.get('penelope.trac.envs')
            for trac in project.tracs:
                tracenv = Environment('%s/%s' % (tracenvs, trac.trac_name))
                tracenv.abs_href.base = trac.api_uri
                try:
                    return Ticket(tracenv, ticket_id)
                except TracError:
                    return None

    def get_tickets_for_project(self, project, query=None, limit=None, not_invoiced=False):

        def queryWithDetails(env, qstr='status!=closed'):
            """
            Perform a ticket query, returning a list of ticket dictionaries.
            All queries will use stored settings for maximum number of results per
            page and paging options. Use `max=n` to define number of results to
            receive, and use `page=n` to page through larger result sets. Using
            `max=0` will turn off paging and return all results.
            """
            # TODO: gestione custom id^= (workaround)
            if "id^=" in qstr:
                startswith = re.search('id\^=([\d]*)', qstr).group(1)
                qstr = re.sub('id\^=[\d]*', '', qstr)
                qstr = re.sub('^&|&$|&&', '', qstr)
                if "max=" in qstr:
                    limit = re.search('max=([\d]*)', qstr).group(1)
                    qstr = re.sub('max=[\d]*', 'max=0', qstr)
                else:
                    limit = None
            else:
                startswith = None
                limit = None

            q = Query.from_string(env, qstr)
            out = []
            for t in q.execute():
                tid = t['id']
                if not startswith or str(tid).startswith(startswith):
                    out.append(t)
                    if limit and len(out) >= limit:
                        break

            # fill 'resolution' value (it is not provided by the above query)
            db = env.get_db_cnx()
            cursor = db.cursor()
            cursor.execute("SELECT id, resolution FROM ticket WHERE status='closed'")
            
            resolution = {}
            for row in cursor:
                resolution[row[0]] = row[1]

            # fill 'sensitive' value (TODO optimize, as it now retrieves all tickets)
            db = env.get_db_cnx()
            cursor = db.cursor()
            cursor.execute("SELECT ticket, value FROM ticket_custom WHERE name='sensitive' AND value='1'")
            sensitive = set()
            for row in cursor:
                sensitive.add(row[0])

            # fill 'customerrequest' value (TODO optimize, as it now retrieves all tickets)
            cursor = db.cursor()
            cursor.execute("SELECT t.id AS ticket, c.value FROM ticket t INNER JOIN ticket_custom c ON (t.id = c.ticket AND c.name = 'customerrequest') order by ticket")
            cr= {}
            for row in cursor:
                cr[row[0]]=row[1]

            for t in out:
                t['sensitive'] = int(t['id'] in sensitive)
                t['resolution'] = resolution.get(t['id'], '')
                t['cr'] = cr.get(t['id'], '')

            return out

        tickets = []
        settings = get_current_registry().settings
        tracenvs = settings.get('penelope.trac.envs')

        for trac in project.tracs:
            if not query:
                query = []
            if limit:
                query.append('max=%s' % limit)
            else:
                query.append('max=0')

            tracenv = Environment('%s/%s' % (tracenvs, trac.trac_name))
            tracenv.abs_href.base = trac.api_uri
            tickets.extend(queryWithDetails(tracenv, '&'.join(query)))

        if not_invoiced:
            cr_ids = [cr.id for cr in project.customer_requests if cr.workflow_state in ['created', 'estimated']]
            tickets = [t for t in tickets if t['cr'] in cr_ids]

        return tickets

    def get_tickets_for_request(self, customer_request, limit=None):
        cr = customer_request
        return self.get_tickets_for_project(project=cr.project,
                                            query=['customerrequest=%s' % (cr.id)],
                                            limit=limit)

    def get_number_of_tickets_per_cr(self, project):
        settings = get_current_registry().settings
        if not settings:
            return

        tracenvs = settings.get('penelope.trac.envs')

        for trac in project.tracs:
            env = Environment('%s/%s' % (tracenvs, trac.trac_name))
            db = env.get_db_cnx()
            cursor = db.cursor()
            cursor.execute("""SELECT c.value as cr, count(t.id) AS number FROM ticket t INNER JOIN ticket_custom c ON (t.id = c.ticket AND c.name = 'customerrequest') group by cr;""")
            tickets = cursor.fetchall()
            db.rollback()
            return dict(tickets)

    def get_requests_from_tickets(self, project, ticket_ids):

        def queryCustomerRequestsByTicktes(env, ticket_ids):
            db = env.get_db_cnx()
            cursor = db.cursor()
            cursor.execute("""SELECT ticket, value FROM ticket_custom
                WHERE name='customerrequest' AND ticket IN %(tickets)s;""",
                    {'tickets': tuple(ticket_ids)})
            customer_request_ids = cursor.fetchall() or []
            db.rollback()
            return customer_request_ids

        ticket_cr = []
        settings = get_current_registry().settings
        tracenvs = settings.get('penelope.trac.envs')
        for trac in project.tracs:
            tracenv = Environment('%s/%s' % (tracenvs, trac.trac_name))
            tracenv.abs_href.base = trac.api_uri
            ticket_cr.extend(queryCustomerRequestsByTicktes(tracenv, ticket_ids))
        return ticket_cr

    def add_tickets(self, project, customerrequest, tickets, reporter, notify=False):
        from trac.ticket.notification import TicketNotifyEmail
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
