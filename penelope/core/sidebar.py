
import logging
import re

import zope.component
from zope.interface import Interface

from webhelpers.html import literal
from pyramid_formalchemy.actions import Actions
from pyramid.renderers import get_renderer
from fa.bootstrap.actions import TabsActions, TabAction, UIButton

from penelope.core.interfaces import ISidebar
from penelope.core.lib.helpers import unicodelower
from penelope.core.models.interfaces import IProjectRelated, ICustomerRequest, IApplication#, IKanbanBoard

gsm = zope.component.getGlobalSiteManager()

log = logging.getLogger(__name__)


class Button(UIButton):
    body = '''<a class="${_class}" tal:attributes="%(attributes)s">${content}</a>'''



def safe_fa_url(*args):
    params = [ "'%s'" % arg for arg in args ]
    for arg in args:
        if isinstance(arg, int):
            continue
        if not re.match('^[\'a-z0-9_\-]+$', arg.lower()):
            log.error('Prevented unsafe arguments to eval: %s' % params)
            return "''"
    ret = 'request.fa_url(%s)' % ', '.join(params)
    return ret




class SidebarAction(TabAction):
    body = u'''<li class="${action.li_class(request)}">
                   <a tal:condition="not no_link"
                      tal:attributes="%(attributes)s">${content}</a>
                    <tal:nolink tal:condition="no_link">${content}</tal:nolink>
               </li>'''

    def isActive(self, request):
        if not self.attrs.get('href'):
            return False
        for _id in self.rcontext.get('children', ()):
            if _id in request.matchdict.get('traverse'):
                return True
        return request.path_url.strip('/') == eval(self.attrs['href']).strip('/')

    def li_class(self, request):
        return self.isActive(request) and 'active' or ''

    def render(self, request):
        if not self.rcontext.get('no_link'):
            self.rcontext['no_link'] = False
        return super(SidebarAction, self).render(request)


class DividerSidebarAction(SidebarAction):
    body = u'''<li class="divider"></li>'''


class HeaderSidebarAction(Actions, SidebarAction):
    body = u'''<li class="nav-header ${action.li_class(request)}">
                    <a tal:condition="not no_link" tal:attributes="%(attributes)s">${content}</a>
                    <tal:nolink tal:condition="no_link">${content}</tal:nolink>
                    <div class="nav-header-icons">${items}</div>
               </li>'''

    def __init__(self, *args, **kwargs):
        Actions.__init__(self)
        SidebarAction.__init__(self, *args, **kwargs)

    def render(self, request, **kwargs):
        items = Actions.render(self, request, **kwargs)
        self.rcontext.update(items=literal(items))
        return SidebarAction.render(self, request)


class SidebarActions(TabsActions):
    body='''<ul class="nav nav-list">${items}</ul>'''


class EmptyActions(TabsActions):
    body='''${items}'''


class SidebarRenderer(object):
    def __init__(self, context):
        self.context = context
        self.actions = SidebarActions()

    def render(self, request):
        return None

gsm.registerAdapter(SidebarRenderer, (Interface,), ISidebar)


