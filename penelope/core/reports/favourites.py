# -*- coding: utf-8 -*-

import cgi
import colander
import deform

from colander import SchemaNode
from pyramid.view import view_config
from pyramid.response import Response

from penelope.core.models import DBSession, SavedQuery
from penelope.core.lib.widgets import DeleteButton, FavoriteButton, RenameButton, PorInlineForm


class SavedQuerySchema(colander.MappingSchema):
    sq_id = SchemaNode(colander.Int(),
                       widget=deform.widget.HiddenWidget(),
                       title=u'')

    report_name = SchemaNode(colander.String(),
                             widget=deform.widget.HiddenWidget(),
                             title=u'')

    query_name = SchemaNode(colander.String(),
                            title=u'Query name')



def render_saved_query_form(request):
    current_uid = request.authenticated_user.id
    qry = DBSession.query(SavedQuery)

    # retrieve a saved query by the same user...
    qry = qry.filter(SavedQuery.author_id==current_uid)
    # ..for the current report..
    qry = qry.filter(SavedQuery.report_name==request.view_name)
    # ..with the current parameters
    qry = qry.filter(SavedQuery.query_string=='?'+request.query_string)

    # XXX what if there are two queries with the exact same parameters?

    savedqry = qry.first()
    report_name = request.view_name

    if savedqry:
        appstruct = {
                'sq_id': savedqry.id,
                'query_name': savedqry.query_name,
                'report_name': report_name,
                }
        buttons = [
                RenameButton(title=u'Rename', type='button', name='submit_edit'),
                DeleteButton(title=u'Delete', type='button', name='submit_delete'),
                ]
    else:
        appstruct = {
                'report_name': report_name,
                }
        buttons = [
                FavoriteButton(title=u'Save', type='button', name="submit_add"),
                ]


    form = PorInlineForm(SavedQuerySchema().clone(),
                         formid='saved_query_form',
                         action='save_query',
                         method='POST',
                         buttons=buttons,
                         )
    return form.render(appstruct=appstruct)



@view_config(name='save_query', route_name='reports', permission='reports_my_entries')
def save_query(context, request):
    current_uid = request.authenticated_user.id

    query_meta = cgi.parse_qs(request.POST['query_meta'])

    if not 'query_name' in query_meta:
        return Response(u"Please specify a query name.", status=409)

    query_name = query_meta['query_name'][0]

    taken = DBSession.query(SavedQuery).filter(SavedQuery.author_id==current_uid).filter(SavedQuery.query_name==query_name).count()

    submit_type = request.POST['submit_type']

    if submit_type == 'submit_edit':
        if taken:
            return Response(u"Name already in use: '%s'." % query_name, status=409)
        sq_id = query_meta['sq_id'][0]
        qry = DBSession.query(SavedQuery)
        qry = qry.filter(SavedQuery.author_id==current_uid)
        qry = qry.filter(SavedQuery.id==sq_id)
        sq = qry.one()
        sq.query_name = query_name
        return Response(u"The query has been renamed as '%s'." % query_name)
    elif submit_type == 'submit_delete':
        sq_id = query_meta['sq_id'][0]
        qry = DBSession.query(SavedQuery)
        qry = qry.filter(SavedQuery.author_id==current_uid)
        qry = qry.filter(SavedQuery.id==sq_id)
        sq = qry.one()
        DBSession.delete(sq)
        return Response(u"The saved query has been deleted.")
    elif submit_type == 'submit_add':
        if taken:
            return Response(u"Name already in use: '%s'." % query_name, status=409)
        # add
        sq = SavedQuery(query_name=query_name,
                        report_name=query_meta['report_name'][0],
                        query_string=request.POST['query_string'],
                        author_id = current_uid)
        DBSession.add(sq)
        return Response(u"The query has been saved as '%s'." % query_name)
