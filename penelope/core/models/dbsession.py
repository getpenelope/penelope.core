"""
The DBSession is made available to model classes outside of penelope.core.models.__init__
to help avoid circular imports.
"""

from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
