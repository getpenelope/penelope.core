# -*- coding: utf-8 -*-

import datetime
import re

from pyramid.view import view_config
from pyramid.response import Response

from penelope.core.api import timeentry_crstate_validation_errors
from penelope.core.lib.helpers import unicodelower
from penelope.core.lib.helpers import time_chunks
from penelope.core.models import DBSession
from penelope.core.models.dashboard import Project
from penelope.core.models.tp import TimeEntry
from penelope.core.models.tickets import ticket_store


class SmartAdd(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request


    @view_config(name='smartadd_projects', renderer='json')
    def smartadd_projects(self):
        """
        Returns a json list of project tags
        """
        qry = self.request.filter_viewables(DBSession.query(Project).filter(Project.active))
        projects = sorted((u'%s - %s' % (p.name, p.customer.name) for p in qry), key=unicodelower)
        return projects


    @view_config(name='smartadd_tickets', renderer='json')
    def smartadd_tickets(self):
        """
        Returns a json list of ticket tags
        """
        qry = self.request.filter_viewables(DBSession.query(Project).filter(Project.active))
        projects = dict(('%s - %s' % (p.name, p.customer.name), p.id) for p in qry)
        text = self.request.params['text']

        parser = SmartAddParser(text,
                                projects=projects,
                                request=self.request)

        if parser.TAG_TICK in parser.unparsed:
            ticket_search = parser.unparsed.split(parser.TAG_TICK)[-1]
        else:
            ticket_search = ''


        if ticket_search.isdigit():
            # ^= is startswith (http://trac.edgewall.org/wiki/TracQuery)
            query = ['id^=%s' % ticket_search]
        elif ticket_search:
            query = ['summary~=%s' % ticket_search]
        else:
            query = None

        if parser.project_id:
            project = DBSession.query(Project).get(parser.project_id)
            tickets = ticket_store.get_tickets_for_project(
                            project=project,
                            query=query,
                            not_invoiced=True,
                            limit=15)
        else:
            tickets = []

        return [
            "%(id)s %(summary)s" % ticket
            for ticket in tickets
            if ticket['resolution'] not in ('invalid', 'duplicate')
            ]


    @view_config(name='smartadd_submit', request_method='POST')
    def smartadd_submit(self):
        """
        Receives a line of smart-add and performs validation/insertion.
        """
        projects = dict(
                ('%s - %s' % (p.name, p.customer.name), p.id)
                for p in self.request.filter_viewables(DBSession.query(Project).filter(Project.active))
                )

        def ticket_provider(project_id):
            if project_id:
                project = DBSession.query(Project).get(project_id)
                return [
                        t['id']
                        for t in ticket_store.get_tickets_for_project(project=project,
                                                                      not_invoiced=True)
                        ]

        parser = SmartAddParser(unicode(self.request.body, 'utf8', 'ignore'),
                                projects=projects,
                                available_tickets=ticket_provider,
                                request=self.request)

        errors = parser.validation_errors()
        if errors:
            # XXX register appropriate exception handler
            return Response(' - '.join(errors), status_int=400)

        pte = parser.parsed_time_entry
        parsed_tickets = pte['tickets']
        ticket_summaries = []

        entry_durations = list(time_chunks(pte['hours'], len(parsed_tickets)))

        for parsed_ticket, duration in zip(parsed_tickets, entry_durations):
            date = pte.get('date') or datetime.date.today()

            te = TimeEntry(date = date,
                           start = pte['start'],
                           end = pte['start'],
                           description = pte['description'],
                           ticket = parsed_ticket,
                           project_id = pte['project_id'],
                           hours = duration,
                           )
            te.request = self.request #bind for user calculation
            DBSession.add(te)
            # retrieve ticket descriptions (another trip to the store..)
            ticket_summaries.append(
                    '#%s (%s)' % (te.ticket, ticket_store.get_ticket(te.project_id, te.ticket)[3]['summary'])
                )

        return Response(u'Added to ticket(s) %s' % ', '.join(ticket_summaries))


class SmartAddParser(object):
    TAG_PROJ = '@'
    TAG_TIME = '^'
    TAG_TICK = '#'
    TAG_DATE = '!'

    project_id = None
    ticket = None
    hours = None
    unparsed = None

    def __init__(self, text, projects=None, available_tickets=None, request=None):
        self.project_id, text = self.parse_project(text, projects or {})
        self.tickets, text = self.parse_tickets(text, self.project_id, available_tickets or {})
        self.hours, text = self.parse_hours(text)
        self.date, text = self.parse_date(text)
        self.unparsed = text.strip()
        self.request = request


    @classmethod
    def parse_project(cls, text, projects):
        found_match = None
        found_string = ''
        found_start = 1e6

        # case insensitive search and lookup
        projects = dict((p[0].lower(), p[1]) for p in projects.iteritems())

        for project_name, project_id in projects.items():
            m = re.search('%s(%s)' % (re.escape(cls.TAG_PROJ), re.escape(project_name)), text, flags=re.IGNORECASE)
            if m and ((found_start > m.start()) or len(project_name) > len(found_string)):
                found_match = m
                found_string = m.groups()[0].lower()
                found_start = m.start()

        if found_string:
            text = cls._removematch(text, found_match)

        return projects.get(found_string), text


    @classmethod
    def _removematch(self, text, m):
        """
        Returns the text string minus the match.
        """
        start, end = m.span()
        head, tail = text[:start], text[end:]
        if tail.startswith(' '):
            tail = tail[1:]
        return head + tail


    @classmethod
    def _removematchingticket(self, text, ticket_id):
        """
        Returns the text string minus the matching ticket occurrences.
        """
        while True:
            match = re.search('%s(%s)(?=\D|$)' % (re.escape(self.TAG_TICK), ticket_id), text)
            if not match:
                break
            text = self._removematch(text, match)

        return text


    def _matching_tickets(self, text):
        """
        Returns the matching ticket numbers still inside 'text'.
        """
        return re.findall('%s(\d+)(?=\D|$)' % re.escape(self.TAG_TICK), text)


    def parse_tickets(self, text, project_id, available_tickets):

        if callable(available_tickets):
            available_tickets = available_tickets(project_id)

        if available_tickets is None:
            available_tickets = []

        available_tickets = map(str, available_tickets)

        found_tickets = []
        for ticket_id in self._matching_tickets(text):
            if ticket_id in available_tickets and ticket_id not in found_tickets:
                found_tickets.append(ticket_id)

        for ticket_id in found_tickets:
            text = self._removematchingticket(text, ticket_id)

        return found_tickets, text


    def parse_hours(self, text):
        m = re.search('%s(?P<hh>\d\d*):(?P<mm>\d\d)(?=\D|$)' % re.escape(self.TAG_TIME), text)
        if m:
            gd = m.groupdict()
            text = self._removematch(text, m)
            return datetime.timedelta(hours=int(gd['hh']), minutes=int(gd['mm'])), text

        m = re.search('%s(?P<hh>\d\d*)(?=[^:\d]|$)' % re.escape(self.TAG_TIME), text)
        if m:
            gd = m.groupdict()
            text = self._removematch(text, m)
            return datetime.timedelta(hours=int(gd['hh'])), text

        m = re.search('%s:(?P<mm>\d\d*)(?=\D|$)' % re.escape(self.TAG_TIME), text)
        if m:
            gd = m.groupdict()
            text = self._removematch(text, m)
            return datetime.timedelta(minutes=int(gd['mm'])), text

        return None, text


    def parse_date(self, text):
        m = re.search('%s(today|yesterday)' % re.escape(self.TAG_DATE), text)
        if m:
            day = m.groups()[0]
            text = self._removematch(text, m)
            if day == 'today':
                return datetime.date.today(), text
            elif day == 'yesterday':
                return (datetime.date.today() - datetime.timedelta(days=1)), text

        return None, text


    def validation_errors(self):
        errors = []

        if self.project_id is None:
            if self.TAG_PROJ in self.unparsed:
                errors.append(u'Project not found')
            else:
                errors.append(u'Project is missing')

        if self.hours is None:
            if self.TAG_TIME in self.unparsed:
                errors.append(u'Could not parse time')
            else:
                errors.append(u'Time is missing')

        if self.date is None and self.TAG_DATE in self.unparsed:
            errors.append(u'Cannot parse date')

        missing_tickets = self._matching_tickets(self.unparsed)
        if missing_tickets:
            errors.append(u'{ticket_label} {ticket_numbers} not found or customer request already invoiced'.format(
                                        ticket_label = ['Ticket', 'Tickets'][len(missing_tickets)>1],
                                        ticket_numbers = ', '.join('#'+ticket_id for ticket_id in missing_tickets)),
                                        )
        elif not self.tickets:
            errors.append(u'Ticket is missing')

        if not self.unparsed:
            errors.append(u'Description is empty')

        if self.request:
            errors.extend(timeentry_crstate_validation_errors(self.project_id, self.tickets, request=self.request))

        return errors


    @property
    def parsed_time_entry(self):
        return {
                'start': None,
                'end': None,
                'hours': self.hours,
                'description': self.unparsed,
                'location': None,
                'tickets': self.tickets or None,
                'project_id': self.project_id,
                'date': self.date,
                }
