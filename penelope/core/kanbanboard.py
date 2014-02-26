import transaction
import redis

from json import loads, dumps
from socketio.namespace import BaseNamespace
from penelope.core.models.dashboard import KanbanBoard, \
        BACKLOG_PRIORITY_ORDER, BACKLOG_MODIFICATION_ORDER
from penelope.core.models.dashboard import Trac, Project, CustomerRequest
from penelope.core.models import DBSession


class KanbanNamespace(BaseNamespace):

    users_online = {}

    def __init__(self, *args, **kwargs):
        super(KanbanNamespace, self).__init__(*args, **kwargs)
        if 'boards' not in self.session:
            self.session['boards'] = set()

    @property
    def board(self):
        return self.session.get('board')

    @property
    def email(self):
        return self.session.get('email')

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

    def board_channel(self):
        """Get redis pubsub channel key for given chat room."""
        return 'kanbanboard:boards:{n}'.format(n=self.board)

    def notify_redis(self, event, data, notify_me=True):
        r = redis.StrictRedis()
        msg = {'event': event,
               'sessid': self.socket.sessid,
               'data': data,
               'notify_me': notify_me}
        r.publish(self.board_channel(), dumps(msg))

    def _emit_to_board_(self, event, *args):
        """This is sent to all in the board (in this particular Namespace)"""
        pkt = dict(type="event",
                   name=event,
                   args=args,
                   endpoint=self.ns_name)
        return pkt, self._get_board_name(self.board)

    def emit_to_board(self, event, *args):
        pkt, board_name = self._emit_to_board_(event, *args)
        for sessid, socket in self.socket.server.sockets.iteritems():
            if 'boards' not in socket.session:
                continue
            if board_name in socket.session['boards']:
                socket.send_packet(pkt)

    def emit_to_board_not_me(self, event, *args):
        pkt, board_name = self._emit_to_board_(event, *args)
        for sessid, socket in self.socket.server.sockets.iteritems():
            if 'boards' not in socket.session:
                continue
            if board_name in socket.session['boards'] and self.socket != socket:
                socket.send_packet(pkt)

    def listener(self):
        r = redis.StrictRedis()
        r = r.pubsub()
        r.subscribe([self.board_channel(), '*'])

        for m in r.listen():
            if m['type'] == 'message':
                msg = loads(m['data'])
                sessid = msg.get('sessid', None)
                notify_me = msg.get('notify_me', True)
                if notify_me:
                    self.emit_to_board(msg['event'], msg['data'])
                elif not notify_me and self.socket.sessid == sessid:
                    self.emit_to_board_not_me(msg['event'], msg['data'])
                else:
                    continue # we don't want to notify myself

    def on_join(self, data):
        self.spawn(self.listener)
        self.session['board'] = data['board_id']
        self.session['email'] = data['email']
        self.join(data)
        self.notify_redis("connected", data['email'])

        board = DBSession().query(KanbanBoard).get(self.board)
        try:
            boards = loads(board.json)
        except (ValueError, TypeError):
            boards = []

        self.notify_redis("columns", {"value": boards})
        self.notify_redis("emails", {"value": self.board_users(self.board)})

    def recv_disconnect(self):
        if self.board and self.email:
            self.leave(self.board, self.email)
            self.notify_redis("emails", {"value": self.board_users(self.board)})
        self.disconnect(silent=True)

    def on_history(self, data):
        self.notify_redis("history", data, notify_me=False)

    def on_board_changed(self, data):
        # cleanup data - make sure we will not save empty tasks
        self.notify_redis("columns", {"value": data}, notify_me=False)

        for col in data:
            to_remove = []
            try:
                del col['$$hashKey'] # angular id that shouldn't be stored
            except KeyError:
                pass
            for n, task in enumerate(col['tasks']):
                if not task:
                    continue
                if not 'id' in task:
                    to_remove.append(n)
                try:
                    del task['$$hashKey'] # angular id that shouldn't be stored
                except KeyError:
                    pass
            to_remove.reverse()
            for n in to_remove:
                col['tasks'].pop(n)
        with transaction.manager:
            board = DBSession().query(KanbanBoard).get(self.board)
            board.json = dumps(data)

    def on_get_backlog(self, data):
        board = DBSession().query(KanbanBoard).get(self.board)
        try:
            boards = loads(board.json)
        except (ValueError, TypeError):
            boards = []
        existing_tickets = [[b['id'] for b in a['tasks'] if b and b.get('id')] for a in boards]
        existing_tickets = [item for sublist in existing_tickets for item in sublist]
        crs = dict(DBSession().query(CustomerRequest.id, CustomerRequest.name))

        backlog_tickets = [t for t in self.find_tickets(board) \
                                   if '%s#%s' % (t.trac_name, t.id) \
                                                      not in existing_tickets]

        if board.backlog_order == BACKLOG_PRIORITY_ORDER:
            priorities = {'blocker': 0,
                          'critical': 1,
                          'major': 2,
                          'minor': 3,
                          'trivial': 4}
            backlog_tickets.sort(key=lambda t: priorities[t.priority])

        elif board.backlog_order == BACKLOG_MODIFICATION_ORDER:
            backlog_tickets.sort(key=lambda t: t.modification, reverse=True)

        backlog_tickets = backlog_tickets[:board.backlog_limit]
        tasks = []

        for n, ticket in enumerate(backlog_tickets):
            ticket_id = '%s#%s' % (ticket.trac_name, ticket.id)
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
                          'priority': ticket.priority,
                          'summary': ticket.summary})
        self.emit("backlog", {"value": tasks})

    def viewable_tracs(self, board):
        all_tracs = DBSession().query(Trac)
        viewable_tracs = []

        if board.projects:
            for project in board.projects:
                for trac in project.tracs:
                    viewable_tracs.append(trac)
        else:
            # a list of tracs user can view:
            if not self.request.has_permission('manage', None):
                user_projects = [g.project for g in self.request.authenticated_user.groups]
                for project in user_projects:
                    for trac in project.tracs:
                        viewable_tracs.append(trac)
            else:
                viewable_tracs = all_tracs

        query = """SELECT DISTINCT '%(trac)s' AS trac_name
                   FROM "trac_%(trac)s".permission
                   WHERE username IN ('internal_developer', '%(user)s')"""

        queries = []
        for trac in viewable_tracs:
            queries.append(query % {'trac': trac.trac_name,
                                    'user': self.request.authenticated_user.email})
        sql = '\nUNION '.join(queries)
        sql += ';'
        return DBSession().execute(sql).fetchall()

    def find_tickets(self, board):
        viewable_tracs = [t.trac_name for t in self.viewable_tracs(board)]
        all_tracs = DBSession.query(Trac).join(Project).filter(Project.active).filter(Trac.trac_name.in_(viewable_tracs))
        if all_tracs.count() == 0:
            return []
        where =  board.backlog_query
        query = """SELECT DISTINCT '%(trac)s' AS trac_name,
                                '%(project)s' AS project,
                                '%(customer)s' AS customer,
                                ticket.id AS id,
                                ticket.summary AS summary,
                                ticket.priority AS priority,
                                ticket.owner AS owner,
                                ticket.changetime as modification,
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
        #WHERE %(where)s AND tp.username in ('internal_developer', '%(user)s')
        queries = []
        for trac in all_tracs:
            project_name = trac.project.name.replace("'", "''")
            customer_name = trac.project.customer.name.replace("'", "''")
            queries.append(query % {'trac': trac.trac_name,
                                    'project': project_name,
                                    'customer': customer_name,
                                    'where': where})
        sql = '\nUNION '.join(queries)
        sql += ';'
        tracs =  DBSession().execute(sql).fetchall()
        return tracs
