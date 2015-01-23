# -*- coding: utf-8 -*-

import collections
import json
import logging

import colander
from sqlalchemy.orm import lazyload
from sqlalchemy import distinct
from colander import SchemaNode

from deform import ValidationFailure
from deform.widget import SelectWidget
from pyramid.httpexceptions import HTTPForbidden
from pyramid.view import view_config

from penelope.core.models import DBSession, Project, TimeEntry, User, CustomerRequest, Contract, Customer
from penelope.core.models.tickets import ticket_store
from penelope.core import fanstatic_resources
from penelope.core.lib.helpers import ticket_url, total_seconds
from penelope.core.lib.widgets import SearchButton, PorInlineForm
from penelope.core.reports.queries import qry_active_projects, te_filter_by_customer_requests, filter_users_with_timeentries, te_filter_by_contracts
from penelope.core.reports.validators import validate_period
from penelope.core.reports.favourites import render_saved_query_form
from penelope.core.reports import fields

log = logging.getLogger(__name__)


class IDTree(dict):
    # XXX see if we can do without this silly tree

    def insert_entry(self, groupby, te_id, customer, project, contract, request, user, date, **discard):
        """
        populates the tree with time-entry ids
        """
        node = self
        for idx, nodetype in enumerate(groupby, 1):
            if idx < len(groupby):
                default = {}
            else:
                default = []

            if nodetype == 'customer':
                node.setdefault(customer, default)
                node = node[customer]
            elif nodetype == 'project':
                node.setdefault(project, default)
                node = node[project]
            elif nodetype == 'contract':
                node.setdefault(contract, default)
                node = node[contract]
            elif nodetype == 'request':
                node.setdefault(request, default)
                node = node[request]
            elif nodetype == 'user':
                node.setdefault(user, default)
                node = node[user]
            elif nodetype == 'date':
                node.setdefault(date, default)
                node = node[date]
            else:
                raise ValueError('unsupported groupby value: {}'.format(nodetype))

        node.append(te_id)


