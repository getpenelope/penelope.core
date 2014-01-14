# -*- coding: utf-8 -*-

import os.path, time
import zope.component
from zope.interface import implements
from pyramid.view import view_config
from pyramid.renderers import get_renderer
from pyramid.threadlocal import get_current_registry
from penelope.core.sidebar import SidebarRenderer, HeaderSidebarAction, SidebarAction
from penelope.core.interfaces import ISidebar
from penelope.core.interfaces import IManageView
from penelope.core.views import DefaultContext


class ManageContext(DefaultContext):
    "Default context factory for Manage views."
    implements(IManageView)

    @property
    def title(self):
        view = self.request.view_name or self.request.environ['PATH_INFO'].split('/')[-1]
        if view == 'manage':
            view = 'index'
        return 'Manage %s' % self.prettify_title(view)


class ManageSidebarRenderer(SidebarRenderer):

    def render(self, request):
        self.actions.append(HeaderSidebarAction('manage',content=u'Manage penelope', permission='manage', no_link=True))
        self.actions.append(SidebarAction('manage_users',
                                          content=u'Manage users',
                                          permission='manage',
                                          attrs=dict(href="'%s/admin/User' % request.application_url")))
        self.actions.append(SidebarAction('manage_roles',
                                          content=u'Manage roles',
                                          permission='manage',
                                          attrs=dict(href="'%s/admin/Role' % request.application_url")))
        self.actions.append(SidebarAction('manage_groups',
                                          content=u'Manage groups',
                                          permission='manage',
                                          attrs=dict(href="'%s/admin/Group' % request.application_url")))
        self.actions.append(SidebarAction('manage_svn_authz',
                                          content=u'Manage SVN authz',
                                          permission='manage_svn',
                                          attrs=dict(href="'%s/manage/svn_authz' % request.application_url")))
        actions = self.actions.render(request)
        template =  get_renderer('penelope.core.forms:templates/project_sidebar.pt').implementation()
        return template(actions=actions,
                        request=request)

gsm = zope.component.getGlobalSiteManager()
gsm.registerAdapter(ManageSidebarRenderer, (IManageView,), ISidebar)


@view_config(route_name='administrator', permission='manage', renderer='skin')
def manage_home(request):
    return {}

@view_config(route_name='manage_svn_authz', renderer='skin', permission='manage_svn')
def manage_svn_authz(request):
    settings = get_current_registry().settings
    authz_file = settings.get('por.svn.authz')

    if request.method == 'POST':
        from penelope.trac.authz import generate_authz
        generate_authz(request.registry.settings)

    with open(authz_file, 'r') as configfile:
        authz = configfile.read()

    modified = time.ctime(os.path.getmtime(authz_file))
    return {'authz': authz,
            'authz_modified': modified}
