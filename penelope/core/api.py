
import datetime

from sqlalchemy.orm import exc as orm_exc
from pyramid_rpc.jsonrpc import jsonrpc_method

from penelope.core.lib.helpers import time_parse

from penelope.core.models import DBSession
from penelope.core.models.tp import TimeEntry, timedelta_as_human_str
from penelope.core.models.dashboard import User, Customer, Project, CustomerRequest
from penelope.core.models.tickets import ticket_store


def decode_string(entry):
    if not isinstance(entry, basestring):
        entry = entry.decode('utf-8')
    return entry


def timeentry_crstate_validation_errors(project_id, tickets, request):
    # XXX this check is deactivated for now (see #312)
    return []

    project = DBSession.query(Project).get(project_id)

    customer_requests = ticket_store.get_requests_from_tickets(project, tickets)

    for ticket_id, cr_id in customer_requests:
        cr = DBSession.query(CustomerRequest).get(cr_id)
        if cr.workflow_state != 'estimated':
            return ['Customer Request is not estimated']

    return []


@jsonrpc_method(endpoint='DashboardAPI')
def get_user_by_email(request, email):
    """
    This method search for user using his email address
    """
    session = DBSession()
    if not isinstance(email, basestring):
        return {
                'status:': False,
                'message': u'Email parameter must be a string!',
                }
    try:
        user = session.query(User).filter_by(email=email).one()
    except orm_exc.NoResultFound:
        return {
                'status': False,
                'message': u'No user found in db for %s mail address' % email,
                }

    return {
            'status': True,
            'message': u'User found.',
            'email': user.email,
            'login': user.login,
            'openids': [x.openid for x in user.openids]
            }


@jsonrpc_method(endpoint='DashboardAPI')
def get_user_by_openid(request, openid):
    """
    This method search for user using one of the possible user openids
    """
    session = DBSession()

    if not isinstance(openid, basestring):
        return {
                'status:': False,
                'message': u'Openid parameter must be a string!',
                }

    try:
        user = session.query(User).join('openids').filter_by(openid=openid).one()
    except orm_exc.NoResultFound:

        return {
                'status': False,
                'message': u'No user found in db for %s openid' % openid,
                }

    return {
            'status': True,
            'message': u'User found.',
            'email': user.email,
            'login': user.login,
            'openids': [x.openid for x in user.openids],
            }


@jsonrpc_method(endpoint='DashboardAPI')
def get_customer_by_name(request, customer_name):
    """
    This method search for customer by name
    """
    session = DBSession()

    if not isinstance(customer_name, basestring):
        return {
                'status:': False,
                'message': u'Customer name parameter must be a string!',
                }

    try:
        customer = session.query(Customer).filter_by(name=customer_name).one()
    except orm_exc.NoResultFound:
        return {
                'status': False,
                'message': u'No customer found in db for %s name' % customer_name,
                }

    return {
            'status': True,
            'message': u'Customer found.',
            'name': customer.name,
            'projects': [x.name for x in customer.projects],
            }


@jsonrpc_method(endpoint='DashboardAPI')
def get_project_by_id(request, project_id):
    """
    This method search for project by name
    """
    session = DBSession()

    if not isinstance(project_id, basestring):
        return {
                'status:': False,
                'message': u'Project id parameter must be a string!',
                }

    try:
        project = session.query(Project).get(project_id)
    except orm_exc.NoResultFound:
        return {
                'status': False,
                'message': u'No project found in db for %s name' % project_id
                }

    return {
            'status': True,
            'message': u'Project found.',
            'name': project.name,
            'id': project.id,
            'customer': project.customer.name,
            'applications': [x.name for x in project.applications],
            'customer_requests': [
                                    {
                                        'id': cr.id,
                                        'name': cr.name,
                                        'active': True
                                    }
                                    for cr in project.customer_requests
                                    ]
            }


@jsonrpc_method(endpoint='DashboardAPI')
def get_project_by_name(request, project_name):
    """
    This method search for project by name
    """
    session = DBSession()

    if not isinstance(project_name, basestring):
        return {
                'status:': False,
                'message': u'Project name parameter must be a string!',
                }

    try:
        project = session.query(Project).filter_by(name=project_name).one()
    except orm_exc.NoResultFound:
        return {
                'status': False,
                'message': u'No project found in db for %s name' % project_name,
                }

    return {
            'status': True,
            'message': u'Project found.',
            'name': project.name,
            'id': project.id,
            'customer': project.customer.name,
            'applications': [x.name for x in project.applications],
            'customer_requests': [(x.id, x.name,) for x in project.customer_requests],
            }


