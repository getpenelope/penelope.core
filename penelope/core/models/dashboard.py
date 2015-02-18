# -*- coding: utf-8 -*-

import hashlib
import string
import random
import re
import urllib
import datetime

from json import loads
from copy import deepcopy
from zope.interface import implements
from zope.component import getMultiAdapter
from plone.i18n.normalizer import idnormalizer
from pyramid.security import ALL_PERMISSIONS
from pyramid.security import Authenticated
from pyramid.threadlocal import get_current_request
from repoze.workflow import get_workflow
from repoze.workflow import WorkflowError

from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer, Float
from sqlalchemy import String, Date
from sqlalchemy import Unicode
from sqlalchemy import Boolean
from sqlalchemy import Sequence
from sqlalchemy import Table
from sqlalchemy import event, func, and_
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import deferred
from sqlalchemy.orm import column_property
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.orm.properties import ColumnProperty

from penelope.core.security.acl import CRUD_ACL, ACL, IRoleFinder
from penelope.core.security.acl import invalidate_user_calculate_matrix, invalidate_users_calculate_matrix
from penelope.core import html2text
from penelope.core.models import Base, DBSession, dublincore, workflow, classproperty
from penelope.core.models.interfaces import ICustomerRequest, IRoleable, IProjectRelated
from penelope.core.models.interfaces import IProject, IUser, IPorModel, ICustomer, IRole
from penelope.core.models.interfaces import IApplication, ITrac, ISVN, IGoogleDocs
from penelope.core.models.interfaces import ITracReport, IGenericApp, IContract, IKanbanBoard


role_assignments = Table('role_assignments', Base.metadata,
    Column('principal_id', Integer, ForeignKey('principals.id')),
    Column('role_id', String, ForeignKey('roles.id'))
)

group_assignments = Table('group_assignments', Base.metadata,
    Column('group_id', Integer, ForeignKey('groups.id')),
    Column('user_id', Integer, ForeignKey('users.id'))
)

favorite_projects = Table('favorite_projects', Base.metadata,
    Column('project_id', String, ForeignKey('projects.id')),
    Column('user_id', Integer, ForeignKey('users.id'))
)

kanban_projects = Table('kanban_projects', Base.metadata,
    Column('project_id', String, ForeignKey('projects.id')),
    Column('kanban_id', Integer, ForeignKey('kanban_boards.id'))
)


class GlobalConfig(Base):
    implements(IPorModel)

    __tablename__ = "global_config"
    __acl__ = ACL('por_global_config_acl')
    __acl__.deny('system.Everyone', ALL_PERMISSIONS)

    id = Column(Integer, primary_key=True)
    active_iteration_url = Column(Unicode)

    def cost_per_day(self, day):
        for cost in self.costs:
            if day >= cost.date:
                return cost


class Principal(Base):
    implements(IPorModel)

    __tablename__ = "principals"
    __acl__ = deepcopy(CRUD_ACL)

    id = Column(Integer, Sequence("principals_id"), primary_key=True)


class Role(Base):
    implements(IRole)

    __tablename__ = "roles"
    __acl__ = deepcopy(CRUD_ACL)

    id = Column(String, primary_key=True)
    name = Column(String(64), unique=True)

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return "<Role id=%s name=%s>" % (self.id, self.name)


def new_role_created(mapper, connection, target):
    target.id = idnormalizer.normalize(target.name, max_length=100)

event.listen(Role, "before_insert", new_role_created)


class LowercaseComparator(ColumnProperty.Comparator):
    def __eq__(self, other):
        return func.lower(self.__clause_element__()) == func.lower(other)


