# -*- coding: utf-8 -*-

import os.path, time
import zope.component
from zope.interface import implements
from pyramid.view import view_config
from pyramid_formalchemy.resources import Base, actions as factions
from pyramid.renderers import get_renderer
from pyramid.threadlocal import get_current_registry
from penelope.core.forms import ModelView
from penelope.core.sidebar import SidebarRenderer, HeaderSidebarAction, SidebarAction
from penelope.core.interfaces import ISidebar
from penelope.core.interfaces import IManageView
from penelope.core.views import DefaultContext
from penelope.core.models import dashboard, DBSession
from penelope.core import forms


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
        self.actions.append(SidebarAction('manage_costs',
                                          content=u'Manage company cost',
                                          permission='costs',
                                          attrs=dict(href="'%s/manage/costs' % request.application_url")))
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


@view_config(route_name='manage_costs', permission='manage', renderer='skin')
def manage_costs(context, request):

    # make fake FA request
    request.model_name = 'Company costs'
    request.model_class = dashboard.Cost
    request.session_factory = DBSession
    request.forms = forms
    request.format = 'html'
    request.actions = factions.RequestActions()
    request.actions['buttons'] = forms.actions.defaults_actions['new_buttons']
    request.action = 'add_cost'
    request.model_id = None
    request.route_name = 'manage_costs'
    base = Base(request, request.model_name)
    request.fa_url = base._fa_url

    global_config = DBSession().query(dashboard.GlobalConfig).first()
    view = ModelView(context, request)
    response = view.new()

    if request.method == 'GET':
        page = view.get_page(collection=global_config.costs)
        pager = page.pager(**view.pager_args)
        response['items'] = page
        response['pager'] = pager
    return response
