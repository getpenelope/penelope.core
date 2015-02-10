import os
import argparse
import sys
import beaker
import csv
import tempfile

import gdata.data
import gdata.docs.client
import gdata.docs.data
import gdata.docs.service
import gdata.sample_util

from pyramid.paster import get_appsettings, setup_logging
from datetime import datetime, date, timedelta
from sqlalchemy.orm import mapper
from sqlalchemy import engine_from_config, extract
from sqlalchemy import MetaData, Table, and_, or_
from sqlalchemy import func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, backref, defer

from trac.util.datefmt import from_utimestamp
from penelope.core.models.dashboard import Project, CustomerRequest, Trac, Estimation, Customer, Contract, User
from penelope.core.models.tp import TimeEntry, timedelta_as_work_days
from penelope.core.models.dbsession import DBSession
from penelope.core.models import Base


beaker.cache.cache_regions.update(dict(calculate_matrix={}))


def encode_row(row):
    result = []
    for r in row:
        if isinstance(r, unicode):
            result.append(r.encode('utf8'))
        else:
            result.append(r)
    return result


def create_client():
    client = gdata.docs.client.DocsClient(source='GDataDocumentsListAPISample-v1.0')
    try:
        gdata.sample_util.authorize_client(
            client,
            1,
            service=client.auth_service,
            source=client.source,
            scopes=client.auth_scopes
        )
    except gdata.client.BadAuthentication:
        exit('Invalid user credentials given.')
    except gdata.client.Error:
        exit('Login Error')
    return client


def upload_file(client, path, title, collection):

    def get_upload_folder():
        folders = client.get_doclist(uri='/feeds/default/private/full?title=%s&category=folder' % collection)
        for folder in folders.entry:
            return folder

    content_type = gdata.docs.service.SUPPORTED_FILETYPES['CSV']
    entry = client.Upload(path, title=title, content_type=content_type)
    folder = get_upload_folder()
    if folder:
        client.move(entry, folder)
    print 'Uploaded...'


def tickets_for_cr(metadata, session, trac_name, cr_id=None):

    class Ticket(object):
        @hybrid_property
        def date(self):
            return datetime.fromtimestamp(self.time/1000000)

        def last_history(self, name, year):
            from_year = [a for a in self.history \
                                   if a.date.year == year and a.field == name]
            from_year.sort(key=lambda a: a.date, reverse=True)
            for history in from_year:
                return history.newvalue
            return getattr(self, name)

        @property
        def close_date(self):
            status = [a for a in self.history if a.field == 'status']
            status.sort(key=lambda a: a.date, reverse=True)
            for history in status:
                if history.newvalue == 'closed':
                    return history.date
            return None


    class TicketChange(object):
        @hybrid_property
        def date(self):
            return datetime.fromtimestamp(self.time/1000000)


    class TicketCustom(object):
        def __init__(self, ticket, name, value):
            self.ticket = ticket
            self.name = name
            self.value = value

        @property
        def unicode_value(self):
            return self.value.encode('utf8','ignore')

    ticket = Table('ticket', metadata, autoload=True, schema='trac_%s' % trac_name)
    ticket_custom = Table('ticket_custom', metadata, autoload=True, schema='trac_%s' % trac_name)
    ticket_change = Table('ticket_change', metadata, autoload=True, schema='trac_%s' % trac_name)
    mapper(TicketCustom, ticket_custom)
    mapper(TicketChange, ticket_change, properties={
            'realticket':relationship(Ticket, primaryjoin=ticket_change.c.ticket==ticket.c.id,
                                      foreign_keys=[ticket_change.c.ticket],
                                      backref=backref('history')),
    })
    mapper(Ticket, ticket, properties={
            'customer_request':relationship(TicketCustom, primaryjoin=and_(ticket_custom.c.ticket==ticket.c.id,
                                                                          ticket_custom.c.name=='customerrequest'),
                                           foreign_keys=[ticket.c.id]),
            'excluded':relationship(TicketCustom, primaryjoin=and_(ticket_custom.c.ticket==ticket.c.id,
                                                                          ticket_custom.c.name=='stats_exclude'),
                                           foreign_keys=[ticket.c.id]),
            'open_by_customer':relationship(TicketCustom, primaryjoin=and_(ticket_custom.c.ticket==ticket.c.id,
                                                                           ticket_custom.c.name=='esogeno'),
                                            foreign_keys=[ticket.c.id]),
            'issue_type':relationship(TicketCustom, primaryjoin=and_(ticket_custom.c.ticket==ticket.c.id,
                                                                     ticket_custom.c.name=='issuetype'),
                                      foreign_keys=[ticket.c.id]),
            })

    query = session.query(Ticket)
    if cr_id:
        query = query.outerjoin(TicketCustom, TicketCustom.ticket==Ticket.id)\
                     .filter(and_(TicketCustom.name=='customerrequest',
                                  TicketCustom.value==cr_id))
    return query, Ticket, TicketCustom


