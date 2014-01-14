import mandrill

from pyramid.i18n import TranslationStringFactory
from pyramid.threadlocal import get_current_request
from pyramid.threadlocal import get_current_registry
from pyramid.view import view_config
from pyramid.response import Response

_ = TranslationStringFactory('penelope')


@view_config(route_name="inbound_email")
def inbound_email(request):
    return Response('OK')


def send(template_name, message):
    settings = get_current_registry().settings
    if not settings:
        return

    if not 'from_email' in message:
        message['from_email'] = settings['mail.default_sender']
        message['headers'] = {'Reply-To': settings['mail.default_sender']}

    mandrill_client = mandrill.Mandrill(settings['mail.password'])
    return mandrill_client.messages.send_template(template_name=template_name,
                                                  template_content=[],
                                                  message=message)


def notify_with_password_reset(email, token):
    request = get_current_request()
    if not request:
        return

    params = {"header": u'Password reset',
              "message": u'Please click on the link bellow to reset your penelope account\'s password.',
              "link": '%s/change_password?token=%s' % (request.application_url, token),
              "action": 'Reset password'}

    merged_params = []
    for k,v in params.items():
        merged_params.append({'name': k, 'content':v})

    message = {'auto_html': None,
               'auto_text': None,
               'from_name': 'RedTurtle Team',
               'important': True,
               'inline_css': True,
               'global_merge_vars': merged_params,
               'subject': u"Password reset request",
               'to': [{'email': email}]}

    return send('general', message)


def notify_user_with_welcoming_mail(email):
    request = get_current_request()
    if not request:
        return

    subject = _(u"Welcome to Penelope, Issue tracking system.")
    body = _(u"""Sei stato abilitato all'utilizzo di Penelope, la nostra piattaforma online di gestione dei progetti e dei "trouble ticket". Con Penelope potrai aprire nuovi ticket e seguire l'evoluzione delle tue segnalazioni. Ci raccomandiamo di verificare che i ticket che hai aperto abbiano la marcatura "Ticket Aperto dal Cliente = SI".
    <br/>
    Utilizzando questo link: %(url)s/password_reset_form?email=%(email)s potrai definire la tua nuova password di accesso a Penelope.
    RedTurtle ti ringrazia della collaborazione.
    <br/>
    <br/>
    You were enabled as a user of Penelope, our online projects and trouble ticket management platform. With penelope you will be able to open new tickets and follow the evolution of the issues you opened. We recommend to double check that the tickets you open have the "Ticked opened by customer" field set at "SI" (Yes).
    <br/>
    By this link: %(url)s/password_reset_form?email=%(email)s you can set your new Penelope password.
    RedTurtle thanks you for your collaboration.
    """ % {'email': email,
           'url' : request.application_url})

    params = {"header": subject,
              "message": body,
              "link": '%s/password_reset_form?email=%s' % (request.application_url, email),
              "action": 'Activate your account NOW!'}

    merged_params = []
    for k,v in params.items():
        merged_params.append({'name': k, 'content':v})

    message = {'auto_html': None,
               'auto_text': None,
               'from_name': 'RedTurtle Team',
               'important': True,
               'inline_css': True,
               'global_merge_vars': merged_params,
               'subject': subject,
               'to': [{'email': email}]}

    return send('general', message)
