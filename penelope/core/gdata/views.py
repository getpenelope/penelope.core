# -*- coding: utf-8 -*-

import gdata.docs.data
import logging
import transaction
import re
import zope.component
from copy import deepcopy

from sqlalchemy import func
from gdata.client import RequestError
from pyramid_skins import SkinObject
from pyramid.renderers import get_renderer
from pyramid.exceptions import Forbidden
from pyramid.httpexceptions import HTTPFound
from pyramid.threadlocal import get_current_registry
from gdata.calendar.client import CalendarEventQuery
from dateutil.parser import parse
from datetime import timedelta

from penelope.core.sidebar import SidebarRenderer, HeaderSidebarAction, SidebarAction
from penelope.core.interfaces import ISidebar
from penelope.core.gdata import IIterationView
from penelope.core.gdata.utils import documents, spreadsheets, calendar, get_working_days
from penelope.core.models import Project, DBSession, User, GlobalConfig, Customer, Role


logging.basicConfig()
log = logging.getLogger(__file__)


def clear_token(context, request):
    identity = request.environ.get('repoze.who.identity')
    if not identity:
        raise Forbidden

    user = identity.get('user')
    if not user:
        raise Forbidden

    user.gdata_auth_token = None
    next_url = '%s/admin/User/%s/user_tokens' % (request.application_url, request.authenticated_user.id)
    transaction.commit()
    raise HTTPFound(next_url)


@documents.auth_required
def add_token(context, request):
    next_url = '%s/admin/User/%s/user_tokens' % (request.application_url, request.authenticated_user.id)
    raise HTTPFound(next_url)


def get_cell_values(request, query):
    docid = request.params.get('docid')
    docid = docid.split(':')[1]

    cells = request.gservice['SpreadsheetsService'].GetCellsFeed(docid, query=query)
    return [a.content.text for a in cells.entry]


@spreadsheets.auth_required
def activate_iteration(context, request):
    docid = request.params.get('docid')
    if not docid:
        return view_iterations(context, request, validation_error=u'Missing document_id')

    #query = gdata.spreadsheet.service.CellQuery()

    #first take project names
    #query['min-col'] = '3'
    #query['max-col'] = '3'
    #query['min-row'] = '5'
    #cr_raw = get_cell_values(request, query)

    session = DBSession()

    #deactivate all CR
    #for cr in session.query(CustomerRequest):
    #    cr.active = False

    #activate selected CR
    #cr_ids = set([item for sublist in [a.split(',') for a in cr_raw] for item in sublist])
    #crs = session.query(CustomerRequest).filter(CustomerRequest.id.in_(cr_ids))
    #for cr in crs:
    #    cr.active = True

    gc = session.query(GlobalConfig).get(1)
    gc.active_iteration_url = docid

    return manage_iterations(context,request)

@documents.auth_graceful
def get_google_document(context, request, **kwargs):

    is_folder = re.compile(r'folders/(.*)$').search(kwargs['uri'])
    is_document = re.compile(r'/([a-z]*)/d/(.*)/.*$').search(kwargs['uri'])
    is_spreadsheet = re.compile(r'/([a-z]*)/ccc\?key=([0-9a-zA-Z]*)').search(kwargs['uri'])
    params = {}
    status = None
    folder = None
    document = None

    if is_spreadsheet:
        is_document = is_spreadsheet

    if is_folder:
        folder_id = is_folder.groups()[0]
        try:
            folder = request.gclient['DocsClient'].get_doclist(uri='/feeds/default/private/full/%s/contents/' % folder_id).entry
        except (ValueError, RequestError), e:
            status = u'''Something is not working correctly.
                         We cannot open Google Collection you have provided.
                         Please check if %s is correct.
                         Full exception: %s''' % (kwargs['uri'], e)
        params.update(folder=folder, status=status)

    elif is_document:
        document_type, document_id = is_document.groups()
        try:
            document = request.gclient['DocsClient'].get_doc('%s:%s' % (document_type, document_id))
        except (ValueError, RequestError), e:
            status = u'''Something is not working correctly.
                         We cannot open Google Doc url you have provided.
                         Please check if %s is correct.
                         Full exception: %s''' % (kwargs['uri'], e)
        params.update(document=document,status=status)

    else:
        params.update(status='''Something is not working correctly. We cannot open Google Apps url you have provided.
        Please check if %s is correct''' % kwargs['uri'])

    return params