class User(Principal):
    implements(IRoleable, IUser)

    __tablename__ = 'users'

    @classproperty
    def __acl__(cls):
        acl = deepcopy(CRUD_ACL)
        if bool(cls.active):
            acl.allow('role:owner', 'edit')
            acl.allow('role:owner', 'view')
        return acl

    id = Column(Integer, ForeignKey(Principal.id),
        Sequence("principals_id"),
        primary_key=True)

    fullname = Column(Unicode)
    __mapper_args__ = {'order_by': func.substring(fullname, '([^[:space:]]+)(?:,|$)')}
    email = column_property(Column('email', Unicode, unique=True),
                            comparator_factory=LowercaseComparator)
    svn_login = deferred(Column(Unicode, unique=True, nullable=False))
    phone = deferred(Column(String(20)))
    mobile = deferred(Column(String(20)))
    password = deferred(Column(String))
    salt = deferred(Column(String(12)))
    roles = relationship(Role, secondary=role_assignments, backref="users")
    gdata_auth_token = deferred(Column(String(64)))
    active = deferred(Column(Boolean, nullable=False, default=True))

    @hybrid_property
    def login(self):
        return self.email

    def generate_salt(self):
        return ''.join(random.sample(string.letters, 12))

    def encrypt(self, password):
        #force everything to become string:
        password = password.encode('utf8','ignore')
        return str(hashlib.sha1(password + str(self.salt)).hexdigest())

    def set_password(self, password):
        self.salt = self.generate_salt()
        self.password = self.encrypt(password)

    def check_password(self, password):
        if not self.active:
            return False
        if not self.password:
            return False
        return self.encrypt(password) == self.password

    def add_openid(self, openid):
        openid = OpenId(openid=openid)
        self.openids.append(openid)

    def cost_per_day(self, day):
        for cost in self.costs:
            if day >= cost.date:
                return cost

    @property
    def email_domains(self):
        return re.compile("@([\w.]+)").findall(self.email)

    @property
    def gdata_token_status(self):
        return self.gdata_auth_token and 'Active' or 'Not active'

    @hybrid_property
    def roles_names(self):
        return [a.id.lower() for a in self.roles]

    def roles_in_context(self, context=None):
        return getMultiAdapter((context, self), IRoleFinder).get_roles()

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        return self.fullname or self.email

    def __repr__(self):
        return "<User login=%s>" % self.login


def user_email(mapper, connection, target):
    if target.email:
        target.email = target.email.lower().strip()
        if not target.svn_login:
            target.svn_login = target.email

event.listen(User, "before_insert", user_email)
event.listen(User, "before_update", user_email)
event.listen(User.roles, "append", invalidate_user_calculate_matrix)
event.listen(User.roles, "remove", invalidate_user_calculate_matrix)


class PasswordResetToken(Base):
    __tablename__ = 'password_reset_tokens'
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    user = relationship(User, uselist=False)
    token = Column(String, unique=True)

    @property
    def id(self):
        return self.token


class OpenId(Base):
    implements(IPorModel)

    __tablename__ = 'openids'
    __acl__ = deepcopy(CRUD_ACL)
    id = Column(Integer, primary_key=True)
    openid = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship(User, uselist=False, backref=backref('openids', order_by=id))

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        return self.openid

    def __repr__(self):
        return "<OpenID openid=%s>" % self.openid


class Cost(Base):
    implements(IPorModel)

    __tablename__ = 'costs'
    __acl__ = deepcopy(CRUD_ACL)
    id = Column(Integer, primary_key=True)
    date = Column(Date, index=True)
    amount = Column(Float(precision=2))
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship(User, uselist=False, backref=backref('costs', order_by=date.desc()))
    global_config_id = Column(Integer, ForeignKey('global_config.id'))
    global_config = relationship(GlobalConfig, uselist=False, backref=backref('costs', order_by=date.desc()))

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        name = self.user and self.user.fullname or 'Company'
        return u"%s's cost for %s" % (name, self.date)

    def __repr__(self):
        return "<Cost user=%s>" % self.user_id


class Customer(dublincore.DublinCore, Base):
    implements(ICustomer)

    __tablename__ = 'customers'
    __acl__ = deepcopy(CRUD_ACL)
    #view
    __acl__.allow('role:customer', 'view')
    __acl__.allow('role:external_developer', 'view')
    __acl__.allow('role:internal_developer', 'view')
    __acl__.allow('role:secretary', 'view')
    __acl__.allow('role:project_manager', 'view')
    #metadata
    __acl__.allow('role:customer', 'metadata')
    __acl__.allow('role:project_manager', 'metadata')
    #timeentries
    __acl__.allow('role:secretary', 'time_entries')
    __acl__.allow('role:project_manager', 'time_entries')
    #edit
    __acl__.allow('role:project_manager', 'edit')
    #new
    __acl__.allow('role:project_manager', 'new')
    #delete
    __acl__.allow('role:project_manager', 'delete')

    id = Column(String, primary_key=True)
    name = Column(Unicode, unique=True)
    __mapper_args__ = {'order_by': name}

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        return self.name

    def add_project(self, project):
        if [proj for proj in self.projects if proj.name == project.name]:
            raise AttributeError('Duplicated project name. %s already exists' % project.name)
        self.projects.append(project)

    @property
    def color(self):
        return hashlib.md5(self.name.encode('utf8','ignore')).hexdigest()[:6]