class ProjectSidebarRenderer(SidebarRenderer):

    def __init__(self, *args, **kwargs):
        super(ProjectSidebarRenderer, self).__init__(*args, **kwargs)
        self.applications = EmptyActions()
        self.crs = EmptyActions()
        self.contracts = EmptyActions()

    def add_base_actions(self, request):
        project = self.context.project

        #Project name
        prj = HeaderSidebarAction('project_home',
                    content=project.name,
                    permission='view',
                    no_link=True)

        prj.append(Button(id='view',
                          content=literal('<i class="icon-info-sign icon-white"></i>'),
                          _class='btn btn-info btn-mini',
                          permission='edit',
                          attrs=dict(href=safe_fa_url('Project', project.id, 'metadata'),
                                     title="'Project metadata'")))

        if not request.authenticated_user in project.favorite_users:
            prj.append(Button(id='add_as_favorite',
                              content=literal('<i class="icon-star icon-white"></i>'),
                              permission='view',
                              _class='btn btn-success btn-mini',
                              attrs=dict(href=safe_fa_url('Project', project.id, 'toggle_favorite'),
                                         title="'Add as favorite'")))
        else:
            prj.append(Button(id='remove_as_favorite',
                              content=literal('<i class="icon-star icon-white"></i>'),
                              _class='btn btn-danger btn-mini',
                              permission='view',
                              attrs=dict(href=safe_fa_url('Project', project.id, 'toggle_favorite'),
                                         title="'Remove from favorites'")))
        prj.append(Button(id='project_edit',
                          content=literal('<i class="icon-cog icon-white"></i>'),
                          permission='edit',
                          _class='btn btn-warning btn-mini',
                          attrs=dict(href=safe_fa_url('Project', project.id, 'edit'),
                                     title="'Project configuration'")))
        self.actions.append(prj)
        self.actions.append(DividerSidebarAction('div'))

        #Documentation
        docs = HeaderSidebarAction('documentation',
                        content=u'Documentation',
                        permission='view',
                        no_link=True)
        docs.append(Button(id='add',
                           content=literal('<i class="icon-plus-sign icon-white"></i>'),
                           _class='btn btn-success btn-mini',
                           permission='new',
                           attrs=dict(href=safe_fa_url('Project', project.id, 'add_application'),
                                      title="'Add application'")))
        self.actions.append(docs)
        self.actions.append(self.applications)
        self.actions.append(SidebarAction('list_all_docs',
                                          content=u'List all...',
                                          permission='view',
                                          attrs=dict(href=safe_fa_url('Project', project.id, 'applications'))))
        self.actions.append(DividerSidebarAction('div'))

        #Customer request
        cr = HeaderSidebarAction('customer_requests',
                      content=u'Customer requests',
                      permission='list_customer_request',
                      no_link=True)
        cr.append(Button(id='add',
                      content=literal('<i class="icon-plus-sign icon-white"></i>'),
                      _class='btn btn-success btn-mini',
                      permission='add_customer_request',
                      attrs=dict(href=safe_fa_url('Project', project.id, 'add_customer_request'),
                                 title="'Add customer request'")))
        self.actions.append(cr)
        self.actions.append(self.crs)
        self.actions.append(SidebarAction('list_all_cr',
                                          content=u'List all...',
                                          permission='list_customer_request',
                                          attrs=dict(href=safe_fa_url('Project', project.id, 'customer_requests'))))

        #Contract
        if request.has_permission('view_contracts', self.context.project):
            contract = HeaderSidebarAction('contracts',
                        content=u'Contracts',
                        permission='view',
                        no_link=True)
            if request.has_permission('add_contracts', self.context.project):
                contract.append(Button(id='add',
                            content=literal('<i class="icon-plus-sign icon-white"></i>'),
                            _class='btn btn-success btn-mini',
                            permission='view',
                            attrs=dict(href=safe_fa_url('Project', project.id, 'add_contract'),
                                        title="'Add contract'")))
            self.actions.append(contract)
            self.actions.append(self.contracts)
            self.actions.append(SidebarAction('list_all_contracts',
                                            content=u'List all...',
                                            permission='view',
                                            attrs=dict(href=safe_fa_url('Project', project.id, 'contracts'))))
            self.actions.append(DividerSidebarAction('div'))

        #Permissions
        if request.has_permission('view_groups', self.context.project):
            permissions = HeaderSidebarAction('permissions',
                                content=u'Permissions',
                                permission='view',
                                no_link=True)

            permissions.append(Button(id='view',
                                content=literal('<i class="icon-info-sign icon-white"></i>'),
                                _class='btn btn-info btn-mini',
                                permission='view',
                                attrs=dict(href=safe_fa_url('Project', project.id, 'configuration'),
                                            title="'View groups'")))

            if request.has_permission('add_groups', self.context.project):
                permissions.append(Button(id='add',
                                        content=literal('<i class="icon-plus-sign icon-white"></i>'),
                                        _class='btn btn-success btn-mini',
                                        permission='view',
                                        attrs=dict(href=safe_fa_url('Project', project.id, 'add_group'),
                                                    title="'Add group'")))
            self.actions.append(permissions)

    def add_document_actions(self, only_trac=True):
        project = self.context.project
        if only_trac:
            apps = project.tracs
        else:
            apps = project.applications

        request = self.context.request

        if not request:
            return

        for app in request.filter_viewables(apps):
            if app.application_type == 'trac':
                href = "'%s'" % app.api_uri
            else:
                href = safe_fa_url('Application', app.id)

            self.applications.append(SidebarAction('app_%s' % app.id,
                                     content=literal(u'<i class="%s"></i> %s' % (app.get_icon(), app.name)),
                                     permission='view',
                                     attrs=dict(href=href)))

    def add_cr_actions(self, only_active=True):
        project = self.context.project
        for cr in sorted(project.customer_requests, key=unicodelower):
            if only_active:
                if cr.workflow_state != 'estimated':
                    continue

            icon = 'icon-time'
            self.crs.append(SidebarAction('cr_%s' % cr.id,
                                          content=literal(u'<i class="%s"></i> %s' % (icon, cr)),
                                          permission='view',
                                          attrs=dict(href=safe_fa_url('CustomerRequest', cr.id))))

    def add_contract_actions(self):
        project = self.context.project
        for cr in sorted(project.contracts, key=unicodelower):
            icon = 'icon-file'
            self.contracts.append(SidebarAction('cr_%s' % cr.id,
                                          content=literal('<i class="%s"></i> %s' % (icon, cr.name)),
                                          permission='view',
                                          attrs=dict(href=safe_fa_url('Contract', cr.id))))

    def render(self, request):
        project = self.context.project
        action = getattr(request, 'action', '')
        self.add_base_actions(request)
        self.add_document_actions(only_trac = action != 'applications')
        self.add_cr_actions(only_active = action != 'customer_requests')
        self.add_contract_actions()
        actions = self.actions.render(request)

        template =  get_renderer('penelope.core.forms:templates/project_sidebar.pt').implementation()
        return template(project=project,
                        actions=actions,
                        request=request)