def trac_bool(value):
    """
    Make sure all the strange trac formats are supported and proper bool is returned.
    """
    if value == 0 or value == 'false' or value == None or value == '0':
        return False
    else:
        return True


def round_to(n, precission):
    correction = 0.5 if n >= 0 else -0.5
    return int(n/precission+correction)*precission


def elapsed_time_in_hours(start, end, email, customer_time, rt_time):
    """
    Calculate elapsed time in minutes taking under consideration ticket owner.
    """
    td = from_utimestamp(end) - from_utimestamp(start)
    total_seconds = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6
    elapsed = total_seconds / 3600.0

    if email and 'redturtle' in email or False:
        rt_time += elapsed
    else:
        customer_time += elapsed

    return customer_time, rt_time


class Quality(argparse.Action):
    def __call__(self, parser, namespace, values, option_string):
        super(Quality, self).__init__(parser, namespace, values, option_string)
        self.namespace = namespace
        config_uri = namespace.configuration
        setup_logging(config_uri)
        settings = get_appsettings(config_uri, name='dashboard')
        engine = engine_from_config(settings, 'sa.dashboard.')
        DBSession.configure(bind=engine)
        Base.metadata.bind = engine
        Base.metadata.create_all()
        self.metadata = MetaData(engine)

        configuration = {}
        tmp = tempfile.NamedTemporaryFile(suffix='.csv')
        namespace.filename = tmp.name
        tmp.close()
        configuration['filename'] = namespace.filename
        print 'Creating file %s' % namespace.filename
        setattr(namespace, option_string.strip('--'), configuration)


class QualityProject(Quality):
    def __call__(self, parser, namespace, values, option_string):
        super(QualityProject, self).__call__(parser, namespace, values, option_string)
        session = DBSession()
        with open(namespace.filename, 'wb') as ofile:
            writer = csv.writer(ofile, dialect='excel')
            writer.writerow(['Project ID', 'Customer', 'Project creation year',
                             'Project creation month', 'Project creation day',
                             'Project completion year', 'Project completion month',
                             'Project completion day'])
            for project in session.query(Project.id, Project.completion_date,
                                   Project.customer_id, Project.creation_date)\
                                  .outerjoin(TimeEntry, TimeEntry.project_id==Project.id)\
                                  .filter(extract('year', TimeEntry.date) == namespace.year)\
                                  .distinct():

                writer.writerow(encode_row([project.id, project.customer_id, 
                                 project.creation_date and project.creation_date.strftime('%Y') or '',
                                 project.creation_date and project.creation_date.strftime('%m') or '',
                                 project.creation_date and project.creation_date.strftime('%d') or '',
                                 project.completion_date and project.completion_date.strftime('%Y') or '',
                                 project.completion_date and project.completion_date.strftime('%m') or '',
                                 project.completion_date and project.completion_date.strftime('%d') or '',
                                 ]))


