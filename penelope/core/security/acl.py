"this code is shared from ptahproject under BSD license"

import logging
import zope.component

from beaker.cache import cache_region
from beaker.cache import region_invalidate
from pyramid.security import ALL_PERMISSIONS
from pyramid.security import Allow, Deny
from pyramid.security import Authenticated
from zope.interface import Interface

from penelope.core.interfaces import IRoleFinder
from penelope.core.models.interfaces import IProjectRelated, ICustomer, IUser, IDublinCore


class ACL(list):
    """ Named ACL map

    ACL contains list of permit rules, for example::

      >> acl = ACL('test', 'Test ACL')
      >> acl.allow('system.Everyone', 'View')
      >> acl.deny('system.Everyone', 'Edit')

      >> list(acl)
      [(Allow, 'system.Everyone', ('View',)),
       (Deny, 'system.Everyone', ('Edit',))]

    """

    def __init__(self, name):
        self.name = name

    def get(self, typ, role):
        for r in self:
            if r[0] == typ and r[1] == role:
                return r

        return None

    def allow(self, role, *permissions):
        """ Give permissions to role """

        if not isinstance(role, basestring):
            role = role.id

        rec = self.get(Allow, role)
        if rec is None:
            rec = [Allow, role, set()]
            self.append(rec)

        if rec[2] is ALL_PERMISSIONS:
            return

        if ALL_PERMISSIONS in permissions:
            rec[2] = ALL_PERMISSIONS
        else:
            rec[2].update(permissions)

    def deny(self, role, *permissions):
        """ Deny permissions for role """

        if not isinstance(role, basestring):
            role = role.id

        rec = self.get(Deny, role)
        if rec is None:
            rec = [Deny, role, set()]
            self.append(rec)

        if rec[2] is ALL_PERMISSIONS:
            return

        if ALL_PERMISSIONS in permissions:
            rec[2] = ALL_PERMISSIONS
        else:
            rec[2].update(permissions)

    def unset(self, role, *permissions):
        """ Unset any previously defined permissions """
        for perm in permissions:
            for rec in self:
                if role is not None and rec[1] != role:
                    continue

                if rec[2] is ALL_PERMISSIONS or perm is ALL_PERMISSIONS:
                    rec[2] = set()
                else:
                    if perm in rec[2]:
                        rec[2].remove(perm)

        records = []
        for rec in self:
            if rec[2]:
                records.append(rec)
        self[:] = records


DEFAULT_ACL = ACL('default_por_acl') 
DEFAULT_ACL.allow('system.Everyone', 'view_anon')
DEFAULT_ACL.allow('role:administrator', ALL_PERMISSIONS)

#/home
DEFAULT_ACL.allow(Authenticated, 'view_home')
DEFAULT_ACL.allow('role:redturtle_developer', 'search')

#/manage_svn
DEFAULT_ACL.allow('role:redturtle_developer', 'manage_svn')

#/view_iterations
DEFAULT_ACL.allow('role:local_developer', 'view_iterations')
DEFAULT_ACL.allow('role:local_project_manager', 'view_iterations')
DEFAULT_ACL.allow('role:internal_developer', 'view_iterations')
DEFAULT_ACL.allow('role:secretary', 'view_iterations')
DEFAULT_ACL.allow('role:project_manager', 'view_iterations')

#/manage_iterations and /generate_iterations
DEFAULT_ACL.allow('role:local_project_manager', 'manage_iterations')
DEFAULT_ACL.allow('role:secretary', 'manage_iterations')
DEFAULT_ACL.allow('role:project_manager', 'manage_iterations')

#/add_entry
DEFAULT_ACL.allow('role:local_developer', 'add_entry')
DEFAULT_ACL.allow('role:local_project_manager', 'add_entry')
DEFAULT_ACL.allow('role:external_developer', 'add_entry')
DEFAULT_ACL.allow('role:internal_developer', 'add_entry')
DEFAULT_ACL.allow('role:secretary', 'add_entry')
DEFAULT_ACL.allow('role:project_manager', 'add_entry')

#/reports/index
DEFAULT_ACL.allow('role:local_project_manager', 'reports_index')
DEFAULT_ACL.allow('role:local_developer', 'reports_index')
DEFAULT_ACL.allow('role:secretary', 'reports_index')
DEFAULT_ACL.allow('role:project_manager', 'reports_index')

#/reports/report_custom
DEFAULT_ACL.allow('role:local_project_manager', 'reports_custom')
DEFAULT_ACL.allow('role:secretary', 'reports_custom')
DEFAULT_ACL.allow('role:project_manager', 'reports_custom')

#/reports/report_all_entries
DEFAULT_ACL.allow('role:local_project_manager', 'reports_all_entries')
DEFAULT_ACL.allow('role:local_developer', 'reports_all_entries')
DEFAULT_ACL.allow('role:secretary', 'reports_all_entries')
DEFAULT_ACL.allow('role:project_manager', 'reports_all_entries')

#/reports/report_state_change
DEFAULT_ACL.allow('role:secretary', 'reports_state_change')
DEFAULT_ACL.allow('role:project_manager', 'reports_state_change')
DEFAULT_ACL.allow('role:local_project_manager', 'reports_state_change')

