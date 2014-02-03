from sqlalchemy import engine_from_config
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.declarative import declarative_base
from penelope.core.models.dbsession import DBSession

Base = declarative_base()


class classproperty(object):
    def __init__(self, getter):
        self.getter = getter

    def __get__(self, instance, owner):
        if instance:
            return self.getter(instance)
        else:
            return self.getter(owner)


from penelope.core.models.dashboard import Project, User, GlobalConfig, Role, OpenId,\
                                 PasswordResetToken, Application, CustomerRequest,\
                                 Estimation, Group, SavedQuery, Customer,\
                                 Contract, KanbanBoard, Cost, Activity

Project; User; GlobalConfig; PasswordResetToken; Role; SavedQuery
Application; Customer; CustomerRequest; Group; OpenId; Estimation; Contract
KanbanBoard; Cost; Activity

from penelope.core.models.tp import TimeEntry; TimeEntry
from penelope.trac import events; events


def includeme(config):
    if not config.registry.settings.get('test',False):
        initialize_sql(config)


def initialize_sql(config=None, engine=None):
    if not engine:
        engine = engine_from_config(config.registry.settings, 'sa.dashboard.', poolclass=NullPool)
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
