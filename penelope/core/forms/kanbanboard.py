# -*- coding: utf-8 -*-
import transaction

from copy import deepcopy
from fa.bootstrap import actions as factions
from json import loads, dumps
from pyramid.httpexceptions import HTTPFound
from pyramid_formalchemy import actions

from penelope.core.forms import ModelView
from penelope.core.fanstatic_resources import kanban
from penelope.core.models.dashboard import Trac, Project, KanbanBoard, CustomerRequest
from penelope.core.models import DBSession


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
            permission='view',
            name='get_backlog.json',
            renderer='json',
            attr='get_backlog',
            model='penelope.core.models.dashboard.KanbanBoard',
            view=KanbanBoardModelView)

    config.formalchemy_model_view('admin',
            request_method='GET',
            permission='view',
            name='get_columns.json',
            renderer='json',
            attr='get_columns',
            model='penelope.core.models.dashboard.KanbanBoard',
            view=KanbanBoardModelView)

    config.formalchemy_model_view('admin',
            request_method='POST',
            permission='edit',
            name='post_columns.json',
            renderer='json',
            attr='post_columns',
            model='penelope.core.models.dashboard.KanbanBoard',
            view=KanbanBoardModelView)

    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='edit',
                                  name='security',
                                  attr='security',
                                  model='penelope.core.models.dashboard.KanbanBoard',
                                  renderer='penelope.core.forms:templates/kanbanboard_acl.pt',
                                  view=KanbanBoardModelView)

    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='edit',
                                  name='security_edit',
                                  attr='security_edit',
                                  model='penelope.core.models.dashboard.KanbanBoard',
                                  renderer='penelope.core.forms:templates/kanbanboard_acl.pt',
                                  view=KanbanBoardModelView)

    config.formalchemy_model_view('admin',
                                  request_method='POST',
                                  permission='edit',
                                  name='security_save',
                                  attr='security_save',
                                  model='penelope.core.models.dashboard.KanbanBoard',
                                  renderer='penelope.core.forms:templates/kanbanboard_acl.pt',
                                  view=KanbanBoardModelView)

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

    def find_tickets(self):
        board = self.context.get_instance()
        viewable_projects = board.projects or self.request.filter_viewables(DBSession.query(Project).filter(Project.active).order_by('name'))
        viewable_project_ids = [p.id for p in viewable_projects]
        all_tracs = DBSession.query(Trac).join(Project).filter(Project.active).filter(Trac.project_id.in_(viewable_project_ids))
        where =  board.board_query or "owner='%s' AND status!='closed'" % self.request.authenticated_user.email
        query = """SELECT DISTINCT '%(trac)s' AS trac_name,
                                   '%(project)s' AS project,
                                   '%(customer)s' AS customer,
                                   ticket.id AS id,
                                   ticket.summary AS summary,
                                   ticket.priority AS priority,
                                   ticket.owner AS owner,
                                   custom.value AS customerrequest
                                   FROM "trac_%(trac)s".ticket AS ticket
                                   JOIN "trac_%(trac)s".ticket_custom AS custom ON ticket.id=custom.ticket AND custom.name='customerrequest'
                                   WHERE %(where)s"""
        queries = []
        for trac in all_tracs:
            queries.append(query % {'trac': trac.trac_name,
                                    'project': trac.project.name,
                                    'customer': trac.project.customer.name,
                                    'where': where})
        sql = '\nUNION '.join(queries)
        sql += ';'
        tracs =  DBSession().execute(sql).fetchall()
        return tracs

    def get_backlog(self):
        """
        Get backlog from trac query
        """
        board = self.context.get_instance()
        try:
            boards = loads(board.json)
        except (ValueError, TypeError):
            boards = []
        existing_tickets = [[b['id'] for b in a['tasks'] if b.get('id')] for a in boards]
        existing_tickets = [item for sublist in existing_tickets for item in sublist]
        crs = dict(DBSession().query(CustomerRequest.id, CustomerRequest.name))

        limit = 50
        tasks = []
        for n, ticket in enumerate(self.find_tickets()):
            if n > limit:
                break
            ticket_id = '%s_%s' % (ticket.trac_name, ticket.id)
            if ticket_id not in existing_tickets:
                tasks.append({'id': ticket_id,
                              'project': ticket.project,
                              'customer': ticket.customer,
                              'url': '%s/trac/%s/ticket/%s' % (self.request.application_url,
                                                               ticket.trac_name,
                                                               ticket.id),
                              'ticket': ticket.id,
                              'owner': ticket.owner,
                              'customerrequest': crs.get(ticket.customerrequest,''),
                              'priority': ticket.priority in ['critical', 'blocker'] and 'true' or None,
                              'summary': ticket.summary})

        return tasks

    def get_columns(self):
        """
        Get columns from board json.
        """
        board = self.context.get_instance()
        try:
            boards = loads(board.json)
        except (ValueError, TypeError):
            boards = []

        return boards

    def post_columns(self):
        """
        Update board with json
        """
        data = loads(self.request.body)
        # cleanup data - make sure we will not save empty tasks
        for col in data:
            to_remove = []
            for n, task in enumerate(col['tasks']):
                if not 'id' in task:
                    to_remove.append(n)
            to_remove.reverse()
            for n in to_remove:
                col['tasks'].pop(n)

        with transaction.manager:
            board = self.context.get_instance()
            board.json = dumps(data)
        return 'OK'

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
