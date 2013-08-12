import zope.interface

from repoze.who.interfaces import IChallengeDecider
from repoze.who.plugins.friendlyform import FriendlyFormPlugin as BasePlugin


def challenge_decider(environ, status, headers):
    return status.startswith('403') or status.startswith('401')
zope.interface.directlyProvides(challenge_decider, IChallengeDecider)


class FriendlyFormPlugin(BasePlugin):
    def _get_full_path(self, path, environ):
        """
        Return the full path to ``path`` by prepending the SCRIPT_NAME.
        If ``path`` is a URL, do nothing.
        BBB: If ``path`` start with double /, do nothing
        """
        if path.startswith('//'):
            path = path[1:]
        elif path.startswith('/'):
            path = environ.get('SCRIPT_NAME', '') + path
        return path


def make_plugin(login_form_url, login_handler_path, logout_handler_path,
                rememberer_name, post_login_url=None, post_logout_url=None,
                login_counter_name=None):

    if login_form_url is None:
        raise ValueError(
            'must include login_form_url in configuration')
    if login_handler_path is None:
        raise ValueError(
            'login_handler_path must not be None')
    if logout_handler_path is None:
        raise ValueError(
            'logout_handler_path must not be None')
    if rememberer_name is None:
        raise ValueError(
            'must include rememberer key (name of another IIdentifier plugin)')

    plugin = FriendlyFormPlugin(login_form_url,
                                login_handler_path,
                                post_login_url,
                                logout_handler_path,
                                post_logout_url,
                                rememberer_name,
                                login_counter_name,
                                charset=None)
    return plugin


def rolefinder(identity, request):
    roles = set()
    user = request.authenticated_user or identity.get('user')
    if user and user.active:
        context = request.challenge_item or request.model_instance
        roles = set(['role:%s' % a for a in user.roles_in_context(context)])
    return roles
