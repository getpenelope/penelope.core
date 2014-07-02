# -*- coding: utf-8 -*-
import logging
import bleach
import colander
import deform
from sunburnt import SolrInterface
from pyramid.view import view_config
from pyramid.url import current_route_url
from penelope.core.models.dashboard import Trac, User
from penelope.core.models import DBSession
from penelope.core.lib.widgets import SearchButton, PorInlineForm
from deform_bootstrap.widget import ChosenMultipleWidget

log = logging.getLogger('penelope')


def searchable_tracs(request):
    all_tracs = DBSession().query(Trac)
    # a list of tracs user can view:
    if not request.has_permission('manage', None):
        user_projects = [g.project for g in request.authenticated_user.groups]
        viewable_tracs = []
        for project in user_projects:
            for trac in project.tracs:
                viewable_tracs.append(trac)
    else:
        viewable_tracs = all_tracs

    query = """SELECT DISTINCT '%(trac)s' AS trac_name, '%(project)s' AS project_name FROM "trac_%(trac)s".permission
 WHERE username IN ('internal_developer', '%(user)s')"""

    queries = []
    for trac in viewable_tracs:
        project_name = trac.project.name.replace("'", "''")
        customer_name = trac.project.customer.name.replace("'", "''")
        queries.append(query % {'trac': trac.trac_name,
                                'project': '%s [%s]' % (project_name, customer_name),
                                'user': request.authenticated_user.email})
    sql = '\nUNION '.join(queries)
    sql += ';'
    tracs =  DBSession().execute(sql).fetchall()
    return sorted(tracs, key=lambda s: s[1].lower())


class SearchSchema(colander.MappingSchema):

    tracs = colander.SchemaNode(colander.Set(),
                      widget=ChosenMultipleWidget(placeholder=u'Select tracs',
                                                  style="width:250px"),
                      missing=colander.null,
                      title=u'')

    realms = colander.SchemaNode(colander.Set(),
               widget=ChosenMultipleWidget(placeholder=u'Select realms',
                                           style="width:250px",
                                           values=[('', ''),
                                                   ('ticket', 'Ticket'),
                                                   ('wiki', 'Wiki'),
                                                   ('milestone', 'Milestone'),
                                                   ('TimeEntry', 'Time entry'),
                                                   ('changeset','Changeset')]),
               missing=colander.null,
               title=u'')

    authors = colander.SchemaNode(colander.Set(),
                    widget=ChosenMultipleWidget(placeholder=u'Select author',
                                                 style="width:250px"),
                    missing=colander.null,
                    title=u'')

    searchable = colander.SchemaNode(typ=colander.String(),
                            title=u'',
                            widget = deform.widget.TextInputWidget(
                                            css_class=u'input-xxlarge',
                                            placeholder=u'Searchable text'),)


@view_config(route_name='search', permission='search', renderer='skin')
def search(request):

    schema = SearchSchema().bind(request=request)
    form = PorInlineForm(
                schema,
                action=request.current_route_url(),
                formid='search',
                method='GET',
                buttons=[SearchButton(title=u'Search'),]
            )

    tracs = searchable_tracs(request)
    form['tracs'].widget.values = [('', '')] \
                              + [(t.trac_name, t.project_name) for t in tracs]

    users = DBSession.query(User).order_by(User.fullname)
    form['authors'].widget.values = [('', '')] \
                              + [(a.email, a.fullname) for a in users]

    controls = request.GET.items()
    if not controls:
        return {'form': form.render(),
                'results':[]}
    try:
        appstruct = form.validate(controls)
    except deform.ValidationFailure as e:
        return {'form': e.render(),
                'results':[]}

    params = appstruct.copy()
    if not params['tracs']:
        params['tracs'] = [t.trac_name for t in tracs]

    fs = FullTextSearch(request=request, **params)
    results = fs.get_search_results()
    next_url = None
    previous_url = None
    docs = []

    if results:
        docs = [FullTextSearchObject(**doc) for doc in results]
        records_len = results.result.numFound
        if not fs.page_start + fs.page_size >= records_len: # end of set
            next_query = add_param(request, 'page_start', fs.page_start + fs.page_size)
            next_url = current_route_url(request, _query=next_query)

        if not fs.page_start == 0:
            previous_page = fs.page_start - fs.page_size
            if previous_page < 0:
                previous_page = 0
            previous_query = add_param(request, 'page_start', previous_page)
            previous_url = current_route_url(request, _query=previous_query)

    return {'docs': docs,
            'next': next_url,
            'form': form.render(appstruct=appstruct),
            'previous': previous_url,
            'add_params': add_params,
            'results': results}


def add_params(request, key, value):
    base_query = request.params.copy()
    base_query['__start__'] = '%s:sequence' % key
    base_query[key] = value
    base_query['__end__'] = '%s:sequence' % key
    return base_query


def add_param(request, key, value):
    base_query = request.params.copy()
    base_query[key] = value
    return base_query


