import unittest2
import transaction

from pyramid import testing
from pyramid_mailer.mailer import DummyMailer
from pyramid_mailer.interfaces import IMailer

from penelope.core import messages
from penelope.core.models.dashboard import User, PasswordResetToken
from penelope.core.models import DBSession


class Request(testing.DummyRequest):
    """just for testing"""

    def __init__(self, **kwargs):
        self.msgs = messages.Messages()
        testing.DummyRequest.__init__(self, **kwargs)
        mailer = DummyMailer()
        self.registry.registerUtility(mailer, IMailer)

    def add_message(self, *args, **kwargs):
        self.msgs.add(*args, **kwargs)


class TestSecurity(unittest2.TestCase):

    def test_password_reset_for_no_user(self):
        from penelope.core.security.views import password_reset 
        request = Request(params={'email':u'notexistinguser'})
        self.assertFalse(password_reset(request)['token'])

    def add_user(self, email):
        session = DBSession()
        user = User(email=email)
        session.add(user)
        transaction.commit()

    def generate_token(self, email):
        from penelope.core.security.views import password_reset 
        request = Request(params={'email':email})
        return password_reset(request)

    def test_autoregister(self):
        from penelope.core.security.views import autoregister

        profile = {'emails': [u'user0@dummy.it'],
                   'displayName': u'user0',
                   'accounts': [{'username': u'user0'}]}
        user = autoregister(profile)
        self.assertEqual(user.email, 'user0@dummy.it')

    def test_password_reset_for_existing_user(self):
        email = u'user1@dummy.it'
        self.add_user(email)
        self.assertTrue(self.generate_token(email)['token'])

    def test_token_store(self):
        email = u'user2@dummy.it'
        self.add_user(email)
        token = self.generate_token(email)['token']
        session = DBSession()
        self.assertEqual(session.query(PasswordResetToken).filter_by(token=token).one().user.email, email)

    def test_token_password_change_wrong_token(self):
        from penelope.core.security.views import change_password
        request = Request(method='POST', params={'token': u'notexistingtoken',
                                                 'password': 'topsecret',
                                                 'password_repeat': 'topsecret'})
        response = change_password(request)
        self.assertEqual(response['request'].msgs[0].message, u'Token doesn\'t exist.')

    def test_token_password_change_missmatch(self):
        email = u'user5@dummy.it'
        self.add_user(email)
        token = self.generate_token(email)['token']
        from penelope.core.security.views import change_password
        request = Request(method='POST', params={'token': token,
                                                 'password': 'thisisverylong',
                                                 'password_repeat': 'missmatch'})
        response = change_password(request)
        self.assertEqual(response['request'].msgs[0].message, u'Passwords missmatch.')


    def test_token_store_cleanup(self):
        email = u'user6@dummy.it'
        self.add_user(email)
        self.generate_token(email)['token']
        token2 = self.generate_token(email)['token']
        session = DBSession()
        self.assertEqual(len(session.query(PasswordResetToken).join(User).filter(User.email == email).all()),1)
        from penelope.core.security.views import change_password
        request = Request(method='POST', params={'token': token2,
                                                 'password': 'topsecret',
                                                 'password_repeat': 'topsecret'})
        response = change_password(request)
        self.assertEqual(response.headers.get('Location'),'/login_form')
        self.assertEqual(len(session.query(PasswordResetToken).join(User).filter(User.email == email).all()),0)

    def test_password_set(self):
        email = u'user7@dummy.it'
        self.add_user(email)
        session = DBSession()
        self.assertEqual(session.query(User).filter_by(email=email).one().password, None)
        token = self.generate_token(email)['token']
        from penelope.core.security.views import change_password
        request = Request(method='POST', params={'token': token,
                                                 'password': 'topsecret',
                                                 'password_repeat': 'topsecret'})
        response = change_password(request)
        self.assertEqual(response.headers.get('Location'),'/login_form')
        self.assertNotEqual(session.query(User).filter_by(email=email).one().password, None)



if __name__ == '__main__':
    unittest2.main()
