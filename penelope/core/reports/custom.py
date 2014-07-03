# -*- coding: utf-8 -*-

import colander
import collections
import datetime
import itertools
import logging
import operator
import sqlalchemy as sa

from colander import SchemaNode
from deform import ValidationFailure
from deform.widget import SelectWidget
from pyramid.renderers import render
from pyramid.view import view_config
from repoze.workflow import get_workflow
from sqlalchemy.orm import lazyload
from sqlalchemy import distinct
from webhelpers.html.builder import HTML, literal

from penelope.core.events import AfterEntryCreatedEvent
from penelope.core.lib.helpers import ticket_url, timeentry_url, ReversedOrder, total_seconds
from penelope.core.lib.widgets import SearchButton, PorInlineForm
from penelope.core.reports import fields
from penelope.core.reports.favourites import render_saved_query_form
from penelope.core.reports.queries import qry_active_projects, te_filter_by_customer_requests, filter_users_with_timeentries, te_filter_by_contracts
from penelope.core.reports.validators import validate_period

from penelope.core.models import DBSession, Project, TimeEntry, User, CustomerRequest, Contract, Customer
from penelope.core.models.tickets import ticket_store
from penelope.core.models.tp import timedelta_as_human_str

log = logging.getLogger(__name__)


class CustomerReport(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request


    class CustomSchema(colander.MappingSchema):
        customer_id = fields.customer_id.clone()
        customer_id.missing = colander.null

        project_id = fields.project_id.clone()
        customer_requests = fields.customer_requests.clone()
        contracts = fields.contracts.clone()
        date_from = fields.date_from.clone()
        date_to = fields.date_to.clone()
        users = fields.users.clone()
        workflow_states = fields.workflow_states.clone()

        detail_level = SchemaNode(colander.String(),
                                  validator=colander.OneOf(['project', 'request', 'ticket', 'timeentry', 'date']),
                                  widget=SelectWidget(values=[
                                          ('project', 'Project'),
                                          ('request', 'Request'),
                                          ('ticket', 'Ticket'),
                                          ('timeentry', 'Time Entry'),
                                          ('date', 'Date'),
                                      ]),
                                  default='timeentry',
                                  missing=colander.null,
                                  title=u'Detail')

    def format_web(self, value):
        if isinstance(value, datetime.timedelta):
            return timedelta_as_human_str(value)
        elif isinstance(value, float):
            return u'%.2f €' % value
        return value


    def format_xls(self, value):
        if isinstance(value, datetime.timedelta):
            # Render durations as float in order to sum them
            return total_seconds(value) / 60.0 / 60.0
        if isinstance(value, literal):
            # sanitize HTML
            return value.striptags()
        return value


    def search(self, customer_id, project_id, date_from, date_to, contracts,
               users, customer_requests, workflow_states, detail_level, render_links=True):

        # also search archived projects, if none are specified
        qry = DBSession.query(TimeEntry).join(TimeEntry.project).join(Project.customer).outerjoin(TimeEntry.author)
        qry = qry.options(lazyload(TimeEntry.project, TimeEntry.author, Project.customer))

        if customer_id is not colander.null:
            qry = qry.filter(Project.customer_id == customer_id)

        if project_id is not colander.null:
            qry = qry.filter(TimeEntry.project_id == project_id)

        if date_from is not colander.null:
            qry = qry.filter(TimeEntry.date>=date_from)

        if date_to is not colander.null:
            qry = qry.filter(TimeEntry.date<=date_to)

        if users:
            qry = qry.filter(TimeEntry.author_id.in_(users))

        if workflow_states:
            qry = qry.filter(TimeEntry.workflow_state.in_(workflow_states))

        qry = qry.filter(te_filter_by_customer_requests(customer_requests, request=self.request))

        qry = qry.filter(te_filter_by_contracts(contracts))

        qry = qry.order_by(sa.desc(TimeEntry.date), sa.desc(TimeEntry.start), sa.desc(TimeEntry.creation_date))

        time_entries = self.request.filter_viewables(qry)

        proj_tickets = collections.defaultdict(set)
        for te in time_entries:
            if te.ticket is None:
                continue
            proj_tickets[te.project_id].add(te.ticket)

        # projectsmap = {
        #    'project_id': {
        #         'ticket_id': 'customer_request_id',
        #         ...
        #    },
        #    ...
        # }

        projectsmap = {}
        for project_id, ticket_ids in proj_tickets.items():
            project = DBSession.query(Project).get(project_id)
            projectsmap[project_id] = dict(ticket_store.get_requests_from_tickets(
                                            project, tuple(ticket_ids)))

        tkts = {}
        for project_id, ticket_ids in proj_tickets.items():
            project = DBSession.query(Project).get(project_id)
            for tkt in ticket_store.get_tickets_for_project(project):
                tkts[(project_id, tkt['id'])] = tkt

        rows = []

        for te in time_entries:
            customer_request = te.customer_request
            if render_links:
                rendered_request = HTML.A(customer_request.name.strip(),
                                            href="%s/admin/CustomerRequest/%s" % (
                                                self.request.application_url,
                                                customer_request.id
                                                )
                                            )
            else:
                rendered_request = customer_request.name.strip()

            tkt = tkts[(te.project_id, te.ticket)]

            ticket_type = tkt['type']
            ticket_summary = tkt['summary']
            if render_links:
                ticket_summary = HTML.A(ticket_summary,
                                        href=ticket_url(request=self.request,
                                                        project=te.project,
                                                        ticket_id=te.ticket))

            description = HTML.A(te.description,
                                    href=timeentry_url(request=self.request,
                                                    time_entry=te))


            entry = {
                        'customer': te.project.customer.name.strip(),
                        'project': te.project.name.strip(),
                        'request': rendered_request,
                        'ticket_summary': ticket_summary,
                        'user': te.author.fullname.strip(),
                        'date': te.date.strftime('%Y-%m-%d'),
                        'description': description,
                        'location': te.location,
                        'ticket_type': ticket_type,
                        'sensitive': ['no', 'yes'][tkt['sensitive']],
                        'hours': te.hours,
                    }

            event = AfterEntryCreatedEvent(entry, te)
            self.request.registry.notify(event)

            rows.append(entry)

        columns = [
                    ('customer', u'Cliente'),
                    ('project', u'Progetto'),
                    ('request', u'Request'),
                    ('ticket_summary', u'Ticket'),
                    ('ticket_type', u'Tipologia'),
                    ('sensitive', u'Sensitive'),
                    ('user', u'Persona'),
                    ('date', u'Data'),
                    ('description', u'Descrizione attività'),
                    ('location', u'Sede'),
                    ('hours', u'Ore'),
                ]

        group_by = {
                    'project': ['customer', 'project', 'user'],
                    'request': ['customer', 'project', 'request', 'user'],
                    'ticket': ['customer', 'project', 'request', 'ticket_summary', 'ticket_type', 'sensitive', 'user'],
                    'timeentry': None,
                    'date': ['user', 'date', 'location'],
                }[detail_level]

        if group_by:
            rows, columns = self.group(rows, columns, group_by)

        return {
                'rows': rows,
                'columns': columns,
                }


    def group(self, rows, columns, group_by):
        missing = set(group_by) - set(c[0] for c in columns)
        if missing:
            raise ValueError(u"Could not find column: %s" % ', '.join(missing))

        hours = collections.defaultdict(datetime.timedelta)

        for key, group in itertools.groupby(rows,
                                            operator.itemgetter(*group_by)):
            for row in group:
                hours[key] += row['hours']

        rows = [
                dict(zip(group_by, key), hours=hours[key])
                for key in hours
                ]

        # order by the grouped columns again
        rows.sort(
                key = lambda row: [
                    # date is sorted descedent
                    (ReversedOrder(row[k]) if k=='date' else row[k])
                    for k in group_by
                    ]
                )

        return rows, [c for c in columns if c[0] in (group_by + ['hours'])]

    @view_config(name='custom_json', route_name='reports', renderer='json', permission='reports_custom')
    def custom_json(self):
        schema = self.CustomSchema(validator=validate_period).clone()
        form = PorInlineForm(schema,
                             action=self.request.current_route_url())
        controls = self.request.GET.items()
        appstruct = form.validate(controls)
        detail = self.search(render_links=False, **appstruct)
        result = []
        for row in detail['rows']:
            row['hours'] = timedelta_as_human_str(row['hours'])
            if 'description' in row:
                del row['description']
            result.append(row)
        return result

    @view_config(name='custom_xls', route_name='reports', renderer='xls_report', permission='reports_custom')
    def custom_xls(self):
        schema = self.CustomSchema(validator=validate_period).clone()
        form = PorInlineForm(schema,
                             action=self.request.current_route_url())
        controls = self.request.GET.items()
        appstruct = form.validate(controls)

        detail = self.search(render_links=False, **appstruct)

        columns = detail['columns']

        rows = [
                [
                    self.format_xls(row[col_key])
                    for col_key, col_title in columns
                    ] + [timedelta_as_human_str(row['hours'])]
                for row in detail['rows']
                ]

        return {
                'header': [col_title for col_key, col_title in columns] + ['Ore'],
                'rows': rows,
                }


    @view_config(name='report_custom', route_name='reports', renderer='skin', permission='reports_custom')
    def __call__(self):
        schema = self.CustomSchema(validator=validate_period).clone()
        projects = self.request.filter_viewables(qry_active_projects())
        project_ids = [p.id for p in projects]
        customers = DBSession.query(distinct(Customer.id), Customer.id, Customer.name).join(Project).filter(Project.id.in_(project_ids)).order_by(Customer.name)
        users = DBSession.query(User).order_by(User.fullname)
        users = filter_users_with_timeentries(users)
        customer_requests = DBSession.query(CustomerRequest.id, CustomerRequest.name).order_by(CustomerRequest.name)
        contracts = DBSession.query(Contract.id, Contract.name).order_by(Contract.name)

        form = PorInlineForm(schema,
                             action=self.request.current_route_url(),
                             formid='report-customer',
                             method='GET',
                             buttons=[
                                 SearchButton(title=u'Search'),
                             ])

        workflow = get_workflow(TimeEntry(), 'TimeEntry')

        all_wf_states = [
                            (state, workflow._state_data[state]['title'] or state)
                            for state in workflow._state_order
                        ]

        form['workflow_states'].widget.values = all_wf_states
        # XXX the following validator is broken
        form['workflow_states'].validator = colander.OneOf([str(ws[0]) for ws in all_wf_states])

        form['customer_id'].widget.values = [('', '')] + [(str(c.id), c.name) for c in customers]
        # don't validate as it might be an archived customer
        form['project_id'].widget.values = [('', '')] + [(str(p.id), p.name) for p in projects]
        # don't validate as it might be an archived project

        form['users'].widget.values = [(str(u.id), u.fullname) for u in users]
        form['customer_requests'].widget.values = [(str(c.id), c.name) for c in customer_requests]
        form['contracts'].widget.values = [(str(c.id), c.name) for c in contracts]

        controls = self.request.GET.items()

        if not controls or len(controls)==1: # detail_level param
            # the form is empty
            return {
                    'form': form.render(),
                    'saved_query_form': render_saved_query_form(self.request),
                    'qs':'',
                    'result_table': None
                    }

        try:
            appstruct = form.validate(controls)
        except ValidationFailure as e:
            return {
                    'form': e.render(),
                    'saved_query_form': render_saved_query_form(self.request),
                    'qs':'',
                    'result_table': None
                    }

        detail = self.search(render_links=True, **appstruct)

        result_table = None

        if detail['rows']:
            base_link = self.request.path_url.rsplit('/', 1)[0]
            xls_link = ''.join([base_link, '/', 'custom_xls', '?', self.request.query_string])
            json_link = ''.join([base_link, '/', 'custom_json', '?', self.request.query_string])
            delta0 = datetime.timedelta()
            delta_tot = sum((row['hours'] for row in detail['rows']), delta0)
            human_tot = timedelta_as_human_str(delta_tot)

            result_table = render('penelope.core:reports/templates/custom_results.pt',
                                  {
                                      'rows': detail['rows'],
                                      'columns': detail['columns'],
                                      'xls_link': xls_link,
                                      'json_link': json_link,
                                      'format_web': self.format_web,
                                      'human_tot': human_tot,
                                  },
                                  request=self.request)

        return {
                'form': form.render(appstruct=appstruct),
                'saved_query_form': render_saved_query_form(self.request),
                'qs': self.request.query_string,
                'result_table': result_table,
                }


