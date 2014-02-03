# -*- coding: utf-8 -*-

import colander
import datetime
import functools
import itertools
import logging
import operator
import sqlalchemy as sa
import webhelpers

from deform import ValidationFailure
from pyramid.renderers import render
from pyramid.view import view_config

from penelope.core.lib.helpers import ticket_url
from penelope.core.lib.widgets import SearchButton, PorInlineForm
from penelope.core.models import DBSession, TimeEntry
from penelope.core.models.tp import timedelta_as_human_str, timedelta_as_work_days
from penelope.core.reports import fields
from penelope.core.reports.favourites import render_saved_query_form
from penelope.core.reports.queries import qry_active_projects
from penelope.core.reports.validators import validate_period

log = logging.getLogger(__name__)


def yesterday():
    return datetime.date.today() - datetime.timedelta(1)


@colander.deferred
def deferred_today(node, kw):
    default_date = kw.get('today')
    if default_date is None:
        default_date = datetime.date.today()
    return default_date


@colander.deferred
def deferred_yesterday(node, kw):
    default_date = kw.get('yesterday')
    if default_date is None:
        default_date = yesterday()
    return default_date


class MyEntriesReport(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request


    class MyEntriesSchema(colander.MappingSchema):
        project_id = fields.project_id.clone()
        date_from = fields.date_from.clone()
        date_from.default = deferred_yesterday
        date_from.missing = deferred_yesterday
        date_to = fields.date_to.clone()
        date_to.default = deferred_today
        date_to.missing = deferred_today
        searchtext = fields.searchtext.clone()


    def search(self, limit, author_id, project_id, date_from, date_to, searchtext):
        qry = DBSession.query(TimeEntry)

        qry = qry.filter(TimeEntry.author_id==author_id)

        if project_id is not colander.null:
            qry = qry.filter(TimeEntry.project_id==project_id)

        if date_from is not colander.null:
            qry = qry.filter(TimeEntry.date>=date_from)

        if date_to is not colander.null:
            qry = qry.filter(TimeEntry.date<=date_to)

        if searchtext is not colander.null:
            qry = qry.filter(TimeEntry.description.ilike(u'%{0}%'.format(searchtext)))

        qry = qry.order_by(sa.desc(TimeEntry.date), sa.desc(TimeEntry.start), sa.desc(TimeEntry.creation_date))

        if limit:
            qry = qry.limit(limit)

        qry = self.request.filter_viewables(qry)
        entries_by_date = []
        entries_count = 0
        
        for k, g in itertools.groupby(qry, operator.attrgetter('date')):
            g = list(g)
            entries_by_date.append((k, g))
            entries_count += len(g)

        return entries_by_date, entries_count


    @view_config(name='report_my_entries', route_name='reports', renderer='skin', permission='reports_my_entries')
    def __call__(self):
        schema = self.MyEntriesSchema(validator=validate_period).clone()\
                     .bind(yesterday=yesterday(),
                           today=datetime.date.today())
        limit = 1000
        projects = qry_active_projects().all()
        form = PorInlineForm(schema,
                             action=self.request.current_route_url(),
                             formid='my_entries',
                             method='GET',
                             buttons=[
                                 SearchButton(title=u'Search'),
                             ])

        form['project_id'].widget.values = [('', '')] + sorted([(str(p.id), ' / '.join([p.customer.name, p.name])) for p in projects],
                                                               key=lambda x: x[1].lower())

        result_table = ''
        controls = self.request.GET.items()

        try:
            appstruct = form.validate(controls)
        except ValidationFailure as e:
            return {
                    'form': e.render(),
                    'saved_query_form': render_saved_query_form(self.request),
                    'result_table': None
                    }
        
        current_uid = self.request.authenticated_user.id
        entries_by_date, entries_count = self.search(author_id=current_uid,
                                                     limit=limit,
                                                     **appstruct)

        highlight = functools.partial(webhelpers.html.tools.highlight,
                                      phrase=appstruct['searchtext'])

        delta0 = datetime.timedelta()
        delta_tot = sum([sum((e.hours for e in x[1]), delta0) for x in entries_by_date], delta0)

        human_tot = timedelta_as_human_str(delta_tot)
        days_tot = timedelta_as_work_days(delta_tot)

        result_table = render('penelope.core:reports/templates/my_entries_results.pt',
                              {
                                  'entries_by_date': entries_by_date,
                                  'entries_count': entries_count,
                                  'highlight': highlight,
                                  'human_tot': human_tot,
                                  'days_tot': days_tot,
                                  'datetime': datetime,
                                  'ticket_url': ticket_url,
                                  'timedelta_as_human_str': timedelta_as_human_str,
                              },
                              request=self.request)

        return {
                'form': form.render(appstruct=appstruct),
                'saved_query_form': render_saved_query_form(self.request),
                'result_table': result_table,
                }