class AllEntriesReport(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request


    class AllEntriesSchema(colander.MappingSchema):
        customer_id = fields.customer_id.clone()
        project_id = fields.project_id.clone()
        date_from = fields.date_from.clone()
        date_to = fields.date_to.clone()
        users = fields.users.clone()
        contracts = fields.contracts.clone()
        customer_requests = fields.customer_requests.clone()

        groupbyfirst = SchemaNode(colander.String(),
                                  validator=colander.OneOf([
                                                            'project.contract.request.user.date',
                                                            'project.contract.request.date.user',
                                                            'project.user.contract.request.date',
                                                            'project.user.date.contract.request',
                                                            'project.date.user.contract.request',
                                                            'user.project.contract.request.date',
                                                            'user.project.date.contract.request',
                                                            'user.date.project.contract.request',
                                                            'date.user.project.contract.request',
                                                            ]),
                                  widget=SelectWidget(values=[
                                          ('project.contract.request.user.date', 'Project/Request/User/Date'),
                                          ('project.contract.request.date.user', 'Project/Request/Date/User'),
                                          ('project.user.contract.request.date', 'Project/User/Request/Date'),
                                          ('project.user.date.contract.request', 'Project/User/Date/Request'),
                                          ('project.date.user.contract.request', 'Project/Date/User/Request'),
                                          ('user.project.contract.request.date', 'User/Project/Request/Date'),
                                          ('user.project.date.contract.request', 'User/Project/Date/Request'),
                                          ('user.date.project.contract.request', 'User/Date/Project/Request'),
                                          ('date.user.project.contract.request', 'Date/User/Project/Request'),
                                      ]),
                                  default='project.contract.request.user.date',
                                  missing='project.contract.request.user.date',
                                  title=u'')



    def search(self, customer_id, project_id, date_from, date_to,
               users, customer_requests, groupbyfirst, contracts):

        # also search archived projects, if none are specified
        qry = DBSession.query(TimeEntry).join(TimeEntry.project).join(Project.customer).outerjoin(TimeEntry.author)
        qry = qry.options(lazyload(TimeEntry.project, TimeEntry.author, Project.customer))

        groupby = ['customer']

        groupby.extend(groupbyfirst.split('.'))

        if customer_id is not colander.null:
            qry = qry.filter(Project.customer_id == customer_id)
            groupby.remove('customer')

        if project_id is not colander.null:
            qry = qry.filter(TimeEntry.project_id == project_id)
            try:
                groupby.remove('customer')
            except ValueError:
                pass
            groupby.remove('project')

        if date_from is not colander.null:
            qry = qry.filter(TimeEntry.date>=date_from)

        if date_to is not colander.null:
            qry = qry.filter(TimeEntry.date<=date_to)

        if date_from == date_to and date_from is not colander.null:
            groupby.remove('date')

        if contracts:
            groupby.remove('contract')

        if users:
            qry = qry.filter(TimeEntry.author_id.in_(users))

        qry = qry.filter(te_filter_by_customer_requests(customer_requests, request=self.request))

        qry = qry.filter(te_filter_by_contracts(contracts))

        rows = []

        id_tree = IDTree()

        time_entries = list(self.request.filter_viewables(qry))

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
            if not self.request.has_permission('reports_all_entries_for_project', project):
                continue
            projectsmap[project_id] = dict(ticket_store.get_requests_from_tickets(
                                            project, tuple(ticket_ids)))

        for te in time_entries:
            if not self.request.has_permission('reports_all_entries_for_project', te.project):
                continue

            customer_request = te.customer_request
            entry = {
                        'customer': te.project.customer.name.strip(),
                        'project': te.project.name.strip(),
                        'contract': customer_request.contract.name.strip(),
                        'request': customer_request.name.strip(),
                        'user': te.author.fullname.strip(),
                        'date': te.date.strftime('%Y-%m-%d'),
                        'description': te.description,
                        'seconds': total_seconds(te.hours),
                        'time': 'ore',
                    }

            rows.append(entry)
            id_tree.insert_entry(groupby, te.id, **entry)

        return {
                'groupby': groupby,
                'rows': rows,
                'id_tree': id_tree,
                }


    @view_config(name='report_all_entries', route_name='reports', renderer='skin', permission='reports_all_entries')
    def __call__(self):
        fanstatic_resources.report_all_entries.need()

        schema = self.AllEntriesSchema(validator=validate_period).clone()

        if len([a for a in self.request.authenticated_user.roles if a.name == 'administrator']) == 1:
            projects = qry_active_projects()
        else:
            projects = [
                    project for project in self.request.filter_viewables(qry_active_projects())
                    if self.request.has_permission('reports_all_entries_for_project', project)
                    ]

        project_ids = [p.id for p in projects]
        customers = DBSession.query(distinct(Customer.id), Customer.id, Customer.name).join(Project).filter(Project.id.in_(project_ids)).order_by(Customer.name)
        users = DBSession.query(User).order_by(User.fullname)
        users = filter_users_with_timeentries(users)
        customer_requests = DBSession.query(CustomerRequest.id, CustomerRequest.name).order_by(CustomerRequest.name)
        contracts = DBSession.query(Contract.id, Contract.name).order_by(Contract.name)


        form = PorInlineForm(schema,
                             action=self.request.current_route_url(),
                             formid='all_entries',
                             method='GET',
                             buttons=[
                                 SearchButton(title=u'Search'),
                             ])

        form['customer_id'].widget.values = [('', '')] + [(str(c.id), c.name) for c in customers]
        # don't validate as it might be an archived customer
        form['project_id'].widget.values = [('', '')] + [(str(p.id), p.name) for p in projects]
        # don't validate as it might be an archived project

        form['users'].widget.values = [(str(u.id), u.fullname) for u in users]
        form['customer_requests'].widget.values = [(str(c.id), c.name) for c in customer_requests]
        form['contracts'].widget.values = [(str(c.id), c.name) for c in contracts]

        controls = self.request.GET.items()

        if not controls:
            # the form is empty
            return {
                    'form': form.render(),
                    'saved_query_form': render_saved_query_form(self.request),
                    'qs':'',
                    'has_results': False
                    }

        try:
            appstruct = form.validate(controls)
        except ValidationFailure as e:
            return {
                    'form': e.render(),
                    'saved_query_form': render_saved_query_form(self.request),
                    'qs': self.request.query_string,
                    'has_results': False
                    }

        entries_detail = self.search(**appstruct)

        col_headers = {
            'customer': u'Customer',
            'project': u'Project',
            'contract': u'Contract',
            'request': u'Request',
            'user': u'User',
            'date': u'Data',
        }

        columns = [
            { 'colvalue': 'time', 'groupbyrank': None, 'pivot': True, 'result': False },
        ]

        for idx, colname in enumerate(entries_detail['groupby']):
            columns.append({
                            'colvalue': colname,
                            'coltext': colname,
                            'header': col_headers[colname],
                            'groupbyrank': idx+1,
                            'pivot': False,
                            'result': False
                           })

        columns.append({'colvalue': 'description', 'coltext': 'description', 'header': 'description', 'pivot': False, 'result': False})
        columns.append({'colvalue': 'seconds', 'groupbyrank': None, 'pivot': False, 'result': True})

        sourcetable = {
                    'rows': entries_detail['rows'],
                    'columns': columns
                }

        return {
                'form': form.render(appstruct=appstruct),
                'saved_query_form': render_saved_query_form(self.request),
                'qs': self.request.query_string,
                'has_results': len(sourcetable['rows'])>0,
                'tpReport_oConf': json.dumps({
                                    'sourcetable': sourcetable,
                                    'id_tree': entries_detail['id_tree'],
                                    'groupby': entries_detail['groupby'],
                                }),
                }



    @view_config(name='all_entries_xls', route_name='reports', renderer='xls_report', permission='reports_all_entries')
    @view_config(name='all_entries_csv', route_name='reports', renderer='csv_report', permission='reports_all_entries')
    def all_entries_download(self):
        schema = self.AllEntriesSchema().clone()
        form = PorInlineForm(schema)
        controls = self.request.GET.items()
        appstruct = form.validate(controls)

        header = ['cliente', 'progetto', 'request', 'user', 'data', 'descrizione', 'ore']

        rows = [
                (
                    row['customer'],
                    row['project'],
                    row['request'],
                    row['user'],
                    row['date'],
                    row['description'],
                    row['seconds']/60.0/60.0,
                )
            for row in self.search(**appstruct)['rows']
            ]

        return {
                'header': header,
                'rows': rows
                }


@view_config(name='report_te_detail', route_name='reports', renderer='skin', permission='reports_all_entries')
def report_te_detail(context, request):
    ids = map(int, request.params['ids'].split(','))
    qry = DBSession.query(TimeEntry).filter(TimeEntry.id.in_(ids)).order_by(TimeEntry.id)
    projects = set(te.project for te in qry)
    for project in projects:
        if not request.has_permission('reports_all_entries_for_project', project):
            return HTTPForbidden()
    return {
            'time_entries': qry.all(),
            'ticket_url': ticket_url,
            }