class QualityCR(Quality):
    def __call__(self, parser, namespace, values, option_string):
        super(QualityCR, self).__call__(parser, namespace, values, option_string)
        session = DBSession()
        with open(namespace.filename, 'wb') as ofile:
            writer = csv.writer(ofile, dialect='excel')
            writer.writerow(['CR ID', 'Description', 'Customer', 'CR state',
                             'Estimation in days', 'TE duration in days - current year',
                             'TE sistem/install in days - current year',
                             'TE duration in days - overall', 'TE sistem/install in days - overall'])
            crs = session.query(CustomerRequest.id,
                                CustomerRequest.name,
                                CustomerRequest.workflow_state,
                                CustomerRequest.project_id,
                                Project.customer_id).\
                   outerjoin(Project, CustomerRequest.project_id == Project.id).distinct()

            for cr in crs:

                all_entries = session.query(TimeEntry).filter_by(customer_request_id=cr.id)
                if not all_entries.count():
                    continue

                estimations = sum([a.days for a in \
                                session.query(Estimation.days)\
                                       .filter_by(customer_request_id=cr.id)])

                current_year_entries = session.query(TimeEntry)\
                                              .filter_by(customer_request_id=cr.id)\
                                              .filter(extract('year', TimeEntry.date) == namespace.year)

                total_hours = timedelta_as_work_days(sum([a.hours for a in all_entries], timedelta()))
                total_dev_hours = timedelta_as_work_days(sum([a.hours for a in
                                            all_entries.filter(or_(TimeEntry.description.ilike('%install%'),
                                                                    TimeEntry.description.ilike('%sistem%')))], timedelta()))
                current_year_hours = timedelta_as_work_days(sum([a.hours for a in current_year_entries], timedelta()))
                current_year_dev_hours = timedelta_as_work_days(sum([a.hours for a in
                                                    current_year_entries.filter(or_(TimeEntry.description.ilike('%install%'),
                                                                                    TimeEntry.description.ilike('%sistem%')))], timedelta()))

                writer.writerow(encode_row([cr.id, cr.name, cr.customer_id,
                                            cr.workflow_state, estimations, current_year_hours,
                                            current_year_dev_hours, total_hours, total_dev_hours]))


class QualityTicket(Quality):
    def __call__(self, parser, namespace, values, option_string):
        super(QualityTicket, self).__call__(parser, namespace, values, option_string)
        session = DBSession()
        with open(namespace.filename, 'wb') as ofile:
            writer = csv.writer(ofile, dialect='excel')
            writer.writerow(['Ticket ID',
                             'Customer',
                             'Ticket creation year',
                             'Ticket creation month',
                             'Ticket creation day',
                             'Ticket completion year',
                             'Ticket completion moneth',
                             'Ticket completion day',
                             'Ticket state',
                             'Ticket summary', # new field
                             'Ticket last owner',
                             'Ticket types',
                             'Ticket opened by customer',
                             'Problem nature',
                             'Excluded from stats' # new field
                             ])

            for pr in session.query(Project.customer_id, Project.id, Trac.trac_name)\
                             .outerjoin(Trac, Project.id==Trac.project_id)\
                             .outerjoin(TimeEntry, TimeEntry.project_id==Project.id)\
                             .filter(TimeEntry.project_id==Project.id)\
                             .filter(extract('year', TimeEntry.date) == namespace.year).distinct():
                tickets, Ticket, TicketCustom = tickets_for_cr(self.metadata, session, pr.trac_name)
                tickets_in_year = session.query(Ticket)\
                                         .outerjoin(TimeEntry,
                                                    and_(TimeEntry.project_id==pr.id,
                                                         TimeEntry.ticket==Ticket.id))\
                                         .filter(extract('year', TimeEntry.date) == namespace.year).distinct()
                for ticket in tickets_in_year:
                    last_status = ticket.last_history('status', namespace.year)
                    close_date = ticket.close_date
                    all_types = set([])
                    for h in ticket.history:
                        if h.field == 'type':
                            all_types.update([h.oldvalue])
                    all_types.update([ticket.type])
                    all_types = '|'.join(all_types)

                    writer.writerow(encode_row(
                          [ticket.id,
                           pr.customer_id,
                           ticket.date.strftime('%Y'),
                           ticket.date.strftime('%m'),
                           ticket.date.strftime('%d'),
                           close_date and close_date.strftime('%Y') or '',
                           close_date and close_date.strftime('%m') or '',
                           close_date and close_date.strftime('%d') or '',
                           last_status,
                           ticket.summary,
                           ticket.owner,
                           all_types,
                           ticket.open_by_customer and ticket.open_by_customer.unicode_value or '',
                           ticket.issue_type and ticket.issue_type.unicode_value or '',
                           ticket.excluded and ticket.excluded.unicode_value or '']))


class QualityRaw(Quality):
    def __call__(self, parser, namespace, values, option_string):
        super(QualityRaw, self).__call__(parser, namespace, values, option_string)
        session = DBSession()
        with open(namespace.filename, 'wb') as ofile:
            writer = csv.writer(ofile, dialect='excel')
            writer.writerow(['CR ID', 'Customer', 'Duration in days'])
            for cr in session.query(CustomerRequest.id,
                                    CustomerRequest.project_id,
                                    Project.customer_id,
                                    Trac.trac_name).\
                              outerjoin(Project,
                                        CustomerRequest.project_id == Project.id).\
                              outerjoin(Trac,
                                        Project.id==Trac.project_id).distinct():

                tickets, Ticket, TicketCustom = tickets_for_cr(self.metadata, session, cr.trac_name, cr.id)
                tids = [t.id for t in tickets]
                if not tids:
                    continue

                entries = session.query(TimeEntry)\
                                 .filter_by(project_id=cr.project_id)\
                                 .filter(TimeEntry.ticket.in_(tids))\
                                 .filter(extract('year', TimeEntry.date) == namespace.year)

                if entries.count():
                    hours = timedelta_as_work_days(sum([a.hours for a in entries], timedelta()))
                    writer.writerow(encode_row([cr.id, cr.customer_id, hours]))


