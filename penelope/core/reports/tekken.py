# -*- coding: utf-8 -*-

import json
import logging
import colander

from sqlalchemy import distinct

from deform import ValidationFailure
from pyramid.view import view_config
from webhelpers.html.builder import literal

from penelope.core.models import (
    DBSession,
    Project,
    Customer,
    Contract,
    CustomerRequest
)
from penelope.core import fanstatic_resources
from penelope.core.lib.widgets import SearchButton, PorInlineForm
from penelope.core.reports.queries import (
    qry_active_projects,
)
from penelope.core.reports import fields

log = logging.getLogger(__name__)


class IDTree(dict):
    # XXX see if we can do without this silly tree

    def insert_entry(self, groupby, cr_id, customer,
                     project, request, contract, **ignore):
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
            elif nodetype == 'request':
                node.setdefault(request, default)
                node = node[request]
            elif nodetype == 'contract':
                node.setdefault(contract, default)
                node = node[contract]
            else:
                raise ValueError('unsupported groupby value?')
        node.append(cr_id)


class TekkenReport(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def format_xls(self, value):
        if isinstance(value, literal):
            # sanitize HTML
            return value.striptags()
        return value

    class TekkenSchema(colander.MappingSchema):
        customer_id = fields.customer_id.clone()
        project_id = fields.project_id.clone()

    def search(self, customer_id, project_id):
        qry = DBSession.query(CustomerRequest)\
                       .join(Contract)\
                       .join(Project)\
                       .join(Customer)\
                       .filter(Project.activated == True)  # noqa

        groupby = ['customer', 'project', 'contract', 'request']

        if customer_id is not colander.null:
            qry = qry.filter(Project.customer_id == customer_id)

        if project_id is not colander.null:
            qry = qry.filter(Project.id == project_id)

        rows = []
        id_tree = IDTree()

        for cr in qry:
            entry = {
                'customer': cr.project.customer.name.strip(),
                'project': cr.project.name.strip(),
                'request': cr.name.strip(),
                'contract': cr.contract.name.strip(),
                'estimated_days_label': 'Estimated days',
                'estimated_days': cr.estimation_days,
                'worked_days_label': 'Worked days',
                'worked_days': cr.timeentries_days
            }
            rows.append(entry)
            id_tree.insert_entry(groupby, cr.id, **entry)

        return {
                'groupby': groupby,
                'rows': rows,
                'id_tree': id_tree,
                }

    @view_config(name='report_tekken', route_name='reports',
                 renderer='skin', permission='report_tekken')
    def __call__(self):
        fanstatic_resources.report_tekken.need()
        schema = self.TekkenSchema().clone()

        projects = qry_active_projects()
        project_ids = [p.id for p in projects]

        c = [distinct(Customer.id), Customer.id, Customer.name]
        customers = DBSession.query(*c)\
                             .join(Project)\
                             .filter(Project.id.in_(project_ids))\
                             .order_by(Customer.name)

        form = PorInlineForm(schema,
                             action=self.request.current_route_url(),
                             formid='all_entries',
                             method='GET',
                             buttons=[
                                 SearchButton(title=u'Search'),
                             ])

        form['customer_id'].widget.values = [('', '')] + \
            [(str(c.id), c.name) for c in customers]

        form['project_id'].widget.values = [('', '')] + \
            [(str(p.id), p.name) for p in projects]

        controls = self.request.GET.items()
        base_link = self.request.path_url.rsplit('/', 1)[0]
        xls_link = '{}/costs_xls?{}'.format(base_link,
                                            self.request.query_string)

        if not controls:
            # the form is empty
            return {
                    'form': form.render(),
                    'xls_link': xls_link,
                    'qs': '',
                    'has_results': False
                    }

        try:
            appstruct = form.validate(controls)
        except ValidationFailure as e:
            return {
                    'form': e.render(),
                    'xls_link': xls_link,
                    'qs': self.request.query_string,
                    'has_results': False
                    }

        entries_detail = self.search(**appstruct)

        col_headers = {
            'customer': u'Customer',
            'project': u'Project',
            'contract': u'Contract',
            'request': u'Request',
        }

        columns = [
            {'colvalue': 'estimated_days_label',
             'groupbyrank': None,
             'pivot': True,
             'result': False
             },
            {'colvalue': 'worked_days_label',
             'groupbyrank': None,
             'pivot': True,
             'result': False
             }
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

        columns.append({'colvalue': 'estimated_days',
                        'groupbyrank': None,
                        'pivot': False,
                        'result': True})
        columns.append({'colvalue': 'worked_days',
                        'groupbyrank': None,
                        'pivot': False,
                        'result': True})

        sourcetable = {
                    'rows': entries_detail['rows'],
                    'columns': columns
                }

        return {
                'form': form.render(appstruct=appstruct),
                'qs': self.request.query_string,
                'xls_link': None,
                'has_results': len(sourcetable['rows']) > 0,
                'tpReport_oConf': json.dumps({
                                    'sourcetable': sourcetable,
                                    'id_tree': entries_detail['id_tree'],
                                    'groupby': entries_detail['groupby'],
                                }),
                }