@jsonrpc_method(endpoint='DashboardAPI')
def time_entry_total_duration(request, date):
    try:
        date = datetime.datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        return {
                'status': False,
                'message': 'bad date format',
                }

    qry = DBSession.query(TimeEntry).filter(TimeEntry.date==date)
    qry = qry.filter(TimeEntry.author_id==request.authenticated_user.id)
    duration = sum((te.hours for te in qry), datetime.timedelta(0))

    # we can return past timeentry descriptions here

    return {
            'status': True,
            'duration': timedelta_as_human_str(duration),
            }


@jsonrpc_method(endpoint='DashboardAPI')
def create_new_simple_time_entry(request, entry_ticket, entry_date, entry_hours,
                                 entry_description, entry_location, entry_project):
    """
    Time entry creation: simple time entry case
    """

    try:
        entry_location = decode_string(entry_location)
        entry_description = decode_string(entry_description)
        entry_ticket = decode_string(entry_ticket)
        entry_time_delta = time_parse(entry_hours,
                                      minimum=datetime.timedelta(seconds=1*60),
                                      maximum=datetime.timedelta(seconds=16*60*60))
    except Exception, e:
        return {
                'status': False,
                'message': str(e),
                }

    if not entry_description:
        return {
                'status': False,
                'message': u'Description is required.',
                }

    try:
        entry_date = datetime.datetime.strptime(entry_date, '%Y-%m-%d')
    except ValueError, e:
        return {
                'status': False,
                'message': str(e),
                }


    if not entry_time_delta:
        return {
                'status': False,
                'message': 'Duration is required',
                }


    session = DBSession()
    project = session.query(Project).filter(Project.id==entry_project).first()
    if not project:
        return {
                'state': False,
                'message': u'Not able to get the project with id %s' % entry_project,
                }

    crstate_errors = timeentry_crstate_validation_errors(entry_project, [entry_ticket], request)
    if crstate_errors:
        return {
                'state': False,
                'message': '\n'.join(crstate_errors),
                }

    time_entry = TimeEntry(date = entry_date,
                           hours = entry_time_delta,
                           location = entry_location,
                           description = entry_description,
                           ticket = entry_ticket)
    time_entry.request = request        # bind for user lookup

    time_entry.project_id = entry_project
    session.add(time_entry)
    session.flush()

    return {
            'status': True,
            'message': u'Correctly added time entry %s for %s ticket #%s' % (time_entry.id, entry_project, entry_ticket),
            }


@jsonrpc_method(endpoint='DashboardAPI')
def create_new_advanced_time_entry(request, entry_ticket, entry_start, entry_end,
                                   entry_description, entry_location, entry_project):
    """
    Time entry creation: simple time entry case
    """

    try:
        entry_location = decode_string(entry_location)
        entry_description = decode_string(entry_description)
        entry_ticket = decode_string(entry_ticket)
    except Exception, e:
        return {
                'status': False,
                'message': str(e),
                }

    try:
        entry_start = datetime.datetime.strptime(entry_start, '%Y-%m-%d %H:%M:%S')
    except ValueError, e:
        return {
                'status': False,
                'message': str(e),
                }

    try:
        entry_end = datetime.datetime.strptime(entry_end, '%Y-%m-%d %H:%M:%S')
    except ValueError, e:
        return {
                'status': False,
                'message': str(e),
                }

    entry_date = datetime.date.today()
    session = DBSession()
    project = session.query(Project).filter(Project.id==entry_project).first()
    if not project:
        return {
                'state': False,
                'message': u'Not able to get the project with id %s' % entry_project,
                }

    time_entry = TimeEntry(date = entry_date,
                           start = entry_start,
                           end = entry_end,
                           location = entry_location,
                           description = entry_description,
                           ticket = entry_ticket)

    time_entry.project_id = entry_project
    session.add(time_entry)
    session.flush()

    return {
            'status': True,
            'message': u'Correctly added time entry %s for %s ticket #%s' % (time_entry.id, entry_project, entry_ticket)
            }
