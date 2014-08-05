"this code is shared from ptahproject under BSD license"

import logging
import zope.component

from beaker.cache import cache_region
from beaker.cache import region_invalidate
from sqlalchemy import event
from zope.interface import Interface

from penelope.models import User, Project, Group
from penelope.core.interfaces import IRoleFinder
from penelope.core.interfaces import IProjectRelated, ICustomer, IUser, IDublinCore

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
    from penelope.models import User, Project
    from penelope.core.dbsession import DBSession
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


def wrap_users_before_group_delete(mapper, connection, target):
    for user in target.users:
        invalidate_user_calculate_matrix(user, None, None)


event.listen(User.roles, "append", invalidate_user_calculate_matrix)
event.listen(User.roles, "remove", invalidate_user_calculate_matrix)
event.listen(Project.manager, "append", invalidate_users_calculate_matrix)
event.listen(Project.manager, "remove", invalidate_users_calculate_matrix)
event.listen(Group.users, "append", invalidate_users_calculate_matrix)
event.listen(Group.users, "remove", invalidate_users_calculate_matrix)
event.listen(Group, "before_delete", wrap_users_before_group_delete)


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
