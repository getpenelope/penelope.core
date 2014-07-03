# -*- coding: utf-8 -*-

import sqlalchemy as sa

from penelope.core.models import DBSession, Project, TimeEntry, CustomerRequest


class NullCustomerRequest(object):
    def __init__(self, project=None):
        self.project = project

    name = '(no request)'



def qry_active_projects():
    return DBSession.query(Project)\
            .filter(Project.customer_id!=None)\
            .order_by(Project.name)
#            .filter(Project.activated==True)\


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

    return TimeEntry.customer_request_id.in_(customer_requests)


def te_filter_by_contracts(contracts):
    if not contracts:
        return sa.text('1=1')

    # get customer requests for contracts
    customer_requests = DBSession().query(CustomerRequest.id).filter(CustomerRequest.contract_id.in_(contracts))
    return te_filter_by_customer_requests(customer_requests, None)