class QualityOurCustomerTimeOpened(Quality):
    def __call__(self, parser, namespace, values, option_string):
        super(QualityOurCustomerTimeOpened, self).__call__(parser, namespace, values, option_string)
        session = DBSession()

        def url(ticket):
            return "https://penelope.redturtle.it/trac/{0.trac}/ticket/{0.id}".format(ticket)

        namespace.we_vs_customer_new['custom_report_name'] = 'we_vs_customer_new'

        query = u"""SELECT '{0}' AS trac,
                          '{1}' AS project,
                          '{2}' AS customer,
                          id,
                          time,
                          changetime,
                          owner,
                          reporter,
                          summary,
                          type,
                          customerrequest.value AS cr_id,
                          open_by_customer.value AS open_by_customer,
                          exclude_stats.value AS excluded
                    FROM "trac_{0}".ticket AS ticket
                    LEFT OUTER JOIN "trac_{0}".ticket_custom AS open_by_customer ON ticket.id=open_by_customer.ticket AND open_by_customer.name='esogeno'
                    LEFT OUTER JOIN "trac_{0}".ticket_custom AS customerrequest ON ticket.id=customerrequest.ticket AND customerrequest.name='customerrequest'
                    LEFT OUTER JOIN "trac_{0}".ticket_custom AS exclude_stats ON ticket.id=exclude_stats.ticket AND exclude_stats.name='stats_exclude'
                        WHERE status!='closed'"""

        crs = dict(session.query(CustomerRequest.id, CustomerRequest.name).all())
        queries = []
        for trac in session.query(Trac):
            queries.append(query.format(trac.trac_name, trac.project.name.replace("'","''"), trac.project.customer.name.replace("'","''")))
        sql = '\nUNION '.join(queries)
        sql += ';'

        with open(namespace.filename, 'wb') as ofile:
            writer = csv.writer(ofile, dialect='excel')

            writer.writerow(['Customer', 'Project', 'CR ID', 'CR name', 'Ticket #',
                'Ticket created', 'Ticket created year', 'Ticket summary', 'Ticket type',
                'Ticket URL', 'Owner', 'Open by customer', 'Elapsed RT time (in normal hours)',
                'Elapsed non RT time (in normal hours)', 'Excluded from stats'])

            for ticket in session.execute(sql).fetchall():
                reporter = ticket.reporter
                created = from_utimestamp(ticket.time)
                created_year = created.strftime('%Y')
                created = created.strftime('%Y-%m-%d %H:%M')
                owner = ticket.owner or reporter
                history = session.execute("""SELECT time, oldvalue, newvalue 
                                                FROM "trac_{0}".ticket_change
                                                    WHERE ticket={1} AND field='owner'
                                                    ORDER BY time""".format(ticket.trac, ticket.id)).fetchall()

                customer_time = 0
                rt_time = 0
                if not history:
                    customer_time, rt_time = elapsed_time_in_hours(ticket.time, ticket.changetime, owner, customer_time, rt_time)

                else:
                    first_history = history.pop(0)
                    owner = first_history.oldvalue or reporter
                    last_change = first_history.time
                    customer_time, rt_time = elapsed_time_in_hours(ticket.time, last_change, owner, customer_time, rt_time)

                    for h in history:
                        owner = h.oldvalue or reporter
                        customer_time, rt_time = elapsed_time_in_hours(last_change, h.time, owner, customer_time, rt_time)
                        last_change = h.time

                writer.writerow(encode_row(
                        [ ticket.customer, ticket.project, ticket.cr_id, crs.get(ticket.cr_id),
                          ticket.id, created, created_year, ticket.summary, ticket.type,
                          url(ticket), owner, trac_bool(ticket.open_by_customer),
                          round_to(rt_time, 0.5), round_to(customer_time, 0.5), trac_bool(ticket.excluded)]))


