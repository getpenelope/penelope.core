# -*- coding: utf-8 -*-
import itertools
import os
import re

from zope.interface import implements
from pyramid.response import Response
from pyramid import decorator
from pyramid.request import Request
from pyramid.i18n import TranslationStringFactory
from pyramid.view import view_config
from pyramid.security import has_permission

from penelope.core import fanstatic_resources, messages
from penelope.core.interfaces import IBreadcrumbs, IPorRequest, ISidebar
from penelope.core.lib.htmlhelpers import get_application_link
from penelope.core.security import acl
from penelope.core.lib.helpers import chunks, unicodelower
from penelope.core.models import DBSession, Project, KanbanBoard
from penelope.core.models.interfaces import IProjectRelated


_ = TranslationStringFactory('por')


class PORRequest(Request):

    model_instance = None
    challenge_item = None
    charset = 'utf8'

    implements(IPorRequest)

    def __init__(self, *args, **kwargs):
        super(PORRequest, self).__init__(*args, **kwargs)
        self.charset = 'UTF-8'

    def _get_message_from_session(self):
        msgs = self.session.get(messages.STATUSMESSAGEKEY)
        if not msgs:
            msgs = messages.Messages()
            self.session[messages.STATUSMESSAGEKEY] = msgs
        return msgs

    def add_message(self, *args, **kwargs):
        """\
        Call this once or more to add messages to be displayed at the
        top of the web page.

        Examples:

        >>> request.add_message(u'A random warning message', 'warning')

        If no type is given it defaults to 'info'
        >>> request.add_message(u'A random info message')

        The arguments are:
            request:   instance of pyramid Request
            message:   a string, with the text message you want to show,
                        or a HTML fragment
            type:      optional, defaults to 'info'. The type determines how
                        the message will be rendered, as it is used to select
                        the CSS class for the message. Predefined types are:
                        'success' - for successful actions
                        'info' - for informational messages
                        'warning' - for warning messages
                        'error' - for messages about restricted access or errors.
        """
        msgs = self._get_message_from_session()
        msgs.add(*args, **kwargs)

    def show_messages(self):
        msgs = self._get_message_from_session()
        value = msgs.show()
        if self.response.status_int not in (301, 302, 304):
            del self.session[messages.STATUSMESSAGEKEY]
        return value

    @decorator.reify
    def title(self):
        return self.root.title

    @decorator.reify
    def authenticated_user(self):
        user = None
        identity = self.environ.get('repoze.who.identity', None)
        if identity:
            user = identity.get('user', None)
        return user

    def isAuthenticated(self):
        return self.authenticated_user is not None

    def context_for_breadcrumbs(self, view):
        model = self.model_instance
        if model:
            return model
        else:
            return view

    def render_breadcrumbs(self, view):
        context = self.context_for_breadcrumbs(view)
        context.request = view.request
        breadcrumbs = IBreadcrumbs(context)
        return breadcrumbs.render(self)

    def render_sidebar(self, view):
        context = self.context_for_breadcrumbs(view)
        context.request = view.request
        sidebar = ISidebar(context)
        return sidebar.render(self)

    def fa_parent_url(self, context=None):
        if IProjectRelated.providedBy(self.model_instance):
            return self.fa_url('Project', self.model_instance.project.id)
        else:
            return self.fa_url(self.model_name)

    def active_topbar(self, paths):
        for path in paths:
            if path in self.path:
                return 'active'
        return ''

    def filter_viewables(self, items):
        if len([a for a in self.authenticated_user.roles if a.name == 'administrator']) == 1:
            # for administrator let's skip check 
            return items
        return [item for item in items if self.filter_viewable(item)]

    def filter_viewable(self, item):
        self.challenge_item = item
        if has_permission('view', item, self):
            self.challenge_item = None
            return item
        self.challenge_item = None

    def has_permission(self, permission, context):
        if not context:
            context = DefaultContext(self) #we always need a context for ACL to work
        self.challenge_item = context
        result = has_permission(permission, context, self)
        self.challenge_item = None
        return result


class DefaultContext(object):
    """
    Default context factory for TP views.
    """
    __acl__ = acl.DEFAULT_ACL

    def __init__(self, request):
        fanstatic_resources.dashboard.need()
        self.request = request

    def prettify_title(self, title):
        title = title.replace('_', ' ')
        return title

    @property
    def title(self):
        view = self.request.view_name or self.request.environ['PATH_INFO'].split('/')[-1]
        if view == '':
            title = 'Dashboard'
        elif view == 'add_entry':
            title = 'Smart add time entries'
        else:
            title = self.prettify_title(view).title()
        if not title:
            title = 'Penelope'
        return title


@view_config(context='pyramid.exceptions.NotFound', renderer='penelope.core:templates/notfound.pt')
def notfound_view(request):
    request.response.status_int = 404
    return {}


def group_by_customer(projects):
    return  [
                (x[0], list(x[1]))
                for x in itertools.groupby(projects, lambda x: x.customer)
            ]

@view_config(permission='view_home', route_name="favicon")
def favicon(request):
    here = os.path.dirname(__file__)
    icon = open(os.path.join(here, 'static', 'penelope', 'images', 'favicon.png'))
    return Response(content_type='image/x-icon', app_iter=icon)


@view_config(renderer='skin', permission='view_home')
def view_home(request):
    """
    Default home view
    """
    fanstatic_resources.dashboard_home.need()

    session = DBSession()
    user = request.authenticated_user
    projects = session.query(Project)

    my_projects = projects\
                  .filter(Project.users_favorite(user))\
                  .order_by(Project.customer_id).all()

    my_projects = request.filter_viewables(my_projects)

    active_projects = set(projects.filter(Project.active))
    active_projects = sorted(request.filter_viewables(active_projects.difference(my_projects)), key=unicodelower)

    listings = []
    listing_columns = 4
    listings.append({'title': 'Active projects',
                     'projgroups': tuple(chunks(tuple(active_projects), listing_columns)),})
    kanbanboards = user.kanban_boards

    return {
            'my_projects': my_projects,
            'kanbanboards': kanbanboards,
            'listings': listings,
            'can_see_kanbanboards':  request.has_permission('listing', KanbanBoard),
            'get_application_link': get_application_link,
            }


@view_config(renderer='skin', permission='view_home', route_name='navbar')
def view_navbar(request):
    """
    Navbar is rendered separately, and served to Trac via ajax.
    """
    trac = re.search('/trac/(?P<trac>[a-zA-z0-9\-_]+)',request.environ.get('HTTP_REFERER', ''))
    if trac:
        return {'trac':trac.group('trac')}
    else:
        return {}
