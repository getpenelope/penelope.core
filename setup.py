import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = """penelope.core
=============

for more details visit: http://getpenelope.github.com/"""

CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = [
    'Babel',
    'Beaker',
    'bleach',
    'deform',
    'deform_bootstrap',
    'distribute',
    'fa.bootstrap',
    'feedparser',
    'gdata==2.0.14',
    'gevent-socketio',
    'gevent-psycopg2',
    'gspread',
    'js.chart',
    'js.jqgrid',
    'js.jquery_datatables==1.8.2',
    'js.jquery_timepicker_addon',
    'js.lesscss',
    'js.socketio',
    'js.xeditable',
    'jsonrpc',
    'lingua',
    'lorem-ipsum-generator',
    'lxml',
    'Paste',
    'PasteScript',
    'penelope.trac',
    'plone.i18n',
    'profilehooks',
    'psycopg2',
    'py-pretty',
    'pyramid',
    'pyramid_beaker',
    'pyramid_debugtoolbar',
    'pyramid_exclog',
    'pyramid_fanstatic',
    'pyramid_formalchemy',
    'pyramid_mailer',
    'pyramid_rpc',
    'pyramid_skins',
    'pyramid_zcml',
    'python-cjson',
    'python-dateutil==1.5',
    'python-openid>=2.0',
    'raven',
    'redis',
    'repoze.tm2>=1.0b1', # default_commit_veto
    'repoze.who-friendlyform',
    'repoze.who.plugins.sa',
    'repoze.who<1.9',
    'repoze.workflow',
    'setuptools',
    'sunburnt',
    'SQLAlchemy',
    'transaction',
    'Trac',
    'unittest2',
    'velruse',
    'WebError',
    'WebTest',
    'xlwt',
    'zope.interface',
    'zope.sqlalchemy',
    ]

tests_require = [
    'WebTest',
    'mock',
    'pyquery',
    'pytest',
    'pytest-cov',
    'pytest-pep8!=1.0.3',
    'pytest-xdist',
    'wsgi_intercept',
    'zope.testbrowser',
    'pyramid_robot'
    ]


setup(name='penelope.core',
      version='2.1.39',
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
      namespace_packages=['penelope'],
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='penelope.core',
      install_requires = requires,
      tests_require=tests_require,
      entry_points = """\
      [paste.app_factory]
      main = penelope.core:main

      [paste.filter_app_factory]
      raven = penelope.core.ravenlog:sentry_filter_factory

      [fanstatic.libraries]
      por = penelope.core.fanstatic_resources:por_library
      deform_library = penelope.core.fanstatic_resources:deform_library
      deform_bootstrap_library = penelope.core.fanstatic_resources:deform_bootstrap_library

      [console_scripts]
      populate_penelope = penelope.core.scripts.populate:main
      populate_with_dummies = penelope.core.scripts.dummies:main
      import_svn = penelope.core.scripts.importsvn:main
      quality_export = penelope.core.scripts.quality_export:main
      contracts_import = penelope.core.scripts.contracts_import:main
      """,
      extras_require={
        'test': tests_require,}
      )