def new_customer_created(mapper, connection, target):
    target.id = idnormalizer.normalize(target.name, max_length=100)

event.listen(Customer, "before_insert", new_customer_created)
event.listen(Customer, "before_insert", dublincore.dublincore_insert)
event.listen(Customer, "before_update", dublincore.dublincore_update)


class Project(dublincore.DublinCore, Base):

    implements(IProject, IProjectRelated)

    project_related_label = 'Project'
    project_related_id = ''

    __acl__ = deepcopy(CRUD_ACL)
    #listing
    __acl__.allow(Authenticated, 'listing')
    #view
    __acl__.allow('role:customer', 'view')
    __acl__.allow('role:external_developer', 'view')
    __acl__.allow('role:internal_developer', 'view')
    __acl__.allow('role:secretary', 'view')
    __acl__.allow('role:project_manager', 'view')
    #metadata
    __acl__.allow('role:secretary', 'metadata')
    __acl__.allow('role:project_manager', 'metadata')
    #add
    __acl__.allow('role:project_manager', 'new')
    #edit
    __acl__.allow('role:project_manager', 'edit')
    #edit
    __acl__.allow('role:project_manager', 'delete')
    #estimations
    __acl__.allow('role:secretary', 'estimations')
    __acl__.allow('role:project_manager', 'estimations')
    __acl__.allow('role:internal_developer', 'estimations')
    #view all entries
    __acl__.allow('role:secretary', 'reports_all_entries_for_project')
    __acl__.allow('role:project_manager', 'reports_all_entries_for_project')
    __acl__.allow('role:internal_developer', 'reports_all_entries_for_project')
    #contract
    __acl__.allow('role:project_manager', 'view_contracts')
    __acl__.allow('role:secretary', 'view_contracts')
    __acl__.allow('role:internal_developer', 'view_contracts')
    __acl__.allow('role:project_manager', 'add_contracts')
    __acl__.allow('role:secretary', 'add_contracts')
    #groups
    __acl__.allow('role:project_manager', 'view_groups')
    __acl__.allow('role:project_manager', 'add_groups')
    #customer_requests
    __acl__.allow('role:project_manager', 'list_customer_request')
    __acl__.allow('role:project_manager', 'add_customer_request')
    __acl__.allow('role:internal_developer', 'list_customer_request')
    __acl__.allow('role:internal_developer', 'add_customer_request')
    __acl__.allow('role:secretary', 'list_customer_request')
    __acl__.allow('role:secretary', 'add_customer_request')
    __acl__.allow('role:customer', 'list_customer_request')
    __acl__.allow('role:external_developer', 'list_customer_request')

    __tablename__ = 'projects'

    id = Column(String, primary_key=True)
    name = Column(Unicode)
    __mapper_args__ = {'order_by': name}
    activated = Column(Boolean, nullable=False, default=True)

    # quality end date fields
    completion_date = Column(Date)
    assistance_date = Column(Date)
    test_date = Column(Date)
    inception_date = Column(Date)

    customer_id = Column(String, ForeignKey('customers.id'))
    customer = relationship(Customer, uselist=False, backref=backref('projects'))
    manager_id = Column(Integer, ForeignKey('users.id'))
    manager = relationship(User,
                           primaryjoin=and_(manager_id == User.id,
                                            User.active == True),
                           uselist=False,
                           backref=backref('project_manager'),
                           order_by=func.substring(User.fullname,'([^[:space:]]+)(?:,|$)'))
    favorite_users = relationship(User, secondary=favorite_projects, backref="favorite_projects")

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        if self.customer and self.name:
            return '%s - %s' % (unicode(self.customer), self.name)
        else:
            return self.name or ''

    @property
    def project(self):
        "compatibility with IProjectRelated"
        return self

    def dashboard_apps(self):
        """ return only svn and trac """
        return [a for a in self.applications if a.application_type in [TRAC, SVN]]

    def add_application(self, application):
        if [app for app in self.applications if app.name == application.name]:
            raise AttributeError('Duplicated application name. %s already exists' % application.name)
        self.applications.append(application)

    def add_customer_request(self, customer_request):
        if [cr for cr in self.customer_requests if cr.name == customer_request.name]:
            raise AttributeError('Duplicated customer request name. %s already exists' % customer_request.name)
        self.customer_requests.append(customer_request)

    def add_group(self, group):
        self.groups.append(group)

    @property
    def tracs(self):
        for app in self.applications:
            if ITrac.providedBy(app):
                yield app

    def get_number_of_tickets_per_cr(self):
        from penelope.core.models.tickets import ticket_store
        return ticket_store.get_number_of_tickets_per_cr(self)

    @hybrid_method
    def users_favorite(self, user):
        return (favorite_projects.c.user_id == user.id) & (favorite_projects.c.project_id == self.id)

    @hybrid_property
    def active(self):
        return (self.activated != False) & (self.activated != None)

    def contracts_by_state(self):
        return DBSession().query(Contract.id, Contract.name, Contract.workflow_state)\
                          .join(Project).filter(Project.id==self.id)\
                          .order_by(Contract.active.desc())\
                          .order_by(Contract.modification_date.desc())\
                          .order_by(Contract.name)


