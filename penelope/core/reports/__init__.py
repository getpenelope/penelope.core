# -*- coding: utf-8 -*-
from pyramid.view import view_config

from penelope.core.lib.helpers import unicodelower
from penelope.core.reports.views import ReportContext; ReportContext
from penelope.core.reports.queries import filter_users_with_timeentries, qry_active_projects
from penelope.core.models import DBSession, Project, SavedQuery, User


@view_config(name='index', route_name='reports', renderer='skin', permission='reports_index')
def report_index(context, request):
    users = DBSession.query(User).order_by(User.fullname)
    users = filter_users_with_timeentries(users)
    projects = sorted(request.filter_viewables(qry_active_projects()), key=unicodelower)
    customers = sorted(set(p.customer for p in projects), key=unicodelower)

    current_uid = request.authenticated_user.id
    saved_queries = DBSession.query(SavedQuery).filter(SavedQuery.author_id==current_uid)
    return {
            'users': users,
            'customers': customers,
            'projects': projects,
            'saved_queries': saved_queries.all()
            }



@view_config(name='project_tree', route_name='reports', renderer='json', xhr=True)
def project_tree(context, request):
    """
    This view is used by the customer-project-request javascript filter.
    """
    all_projects = request.filter_viewables(DBSession.query(Project))

    all_projects = [
            project for project in request.filter_viewables(qry_active_projects())
            if request.has_permission('reports_all_entries_for_project', project)
            ]

    customers = request.filter_viewables(set(p.customer for p in all_projects if p.active))

    return [
            {
                'id': str(c.id),
                'name': c.name,
                'projects': [
                    {
                        'id': str(p.id),
                        'name': p.name,
                        'customer_requests': [
                            {
                                'id': str(cr.id),
                                'name': cr.name,
                                }
                            for cr in p.customer_requests
                            ],
                        'contracts': [
                            {
                                'id': str(co.id),
                                'name': co.name,
                                }
                            for co in p.contracts
                            ],
                        }
                    for p in c.projects if p in all_projects
                    ]
                }
            for c in customers
            ]