class QualityOurCustomerTime(Quality):
    def __call__(self, parser, namespace, values, option_string):
        super(QualityOurCustomerTime, self).__call__(parser, namespace, values, option_string)
        session = DBSession()

        def url(ticket):
            return "https://penelope.redturtle.it/trac/{0.trac}/ticket/{0.id}".format(ticket)

        query = u"""SELECT '{0}' AS trac,
                          '{2}' AS project,
                          '{3}' AS customer,
                          id,
                          time,
                          changetime,
                          owner,
                          reporter,
                          summary,
                          type,
                          customerrequest.value AS cr_id,
                          open_by_customer.value AS open_by_customer,
                          exclude_stats.value AS excluded
                    FROM "trac_{0}".ticket AS ticket
                    LEFT OUTER JOIN "trac_{0}".ticket_custom AS open_by_customer ON ticket.id=open_by_customer.ticket AND open_by_customer.name='esogeno'
                    LEFT OUTER JOIN "trac_{0}".ticket_custom AS customerrequest ON ticket.id=customerrequest.ticket AND customerrequest.name='customerrequest'
                    LEFT OUTER JOIN "trac_{0}".ticket_custom AS exclude_stats ON ticket.id=exclude_stats.ticket AND exclude_stats.name='stats_exclude'
                        WHERE status='closed'
                        AND EXTRACT('year' FROM to_timestamp(changetime / 1000000)) = {1}"""

        crs = dict(session.query(CustomerRequest.id, CustomerRequest.name).all())
        queries = []
        for trac in session.query(Trac):
            queries.append(query.format(trac.trac_name, namespace.year, trac.project.name.replace("'","''"), trac.project.customer.name.replace("'","''")))
        sql = '\nUNION '.join(queries)
        sql += ';'

        with open(namespace.filename, 'wb') as ofile:
            writer = csv.writer(ofile, dialect='excel')

            writer.writerow(['Customer', 'Project', 'CR ID', 'CR name', 'Ticket #',
                'Ticket summary', 'Ticket type', 'Ticket URL', 'Owner',
                'Open by customer', 'Elapsed RT time (in normal hours)',
                'Elapsed non RT time (in normal hours)', 'Excluded from stats', 'Closure date', 'Closure year'])

            for ticket in session.execute(sql).fetchall():
                reporter = ticket.reporter
                owner = ticket.owner or reporter
                history = session.execute("""SELECT time, oldvalue, newvalue 
                                                FROM "trac_{0}".ticket_change
                                                    WHERE ticket={1} AND field='owner'
                                                    ORDER BY time""".format(ticket.trac, ticket.id)).fetchall()
                close_date = session.execute("""SELECT time FROM "trac_{0}".ticket_change
                                                            WHERE ticket={1} AND field='status' and newvalue='closed'
                                                            ORDER BY time DESC LIMIT 1""".format(ticket.trac, ticket.id)).fetchone()
                close_date = datetime.fromtimestamp(close_date.time/1000000)
                customer_time = 0
                rt_time = 0

                if not history:
                    customer_time, rt_time = elapsed_time_in_hours(ticket.time, ticket.changetime, owner, customer_time, rt_time)
                else:
                    first_history = history.pop(0)
                    owner = first_history.oldvalue or reporter
                    last_change = first_history.time
                    customer_time, rt_time = elapsed_time_in_hours(ticket.time, last_change, owner, customer_time, rt_time)

                    for h in history:
                        owner = h.oldvalue or reporter
                        customer_time, rt_time = elapsed_time_in_hours(last_change, h.time, owner, customer_time, rt_time)
                        last_change = h.time

                    writer.writerow(encode_row(
                            [ ticket.customer, ticket.project, ticket.cr_id,
                              crs.get(ticket.cr_id), ticket.id, ticket.summary,
                              ticket.type, url(ticket), owner, trac_bool(ticket.open_by_customer),
                              round_to(rt_time, 0.5), round_to(customer_time, 0.5),
                              trac_bool(ticket.excluded), close_date.strftime('%Y-%m-%d'),
                              close_date.strftime('%Y')]))


