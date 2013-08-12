import os
import sys
import transaction
import beaker
import csv

from sqlalchemy import engine_from_config
from pyramid.paster import get_appsettings, setup_logging

from penelope.core.models.dashboard import Project, Application, SVN
from penelope.core.models.dbsession import DBSession
from penelope.core.models import Base


beaker.cache.cache_regions.update(dict(calculate_matrix={}))


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri> <csv_import_file>\n'
          '(example: "%s development.ini import_svn.csv")' % (cmd, cmd)) 
    sys.exit(1)


def main(argv=sys.argv):
    if len(argv) != 3:
        usage(argv)
    config_uri = argv[1]
    svn_csv = argv[2]
    setup_logging(config_uri)
    settings = get_appsettings(config_uri, name='dashboard')
    engine = engine_from_config(settings, 'sa.dashboard.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all()

    with transaction.manager:
        session = DBSession()
        with open(svn_csv, 'rb') as csvfile:
            reader = csv.reader(csvfile)
            for project_id, svn_repo in reader:
                svn_repo = svn_repo.strip()
                project_id = project_id.strip()
                project = session.query(Project).get(project_id)
                app = Application(name='SVN',
                                  project_id=project_id,
                                  application_type=SVN,
                                  svn_name=svn_repo)
                project.add_application(app)
                print 'Creating svn app [%s] for project [%s]' % (svn_repo, project_id)
