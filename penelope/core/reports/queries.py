# -*- coding: utf-8 -*-

import sqlalchemy as sa

from penelope.core.models import DBSession, Project, CustomerRequest, TimeEntry
from penelope.core.models.tickets import ticket_store


class NullCustomerRequest(object):
    def __init__(self, project=None):
        self.project = project

    name = '(no request)'



def qry_active_projects():
    return DBSession.query(Project)\
            .filter(Project.activated==True)\
            .filter(Project.customer_id!=None)\
            .order_by(Project.name)


def filter_users_with_timeentries(users):
    with_te = set(row.author_id for row in DBSession.query(TimeEntry.author_id).group_by(TimeEntry.author_id))
    return [user for user in users if user.id in with_te]


def te_filter_by_customer_requests(customer_requests, request):
    """
    Returns a SQL Expression to filter time entries, that belong to the provided customer_requests.
    The returned expression can be applied to a query on the TimeEntry table.

    If customer_requests is empty, no filter is applied.
    """

    if not customer_requests:
        return sa.text('1=1')

    cr_get = DBSession.query(CustomerRequest).get

    selected_tickets = []
    for cr_id in customer_requests or []:
        cr = cr_get(cr_id)
        selected_tickets.extend((cr.project_id, tkt['id']) for tkt in
                ticket_store.get_tickets_for_request(customer_request=cr, request=request))

    return sa.and_(sa.sql.tuple_(TimeEntry.project_id, TimeEntry.ticket).in_(selected_tickets))