def new_project_created(mapper, connection, target):
    project_id_candidate = target.id or target.name
    target.id = idnormalizer.normalize(project_id_candidate, max_length=100)
    target.inception_date = datetime.datetime.now()

event.listen(Project, "before_insert", new_project_created)
event.listen(Project, "before_insert", dublincore.dublincore_insert)
event.listen(Project, "before_update", dublincore.dublincore_update)
event.listen(Project.manager, "append", invalidate_users_calculate_matrix)
event.listen(Project.manager, "remove", invalidate_users_calculate_matrix)


GOOGLE_DOCS = 'google docs'
SVN = 'svn'
TRAC = 'trac'
TRAC_REPORT = 'trac report'
GENERIC_APP = 'generic'


class Application(dublincore.DublinCore, Base):
    implements(IProjectRelated, IApplication)

    project_related_label = 'Applications'
    project_related_id = 'applications'

    __tablename__ = 'applications'


    @classproperty
    def __acl__(self):
        acl = deepcopy(CRUD_ACL)

        # listing
        acl.allow('role:project_manager', 'listing')
        acl.allow('role:customer', 'listing')
        acl.allow('role:internal_developer', 'listing')
        acl.allow('role:external_developer', 'listing')
        acl.allow('role:secretary', 'listing')

        # project manager
        acl.allow('role:project_manager', 'view')
        acl.allow('role:project_manager', 'edit')
        acl.allow('role:project_manager', 'delete')
        acl.allow('role:project_manager', 'new')

        # dynamically set by CRUD form
        for _acl in self.acl:
            acl.allow('role:%s' % _acl.role_id, _acl.permission_name)

        return acl


    id = Column(Integer, primary_key=True)
    position = Column(Integer, nullable=False, default=-1)
    name = Column(Unicode)
    trac_name = deferred(Column(String(128)))
    svn_name = deferred(Column(String(128)))
    description = deferred(Column(Unicode))
    project_id = Column(String, ForeignKey('projects.id'))

    project = relationship(Project, uselist=False,
                           backref=backref('applications',
                                           collection_class=ordering_list('position'),
                                           order_by=position))

    api_uri = deferred(Column(String, default=''))

    application_type = Column(String(50))
    __mapper_args__ = {'polymorphic_on': application_type,
                       'polymorphic_identity': ''}

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        return self.name

    def application_uri(self, request=None):
        if self.api_uri.startswith('trac://') or self.api_uri.startswith('svn://'):
            new_api_uri = update_trac_svn_uri(None, self.api_uri, None, None)
            self.api_uri = new_api_uri
        return self.api_uri

    def get_icon(self):
        return {
                'google docs': 'icon-file-text-alt',
                'trac': 'icon-bug',
                'svn': 'icon-code-fork',
                }.get(self.application_type, 'icon-folder-close-alt')

    def get_color(self):
        return {
                'google docs': 'btn-primary',
                'trac': 'btn-danger',
                'svn': 'btn-warning',
                }.get(self.application_type, 'btn-inverse')


class ApplicationACL(Base):
    __tablename__ = 'applications_acl'

    application_id = Column(Integer, ForeignKey('applications.id', ondelete='cascade'), primary_key=True)
    role_id = Column(String, ForeignKey('roles.id', ondelete='cascade'), primary_key=True)
    permission_name = Column(String, primary_key=True)

    project = relationship(Application, uselist=False, backref=backref('acl',
                                                                       cascade="all, delete-orphan",
                                                                       passive_deletes=True))
    role = relationship(Role, uselist=False)

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        return '(%s, %s, %s)' % (self.application_id, self.role_id, self.permission_name)