class QualityOperator(Quality):
    def __call__(self, parser, namespace, values, option_string):
        super(QualityOperator, self).__call__(parser, namespace, values, option_string)
        session = DBSession()
        with open(namespace.filename, 'wb') as ofile:
            writer = csv.writer(ofile, dialect='excel')

            writer.writerow(['Customer name', 'Project name', 'CR description', 'CR total estimations (days)', 'CR status',
                             'Contract number', 'Contract amount', 'Contract days', 'Contract end date', 'Contract status',
                             'User', 'Total time in CR (days)'])
            query = session.query(
                                  TimeEntry.customer_request_id,
                                  TimeEntry.author_id,
                                  func.sum(TimeEntry.hours).label('total_time'),
                                  CustomerRequest,
                                  Project.name.label('project'),
                                  Customer.name.label('customer'),
                                  Contract.amount.label('contract_amount'),
                                  Contract.days.label('contract_days'),
                                  Contract.contract_number,
                                  Contract.end_date.label('contract_end_date'),
                                  Contract.workflow_state.label('contract_workflow_state'),
                                  User.fullname.label('user'),
                                  )\
                           .options(defer(CustomerRequest.filler),
                                    defer(CustomerRequest.old_contract_name),
                                    defer(CustomerRequest.uid),
                                    defer(CustomerRequest.description),
                                    defer(CustomerRequest.project_id),
                                    defer(CustomerRequest.contract_id),
                                   )\
                           .join(CustomerRequest)\
                           .join(Project)\
                           .join(Customer)\
                           .join(Contract, and_(TimeEntry.customer_request_id==CustomerRequest.id,
                                                CustomerRequest.contract_id==Contract.id))\
                           .outerjoin(User, TimeEntry.author_id==User.id)\
                           .filter(extract('year', TimeEntry.date) == namespace.year)\
                           .group_by(TimeEntry.customer_request_id)\
                           .group_by(TimeEntry.author_id)\
                           .group_by(Project.name)\
                           .group_by(Contract.amount)\
                           .group_by(Contract.contract_number)\
                           .group_by(Contract.days)\
                           .group_by(Contract.end_date)\
                           .group_by(Contract.workflow_state)\
                           .group_by(CustomerRequest.name)\
                           .group_by(CustomerRequest.id)\
                           .order_by(CustomerRequest.name)\
                           .order_by(CustomerRequest.workflow_state)\
                           .group_by(Customer.name)\
                           .group_by(User.fullname)

            for row in query:
                writer.writerow(encode_row(
                                [row.customer,
                                 row.project,
                                 row.CustomerRequest.name,
                                 row.CustomerRequest.estimation_days,
                                 row.CustomerRequest.workflow_state,
                                 row.contract_number and row.contract_number or 'N/A',
                                 row.contract_amount or 0,
                                 row.contract_days or 0,
                                 row.contract_end_date or 'N/A',
                                 row.contract_workflow_state,
                                 row.user,
                                 timedelta_as_work_days(row.total_time)]))


def main():
    """
    ./bin/quality_export etc/production.ini export_file.csv --report-name
    """

    if len(sys.argv) == 1:
        sys.argv.append('--help')

    parser = argparse.ArgumentParser(description='Quality export')
    DEFAULT_YEAR = date.today().year -1
    parser.set_defaults(year=DEFAULT_YEAR)

    parser.add_argument('configuration', action='store', help='path to the wsgi configuration ini file.')
    parser.add_argument('year', help='Report year. (default %s)' % DEFAULT_YEAR, action='store', type=int)
    parser.add_argument('--google', help='google folder id.')

    parser.add_argument('--project', nargs=0, action=QualityProject, help='generate project quality report.')
    parser.add_argument('--cr', nargs=0, action=QualityCR, help='generate customer request quality report.')
    parser.add_argument('--ticket', nargs=0, action=QualityTicket, help='generate ticket quality report.')
    parser.add_argument('--raw', nargs=0, action=QualityRaw, help='generate raw quality report.')
    parser.add_argument('--we_vs_customer_closed', nargs=0, action=QualityOurCustomerTime, help='generate we vs customer time quality report.')
    parser.add_argument('--we_vs_customer_new', nargs=0, action=QualityOurCustomerTimeOpened, help='generate we vs customer time quality report.')
    parser.add_argument('--operator', nargs=0, action=QualityOperator, help='generate total work time for CR and operator quality report.')
    namespace = parser.parse_args()

    if namespace.google:
        client = create_client()
        for report in  ['project', 'cr', 'ticket', 'raw', 'operator', 'we_vs_customer_closed', 'we_vs_customer_new']:
            configuration = getattr(namespace, report)
            if configuration:
                upload_file(client, configuration['filename'],
                            'Report: %s' % configuration.get('custom_report_name', report),
                            namespace.google)
                os.unlink(configuration['filename'])
