# -*- coding: utf-8 -*-

from copy import deepcopy

from zope.component import getMultiAdapter
from pyramid.httpexceptions import HTTPFound

from fa.bootstrap import actions

from penelope.core.interfaces import IApplicationView
from penelope.core.lib.helpers import unicodelower
from penelope.core.forms import ModelView
from penelope.core.models import DBSession
from penelope.core.models.dashboard import Role, ApplicationACL



def configurate(config):
    #custom view for application
    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='view',
                                  name='',
                                  attr='show',
                                  model='penelope.core.models.dashboard.Application',
                                  renderer='penelope.core.forms:templates/application_show.pt',
                                  view=ApplicationModelView)

    config.formalchemy_model_view('admin',
        request_method='POST',
        permission='delete',
        name='delete',
        attr='delete',
        renderer='fa.bootstrap:templates/admin/edit.pt',
        model='penelope.core.models.dashboard.Application',
        view=ApplicationModelView)

    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='edit',
                                  name='security',
                                  attr='security',
                                  model='penelope.core.models.dashboard.Application',
                                  renderer='penelope.core.forms:templates/application_acl.pt',
                                  view=ApplicationModelView)

    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='edit',
                                  name='security_edit',
                                  attr='security_edit',
                                  model='penelope.core.models.dashboard.Application',
                                  renderer='penelope.core.forms:templates/application_acl.pt',
                                  view=ApplicationModelView)

    config.formalchemy_model_view('admin',
                                  request_method='POST',
                                  permission='edit',
                                  name='security_save',
                                  attr='security_save',
                                  model='penelope.core.models.dashboard.Application',
                                  renderer='penelope.core.forms:templates/application_acl.pt',
                                  view=ApplicationModelView)



app_tabs = actions.TabsActions(actions.TabAction("show",
                                                 content="View",
                                                 permission='view',
                                                 attrs=dict(href="request.fa_url(request.model_name, request.model_id, '')")),
                               actions.TabAction("security",
                                                 content="Security",
                                                 permission='edit',
                                                 attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'security')")))


security_edit = actions.UIButton(id='security_edit',
                                 content='Edit',
                                 permission='edit',
                                 _class='btn btn-info',
                                 attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'security_edit')"))

security_save = actions.UIButton(id='security_save',
                                 content='Save',
                                 permission='edit',
                                 _class='btn btn-success',
                                 attrs=dict(onclick="jQuery(this).parents('form').submit();"))

security_cancel = actions.UIButton(id='security_cancel',
                                   content='Cancel',
                                   permission='edit',
                                   _class='btn',
                                   attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'security')"))


class ApplicationModelView(ModelView):
    """Customizations"""
    actions_categories = ('buttons', 'tabs')
    defaults_actions = deepcopy(actions.defaults_actions)
    defaults_actions['show_tabs'] = app_tabs

    acl_permission_names = ['view', 'edit']

    acl_disabled = [
                (('project_manager', 'view'), (True, True)),
                (('project_manager', 'edit'), (True, True))
            ]


    @actions.action()
    def show(self):
        context = self.context.get_instance()
        result = super(ApplicationModelView, self).show()
        renderer = getMultiAdapter((context, self.context, self.request), IApplicationView)
        result.update(renderer.render())
        return self.render(**result)


    def _security_result(self):
        context = self.context.get_instance()
        result = super(ApplicationModelView, self).show()
        renderer = getMultiAdapter((context, self.context, self.request), IApplicationView)
        result.update(renderer.render())
        roles = sorted(DBSession.query(Role).filter(Role.id!='administrator'), key=unicodelower)
        result['roles'] = roles
        result['permission_names'] = self.acl_permission_names

        result['acl'] = dict(self.acl_disabled)
        for acl in context.acl:
            result['acl'][(acl.role.id, acl.permission_name)] = (True, False)
        return result


    @actions.action()
    def security(self):
        result = self._security_result()
        result['actions']['buttons'] = actions.Actions(security_edit)
        result['form_editing'] = False
        return self.render(**result)


    @actions.action()
    def security_edit(self):
        result = self._security_result()
        result['actions']['buttons'] = actions.Actions(security_save, security_cancel)
        result['form_editing'] = True
        return self.render(**result)


    @actions.action()
    def security_save(self):
        context = self.context.get_instance()

        for acl in context.acl:
            DBSession.delete(acl)

        for checkbox_name in self.request.POST:
            role_id, permission_name = checkbox_name.split('.')
            acl = ApplicationACL(application_id=context.id,
                                 role_id=role_id,
                                 permission_name=permission_name)
            DBSession.add(acl)

        request = self.request
        return HTTPFound(location=request.fa_url(request.model_name, request.model_id, 'security'))

    def delete(self):
        """
        For Application we are always forcing to delete.
        No additional validation
        """
        return self.force_delete()


