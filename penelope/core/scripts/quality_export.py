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
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, backref

from penelope.core.models.dashboard import Project, CustomerRequest, Trac, Estimation
from penelope.core.models.tp import TimeEntry, timedelta_as_work_days
from penelope.core.models.dbsession import DBSession
from penelope.core.models import Base


beaker.cache.cache_regions.update(dict(calculate_matrix={}))


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

        #if not namespace.google and not namespace.filename:
        #    raise argparse.ArgumentTypeError(u'You need to pass filename or google.')

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

                writer.writerow([project.id, project.customer_id, 
                                 project.creation_date.strftime('%Y'),
                                 project.creation_date.strftime('%m'),
                                 project.creation_date.strftime('%d'),
                                 project.completion_date and project.completion_date.strftime('%Y') or '',
                                 project.completion_date and project.completion_date.strftime('%m') or '',
                                 project.completion_date and project.completion_date.strftime('%d') or '',
                                 ])


class QualityCR(Quality):
    def __call__(self, parser, namespace, values, option_string):
        super(QualityCR, self).__call__(parser, namespace, values, option_string)
        session = DBSession()
        with open(namespace.filename, 'wb') as ofile:
            writer = csv.writer(ofile, dialect='excel')
            writer.writerow(['CR ID', 'Customer', 'CR state',
                             'Estimation in days', 'TE Duration in days',
                             'TE sistem/install in days'])
            for cr in session.query(CustomerRequest.id,
                                    CustomerRequest.workflow_state,
                                    CustomerRequest.project_id,
                                    Project.customer_id,
                                    Trac.trac_name).\
                              outerjoin(Project,
                                        CustomerRequest.project_id == Project.id).\
                              outerjoin(Trac,
                                        Project.id==Trac.project_id).distinct():

                tickets, Ticket, TicketCustom = tickets_for_cr(self.metadata,
                                                 session, cr.trac_name, cr.id)
                tids = [t.id for t in tickets]
                if not tids:
                    continue
                estimations = sum([a.days for a in \
                                session.query(Estimation.days)\
                                       .filter_by(customer_request_id=cr.id)])

                entries = session.query(TimeEntry)\
                                 .filter_by(project_id=cr.project_id)\
                                 .filter(TimeEntry.ticket.in_(tids))\
                                 .filter(extract('year', TimeEntry.date) == namespace.year)

                if entries.count():
                    total_hours = timedelta_as_work_days(sum([a.hours for a in entries], timedelta()))
                    only_dev = entries.filter(or_(TimeEntry.description.ilike('%install%'),
                                                  TimeEntry.description.ilike('%sistem%')))
                    only_dev_hours = timedelta_as_work_days(sum([a.hours for a in only_dev], timedelta()))
                    writer.writerow([cr.id, cr.customer_id, cr.workflow_state, estimations, total_hours, only_dev_hours])


class QualityTicket(Quality):
    def __call__(self, parser, namespace, values, option_string):
        super(QualityTicket, self).__call__(parser, namespace, values, option_string)
        session = DBSession()
        with open(namespace.filename, 'wb') as ofile:
            writer = csv.writer(ofile, dialect='excel')
            writer.writerow(['Ticket ID', 'Customer',
                             'Ticket creation year',
                             'Ticket creation month',
                             'Ticket creation day',
                             'Ticket completion year',
                             'Ticket completion moneth',
                             'Ticket completion day',
                             'Ticket state', 'Ticket last owner', 'Ticket types',
                             'Ticket opened by customer', 'Problem nature'])

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
                    all_types = '|'.join(all_types).encode('utf8','ignore')
                    writer.writerow(
                          [ticket.id, pr.customer_id,
                           ticket.date.strftime('%Y'),
                           ticket.date.strftime('%m'),
                           ticket.date.strftime('%d'),
                           close_date and close_date.strftime('%Y') or '',
                           close_date and close_date.strftime('%m') or '',
                           close_date and close_date.strftime('%d') or '',
                           last_status, ticket.owner, all_types,
                           ticket.open_by_customer and ticket.open_by_customer.unicode_value or '',
                           ticket.issue_type and ticket.issue_type.unicode_value or ''])


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
                    writer.writerow([cr.id, cr.customer_id, hours])


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
    #parser.add_argument('--filename', help='path to the output CSV file.')
    parser.add_argument('--google', help='google folder id.')
    parser.add_argument('--project', nargs=0, action=QualityProject, help='generate project quality report.')
    parser.add_argument('--cr', nargs=0, action=QualityCR, help='generate customer request quality report.')
    parser.add_argument('--ticket', nargs=0, action=QualityTicket, help='generate ticket quality report.')
    parser.add_argument('--raw', nargs=0, action=QualityRaw, help='generate raw quality report.')
    namespace = parser.parse_args()

    if namespace.google:
        client = create_client()
        for report in  ['project', 'cr', 'ticket', 'raw']:
            configuration = getattr(namespace, report)
            if configuration:
                upload_file(client, configuration['filename'],
                            'Report: %s' % report,
                            namespace.google)
                os.unlink(configuration['filename'])