#/reports/my_entries
DEFAULT_ACL.allow('role:local_developer', 'reports_my_entries')
DEFAULT_ACL.allow('role:local_project_manager', 'reports_my_entries')
DEFAULT_ACL.allow('role:internal_developer', 'reports_my_entries')
DEFAULT_ACL.allow('role:external_developer', 'reports_my_entries')
DEFAULT_ACL.allow('role:secretary', 'reports_my_entries')
DEFAULT_ACL.allow('role:project_manager', 'reports_my_entries')

#/backlog
DEFAULT_ACL.allow('role:local_developer', 'view_backlog')
DEFAULT_ACL.allow('role:local_project_manager', 'view_backlog')
DEFAULT_ACL.allow('role:secretary', 'view_backlog')

CRUD_ACL = ACL('por_crud_acl')
CRUD_ACL.allow('role:administrator', ALL_PERMISSIONS)
CRUD_ACL.allow('role:redturtle_developer', 'search')

#Customer
CRUD_ACL.allow(Authenticated, 'customer_listing')

ONLY_PROJECT_ROLES = set([u'internal_developer', u'external_developer', u'customer'])

gsm = zope.component.getGlobalSiteManager()
log = logging.getLogger('penelope')


@cache_region('calculate_matrix')
def __calculate_matrix__(user_id):
    """
    Return tuple of global and local roles in following format::
    >>> __calculate_matrix__(140)
    (set(['secretary'], {'fta': set(['internal_developer'])})
    """
    from penelope.core.models import User, DBSession, Project
    user = DBSession.query(User).get(user_id)
    global_roles = set(user.roles_names)
    local_roles = {}
    if 'administrator' in global_roles:
        log.debug("User: %s.\nGlobal roles: %s.\nLocal roles: %s" % (user, global_roles, local_roles))
        return global_roles, local_roles

    def add_local_role(project_id, role_name):
        if not project_id in local_roles:
            local_roles[project_id] = set()
        local_roles[project_id].add(role_name)

    for group in user.groups:
        for role in group.roles_names:
            add_local_role(group.project_id, role)
    for project in DBSession().query(Project.id).filter(Project.manager == user):
        add_local_role(project.id, u'project_manager')

    # extract global_roles from local_roles:
    roles_from_projects = set([item for sublist in local_roles.values() for item in sublist])

    # if user is an internal_developer in one of the projects add:
    if u'internal_developer' in roles_from_projects:
        global_roles.add(u'local_developer')

    # if user is a project_manager in one of the projects add:
    if u'project_manager' in roles_from_projects:
        global_roles.add(u'local_project_manager')

    log.debug("User: %s.\nGlobal roles: %s.\nLocal roles: %s" % (user, global_roles, local_roles))
    return global_roles, local_roles


def invalidate_user_calculate_matrix(target, value, initiator):
    log.debug("Cache invalidated for %s" % target)
    region_invalidate(__calculate_matrix__, 'calculate_matrix', target.id)

def invalidate_users_calculate_matrix(target, value, initiator):
    log.debug("Cache invalidated for %s" % value)
    region_invalidate(__calculate_matrix__, 'calculate_matrix', value.id)


class GenericRoles(object):
    def __init__(self, context, user):
        self.context = context
        self.user = user
        self.global_roles, self.local_roles = self.roles_matrix()
        self.roles = self.global_roles.copy()

    def roles_matrix(self):
        return __calculate_matrix__(self.user.id)

    def get_roles(self):
        return self.roles

gsm.registerAdapter(GenericRoles, (Interface, IUser), IRoleFinder)


class DublincoreRelatedRoles(GenericRoles):
    def __init__(self, context, user):
        super(DublincoreRelatedRoles, self).__init__(context, user)
        if getattr(self.context, 'author', None) == self.user:
            self.roles.add('owner')

gsm.registerAdapter(DublincoreRelatedRoles, (IDublinCore, IUser), IRoleFinder)

class ProjectRelatedRoles(DublincoreRelatedRoles):
    def add_project_roles(self, project):
        if project.manager == self.user:
            self.roles.add('project_manager')
        roles = self.local_roles.get(project.id, [])
        for role in roles:
            self.roles.add(role)

    def get_roles(self):
        self.roles -= ONLY_PROJECT_ROLES
        if self.context.project:
            self.add_project_roles(self.context.project)
        return self.roles

gsm.registerAdapter(ProjectRelatedRoles, (IProjectRelated, IUser), IRoleFinder)


class CustomerRelatedRoles(ProjectRelatedRoles):
    def get_roles(self):
        self.roles -= ONLY_PROJECT_ROLES
        for project in self.context.projects:
            self.add_project_roles(project)
        return self.roles

gsm.registerAdapter(CustomerRelatedRoles, (ICustomer, IUser), IRoleFinder)


class UserRoles(GenericRoles):
    def get_roles(self):
        if self.context == self.user:
            self.roles.add('owner')
        return self.roles

gsm.registerAdapter(UserRoles, (IUser, IUser), IRoleFinder)
