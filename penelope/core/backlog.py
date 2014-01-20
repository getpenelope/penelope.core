# -*- coding: utf-8 -*-

import collections
import datetime
import sqlalchemy as sa

from repoze.workflow import get_workflow
from pyramid.view import view_config

from penelope.core import fanstatic_resources
from penelope.core.lib.helpers import unicodelower, total_seconds
from penelope.core.models import DBSession
from penelope.core.models.dashboard import Project, CustomerRequest
from penelope.core.models.tickets import ticket_store


class ProjectBGB(object):
    """
    Backlog-Grooming-Board table for each project
    """
    def __init__(self, project, estimations_cache, done_cache):
        self.project = project
        self.estimations_cache = estimations_cache
        self.done_cache = done_cache

    def get_estimate(self, cr):
        td = self.estimations_cache.get(cr.id, datetime.timedelta(0))
        return total_seconds(td)

    def get_done(self, cr):
        td = self.done_cache.get(cr.id, datetime.timedelta(0))
        return total_seconds(td)

    def get_percentage(self, cr):
        estimate = self.get_estimate(cr)
        if not estimate:
            return 0
        return float(self.get_done(cr)) / estimate * 100


class Backlog(object):
    def __init__(self, request):
        self.request = request
        self.context = request.context


    def fetch_estimations(self, projects):
        project_ids = [a.id for a in projects]
        return dict(
                (row.id, datetime.timedelta(days=row.estimation_days/3.0))    # 8 vs 24 hour days
                    for row in DBSession().query(CustomerRequest)\
                                          .filter(CustomerRequest.project_id.in_(project_ids))
                )

    def fetch_done(self, projects):
        cr_done = collections.defaultdict(lambda: datetime.timedelta(0))
        for project in projects:
            for t in project.time_entries:
                cr_done[t.customer_request_id] += t.hours
        return cr_done

    @view_config(name='backlog', renderer='skin', permission='view_backlog', http_cache=0)
    def backlog(self, projects=None):
        fanstatic_resources.backlog.need()

        session = DBSession()

        if projects is None:
            projects = session.query(Project)
            projects = sorted(self.request.filter_viewables(projects.filter(Project.active)),
                              key=lambda p: (p.customer.name.lower(), p.customer.name.lower()))

        estimations_cache = self.fetch_estimations(projects)
        done_cache = self.fetch_done(projects)

        bgbs = [ProjectBGB(p, estimations_cache, done_cache) for p in projects]

        workflow = get_workflow(CustomerRequest(), 'CustomerRequest')

        cr_workflow_states = [
                    (state, workflow._state_data[state]['title'] or state)
                    for state in workflow._state_order
                ]

        #------------
        # Permissions
        #------------

        can_view_done = collections.defaultdict(bool)
        can_view_done_column = False

        can_view_percentage = collections.defaultdict(bool)
        can_view_percentage_column = False

        can_view_estimate = collections.defaultdict(bool)
        can_view_estimate_column = False
        can_edit_cr = collections.defaultdict(bool)

        for project in projects:

            if self.request.has_permission('estimations', project):
                # display values in the project's "estimate" column, and the project's total
                can_view_estimate[project] = True
                can_view_done[project] = True
                # display values in the project's "done" column, and the project's total
                can_view_percentage[project] = True
                # display a big-total and inserts an "estimate" column in the table
                can_view_estimate_column = True
                # display a big-total and inserts a "done" column in the table
                can_view_done_column = True
                can_view_percentage_column = True

            for cr in project.customer_requests:
                if self.request.has_permission('edit', cr):
                    # let the user change the CR
                    can_edit_cr[cr] = True

        return {
            'bgbs': bgbs,
            'unicodelower': unicodelower,
            'multiple_bgb': True,
            'cr_workflow_states': cr_workflow_states,
            'cr_workflow_active': set(['created', 'estimated', 'achieved', 'invoiced']),
            'can_view_percentage': can_view_percentage,
            'can_view_percentage_column': can_view_percentage_column,
            'can_view_done': can_view_done,
            'can_view_done_column': can_view_done_column,
            'can_view_estimate': can_view_estimate,
            'can_view_estimate_column': can_view_estimate_column,
            'can_edit_cr': can_edit_cr
            }

