# -*- coding: utf-8 -*-
from pyramid.httpexceptions import HTTPFound, HTTPOk
from pyramid.exceptions import Forbidden
from pyramid.renderers import get_renderer
from pyramid_skins import SkinObject
from dateutil.rrule import DAILY, rrule, SA, SU
from urlparse import urlparse, parse_qsl
from urllib import urlencode

from gdata.auth import AuthSubToken
from gdata.gauth import AuthSubToken as gAuthSubToken
from gdata.service import RequestError
from gdata.auth import generate_auth_sub_url
from gdata.docs.service import DocsService
from gdata.spreadsheet.service import SpreadsheetsService
from gdata.docs.client import DocsClient
from gdata.calendar.client import CalendarClient
from gdata.calendar.service import CalendarService

SCOPES = ['https://docs.google.com/feeds/', 'https://www.google.com/calendar/feeds/', 'https://spreadsheets.google.com/feeds/']


def fallback_tween_factory(handler, registry):
    def fallback_tween(request):
        try:
            response = handler(request)
        except GracefulFallback, e:
            qs_chr = request.query_string and '&' or '?'
            force_url = '%s%sforce=true' % (request.url, qs_chr)
            params = {'context':e.context,
                      'uri': e.kw.get('uri'),
                      'force_url': force_url,
                      'request':request}

            if hasattr(request.root,'fa_url'):
                #fa context
                params['main_template'] = get_renderer('penelope.core:skins/main_template.pt').implementation()
                params['main'] = get_renderer('penelope.core.forms:templates/master.pt').implementation()
                response = SkinObject('fallback_admin')(**params)
            else:
                response = SkinObject('fallback')(**params)
        return response
    return fallback_tween


def get_working_days(date_range, date_events_array):
    """
    It returns a dict of working day for each calendar.

    something like :
    {'%23contacts': 25, 'nicola.senno': 22, 'irene.capatti': 25, 'it.italian%23holiday': 25, 'amleczko': 24}
    """
    day_off = []
    start = date_range[0]
    end = date_range[1]

    for event in date_events_array:
        day_off.append(set(rrule(DAILY, dtstart=event[0], until=event[1])))

    all_dates = set(rrule(DAILY, dtstart=start, until=end))
    weekend = set(rrule(DAILY, dtstart=start, until=end, byweekday=(SA,SU)))
    all_no_weekend = all_dates.difference(weekend)
    merged = []

    for event_set in day_off:
        for event_date in event_set:
            merged.append(event_date)

    return  len(all_no_weekend.difference(set(merged)))


class AuthSubURLRedirect(HTTPFound):
    "Wraper for HTTPFound"
    def __init__(self, next_url, scopes, domain='default'):
        url = str(generate_auth_sub_url(next_url, scopes, domain=domain))
        super(AuthSubURLRedirect, self).__init__(url)


class GracefulFallback(HTTPOk):
    def __init__(self, context, **kw):
        self.context = context
        self.kw = kw
        super(GracefulFallback, self).__init__()


class GDataAuthDecorator(object):
    """ Decorator class for gdata auth."""

    def __init__(self, client, service):
        self.client =  client
        self.service = service
        self.scopes = SCOPES

    def _perform_auth(self, method, context, request, **kw):
        "Internal method"

        if not getattr(request, 'gclient', None):
            request.gclient = {}
        if not getattr(request, 'gservice', None):
            request.gservice = {}

        request.gclient[self.client.__class__.__name__] = self.client
        request.gservice[self.service.__class__.__name__] = self.service

        identity = request.environ.get('repoze.who.identity')
        if not identity:
            raise Forbidden

        user = identity.get('user')
        user_domains = user.email_domains
        if user_domains: 
            user_domain = user_domains[0]
        else:
            user_domain = 'default'
        next_url = request.url

        request_token = request.params.get('token')
        if request_token:
            authsub_token = AuthSubToken(scopes=self.scopes)
            authsub_token.set_token_string(request_token)
            self.service.auth_token = authsub_token
            self.service.UpgradeToSessionToken(token=authsub_token)
            user.gdata_auth_token = self.service.auth_token.get_token_string()

            #cleanup qs
            qs = dict(parse_qsl(urlparse(next_url).query))
            try:
                del qs['auth_sub_scopes']
                del qs['token']
                del qs['force']
            except KeyError: pass

            next_url = '%s?%s' % (request.path_url, urlencode(qs))
            raise HTTPFound(next_url)

        authsub_token = AuthSubToken(user.gdata_auth_token, scopes=self.scopes)
        self.service.SetAuthSubToken(user.gdata_auth_token)

        try:
            self.service.AuthSubTokenInfo()
        except RequestError:
            user.gdata_auth_token = None
            raise AuthSubURLRedirect(next_url, self.scopes, domain=user_domain)

        self.client.auth_token = gAuthSubToken(user.gdata_auth_token, scopes=self.scopes)
        return method(context, request, **kw)

    def auth_graceful(self, method):
        """
        Perform full gdata authsub authorization check.
        Fallback with URL if missing token

        Example:

            decorator = GDataAuthDecorator(GDClient(), GDService())

            @decorator.auth_graceful
            def get_file(context, request):
                return Response('OK')
        """
        def check_auth(context, request, **kw):
            """ perform authsub authorization """
            if request.params.get('force',False):
                return self._perform_auth(method, context, request, **kw)
            try:
                return self._perform_auth(method, context, request, **kw)
            except AuthSubURLRedirect:
                #gracefull fallback to method
                raise GracefulFallback(context, **kw)
        return check_auth

    def auth_required(self, method):
        """
        Perform full gdata authsub authorization check.
        FORCE authorization if missing.

        Example:

            decorator = GDataAuthDecorator(GDClient(), GDService())

            @decorator.auth_required
            def get_file(context, request):
                ...
                return Response('OK')
        """

        def check_auth(context, request, **kw):
            """ perform authsub authorization """
            return self._perform_auth(method, context, request, **kw)

        return check_auth

documents = GDataAuthDecorator(DocsClient(), DocsService())
spreadsheets = GDataAuthDecorator(DocsClient(), SpreadsheetsService())
calendar = GDataAuthDecorator(CalendarClient(), CalendarService())
