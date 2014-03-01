import os
import sys
import beaker

from pyramid.paster import setup_logging, bootstrap

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
    from penelope.core.scripts import populate_dummies
    populate_dummies(settings)
