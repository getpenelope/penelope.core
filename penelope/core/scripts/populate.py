import os
import sys
import transaction
import base64
import beaker

from sqlalchemy import engine_from_config
from pyramid.paster import setup_logging, bootstrap

from penelope.core.models.dbsession import DBSession
from penelope.core.models import Base
from penelope.core.models.scripts import add_user, add_role
from penelope.core.models.dashboard import GlobalConfig


beaker.cache.cache_regions.update(dict(calculate_matrix={'key_length':''}))


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd)) 
    sys.exit(1)

def main(argv=sys.argv):
    if len(argv) != 2:
        usage(argv)

    config_uri = argv[1]
    setup_logging(config_uri)
    env = bootstrap('%s#dashboard'% config_uri)
    settings = env.get('registry').settings
    engine = engine_from_config(settings, 'sa.dashboard.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all()

    def generate_password():
        return base64.urlsafe_b64encode(os.urandom(30))

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
