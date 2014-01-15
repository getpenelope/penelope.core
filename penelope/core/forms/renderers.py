# -*- coding: utf-8 -*-

from datetime import timedelta
from simplejson import dumps

from webhelpers.html import HTML, literal
from formalchemy import helpers as h
from formalchemy import fatypes, validators
from formalchemy import FieldSet, Grid;Grid #pyflakes
from formalchemy import fields

from fa.jquery.fanstatic_resources import fa_js
from fa.jquery.renderers import DateFieldRenderer, default_renderers

from penelope.core.lib.helpers import listwrap, ticket_url, unicodelower
from penelope.core.models import DBSession, User, CustomerRequest, Project, Contract, Application
from penelope.core.models.tickets import ticket_store


def _query_options(L):
    if hasattr(L, '_mapper_adapter_map') and \
                                         User in L._mapper_adapter_map.keys():
        L = L.filter_by(active=True)
    return [(fields._stringify(item), fields._pk(item)) for item in L]
fields._query_options = _query_options


class UrlRenderer(fields.TextFieldRenderer):
    def render_readonly(self, **kwargs):
        return HTML.A(self.value, href=self.value, target="_blank")


class TicketRenderer(fields.IntegerFieldRenderer):
    def render_readonly(self, **kwargs):
        request = self.request
        te = request.model_instance

        if not request.has_permission('view', te.project):
            return '#%s' % te.ticket

        ticket_data = ticket_store.get_ticket(te.project_id, te.ticket)

        if ticket_data:
            ticket_id, dummy_time, dummy_changetime, tkt = ticket_data
            ret = HTML.A(u'#%s - %s' % (ticket_id, tkt['summary']),
                         href=ticket_url(request, te.project, te.ticket))
            cr_id = tkt['customerrequest']
            if cr_id:
                cr = DBSession.query(CustomerRequest).get(cr_id)
                ret += HTML.BR() + HTML.SPAN('CR: ') + HTML.A(cr.name, href='/admin/CustomerRequest/%s' % cr_id)
            return ret
        else:
            return HTML.SPAN(u'#%s - ' % te.ticket, HTML.SPAN(u'NOT FOUND', class_='label label-important'))


class RelationRenderer(fields.SelectFieldRenderer):
    """Make relation linkable in readonly mode
       and aware of js.chosen()"""

    project_related_classes = [CustomerRequest, Contract, Application]

    def project_related_form(self):
        """
        Check if current fieldset has a project field and one project related field.
        """
        return [a for a in self.field.parent.render_fields.values() if a.is_relation and a.relation_type() in self.project_related_classes]

    def render(self, options, **kwargs):
        optional_js = ''

        prf = self.project_related_form()
        if prf and self.field.relation_type() == Project:
            optional_js = """\n$("#%(project_id)s").chosen().change(function(){
                                var $project_id = $(this).val();
                                $.getJSON('/admin/Project/'+$project_id+'/list_customer_requests.json', function(data){
                                    var items = [];
            """
            prf_names = [a.renderer.name for a in prf]

            for n in prf_names:
                optional_js += "$('#%s option').remove();" % n
                optional_js += """$.each(data, function(cr) {
                                        items.push("<option value='" + data[cr]['id'] + "'>" + data[cr]['name'] + "</option>");
                                  });
                                  $('#%s').append(items.join(""));""" % n
                optional_js += "$('#%s').trigger('chosen:updated');" % n

            optional_js += "})});"
            optional_js = optional_js % {'project_id':self.name}

        if callable(options):
            L = fields._normalized_options(options(self.field.parent))
            if not self.field.is_required() and not self.field.is_collection:
                L.insert(0, self.field._null_option)
        else:
            L = list(options)
        if len(L) > 0:
            if len(L[0]) == 2:
                L = sorted([(k, self.stringify_value(v)) for k, v in L], key=lambda x:unicodelower(x[0]))
            else:
                L = sorted([fields._stringify(k) for k in L], key=unicodelower)

        return h.select(self.name, self.value, L, class_='i-can-haz-chzn-select', **kwargs) + \
               h.literal("<script>$('#%s').chosen();%s</script>" % (self.name, optional_js))

    def render_readonly(self, options=None, **kwargs):
        value = self.raw_value
        if value is None:
            return ''

        if not isinstance(value, list):
            if self.request.has_permission('view', value):
                return h.content_tag('a',
                    self.stringify_value(value, as_html=True),
                    href=self.request.fa_url(value.__class__.__name__, fields._pk(value)))
            else:
                return h.content_tag('span', self.stringify_value(value, as_html=True))
        else:
            html = []
            for item in value:
                if self.request.has_permission('view', item):
                    html.append(h.content_tag('a',
                                self.stringify_value(item, as_html=True),
                                href=self.request.fa_url(item.__class__.__name__, fields._pk(item))))
                else:
                    html.append(h.content_tag('span', self.stringify_value(item, as_html=True)))
            return h.literal(',&nbsp;').join(html)


class PORDateFieldRenderer(DateFieldRenderer):
    """Make sure we are using fa_jquery resources"""

    def render(self, **kwargs):
        fa_js.need()
        return super(PORDateFieldRenderer, self).render(**kwargs)


class IntervalFieldRenderer(fields.IntervalFieldRenderer):
    """Use http://jqueryui.com/demos/datepicker/"""

    jq_options = dict(minuteGrid=10, hourGrid=4, showButtonPanel=False, timeFormat='hh:mm')
    template = """<input type="text" autocomplete="off" size="10" value="%(value)s" id="%(name)s" name="%(name)s" />
    <script type="text/javascript">$('#%(name)s').timepicker(%(jq_options)s);</script>"""

    def stringify_timedelta(self, value):
        if not isinstance(value, timedelta):
            return value

        seconds = value.seconds
        days = value.days
        hours, remainder = divmod(seconds, 3600)
        hours += (days * 24)
        minutes, seconds = divmod(remainder, 60)
        return "%d:%02d" % (hours, minutes)

    def stringify_value(self, v, as_html=False):
        if as_html or not v:
            return super(IntervalFieldRenderer, self).stringify_value(v, as_html=as_html)
        return self.stringify_timedelta(v)

    def render_readonly(self, **kwargs):
        value = self.raw_value
        return self.stringify_timedelta(value)

    def render(self, **kwargs):
        value = self.raw_value or ''
        try:
            value = self.stringify_timedelta(value)
        except validators.ValidationError:
            value = '00:00'
        options = self.jq_options.copy()
        kwargs.update(
            name=self.name,
            value=value,
            jq_options=dumps(options),
        )
        return literal(self.template % kwargs)

    def _deserialize(self, data):
        try:
            hours, minutes = [int(s) for s in data.split(':')]
        except ValueError:
            raise validators.ValidationError('Not a proper interval')
        return timedelta(hours=hours, minutes=minutes)


FieldSet.default_renderers.update(default_renderers)
FieldSet.default_renderers['dropdown'] = RelationRenderer
FieldSet.default_renderers[fatypes.Date] = PORDateFieldRenderer
FieldSet.default_renderers[fatypes.Interval] = IntervalFieldRenderer


class ProjectRelationRenderer(RelationRenderer):
    """
    Renders project names without the customer
    """

    def _stringify_project(self, project, as_html):
        if as_html:
            return h.content_tag('a',
                                 project.name,
                                 href=self.request.fa_url(project.__class__.__name__, fields._pk(project)))
        else:
            return project.name

    def stringify_value(self, value, as_html=False):
        return literal(',&nbsp;').join(
                        self._stringify_project(project, as_html=as_html)
                        for project in listwrap(value)
                    )