def modify_application_type(mapper, connection, target):
    request = get_current_request()
    if request:
        _id = target.id or ''
        application_type = str(request.params.get(u'%s-%s-application_type' % (
                               target.__class__.__name__, _id, ),''))
        if application_type:
            target.application_type = application_type

def update_trac_svn_uri(target, value, oldvalue, initiator):
    request = get_current_request()
    if request:
        proto = request.environ.get('wsgi.url_scheme')
        http_host = request.environ.get('HTTP_HOST')
        svnurl = request.registry.settings.get('por.svn.url')
        if svnurl.endswith('/'):
            svnurl = svnurl[:-1]
        if not oldvalue and value:
            if value.startswith('svn://'):
                svn_id = value[6:]
                return '%s/%s' % (svnurl, svn_id)
            elif value.startswith('trac://'):
                trac_id = value[7:]
                return '%s://%s/trac/%s' % (proto, http_host, trac_id)
    return value

def update_app_position(mapper, connection, target):
    for n, app in enumerate(target.project.applications):
        if app.id == target.id:
            if target.position == -1: #  keep last 
                app = target.project.applications.pop(n)
                DBSession().query(Project).get(app.project_id).applications.append(app)
            elif n != target.position:
                app = target.project.applications.pop(n)
                DBSession().query(Project).get(app.project_id).applications.insert(target.position, app)

            target.project.applications.reorder()
            break

def default_app_position(mapper, connection, target):
    if not target.position:
        app_len = len(DBSession().query(Project).get(target.project_id).applications)
        target.position = app_len + 100


def create_initial_application_acl(mapper, connection, target):
    if target.application_type == SVN:
        acl_rules = [
                    ('internal_developer', 'edit'),
                    ('internal_developer', 'view'),
                    ('external_developer', 'edit'),
                    ('external_developer', 'view'),
                    ]
    else:
        acl_rules = [
                    ('internal_developer', 'view'),
                    ('external_developer', 'view'),
                    ('secretary', 'view'),
                    ('secretary', 'edit'),
                    ]

    if target.application_type == 'trac':
        acl_rules.append(('customer', 'view'))

    for role_id, permission_name in acl_rules:
        acl = DBSession.query(ApplicationACL).get((target.id, role_id, permission_name))
        if not acl:
            acl = ApplicationACL(application_id=target.id,
                                 role_id=role_id,
                                 permission_name=permission_name)
            DBSession.add(acl)
        else:
            # XXX this should not happen.
            pass



event.listen(Application.api_uri, "set", update_trac_svn_uri, retval=True)
event.listen(Application, "before_insert", modify_application_type, propagate=True)
event.listen(Application, "before_insert", default_app_position, propagate=True)
event.listen(Application, "before_insert", dublincore.dublincore_insert, propagate=True)
event.listen(Application, "after_insert", create_initial_application_acl, propagate=True)
event.listen(Application, "before_update", modify_application_type, propagate=True)
event.listen(Application, "before_update", dublincore.dublincore_update, propagate=True)
event.listen(Application, "before_update", update_app_position, propagate=True)


class GenericApp(Application):

    implements(IGenericApp)
    __mapper_args__ = {'polymorphic_identity': GENERIC_APP}


class Trac(Application):

    implements(ITrac)
    __mapper_args__ = {'polymorphic_identity': TRAC}


class TracReport(Application):

    implements(ITracReport)
    __mapper_args__ = {'polymorphic_identity': TRAC_REPORT}


class Subversion(Application):

    implements(ISVN)
    __mapper_args__ = {'polymorphic_identity': SVN}


class GoogleDoc(Application):

    implements(IGoogleDocs)
    __mapper_args__ = {'polymorphic_identity': GOOGLE_DOCS}