@documents.auth_graceful
def manage_iterations(context, request, **params):
    docs = []
    folder_iteration = get_iteration_folder(request)
    if folder_iteration:
        log.info("Iteration folder found: %s" % folder_iteration.resource_id.text)
        docs = request.gclient['DocsClient'].get_doclist(
                uri='/feeds/default/private/full/%s/contents/-/spreadsheet' % \
                                      folder_iteration.resource_id.text).entry
    settings = get_current_registry().settings
    domain = settings.get('penelope.core.google_domain')
    params.update({'context':context,
                   'docs': docs,
                   'iteration_folder': 'https://docs.google.com/a/%s/#%s' % (
                       domain,
                       folder_iteration.resource_id.text.replace('folder:','folders/')),
                   'request':request})

    return SkinObject('manage_iterations')(**params)


@documents.auth_graceful
def view_iterations(context, request, **params):
    session = DBSession()
    gc = session.query(GlobalConfig).get(1)
    docid = gc.active_iteration_url
    folder_iteration = get_iteration_folder(request)

    params.update({'context':context,
                   'doc_url': None,
                   'request':request})

    if folder_iteration and docid:
        log.info("Iteration folder found: %s" % folder_iteration.resource_id.text)
        document = request.gclient['DocsClient'].get_doc(docid)
        params.update({'doc_url': '%s&rm=minimal' % document.get_html_link().href})

    return SkinObject('view_iterations')(**params)


@spreadsheets.auth_required
def generate_spreadsheet(context, request):
    date_start = request.params.get('start')
    date_end = request.params.get('end')
    session = DBSession()

    client = request.gclient['DocsClient']
    service = request.gservice['SpreadsheetsService']
    iteration_folder = get_iteration_folder(request)
    settings = get_current_registry().settings

    if not date_start or not date_end:
        params = {'validation_error': 'Please select date range'}
        return manage_iterations(context, request, **params)

    if not iteration_folder:
        params = {'validation_error':
                       'Iteration folder is missing. Please create folder in google docs with title: %s' % \
                       settings.get('penelope.core.iteration_folder')}
        return manage_iterations(context, request, **params)

    users = session.query(User.email, User.fullname)\
                   .group_by(User.email, User.fullname)\
                   .join(User.roles).filter(Role.id.ilike('%developer%'))\
                   .order_by(func.substring(User.fullname, '([^[:space:]]+)(?:,|$)'))

    projects = session.query(Project).join(Customer)\
                      .filter(Project.active)\
                      .order_by(Customer.name, Project.name)


    dockey = settings.get('penelope.core.iteration_template')
    resourceid = 'document%%3A%s' % dockey
    template = client.GetDoc(resourceid)
    entry = client.copy(template, 'Iteration from %s to %s' % (date_start,
                                                               date_end))
    client.move(entry, iteration_folder)

    sp_id = entry.resource_id.text.split(':')[1]
    wk = service.GetWorksheetsFeed(sp_id).entry[0]
    wk.title.text = '%s_%s' % (date_start, date_end)
    wk = service.UpdateWorksheet(wk)
    wk_id = wk.id.text.split('/')[-1]

    query = gdata.spreadsheet.service.CellQuery()
    query['return-empty'] = 'true'
    query['min-col'] = '1'
    query['min-row'] = '1'
    query['max-col'] = '19'
    query['max-row'] = '106'
    cells = service.GetCellsFeed(sp_id, wksht_id=wk_id, query=query)
    batchRequest = gdata.spreadsheet.SpreadsheetsCellsFeed()

    def update_cell(cells, values):
        for cell,value in zip(cells,values):
            cell.cell.inputValue = str(value)
            batchRequest.AddUpdate(cell)

    update_cell([cells.entry[19]],['Iteration from %s to %s' % (date_start, date_end)])
    #Add user fullnames
    update_cell(cells.entry[5:18], [a.fullname for a in users])
    #Add user working days
    dae = _get_calendars_events(users, request)
    dr = [parse(date_start), parse(date_end)]
    update_cell(cells.entry[24:37], [get_working_days(dr,dict(dae).get(u.email,[])) for u in users])
    #Add project names
    update_cell(cells.entry[76::19], [str(a) for a in projects])
    #Add project managers
    update_cell(cells.entry[77::19], [a.manager for a in projects])

    service.ExecuteBatch(batchRequest, cells.GetBatchLink().href)
    return manage_iterations(context, request)


