# -*- coding: utf-8 -*-
import transaction

from json import loads, dumps
from copy import deepcopy
from pyramid_formalchemy import actions
from fa.bootstrap import actions as factions
from penelope.core.forms import ModelView
from penelope.core.fanstatic_resources import kanban
from penelope.core.models.dashboard import Trac, Project
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
            name='get_board_data.json',
            attr='get_board_data',
            renderer='json',
            model='penelope.core.models.dashboard.KanbanBoard',
            view=KanbanBoardModelView)

    config.formalchemy_model_view('admin',
            request_method='POST',
            permission='edit',
            name='set_board_data.json',
            attr='set_board_data',
            renderer='json',
            model='penelope.core.models.dashboard.KanbanBoard',
            view=KanbanBoardModelView)

    config.formalchemy_model_view('admin',
            request_method='GET',
            permission='view',
            name='get_tickets.json',
            renderer='json',
            attr='get_tickets',
            model='penelope.core.models.dashboard.KanbanBoard',
            view=KanbanBoardModelView)

    config.formalchemy_model_view('admin',
            request_method='POST',
            permission='edit',
            name='post_tickets.json',
            renderer='json',
            attr='post_tickets',
            model='penelope.core.models.dashboard.KanbanBoard',
            view=KanbanBoardModelView)

add_column = factions.UIButton(id='add_col',
            content='Add column',
            permission='view',
            _class='btn btn-primary',
            attrs={'href':"'#'",
                   'ng-click': "'addColumn()'",})

remove_column = factions.UIButton(id='remove_col',
            content='Remove column',
            permission='view',
            _class='btn btn-danger',
            attrs={'href':"'#'",
                   'ng-click': "'removeColumn()'",})


def find_tickets(request):
    all_tracs = DBSession.query(Trac).join(Project).filter(Project.active)
    query = """SELECT DISTINCT '%(trac)s' AS trac_name, '%(project)s' as project, id AS ticket, summary  FROM "trac_%(trac)s".ticket WHERE owner='%(email)s' AND status!='closed'"""
    queries = []
    for trac in all_tracs:
        queries.append(query % {'trac': trac.trac_name,
                                'project': trac.project,
                                'email': request.authenticated_user.email})
    sql = '\nUNION '.join(queries)
    sql += ';'
    tracs =  DBSession().execute(sql).fetchall()
    return tracs


class KanbanBoardModelView(ModelView):
    actions_categories = ('buttons',)
    defaults_actions = deepcopy(factions.defaults_actions)
    defaults_actions['show_buttons'] = factions.Actions(factions.edit, add_column)#, remove_column)

    @actions.action()
    def show(self):
        kanban.need()
        return super(KanbanBoardModelView, self).show()

    def delete(self):
        """
        For Application we are always forcing to delete.
        No additional validation
        """
        return self.force_delete()

    def get_tickets(self):
        """
        Get tickets from board and add backlog.
        """
        board = self.context.get_instance()
        try:
            boards = loads(board.json)
        except (ValueError, TypeError):
            boards = []

        existing_tickets = [[b['id'] for b in a['tasks'] if b.get('id')] for a in boards]
        existing_tickets = [item for sublist in existing_tickets for item in sublist]

        backlog = {'title': 'Backlog',
                   'wip': 0,
                   'tasks': []}

        limit = 10
        for n, ticket in enumerate(find_tickets(self.request)):
            if n > limit:
                break
            ticket_id = '%s_%s' % (ticket.trac_name, ticket.ticket)
            if ticket_id not in existing_tickets:
                backlog['tasks'].append({'id': ticket_id,
                                         'project': ticket.project,
                                         'url': '%s/trac/%s/ticket/%s' % (self.request.application_url,
                                                                          ticket.trac_name,
                                                                          ticket.ticket),
                                         'ticket': ticket.ticket,
                                         'summary': ticket.summary})

        boards.insert(0, backlog)
        return boards

    def post_tickets(self):
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