class FullTextSearch(object):

    def __init__(self, request, tracs=None, searchable=None,
                 realms=None, authors=None):
        if not realms:
            realms = []
        if not authors:
            authors = []
        self.request = request
        self.searchable = searchable.split(' ') # always a sequence
        self.viewable_tracs = list(tracs)
        self.realms = list(realms)
        self.authors = list(authors)
        self.solr_endpoint = request.registry.settings.get('por.solr')

    @property
    def page_start(self):
        return int(self.request.params.get('page_start', 0))

    @property
    def page_size(self):
        return 30

    def get_search_results(self,):
        try:
            return self._do_search(sort_by=['-score'])
        except Exception, e:
            log.error("Couldn't perform Full text search, falling back "
                           "to built-in search sources: %s", e)
            return

    def _build_trac_filter(self, si):
        all_tracs = set([a.trac_name for a in DBSession().query(Trac.trac_name)])
        Q = si.query().Q

        def query_include(items):
            if len(items) > 2:
                return Q(project=items.pop()) | query_include(items)
            elif len(items) == 2:
                return Q(project=items.pop()) | Q(project=items.pop())
            elif len(items) == 1:
                return Q(project=items.pop())
            else:
                return ""

        def query_exclude(items):
            if len(items) > 2:
                return ~Q(project=items.pop()) & ~query_exclude(items)
            elif len(items) == 2:
                return ~Q(project=items.pop()) & ~Q(project=items.pop())
            elif len(items) == 1:
                return ~Q(project=items.pop())
            else:
                return ""

        # if viewable_tracs are > (all_tracs / 2)
        # let's exclude
        if len(self.viewable_tracs) > (len(all_tracs) / 2):
            return query_exclude(all_tracs.difference(self.viewable_tracs))
        # in other cases
        # let's use include
        else:
            return query_include(self.viewable_tracs)

    def _build_realm_filter(self, si):

        Q = si.query().Q

        def query(items):
            if len(items) > 2:
                return Q(realm=items.pop()) | query(items)
            elif len(items) == 2:
                return Q(realm=items.pop()) | Q(realm=items.pop())
            elif len(items) == 1:
                return Q(realm=items.pop())
            else:
                return ""
        return query(self.realms)

    def _build_author_filter(self, si):

        Q = si.query().Q

        def query(items):
            if len(items) > 2:
                return Q(author=items.pop()) | query(items)
            elif len(items) == 2:
                return Q(author=items.pop()) | Q(author=items.pop())
            elif len(items) == 1:
                return Q(author=items.pop())
            else:
                return ""
        return query(self.authors)

    def _do_search(self, sort_by=None):
        si = SolrInterface(self.solr_endpoint)

        searchquery = si.Q(*[si.Q(s) for s in self.searchable])
        query = si.query(searchquery)#.field_limit(score=True)

        realm_query = self._build_realm_filter(si)
        if realm_query:
            query = query.filter(realm_query)

        author_query = self._build_author_filter(si)
        if author_query:
            query = query.filter(author_query)

        trac_query = self._build_trac_filter(si)
        if trac_query:
            query = query.filter(trac_query)

        for field in sort_by or []:
            query = query.sort_by(field)

        query = query.paginate(start=self.page_start, rows=self.page_size)\
                            .highlight('oneline',
                                    **{'simple.pre':'<span class="highlight">',
                                       'snippets': 3,
                                       'fragsize': 600,
                                       'simple.post':'</span>'})

        # boosting - super hacky but sunburnt is not support bq
        options = query.options()
        options['defType'] = 'dismax' # make sure we use dismax parser
        options['bq'] = ['realm:ticket^999','status:new^100', 'status:assigned^100',
                         'status:reopened^999', 'status:reviewing^100',
                         'status:accepted^100','(*:* -xxx)^999']
        result = query.interface.search(**options)
        return query.transform_result(result, dict)


class FullTextSearchObject(object):
    '''Minimal behaviour class to store documents going to/comping from Solr.
    '''
    def __init__(self, project, realm, id=None, score=None, status=None,
                 title=None, author=None, changed=None, created=None,
                 oneline=None, involved=None, popularity=None, comments=None,
                 parent_id=None, solr_highlights=None , **kwarg):

        if not involved:
            involved = ()
        if not author:
            author = ()
        self.project = project
        self.author = ', '.join(author)
        self.created = created
        self.popularity = popularity
        self.comments = comments
        self.realm = realm
        self.solr_highlights = solr_highlights
        self._title = ''.join(title)
        self._oneline = oneline
        self.id = id
        self.score = score
        self.parent_id = parent_id
        self.status = status

    @property
    def closed(self):
        return self.status == 'closed'

    @property
    def title(self):
        result = []
        if self.solr_highlights:
            result = self.solr_highlights.get('title')
        if not result:
            result = self._title
        text = ''.join(result)
        return bleach.clean(text, ['span'], ['class'], strip=True)

    @property
    def oneline(self):
        result = []
        if self.solr_highlights:
            result = self.solr_highlights.get('oneline')
        if not result:
            result = self._oneline
        text = ''.join(result)
        return bleach.clean(text, ['span'], ['class'], strip=True)

    def icon(self):
        if self.realm == 'TimeEntry':
            return 'icon-time'
        elif self.realm == 'ticket':
            return 'icon-list-alt'
        elif self.realm == 'changeset':
            return 'icon-random'
        elif self.realm == 'wiki':
            return 'icon-book'
        elif self.realm == 'milestone':
            return 'icon-calendar'


    def href(self):
        if self.realm == 'changeset':
            return "trac/%s/%s/%s/%s" % (self.project, self.realm, self.id, self.parent_id)
        elif self.realm == 'TimeEntry':
            return "admin/TimeEntry/%s" % self.id
        else:
            return "trac/%s/%s/%s" % (self.project, self.realm, self.id)