class Contract(dublincore.DublinCore, workflow.Workflow, Base):
    implements(IContract, IProjectRelated)

    project_related_label = 'Contracts'
    project_related_id = 'contracts'

    __tablename__ = 'contracts'
    __acl__ = deepcopy(CRUD_ACL)
    #view
    __acl__.allow('role:project_manager', 'view')
    __acl__.allow('role:secretary', 'view')
    __acl__.allow('role:internal_developer', 'view')
    #workflow
    __acl__.allow('role:secretary', 'workflow')
    __acl__.allow('role:project_manager', 'workflow')
    __acl__.allow('role:project_manager', 'workflow_activate')
    __acl__.allow('role:project_manager', 'workflow_deactivate')
    __acl__.allow('role:project_manager', 'workflow_achieve')
    __acl__.allow('role:secretary', 'workflow_achieve')
    __acl__.allow('role:project_manager', 'workflow_unachieve')
    __acl__.allow('role:secretary', 'workflow_unachieve')
    #add
    __acl__.allow('role:project_manager', 'new')
    __acl__.allow('role:secretary', 'new')
    #edit
    __acl__.allow('role:project_manager', 'edit')
    __acl__.allow('role:secretary', 'edit')

    id = Column(String, primary_key=True)
    name = Column(Unicode, nullable=False)
    description = deferred(Column(Unicode))
    days = Column(Float(precision=2), nullable=False, default=0)
    amount = Column(Float(precision=2))
    contract_number = Column(Unicode)
    start_date = Column(Date)
    end_date = Column(Date)

    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    project = relationship(Project, uselist=False, backref=backref('contracts', order_by=id))

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        return self.name

    @hybrid_property
    def active(self):
        return (self.workflow_state == 'active')


def new_contract_created(mapper, connection, target):
    contract_id_candidate = '%s_%s' % (target.project_id, target.name)
    target.id = idnormalizer.normalize(contract_id_candidate, max_length=100)

event.listen(Contract, "before_insert", new_contract_created)
event.listen(Contract, "before_insert", dublincore.dublincore_insert)
event.listen(Contract, "before_update", dublincore.dublincore_update)


class CustomerRequest(dublincore.DublinCore, workflow.Workflow, Base):
    implements(ICustomerRequest, IProjectRelated)

    project_related_label = 'Customer requests'
    project_related_id = 'customer_requests'

    __tablename__ = 'customer_requests'
    __acl__ = deepcopy(CRUD_ACL)
    #view
    __acl__.allow('role:project_manager', 'view')
    __acl__.allow('role:secretary', 'view')
    __acl__.allow('role:internal_developer', 'view')
    __acl__.allow('role:customer', 'view')
    #estimations
    __acl__.allow('role:secretary', 'estimations')
    __acl__.allow('role:project_manager', 'estimations')
    __acl__.allow('role:internal_developer', 'estimations')
    #workflow
    __acl__.allow('role:project_manager', 'workflow')
    #add
    __acl__.allow('role:project_manager', 'new')
    __acl__.allow('role:internal_developer', 'new')
    #edit
    __acl__.allow('role:project_manager', 'edit')
    __acl__.allow('role:internal_developer', 'edit')
    #contract view/edit
    __acl__.allow('role:secretary', 'contract')
    __acl__.allow('role:project_manager', 'contract')
    #delete
    __acl__.allow('role:project_manager', 'delete')

    id = Column(String, primary_key=True)
    uid = Column(Integer)
    name = Column(Unicode)
    description = deferred(Column(Unicode))
    project_id = Column(String, ForeignKey('projects.id'))
    project = relationship(Project, uselist=False, backref=backref('customer_requests'))
    contract_id = Column(String, ForeignKey('contracts.id'))
    contract = relationship(Contract, uselist=False, backref=backref('customer_requests'))
    old_contract_name = Column(Unicode)
    filler = Column(Boolean, nullable=False, default=False)

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        if self.contract:
            return '%s [%s]' % (self.name, self.contract)
        else:
            return self.name

    @hybrid_property
    def active(self):
        return (self.workflow_state == 'estimated' or self.workflow_state == 'created')

    def get_tickets(self, request=None):
        from penelope.core.models.tickets import ticket_store
        return ticket_store.get_tickets_for_request(customer_request=self)

    def add_ticket_url(self, request):
        for trac in self.project.tracs:
            trac_url = trac.application_uri(request)
            if self.description:
                desc = html2text.html2text(self.description).encode('utf8')
            else:
                desc = ''
            params = urllib.urlencode({'summary':str(self), 
                                       'type': 'task',
                                       'customerrequest': self.id,
                                       'description': desc})
            return '%s/newticket?%s' % (trac_url, params)

    @property
    def estimation_days(self):
        if self.filler and self.contract:
            other_crs = DBSession().query(CustomerRequest)\
                                   .filter_by(filler=False)\
                                   .filter_by(contract_id=self.contract_id)
            filler = self.contract.days - sum([cr.estimation_days for cr in other_crs])
            if filler < 0:
                return 0
            else:
                return filler
        return sum([a.days for a in self.estimations], float())

    @property
    def timeentries_days(self):
        from penelope.core.lib.helpers import timedelta_as_work_days
        hours = sum([a.hours for a in self.time_entries], datetime.timedelta())
        return timedelta_as_work_days(hours)


