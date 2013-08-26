import transaction

from json import loads, dumps
from pyramid.response import Response
from pyramid.view import view_config
from socketio import socketio_manage
from socketio.namespace import BaseNamespace

from penelope.core.models.dashboard import KanbanBoard
from penelope.core.models.dashboard import Trac, Project, CustomerRequest
from penelope.core.models import DBSession


class BoardMixin(object):

    users_online = {}

    def __init__(self, *args, **kwargs):
        super(BoardMixin, self).__init__(*args, **kwargs)
        if 'boards' not in self.session:
            self.session['boards'] = set()

    def join(self, data):
        """Lets a user join a board on a specific Namespace."""
        self.session['boards'].add(self._get_board_name(data['board_id']))
        self.users_online.setdefault(self._get_board_name(data['board_id']), set()).add(data['email'])

    def leave(self, board, email):
        try:
            return self.users_online.get(self._get_board_name(board), set()).remove(email)
        except KeyError:
            pass

    def board_users(self, board):
        if not board:
            return set()
        return list(self.users_online.get(self._get_board_name(board), set()))

    def _get_board_name(self, board):
        return self.ns_name + '_' + board

    def emit_to_board(self, board, event, *args):
        """This is sent to all in the board (in this particular Namespace)"""
        pkt = dict(type="event",
                   name=event,
                   args=args,
                   endpoint=self.ns_name)
        board_name = self._get_board_name(board)
        for sessid, socket in self.socket.server.sockets.iteritems():
            if 'boards' not in socket.session:
                continue
            if board_name in socket.session['boards']:
                socket.send_packet(pkt)

    def emit_to_board_not_me(self, board, event, *args):
        """This is sent to all in the board (in this particular Namespace)"""
        pkt = dict(type="event",
                   name=event,
                   args=args,
                   endpoint=self.ns_name)
        board_name = self._get_board_name(board)
        for sessid, socket in self.socket.server.sockets.iteritems():
            if 'boards' not in socket.session:
                continue
            if board_name in socket.session['boards'] and self.socket != socket:
                socket.send_packet(pkt)


class KanbanNamespace(BaseNamespace, BoardMixin):

    @property
    def board(self):
        return self.session.get('board')

    @property
    def email(self):
        return self.session.get('email')

    def on_join(self, data):
        self.session['board'] = data['board_id']
        self.session['email'] = data['email']
        self.join(data)

        board = DBSession().query(KanbanBoard).get(self.board)
        try:
            boards = loads(board.json)
        except (ValueError, TypeError):
            boards = []
        self.emit_to_board(self.board, "columns", {"value": boards})
        self.emit_to_board(self.board, "emails", {"value": self.board_users(self.board)})

    def recv_disconnect(self):
        if self.board and self.email:
            self.leave(self.board, self.email)
            self.emit_to_board(self.board, "emails", {"value": self.board_users(self.board)})
        self.disconnect(silent=True)

    def on_board_changed(self, data):
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
            board = DBSession().query(KanbanBoard).get(self.board)
            board.json = dumps(data)
            self.emit_to_board_not_me(self.board, "columns", {"value": data})

    def on_get_backlog(self, data):
        board = DBSession().query(KanbanBoard).get(self.board)
        try:
            boards = loads(board.json)
        except (ValueError, TypeError):
            boards = []
        existing_tickets = [[b['id'] for b in a['tasks'] if b.get('id')] for a in boards]
        existing_tickets = [item for sublist in existing_tickets for item in sublist]
        crs = dict(DBSession().query(CustomerRequest.id, CustomerRequest.name))

        limit = 50
        tasks = []

        for n, ticket in enumerate(self.find_tickets(board)):
            if n > limit:
                break
            ticket_id = '%s_%s' % (ticket.trac_name, ticket.id)
            if ticket_id not in existing_tickets:
                try:
                    involved = set(ticket.involved.split(','))
                except AttributeError:
                    involved = set()

                involved.add(ticket.reporter)
                involved = involved.difference([ticket.owner])

                tasks.append({'id': ticket_id,
                              'project': ticket.project,
                              'customer': ticket.customer,
                              'involvedCollapsed': True,
                              'url': '%s/trac/%s/ticket/%s' % (self.request.application_url,
                                                               ticket.trac_name,
                                                               ticket.id),
                              'ticket': ticket.id,
                              'owner': ticket.owner,
                              'involved': list(involved),
                              'customerrequest': crs.get(ticket.customerrequest,''),
                              'priority': ticket.priority in ['critical', 'blocker'] and 'true' or None,
                              'summary': ticket.summary})
        self.emit("backlog", {"value": tasks})

    def find_tickets(self, board):
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
                                ticket.reporter as reporter,
                                customerrequest.value AS customerrequest,
                                string_agg(DISTINCT change.author,',') AS involved
                                FROM "trac_%(trac)s".ticket AS ticket
                                LEFT OUTER JOIN "trac_%(trac)s".ticket_custom AS customerrequest ON ticket.id=customerrequest.ticket AND customerrequest.name='customerrequest'
                                LEFT OUTER JOIN "trac_%(trac)s".ticket_custom AS probabilita ON ticket.id=probabilita.ticket AND probabilita.name='probabilita'
                                LEFT OUTER JOIN "trac_%(trac)s".ticket_change AS change ON ticket.id=change.ticket
                                WHERE %(where)s
                                GROUP BY ticket.id, customerrequest.value
                                """
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


@view_config(route_name="socketio")
def socketio(request):
    socketio_manage(request.environ, {"/kanban": KanbanNamespace}, request=request)
    return Response('')
