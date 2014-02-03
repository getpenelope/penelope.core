# -*- coding: utf-8 -*-

import deform
import colander
from copy import deepcopy
from deform import ValidationFailure
from deform.widget import SequenceWidget
from deform_bootstrap.widget import ChosenSingleWidget
from fa.bootstrap import actions as factions
from pyramid.httpexceptions import HTTPFound
from pyramid.renderers import get_renderer
from pyramid_formalchemy import actions

from penelope.core.forms import ModelView
from penelope.core.fanstatic_resources import kanban
from penelope.core.models.dashboard import KanbanBoard, User, Role, KanbanACL
from penelope.core.models import DBSession
from penelope.core.lib.widgets import SubmitButton, ResetButton, WizardForm
from penelope.core.fanstatic_resources import wizard as security_fanstatic


def configurate(config):
    config.formalchemy_model_view('admin',
            request_method='GET',
            permission='view',
            name='',
            attr='show',
            renderer='penelope.core.forms:templates/kanbanboard.pt',
            model='penelope.core.models.dashboard.KanbanBoard',
            view=KanbanBoardModelView)

    config.formalchemy_model_view('admin',
            request_method='GET',
            permission='listing',
            attr='listing',
            context='pyramid_formalchemy.resources.ModelListing',
            renderer='pyramid_formalchemy:templates/admin/listing.pt',
            model='penelope.core.models.dashboard.KanbanBoard',
            view=KanbanBoardModelView)

    config.formalchemy_model_view('admin',
            request_method='POST',
            permission='delete',
            name='delete',
            attr='delete',
            renderer='fa.bootstrap:templates/admin/edit.pt',
            model='penelope.core.models.dashboard.KanbanBoard',
            view=KanbanBoardModelView)

    config.formalchemy_model_view('admin',
            request_method='GET',
            permission='edit',
            name='security',
            attr='render',
            model='penelope.core.models.dashboard.KanbanBoard',
            renderer='penelope.core.forms:templates/kanbanboard_acl.pt',
            view=SecurityForm)

    config.formalchemy_model_view('admin',
            request_method='POST',
            permission='edit',
            name='security',
            attr='render',
            model='penelope.core.models.dashboard.KanbanBoard',
            renderer='penelope.core.forms:templates/kanbanboard_acl.pt',
            view=SecurityForm)

add_column = factions.UIButton(id='add_col',
            content='Add column',
            permission='edit',
            _class='btn btn-primary',
            attrs={'href':"'#'",
                   'ng-click': "'addColumn()'",})

security = factions.UIButton(id='remove_col',
            content='Security',
            permission='edit',
            _class='btn btn-inverse',
            attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'security')"))

security_edit = factions.UIButton(id='security_edit',
        content='Edit',
        permission='edit',
        _class='btn btn-info',
        attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'security_edit')"))

security_save = factions.UIButton(id='security_save',
        content='Save',
        permission='edit',
        _class='btn btn-success',
        attrs=dict(onclick="jQuery(this).parents('form').submit();"))

security_cancel = factions.UIButton(id='security_cancel',
        content='Cancel',
        permission='edit',
        _class='btn',
        attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'security')"))


class KanbanBoardModelView(ModelView):
    actions_categories = ('buttons',)
    defaults_actions = deepcopy(factions.defaults_actions)
    defaults_actions['show_buttons'] = factions.Actions(add_column, factions.edit, security)

    acl_permission_names = ['view', 'edit']

    @actions.action()
    def show(self):
        kanban.need()
        draggable = {}
        if self.request.has_permission('edit', self.context.get_instance()):
            draggable['ui-sortable'] = 'sortableOptions'
        return self.render(draggable=draggable)

    def delete(self):
        """
        For Application we are always forcing to delete.
        No additional validation
        """
        return self.force_delete()

    def _security_result(self):
        context = self.context.get_instance()
        result = super(KanbanBoardModelView, self).show()
        result['principals'] = context.acl.principals
        result['permission_names'] = self.acl_permission_names

        result['acl'] = dict()
        for acl in context.acl.principals:
            result['acl'][(acl.principal, acl.permission_name)] = True
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
            principal, permission_name = checkbox_name.split('.')
            acl = KanbanBoard(board_id=context.id,
                    principal=principal,
                    permission_name=permission_name)
            DBSession.add(acl)

        request = self.request
        return HTTPFound(location=request.fa_url(request.model_name, request.model_id, 'security'))


permissions = (
        ('view', 'View'),
        ('edit', 'Edit'),
        )

class PrincipalSchema(colander.Schema):
    name = colander.SchemaNode(colander.String(),
            widget=ChosenSingleWidget(),
            missing=colander.required,
            title=u'')

    permission = colander.SchemaNode(colander.Set(),
            widget=deform.widget.CheckboxChoiceWidget(values=permissions),
            missing=colander.required,
            title=u'')


class PrincipalsSchema(colander.SequenceSchema):
    principal = PrincipalSchema()


class SecuritySchema(colander.Schema):
    principals = PrincipalsSchema()


class SecurityForm(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def render(self):
        result = {}
        result['main_template'] = get_renderer(
                'penelope.core:skins/main_template.pt').implementation()
        result['main'] = get_renderer(
                'penelope.core.forms:templates/master.pt').implementation()

        schema = SecuritySchema().clone()
        security_fanstatic.need()

        form = WizardForm(schema,
                action=self.request.current_route_url(),
                formid='wizard',
                method='POST',
                buttons=[
                    SubmitButton(title=u'Submit'),
                    ResetButton(title=u'Reset'),
                    ])

        form['principals'].widget = SequenceWidget()

        users = DBSession.query(User).order_by(User.fullname)
        roles = DBSession.query(Role).order_by(Role.name)

        form['principals']['principal']['name'].widget.values = [('', '')] + \
                [('role:%s' % role.id, role.name) for role in roles] +\
                [(str(u.login), u.fullname) for u in users]

        controls = self.request.POST.items()
        if controls != []:
            try:
                appstruct = form.validate(controls)
                self.handle_save(form, appstruct)
            except ValidationFailure as e:
                result['form'] = e.render()
                return result

        appstruct = {'principals': []}
        principals = {}
        board = self.context.get_instance()
        for acl in board.acl:
           principals.setdefault(acl.principal, set())
           principals[acl.principal].add(acl.permission_name)

        for k,v in principals.items():
            appstruct['principals'].append({'name': k,
                                            'permission': v})

        result['form'] = form.render(appstruct=appstruct)
        return result

    def handle_save(self, form, appstruct):
        board = self.context.get_instance()

        for acl in board.acl:
            DBSession.delete(acl)

        for principal in appstruct['principals']:
            for permission in principal['permission']:
                acl = KanbanACL(principal=principal['name'],
                                permission_name=permission)
                board.acl.append(acl)

        raise HTTPFound(location=self.request.fa_url('KanbanBoard', board.id))