def after_customer_request_flushed(session, flush_context, instances):
    """ generate unique id per project_id """
    def last_cr4project(obj):
        project_id = idnormalizer.normalize(obj.project_id or obj.project.name, max_length=100)
        last = session.query(CustomerRequest.uid)\
                    .filter_by(project_id=project_id)\
                    .order_by(CustomerRequest.uid.desc()).first()
        if last: new_uid = last.uid + 1
        else: new_uid = 1
        return project_id, new_uid

    last = {}
    for obj in session.new:
        if isinstance(obj, CustomerRequest):
            project_id, new_uid = last_cr4project(obj)
            if not project_id in last.keys():
                last[project_id] = new_uid 
            else:
                last[project_id] = last[project_id] + 1
            obj.uid = last[project_id]
            obj.id = "%s_%s" % (project_id, last[project_id])


event.listen(DBSession, "before_flush", after_customer_request_flushed)
event.listen(CustomerRequest, "before_insert", dublincore.dublincore_insert)
event.listen(CustomerRequest, "before_update", dublincore.dublincore_update)



class Estimation(Base):
    __tablename__ = "estimations"
    __acl__ = deepcopy(CRUD_ACL)
    #view
    __acl__.allow('role:project_manager', 'view')
    __acl__.allow('role:secretary', 'view')
    __acl__.allow('role:internal_developer', 'view')
    #add
    __acl__.allow('role:project_manager', 'new')
    __acl__.allow('role:internal_developer', 'new')
    #edit
    __acl__.allow('role:project_manager', 'edit')
    __acl__.allow('role:internal_developer', 'edit')

    id = Column(Integer, primary_key=True)
    days = Column(Float(precision=2), nullable=False)
    person_type = Column(Unicode, nullable=False)
    customer_request_id = Column(String, ForeignKey('customer_requests.id'))
    customer_request = relationship(CustomerRequest, backref=backref('estimations'))


def check_cr_for_estimation(mapper, connection, target):
    state = ''
    cr = DBSession().query(CustomerRequest).get(target.customer_request_id)

    if target in cr.estimations and len(cr.estimations) == 1 and cr.workflow_state != 'created': # removing last estimation
        state = 'created'
    elif len(cr.estimations)==0 and cr.workflow_state != 'estimated':
        state = 'estimated'

    request = get_current_request()
    if state and request:
        workflow = get_workflow(cr, 'CustomerRequest')
        try:
            workflow.transition_to_state(cr, request, state, skip_same=True)
        except WorkflowError:
            pass


event.listen(Estimation, "before_insert", check_cr_for_estimation)
event.listen(Estimation, "before_delete", check_cr_for_estimation)


class Group(Principal):
    implements(IRoleable, IProjectRelated)

    project_related_label = 'Groups'
    project_related_id = 'configuration'

    __tablename__ = "groups"
    __acl__ = deepcopy(CRUD_ACL)
    #view
    __acl__.allow('role:project_manager', 'view')
    #add
    __acl__.allow('role:project_manager', 'new')
    #edit
    __acl__.allow('role:project_manager', 'edit')
    __acl__.allow('role:project_manager', 'manage_roles')
    #delete
    __acl__.allow('role:project_manager', 'delete')

    id = Column(Integer, ForeignKey(Principal.id),
        Sequence("principals_id"),
        primary_key=True)
    project_id = Column(String, ForeignKey('projects.id'))
    project = relationship(Project, uselist=False, backref=backref('groups'))
    roles = relationship(Role, secondary=role_assignments, backref="groups")
    users = relationship(User,
                         secondary=group_assignments,
                         backref="groups",
                         order_by=func.substring(User.fullname,'([^[:space:]]+)(?:,|$)'))

    def add_user(self, user):
        if [us for us in self.users if us.login == user.login]:
            raise AttributeError('Dupplicated username. %s already exists' % user.login)
        self.users.append(user)

    @hybrid_property
    def roles_names(self):
        if self.roles:
            return [a.id.lower() for a in self.roles]
        else:
            return ['[No role]']

    @roles_names.expression
    def roles_names_expr(cls):
        return Role.name

    def __repr__(self):
        return "<Group id=%d>" % self.id

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        return "[%s] %s" % (self.project.name, ','.join(self.roles_names))

