# -*- coding: utf-8 -*-

import datetime

import sqlalchemy as sa

from pyramid.view import view_config

from penelope.core.models import DBSession
from penelope.core.models.tp import TimeEntry, timedelta_as_human_str
from penelope.core import views, fanstatic_resources


class TPContext(views.DefaultContext):
    """
    Default context factory for TP views.
    """


@view_config(name='add_entry', renderer='skin', permission='add_entry')
def add_entry(context, request):
    fanstatic_resources.add_entry.need()
    return {
            'context': context,
            'request': request,
            }


@view_config(name='latest_entries', renderer='skin')
def latest_entries(context, request):
    """
    Returns an HTML fragment with tables of the latest time entries
    """

    qry = DBSession.query(TimeEntry)

    current_user = request.environ.get('repoze.who.identity')['user']
    qry = qry.filter(TimeEntry.author_id==current_user.id)

    qry = qry.order_by(sa.desc(TimeEntry.date), sa.desc(TimeEntry.start), sa.desc(TimeEntry.creation_date))
    time_entries_today = qry.filter(TimeEntry.date==datetime.date.today()).all()
    today_total = timedelta_as_human_str(sum([a.hours for a in time_entries_today], datetime.timedelta()))

    latest_limit = 20
    time_entries_latest = qry.limit(latest_limit)

    return {
            'context': context,
            'request': request,
            'time_entries_today': time_entries_today,
            'today_total': today_total,
            'time_entries_latest': time_entries_latest,
            'time_entries_latest_limit': latest_limit,
            'report_my_from_date': datetime.date.today() - datetime.timedelta(days=6),
            'today': datetime.date.today(),
            }