@calendar.auth_required
def _get_calendars_events(users, request):

    """
    It retrieves all avalable calendars from the current user, this means also 'Festivita italiane' and 'Compleanni ed eventi'.
    The porpouse is to get all the events from each calendar with by keyword (in this example is 'holidays@google.com').
    and from each event get the date range value.

    return would be something like this:
    [
     ['user1@google.com',
        [[datetime.datetime(2011, 8, 24, 0, 0), datetime.datetime(2011, 8, 24, 23, 59)],
        [datetime.datetime(2011, 8, 23, 0, 0), datetime.datetime(2011, 8, 23, 23, 59)],
        [datetime.datetime(2011, 8, 23, 0, 0), datetime.datetime(2011, 8, 23, 23, 59)],
        [datetime.datetime(2011, 8, 22, 0, 0), datetime.datetime(2011, 8, 22, 23, 59)]]],
     ['user2@google.com',
        [[datetime.datetime(2011, 8, 24, 0, 0), datetime.datetime(2011, 8, 24, 23, 59)]]],
     ['%23contacts@group.v.calendar.google.com', []],
     ['it.italian%23holiday@group.v.calendar.google.com', []],
     ['user3@google.com', []]
    ]
    """
    result = []
    client = request.gclient['CalendarClient']

    # get all calendars
    query_holidays = CalendarEventQuery()
    query_holidays.start_min = request.params.get('start')
    query_holidays.start_max = request.params.get('end')

    cal_holidays_ranges = []
    try:
        italian_holidays = client.GetCalendarEventFeed(
                uri='https://www.google.com/calendar/feeds/en.italian%23holiday%40group.v.calendar.google.com/private/full',
                q=query_holidays)
        for holiday in italian_holidays.entry:
            s = parse(holiday.when[0].start)
            e = parse(holiday.when[0].end)
            cal_holidays_ranges.append([s, e-timedelta(minutes=1)])
    except RequestError: # gracefully ignore request errors
        pass

    settings = get_current_registry().settings
    attendees = settings.get('penelope.core.vacancy_email')
    query = CalendarEventQuery(text_query = attendees)
    query.start_min = request.params.get('start')
    query.start_max = request.params.get('end')

    for user in users:
        username = user.email
        feed_uri = client.GetCalendarEventFeedUri(calendar=username, visibility='private', projection='full')
        cal_events_ranges = deepcopy(cal_holidays_ranges)

        # get the event feed using the feed_uri and the query params in order to get only those with 'holidays@google.com'
        try:
            events_feed = client.GetCalendarEventFeed(uri=feed_uri, q=query)
            for an_event in events_feed.entry:
                if not an_event.when:
                    continue
                s = parse(an_event.when[0].start)
                e = parse(an_event.when[0].end)
                cal_events_ranges.append([s, e-timedelta(minutes=1)])
        except RequestError: # gracefully ignore request errors
            pass
        result.append([username,cal_events_ranges])
    return result


def get_iteration_folder(request):
    settings = get_current_registry().settings
    folders = request.gclient['DocsClient'].get_doclist(
                uri='/feeds/default/private/full?title=%s&category=folder' % \
                               settings.get('penelope.core.iteration_folder'))
    for folder in folders.entry:
        return folder


class IterationSidebarRenderer(SidebarRenderer):

    def render(self, request):
        self.actions.append(HeaderSidebarAction('iterations',
                                                content=u'Iterations',
                                                permission='view',
                                                no_link=True))
        self.actions.append(SidebarAction('view_iterations',
            content=u'View iterations',
            permission='view_iterations',
            attrs=dict(href="'%s/view_iterations' % request.application_url")))
        self.actions.append(SidebarAction('manage_iterations',
            content=u'Manage iterations',
            permission='manage_iterations',
            attrs=dict(href="'%s/manage_iterations' % request.application_url")))
        actions = self.actions.render(request)
        template =  get_renderer('penelope.core.forms:templates/project_sidebar.pt').implementation()
        return template(actions=actions,
                        request=request)

gsm = zope.component.getGlobalSiteManager()
gsm.registerAdapter(IterationSidebarRenderer, (IIterationView,), ISidebar)
