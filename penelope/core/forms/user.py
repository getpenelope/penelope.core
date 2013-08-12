# -*- coding: utf-8 -*-
from zope.interface import implements
from copy import deepcopy

from pyramid import httpexceptions as exc
from pyramid_formalchemy import resources
from fa.bootstrap import actions
from penelope.core.interfaces import IManageView
from penelope.core.forms import ModelView
from penelope.core.forms.renderers import ProjectRelationRenderer


def configurate(config):
    #custom view for user
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='view',
        name='',
        attr='show',
        renderer='penelope.core.forms:templates/user.pt',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)

    config.formalchemy_model_view('admin',
        request_method='POST',
        permission='delete',
        name='delete',
        attr='delete',
        renderer='fa.bootstrap:templates/admin/edit.pt',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)

    config.formalchemy_model_view('admin',
        renderer='penelope.core.forms:templates/user_listing.pt',
        attr='datatable',
        context=ModelListing,
        request_method='GET',
        permission='listing',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)

    #custom view for tokens section
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='edit',
        name='user_tokens',
        attr='user_tokens',
        renderer='penelope.core.forms:templates/user_tokens.pt',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)


user_tabs = actions.Actions(actions.TabAction("show",
    content="View",
    permission='view',
    attrs=dict(href="request.fa_url(request.model_name, request.model_id, '')")),
    actions.TabAction("user_tokens",
        content="User tokens",
        permission='edit',
        attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'user_tokens')")), )


class ModelListing(resources.ModelListing):
    implements(IManageView)


class UserModelView(ModelView):
    actions_categories = ('buttons', 'tabs')

    defaults_actions = deepcopy(actions.defaults_actions)
    defaults_actions.update(show_tabs=user_tabs)
    defaults_actions.update(user_tokens_tabs=user_tabs)

    @actions.action('user_tokens')
    def user_tokens(self, *args, **kwargs):
        context = self.context.get_instance()
        return self.render(user=context)

    @actions.action('listing')
    def datatable(self, **kwargs):
        result = super(UserModelView, self).datatable(**kwargs)

        fs = result['fs']
        fs.configure(pk=False, readonly=True)

        columns = ['email', 'fullname', 'roles', 'project_manager', 'active']
        self.pick_columns(fs, columns)

        fs._render_fields['project_manager']._get_renderer = lambda: ProjectRelationRenderer(fs._render_fields['project_manager'])

        return dict(result,
                    columns=columns)

    def delete(self):
        user = self.context.get_instance()
        request = self.request
        if not user.active:
            request.add_message(u'User is already inactive. You cannot remove it.', type='danger')
            raise exc.HTTPFound(location=request.fa_url('User', user.id))
        else:
            user.active = False
            request.add_message(u'User deactivated.', type='success')
            raise exc.HTTPFound(location=request.fa_url('User', user.id))
