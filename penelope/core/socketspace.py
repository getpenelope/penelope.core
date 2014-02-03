from pyramid.response import Response
from pyramid.view import view_config
from socketio import socketio_manage

from penelope.core.activity_stream import FeedlyNamespace
from penelope.core.kanbanboard import KanbanNamespace


@view_config(route_name="socketio")
def socketio(request):
    socketio_manage(request.environ, {"/kanban": KanbanNamespace,
                                      "/feedly": FeedlyNamespace }, request=request)
    return Response('')
