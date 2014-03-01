import datetime
import lipsum
import random
import transaction
import base64
import os

from sqlalchemy import engine_from_config

from penelope.core.models.dashboard import GlobalConfig
from penelope.core.models.dashboard import User, Customer, CustomerRequest, Project, Role
from penelope.core.models.tp import TimeEntry


def add_user(session, email, fullname=None, password=None):
    model = User(email=email)
    if not password:
        password = email
    model.set_password(password)
    if fullname:
        model.fullname = fullname
    session.add(model)
    return model

def add_customer(session, name):
    model = Customer(name=name)
    session.add(model)
    return model

def add_customer_request(session, name, project_id):
    model = CustomerRequest(name=name, project_id=project_id)
    session.add(model)
    return model


def add_project(session, project_name, customer_id, author_id):
    model = Project(name=project_name,
                    customer_id=customer_id,
                    author_id=author_id)
    session.add(model)
    return model

def add_time_entry(session, description):
    model = TimeEntry(description=description)
    session.add(model)
    return model

def add_role(session, name):
    model = Role(name=name)
    session.add(model)
    return model

def populate_time_entries(session, users, projects, all_tickets):
    for author in users:
        date = datetime.date.today() - datetime.timedelta(days=365*3)
        te_num = 1

        g = lipsum.Generator()

        while date <= datetime.date.today():
            minutes = 8*60
            while minutes > 0:

                te_duration = random.choice([5, 10, 15, 20, 25, 30, 60, 90, 120, 180, 200, 240, 480])
                if te_duration > minutes:
                    te_duration = minutes

                minutes -= te_duration

                description = '%s.%d: %s' % (author.id, te_num, g.generate_sentence())

                te = add_time_entry(session, description=description)
                te.hours = datetime.timedelta(minutes=te_duration)
                te_num += 1
                te.date = date
                te.project_id = random.choice(projects).id

                if random.random()<0.96:
                    te.ticket = random.choice(all_tickets[te.project_id]).id
                else:
                    # once in a while, a time entry has no ticket
                    te.ticket = None

                te.author_id = author.id
            date += datetime.timedelta(days=1)


def populate_dummies(settings=None):
    from penelope.core.models.dbsession import DBSession
    from penelope.core.models import Base

    if settings:
        engine = engine_from_config(settings, 'sa.dashboard.')
        DBSession.configure(bind=engine)
        Base.metadata.bind = engine

    Base.metadata.create_all()

    with transaction.manager:
        session = DBSession()
        users = [
            add_user(session, u'admin@example.com', fullname='Administrator', password='admin@example.com'),
        ]

        role_admin = add_role(session, 'administrator')
        role_admin.users.append(users[0])

        add_role(session, 'external_developer')
        add_role(session, 'internal_developer')
        add_role(session, 'secretary')
        add_role(session, 'customer')
        add_role(session, 'project_manager')

        session.add(GlobalConfig(id=1))
