# -*- coding: utf-8 -*-
from pyramid.config import Configurator
from pyramid_beaker import session_factory_from_settings, set_cache_regions_from_settings
from zope.component import getGlobalSiteManager
from pyramid.authentication import RepozeWho1AuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid_skins.renderer import renderer_factory
import gevent_psycopg2; gevent_psycopg2.monkey_patch()

PROJECT_ID_BLACKLIST = ('portale', 'project', 'support', 'assistenza')

try:
    import pyinotify; pyinotify
    DISCOVERY = True
except ImportError:
    DISCOVERY = False


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    settings['mail.port'] = settings.get('mail_port', None) and int(settings['mail.port']) or 25
    globalreg = getGlobalSiteManager()
    set_cache_regions_from_settings(settings)
    config = Configurator(registry=globalreg)

    config.include('pyramid_zcml')
    config.load_zcml('workflow.zcml')
    config.add_translation_dirs('penelope.core:locale')

    from penelope.core.views import PORRequest
    config.setup_registry(settings=settings,
                          request_factory=PORRequest,
                          root_factory='penelope.core.views.DefaultContext')

    # por security
    from penelope.core import security
    authentication_policy = RepozeWho1AuthenticationPolicy(identifier_name="auth_tkt",callback=security.rolefinder)
    config._set_authentication_policy(authentication_policy)
    authorization_policy = ACLAuthorizationPolicy()
    config._set_authorization_policy(authorization_policy)
    config.scan('penelope.core.security.views')
    config.include('penelope.core.security.openid2')
    config.include('velruse.store.memstore')
    config.add_view('penelope.core.security.views.forbidden', renderer='skin', context="pyramid.httpexceptions.HTTPForbidden")

    #mailier
    config.include('pyramid_mailer')

    # penelope.core.models's configuration
    config.include('penelope.core.models')
    import penelope.core.events; penelope.core.events
    import penelope.core.breadcrumbs; penelope.core.breadcrumbs
    import penelope.core.sidebar; penelope.core.sidebar

    session_factory = session_factory_from_settings(settings)
    config.set_session_factory(session_factory)

    config.add_static_view('static', 'penelope.core:static')
    config.scan('penelope.core.views')
    config.add_route('socketio', 'socket.io/*remaining')
    config.scan('penelope.core.socketspace')

    config.add_route('tp', '/tp/*traverse', factory='penelope.core.tp.TPContext')
    config.scan('penelope.core.tp')
    config.scan('penelope.core.smartadd')
    config.scan('penelope.core.backlog')

    config.add_route('administrator', '/manage', factory='penelope.core.manage.ManageContext')
    config.add_route('manage_svn_authz', '/manage/svn_authz', factory='penelope.core.manage.ManageContext')
    config.add_route('manage_costs', '/manage/costs', factory='penelope.core.manage.ManageContext')
    config.scan('penelope.core.manage')

    config.add_route('search', '/search')
    config.scan('penelope.core.search')

    config.add_route('reports', '/reports/*traverse', factory='penelope.core.reports.ReportContext')
    config.scan('penelope.core.reports')
    config.add_renderer(name='xls_report', factory='penelope.core.renderers.XLSReportRenderer')
    config.add_renderer(name='csv_report', factory='penelope.core.renderers.CSVReportRenderer')

    config.include('pyramid_rpc.jsonrpc')
    config.add_jsonrpc_endpoint('DashboardAPI', '/apis/json/dashboard')
    config.scan('penelope.core.api')

    config.add_renderer('skin', renderer_factory)
    config.include('pyramid_skins')
    config.register_path("penelope.core:skins", discovery=DISCOVERY)

    # penelope.core.gdata configuration
    config.include('penelope.core.gdata')

    # pyramid_formalchemy's configuration
    config.include('pyramid_formalchemy')
    config.include('fa.bootstrap')
    config.include('deform_bootstrap')

    config.formalchemy_admin('admin',
                             package='penelope.core',
                             factory='penelope.core.forms.CrudModels',
                             models='penelope.core.models',
                             view='penelope.core.forms.ModelView',
                             session_factory='penelope.core.models.DBSession')

    config.add_view(context='pyramid_formalchemy.resources.ModelListing',
                    renderer='fa.bootstrap:templates/admin/new.pt',
                    request_method='POST',
                    route_name='admin',
                    request_type='penelope.core.interfaces.IPorRequest',
                    view='penelope.core.forms.security_create')

    config.add_static_view('deform_static', 'deform:static')
    config.add_route('navbar', '/navbar')
    config.add_route('favicon', '/favicon.ico')
    config.add_route('inbound_email', '/inbound_email')
    config.scan('penelope.core.notifications')

    from penelope.core.forms import include_forms
    include_forms(config)

    return config.make_wsgi_app()
