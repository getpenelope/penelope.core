import string

from pyramid.httpexceptions import HTTPForbidden
from pyramid.httpexceptions import HTTPFound
from pyramid.i18n import TranslationStringFactory
from pyramid.security import authenticated_userid
from pyramid.security import remember, forget
from pyramid.view import view_config
from pyramid_skins import SkinObject
from random import choice
from sqlalchemy.orm.exc import NoResultFound
from uuid import uuid4

from penelope.core.models import DBSession
from penelope.core.models.dashboard import User, PasswordResetToken
from penelope.core.notifications import notify_with_password_reset

_ = TranslationStringFactory('penelope')


def autoregister(profile):
    session = DBSession()
    chars = string.letters + string.digits
    password = ''.join(choice(chars) for _ in range(9))
    user = User(fullname = profile.get('displayName'),
                email = profile.get('emails')[0])
    user.set_password(password)
    user.add_openid(profile.get('accounts')[0].get('username'))
    session.add(user)
    return user


def forbidden(context, request, *challenge_args):
    if authenticated_userid(request):
        result =  {'context':context,
                   'request':request}
        return result
    else:
        return HTTPForbidden()


@view_config(context='velruse.api.AuthenticationComplete')
def login(context, request):
    headers={}
    emails = context.profile.get('emails')
    if emails:
        try:
            user = DBSession.query(User).filter(User.email.in_(emails)).one()
        except NoResultFound: #we are in a proper domain - we don't have a user
            user = autoregister(context.profile)
        if not user.active:
            raise HTTPForbidden()
        headers = remember(request, str(user.login))
    return login_success(context, request, headers=headers)


@view_config(name='login_success',permission='view_anon')
def login_success(context, request, headers=None):
    location= request.session.get('came_from')
    if not location or 'favicon' in location:
        location = '/'
    return HTTPFound(location=location, headers=headers)


@view_config(name='logout', permission='view_anon')
def logout(request):
    headers = forget(request)
    request.add_message(_(u'You have been loggout.'),'success')
    return HTTPFound(location='/', headers=headers)


@view_config(name='login_form', renderer='skin', permission='view_anon')
def login_form(context, request):
    """ Return login_form """
    came_from = '/'
    request.session['came_from'] = came_from
    if request.params.get('came_from') and not 'log' in request.params.get('came_from'):
        came_from = request.params.get('came_from')
        request.session['came_from'] = came_from 
    return {'context':context,
            'came_from': came_from,
            'request':request}


@view_config(name='password_reset_form', renderer='skin', permission='view_anon')
def password_reset_form(request):
    return {'request': request}


@view_config(name='password_reset', request_method='POST', renderer='skin', permission='view_anon')
def password_reset(request):
    email = request.params.get('email')
    try:
        session = DBSession()
        user = DBSession.query(User).filter_by(email=email).one()
        ptoken = DBSession.query(PasswordResetToken).get(user.id)
        if not ptoken:
            ptoken = PasswordResetToken(user_id=user.id)
        token = str(uuid4())
        ptoken.token = token 
        session.add(ptoken)
    except NoResultFound:
        token = None

    if token:
        settings = request.registry.settings
        if not settings:
            return {'request': request, 'token': token}
        notify_with_password_reset(email, token)

    return {'request': request, 'token': token}


@view_config(name='change_password', permission='view_anon', request_method='GET', request_param='token')
def change_password_form(context, request):
    token = request.params.get('token')
    return SkinObject('change_password')(request=request, token=token, context=context)


@view_config(name='change_password', renderer='skin', permission='view_anon', request_method='POST', request_param='token')
def change_password(request):
    session = DBSession()
    token = request.params.get('token')
    ptoken = session.query(PasswordResetToken).filter_by(token=token).first()
    password = request.params.get('password')
    repeat = request.params.get('password_repeat')

    if not ptoken:
        request.add_message(_(u'Token doesn\'t exist.'), type='danger')
    elif password != repeat:
        request.add_message(_(u'Passwords missmatch.'), type='danger')
    elif not password or not repeat:
        request.add_message(_(u'Missing password.'), type='danger')
    elif len(password)<6:
        request.add_message(_(u'Password too short. It needs to be at least 6 characters long.'), type='danger')
    else:
        ptoken.user.set_password(password)
        session.delete(ptoken)
        request.add_message(_(u'Password changed.'), type='success')
        return HTTPFound(location='/login_form')
    return {'request': request, 'token': token}
