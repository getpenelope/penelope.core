import os
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = """penelope.core
=============

for more details visit: http://getpenelope.github.com/"""

CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = [
    'distribute',
    'pyramid',
    'transaction',
    'repoze.tm2>=1.0b1', # default_commit_veto
    'WebError',
    'WebTest',
    'pyramid_formalchemy',
    'pyramid_beaker',
    'pyramid_rpc',
    'pyramid_skins',
    'pyramid_debugtoolbar',
    'pyramid_zcml',
    'pyramid_exclog',
    'repoze.workflow',
    'python-cjson',
    'repoze.who.plugins.sa',
    'repoze.who-friendlyform',
    'repoze.who<1.9',
    'python-openid>=2.0',
    'zope.interface',
    'por.trac',
    'jsonrpc',
    'js.jquery_timepicker_addon',
    'js.jqgrid ',
    'fa.bootstrap',
    'xlwt',
    'deform',
    'feedparser',
    'Babel',
    'lingua',
    'profilehooks',
    'velruse',
    'pyramid_mailer',
    'pyramid_fanstatic',
    'js.lesscss',
    'deform_bootstrap',
    'Beaker',
    'js.jquery_datatables==1.8.2',
    'unittest2',
    'bleach',
    'raven',
    'sunburnt',
    'lxml'
    ]

setup(name='penelope.core',
      version='1.0.dev0',
      description='Penelope main package',
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        ],
      author='Penelope Team',
      author_email='penelopedev@redturtle.it',
      url='http://getpenelope.github.com',
      keywords='web wsgi bfg pylons pyramid',
      namespace_packages=['por'],
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='penelope.core',
      install_requires = requires,
      entry_points = """\
      [paste.app_factory]
      main = penelope.core:main
      [paste.filter_app_factory]
      raven = penelope.core.ravenlog:sentry_filter_factory
      [fanstatic.libraries]
      por = penelope.core.fanstatic_resources:por_library
      deform_library = penelope.core.fanstatic_resources:deform_library
      deform_bootstrap_library = penelope.core.fanstatic_resources:deform_bootstrap_library
      """,
      )
