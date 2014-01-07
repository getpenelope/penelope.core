import os
import sys
import transaction
import random
import beaker

from sqlalchemy import engine_from_config
from pyramid.paster import setup_logging
from pyramid.paster import bootstrap

from penelope.core.models.dashboard import Trac
from penelope.core.scripts import add_customer, add_customer_request, add_project, populate_time_entries, add_user, add_role
from penelope.core.models.dbsession import DBSession
from penelope.core.models import Base
from penelope.core.models.dashboard import GlobalConfig
from penelope.trac.populate import add_trac_tickets


beaker.cache.cache_regions.update(dict(calculate_matrix={'key_length':''}))


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini [--use-small]")' % (cmd, cmd)) 
    sys.exit(1)


def main(argv=sys.argv):
    if len(argv) > 3:
        usage(argv)
    if len(argv) == 3:
        use_small = True
    else:
        use_small = False
    config_uri = argv[1]
    setup_logging(config_uri)
    env = bootstrap('%s#dashboard'% config_uri)
    settings = env.get('registry').settings
    engine = engine_from_config(settings, 'sa.dashboard.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all()


    with transaction.manager:
        random.seed(42)
        session = DBSession()
        session.add(GlobalConfig(id=1))

        users = [
                 add_user(session, u'john@example.com', fullname='John Smith'),
                 add_user(session, u'customer@example.com', fullname='Mr. Customer'),
        ]

        role_admin = add_role(session, 'administrator')
        role_admin.users.append(users[0])

        add_role(session, 'external_developer')
        add_role(session, 'internal_developer')
        add_role(session, 'secretary')
        role_customer = add_role(session, 'customer')
        role_customer.users.append(users[1])
        add_role(session, 'project_manager')

        if use_small:
            small_dummies(session,users,settings)
        else:
            full_dummies(session,users,settings)


def small_dummies(session, users, settings):
        customers = [
            add_customer(session, u'Mr. Customer'),
        ]
        session.flush()

        projects = []
        for project_name, customer_id in [
                (u'Ferrara', customers[0].id),
                (u'Bologna', customers[0].id),
            ]:
            projects.append(add_project(session, project_name, customer_id, None))
            session.flush()

        customer_requests = [
            add_customer_request(session, u"Want this",                     project_id='ferrara'),
            add_customer_request(session, u"Want that",                     project_id='bologna'),
        ]
        session.flush()

        all_tickets = {}
        for project in projects:
            all_tickets[project.id] = []
            # add_trac_to_project(project, config)
            trac_app = Trac(name='trac for project %s' % project.id)
                            # api_uri e' generata dinamicamente dall'evento before_insert di application
                            # api_uri = 'http://localhost:8081/trac/%s' % project.id,
            project.add_application(trac_app)
        session.flush()

        for cr in customer_requests:
            all_tickets[cr.project.id].extend(add_trac_tickets(cr.project, cr, settings, users))
        populate_time_entries(session, users, projects, all_tickets)


def full_dummies(session, users, settings):
        customers = [
            add_customer(session, u'Mr. Customer'),
            add_customer(session, u'Rick Astley'),
            add_customer(session, u'Lady Gaga'),
            add_customer(session, u'Tom Waits'),
        ]

        session.flush()

        projects = []
        for project_name, customer_id in [
                (u'Plone', customers[0].id),
                (u'Pyramid', customers[0].id),
                (u'Ferrara', customers[1].id),
                (u'Bologna', customers[1].id),
                (u'Verona', customers[2].id),
                (u'Genova', customers[2].id),
                (u'Modena', customers[3].id),
                (u'Batman Returns', customers[3].id),
                (u'Totoro 1', customers[1].id),
                (u'Totoro 2', customers[2].id),
                (u'Totoro 3', customers[3].id),
            ]:
            projects.append(add_project(session, project_name, customer_id, None))
            session.flush()


        customer_requests = [
            add_customer_request(session, u"Want this",                     project_id='plone'),
            add_customer_request(session, u"Want that",                     project_id='pyramid'),
            add_customer_request(session, u"Want something different",      project_id='ferrara'),
            add_customer_request(session, u"Doesn't really know",           project_id='ferrara'),
            add_customer_request(session, u"Will know when it's done",      project_id='bologna'),
            add_customer_request(session, u"A pony",                        project_id='verona'),
            add_customer_request(session, u"OMG double rainbow!!",          project_id='verona'),
            add_customer_request(session, u"A white kitten",                project_id='verona'),
            add_customer_request(session, u"A scary jabberwocky",           project_id='genova'),
            add_customer_request(session, u"A black kitten",                project_id='genova'),
            add_customer_request(session, u"A Facebook clone",              project_id='genova'),
            add_customer_request(session, u"Many unrelated things",         project_id='modena'),
            add_customer_request(session, u"The blink tag",                 project_id='modena'),
            add_customer_request(session, u"And one more thing..",          project_id='modena'),
            add_customer_request(session, u"Emacs emulation for EDLIN.COM", project_id='batman-returns'),
            add_customer_request(session, u"Totoro 1",                      project_id='totoro-1'),
            add_customer_request(session, u"Stuff for Totoro 2",            project_id='totoro-2'),
            add_customer_request(session, u"Totoro 3 again",                project_id='totoro-3'),
        ]

        session.flush()

        all_tickets = {}
        for project in projects:
            all_tickets[project.id] = []
            # add_trac_to_project(project, config)
            trac_app = Trac(name='trac for project %s' % project.id)
                            # api_uri e' generata dinamicamente dall'evento before_insert di application
                            # api_uri = 'http://localhost:8081/trac/%s' % project.id,
            project.add_application(trac_app)

        session.flush()

        for cr in customer_requests:
            all_tickets[cr.project.id].extend(add_trac_tickets(cr.project, cr, settings, users))
        populate_time_entries(session, users, projects, all_tickets)

