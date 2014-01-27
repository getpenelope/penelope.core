# -*- coding: utf-8 -*-

from copy import deepcopy
from zope.interface import implements
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Interval
from sqlalchemy import Unicode
from sqlalchemy import String
from sqlalchemy import event
from sqlalchemy.orm import relationship, backref

from penelope.core.models.dublincore import dublincore_insert, dublincore_update, DublinCore
from penelope.core.models import Base, CustomerRequest, GlobalConfig, DBSession
from penelope.core.models import workflow, classproperty
from penelope.core.models.tickets import ticket_store
from penelope.core.models.interfaces import ITimeEntry, IProjectRelated
from penelope.core.security.acl import CRUD_ACL
from penelope.core.lib.helpers import timedelta_as_human_str, timedelta_as_work_days


class TimeEntryException(Exception):
    """Something wrong happened trying to add a time entry to a project"""


class TimeEntry(DublinCore, workflow.Workflow, Base):
    implements(ITimeEntry, IProjectRelated)
    __tablename__ = 'time_entries'

    id = Column(Integer, primary_key=True)
    start = Column(DateTime)
    end = Column(DateTime)
    date = Column(Date, index=True)
    hours = Column(Interval)
    description = Column(Unicode)
    location = Column(Unicode, nullable=False, default=u'RedTurtle')
    ticket = Column(Integer, index=True)
    tickettype = Column(String(25))
    tickettitle = Column(Unicode)
    invoice_number = Column(String(10))

    customer_request_id = Column(String, ForeignKey('customer_requests.id'))
    customer_request = relationship(CustomerRequest, backref=backref('time_entries', order_by=date.desc()))

    project_id = Column(String, ForeignKey('projects.id'), index=True, nullable=False)
    project = relationship('Project', uselist=False, backref=backref('time_entries', order_by=date.desc()))

    @classproperty
    def __acl__(cls):
        acl = deepcopy(CRUD_ACL)
        #add
        acl.allow('role:local_developer', 'new')
        acl.allow('role:local_project_manager', 'new')
        acl.allow('role:external_developer', 'new')
        acl.allow('role:internal_developer', 'new')
        acl.allow('role:secretary', 'new')
        acl.allow('role:project_manager', 'new')
        #view
        acl.allow('role:owner', 'view')
        acl.allow('role:project_manager', 'view')
        acl.allow('role:internal_developer', 'view')
        #edit
        acl.allow('role:project_manager', 'edit')
        acl.allow('role:secretary', 'manage')
        #delete
        isnew = bool(cls.workflow_state == u'new')
        if isnew: #only in new state
            acl.allow('role:owner', 'edit')
            acl.allow('role:owner', 'delete')
        acl.allow('role:project_manager', 'delete')
        #workflow
        acl.allow('role:secretary', 'workflow')
        acl.allow('role:project_manager', 'workflow')
        #listing
        acl.allow('role:project_manager', 'listing')
        return acl

    def __init__(self, *args, **kwargs):
        super(TimeEntry, self).__init__(*args, **kwargs)

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        return self.plaintext_description

    @property
    def contract(self):
        return self.customer_request.contract

    @property
    def plaintext_description(self):
        return self.description or ''

    @property
    def hours_str(self):
        return timedelta_as_human_str(self.hours)

    @property
    def hours_as_work_days(self):
        return timedelta_as_work_days(self.hours)

    def get_ticket(self, request=None):
        request = request or getattr(self, 'request', None)
        return ticket_store.get_ticket(self.project_id, self.ticket)

    def get_cost(self, author_only=False, company_only=False):
        """
        Return cost as a total of:
         * timeentry author cost
         * company cost
        """
        def get_author_cost():
            author = self.author.cost_per_day(self.date)
            return author and author.amount or 0

        def get_company_cost():
            company = DBSession().query(GlobalConfig).one().cost_per_day(self.date)
            return company and company.amount or 0

        if author_only:
            author_cost = get_author_cost()
            return self.hours_as_work_days * author_cost

        elif company_only:
            company_cost = get_company_cost()
            return self.hours_as_work_days * company_cost

        else:
            author_cost = get_author_cost()
            company_cost = get_company_cost()
            return (self.hours_as_work_days * author_cost) + (self.hours_as_work_days * company_cost)


def new_te_created(mapper, connection, target):
    trac_ticket = target.get_ticket()
    if trac_ticket:
        target.tickettype = trac_ticket[3]['type']
        target.tickettitle = trac_ticket[3]['summary']
        target.customer_request_id = trac_ticket[3]['customerrequest']


event.listen(TimeEntry, "before_insert", new_te_created)
event.listen(TimeEntry, "before_insert", dublincore_insert)
event.listen(TimeEntry, "before_update", dublincore_update)