gsm.registerAdapter(ProjectSidebarRenderer, (IProjectRelated,), ISidebar)


class CRSidebarRenderer(ProjectSidebarRenderer):
    def render(self, request):
        project = self.context.project

        self.add_base_actions(request)
        self.add_document_actions()
        self.add_cr_actions(only_active=False)
        actions = self.actions.render(request)

        template =  get_renderer('penelope.core.forms:templates/project_sidebar.pt').implementation()
        return template(project=project,
                        actions=actions,
                        request=request)

gsm.registerAdapter(CRSidebarRenderer, (ICustomerRequest,), ISidebar)


class AppSidebarRenderer(ProjectSidebarRenderer):
    def render(self, request):
        project = self.context.project

        self.add_base_actions(request)
        self.add_document_actions(only_trac=False)
        self.add_cr_actions()
        actions = self.actions.render(request)

        template =  get_renderer('penelope.core.forms:templates/project_sidebar.pt').implementation()
        return template(project=project,
                        actions=actions,
                        request=request)

gsm.registerAdapter(AppSidebarRenderer, (IApplication,), ISidebar)


class ManageSidebarRenderer(SidebarRenderer):

    def render(self, request):
        #Customer request
        board = HeaderSidebarAction('kanban_boards',
                      content=u'Boards',
                      permission='view',
                      no_link=True)
        board.append(Button(id='add',
                      content=literal('<i class="icon-plus-sign icon-white"></i>'),
                      _class='btn btn-success btn-mini',
                      permission='new',
                      attrs=dict(href=safe_fa_url('KanbanBoard', 'new'),
                                 title="'Add new board'")))
        self.actions.append(board)
        for kanban in request.authenticated_user.kanban_boards:
            icon = 'icon-time'
            self.actions.append(SidebarAction('board_%s' % kanban.id,
                                              content=literal(u'<i class="%s"></i> %s' % (icon, kanban)),
                                              permission='view',
                                              attrs=dict(href=safe_fa_url('KanbanBoard', kanban.id))))

        actions = self.actions.render(request)
        template =  get_renderer('penelope.core.forms:templates/project_sidebar.pt').implementation()
        return template(actions=actions, request=request)

#gsm.registerAdapter(ManageSidebarRenderer, (IKanbanBoard,), ISidebar)
