from sqlalchemy import Column, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm import deferred
from sqlalchemy.ext.declarative import declared_attr
from datetime import datetime
from zope.interface import implements

from penelope.core.models.interfaces import IDublinCore
from pyramid.threadlocal import get_current_request


class DublinCore(object):
    """
    Base dublincore implementation for POR project
    """

    implements(IDublinCore)

    @declared_attr
    def creation_date(cls):
        return deferred(Column(DateTime), group='dublincore')

    @declared_attr
    def modification_date(cls):
        return deferred(Column(DateTime), group='dublincore')

    @declared_attr
    def author_id(cls):
        return deferred(Column(Integer, ForeignKey('users.id')), group='dublincore')

    @declared_attr
    def author(cls):
        return relationship('User', uselist=False, primaryjoin="%s.author_id==User.id" % cls.__name__)


def dublincore_insert(mapper, connection, target):
    target.creation_date = datetime.now()
    target.modification_date = datetime.now()

    #try to get author in gracemode:
    if hasattr(target, 'request'):
        request = target.request
    else:
        request = get_current_request()

    if request and not target.author_id:
        environ = request.environ
        if environ.has_key('repoze.who.identity'):
            if environ['repoze.who.identity'].has_key('user'):
                target.author_id = environ['repoze.who.identity']['user'].id


def dublincore_update(mapper, connection, target):
    target.modification_date = datetime.now()