def wrap_users_before_group_delete(mapper, connection, target):
    for user in target.users:
        invalidate_user_calculate_matrix(user, None, None)

event.listen(Group.users, "append", invalidate_users_calculate_matrix)
event.listen(Group.users, "remove", invalidate_users_calculate_matrix)
event.listen(Group, "before_delete", wrap_users_before_group_delete)


class SavedQuery(dublincore.DublinCore, Base):
    implements(IPorModel)

    __tablename__ = 'saved_queries'

    id = Column(Integer, primary_key=True)
    query_name = Column(Unicode)
    report_name = Column(Unicode)
    query_string = Column(Unicode)

    def __repr__(self):
        return "<SavedQuery id=%d name=%s>" % (self.id, self.query_name)

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        return self.query_name

    def full_url(self, request):
        return request.route_url('reports', traverse=[self.report_name]) + self.query_string

event.listen(SavedQuery, "before_insert", dublincore.dublincore_insert)
event.listen(SavedQuery, "before_update", dublincore.dublincore_update)


BACKLOG_PRIORITY_ORDER = 'priority'
BACKLOG_MODIFICATION_ORDER = 'modification'


class KanbanBoard(dublincore.DublinCore, Base):
    implements(IKanbanBoard)

    __tablename__ = 'kanban_boards'

    @classproperty
    def __acl__(self):
        acl = deepcopy(CRUD_ACL)

        acl.allow('role:redturtle_developer', 'new')
        acl.allow('role:redturtle_developer', 'listing')

        acl.allow('role:owner', 'view')
        acl.allow('role:owner', 'edit')
        acl.allow('role:owner', 'delete')

        # dynamically set by deform
        try:
            for _acl in self.acl:
                acl.allow(_acl.principal, _acl.permission_name)
        except TypeError: # if self is a class the acl attribute is not iterable
            pass
        return acl

    id = Column(Integer, primary_key=True)
    name = Column(Unicode, nullable=False)
    json = Column(Unicode)
    backlog_query = Column(Unicode, nullable=False)
    backlog_limit = Column(Integer, default=10, nullable=False)
    backlog_order = Column(Unicode, nullable=False)
    author = relationship(User,
                          uselist=False,
                          primaryjoin='KanbanBoard.author_id==User.id',
                          backref='kanban_boards')
    projects = relationship(Project, secondary=kanban_projects, backref="kanban_boards")

    def __repr__(self):
        return "<KanbanBoard id=%d>" % self.id

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        return self.name

    def get_board_columns(self):
        columns = self.json and loads(self.json) or []
        return [str(len(c['tasks'])) for c in columns]

def create_initial_kanban_acl(mapper, connection, target):
    acl_rules = [
                 ('role:redturtle_developer', 'view'),
                ]

    for principal_id, permission_name in acl_rules:
        acl = KanbanACL(principal=principal_id,
                board_id=target.id,
                permission_name=permission_name)
        DBSession().add(acl)

event.listen(KanbanBoard, "after_insert", create_initial_kanban_acl, propagate=True)
event.listen(KanbanBoard, "before_insert", dublincore.dublincore_insert)
event.listen(KanbanBoard, "before_update", dublincore.dublincore_update)

class KanbanACL(Base):
    __tablename__ = 'kanban_acl'

    id = Column(Integer, primary_key=True)
    principal = Column(String)
    permission_name = Column(String)
    board_id = Column(Integer, ForeignKey(KanbanBoard.id))
    board = relationship(KanbanBoard, uselist=False, backref=backref('acl',
        cascade="all, delete-orphan",
        passive_deletes=True))

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        return '(%s, %s, %s)' % (self.principal, self.board_id, self.permission_name)


class Activity(Base):

    __tablename__ = 'activities'
    id = Column(Integer, primary_key=True)
    message = Column(Unicode)
    absolute_path = Column(String)
    created_by = Column(String)
    created_at = Column(Date, index=True)
    seen_at = Column(Date, index=True)
    read_at = Column(Date, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship(User, uselist=False, backref=backref('activities', order_by=created_at.desc()))

    @property
    def unseen(self):
        return self.seen_at == None
