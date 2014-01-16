# -*- coding: utf-8 -*-
import zope.component.event
import json

from chameleon import PageTemplate
from beaker.cache import cache_region
from zope.interface import alsoProvides
from pyramid.renderers import get_renderer
from pyramid import httpexceptions as exc
from pyramid.security import has_permission
from pyramid.response import Response
from pyramid.exceptions import NotFound
from pyramid.i18n import TranslationStringFactory
from pyramid_formalchemy.utils import TemplateEngine
from pyramid_formalchemy.resources import Models
from pyramid_formalchemy import actions as factions
from pyramid_formalchemy import events
from formalchemy import config
from formalchemy import FieldSet;FieldSet
from formalchemy import Grid;Grid #pyflakes
from formalchemy import forms;forms
from fa.bootstrap.views import ModelView as Base
from fa.bootstrap import actions
from formalchemy import fields
from formalchemy.exceptions import ValidationError
from webhelpers.paginate import Page

from penelope.core.models.dbsession import DBSession
from penelope.core.models import dashboard
from penelope.core import fanstatic_resources, views
from penelope.core.forms import application_views;application_views
from penelope.core.forms import renderers;renderers


config.engine = TemplateEngine()
_ = TranslationStringFactory('penelope')


newcancel = actions.UIButton(
            id='cancel',
            content=actions._('Cancel'),
            permission='edit',
            _class='btn',
            attrs=dict(href="request.fa_parent_url()"),
            )

editcancel = actions.UIButton(
            id='cancel',
            content=actions._('Cancel'),
            permission='edit',
            _class='btn',
            attrs=dict(href="request.fa_url(request.model_name, request.model_id)"),
            )

save_new = actions.UIButton(
        id='save',
        content=_('Save'),
        permission='new',
        _class='btn btn-success',
        attrs=dict(onclick="jQuery(this).parents('form').submit();"),
        )

actions.defaults_actions['new_buttons'][-1] = newcancel
actions.defaults_actions['edit_buttons'][-1] = editcancel
actions.defaults_actions['show_buttons'].pop(1)
actions.defaults_actions['new_buttons'][0] = save_new


class CrudModels(Models, views.DefaultContext):
    def __init__(self, request):
        Models.__init__(self, request)
        views.DefaultContext.__init__(self, request)

    @property
    def title(self):
        area = self.request.model_name
        name = self.request.model_instance and str(self.request.model_instance).title() or ''
        view = self.prettify_title(self.request.view_name) or 'view'
        title = '%s: %s %s' % (area, name.decode('utf8'), view)
        return title.title()


class ModelView(Base):
    pager_args = dict(link_attr={'class': ''},
        curpage_attr={'class': 'active'},
        format="~5~")

    def render(self, **kwargs):
        fanstatic_resources.dashboard.need()
        result = super(ModelView, self).render(**kwargs)
        result['main_template'] = get_renderer('penelope.core:skins/main_template.pt').implementation()
        result['main'] = get_renderer('penelope.core.forms:templates/master.pt').implementation()
        return result

    def models(self, **kwargs):
        self.context.request.models = [dashboard.Project, dashboard.User, dashboard.Group, dashboard.Customer]
        return super(ModelView, self).models(**kwargs)

    def update_grid(self, grid):
        pass

    def breadcrumb(self, **args):
        " This we are ignoring from pyramid_formalchemy "
        return actions.Actions()

    def get_page(self, **kwargs):
        """return a ``webhelpers.paginate.Page`` used to display ``Grid``.
        """
        request = self.request
        def get_page_url(page, partial=None):
            url = "%s?page=%s" % (self.request.path, page)
            if partial:
                url += "&partial=1"
            return url
        options = dict(page=int(request.GET.get('page', '1')),
                       url=get_page_url)
        options.update(kwargs)
        if 'collection' not in options:
            query = self.session.query(request.model_class)
            options['collection'] = request.query_factory(request, query)
        collection = list(request.filter_viewables(options.pop('collection')))

        return Page(collection, **options)

    @factions.action()
    def new(self):
        if not hasattr(self.request,'form_action'):
            self.request.form_action = self.request.model_name
        if self.request.method == 'POST':
            return self.create()
        else:
            return super(ModelView, self).new()

    @factions.action('new')
    def create(self):
        request = self.request
        fs = self.get_fieldset(suffix='Add')

        event = events.BeforeRenderEvent(fs.model, self.request, fs=fs)
        alsoProvides(event, events.IBeforeNewRenderEvent)
        zope.component.event.objectEventNotify(event)

        if request.format == 'json' and request.method == 'PUT':
            data = json.load(request.body_file)
        elif request.content_type == 'application/json':
            data = json.load(request.body_file)
        else:
            data = request.POST

        with_prefix = True
        if request.format == 'json':
            with_prefix = bool(request.params.get('with_prefix'))

        fs = fs.bind(data=data, session=self.session, request=request, with_prefix=with_prefix)
        if self.validate(fs):
            fs.sync()
            self.sync(fs)
            self.session.flush()
            if request.format in ('html', 'xhr'):
                if request.is_xhr or request.format == 'xhr':
                    return Response(content_type='text/plain')
                next = request.POST.get('next') or request.fa_url(request.model_name,fs.model.id)
                return exc.HTTPFound(
                    location=next)
            else:
                fs.rebind(fs.model, data=None)
                return self.render(fs=fs)
        return self.render(fs=fs, id=None)

    def delete(self):
        "We shouldn't use default formalchemy delete."
        request = self.request
        request.add_message(u'You cannot remove the object.', type='danger')
        raise exc.HTTPFound(location=request.fa_url(request.model_name, request.model_instance.id))

    def force_delete(self):
        """Forced only by specific models"""
        request = self.request
        record = request.model_instance

        event = events.BeforeDeleteEvent(record, self.request)
        zope.component.event.objectEventNotify(event)

        if record:
            self.session.delete(record)
        else:
            raise NotFound()

        request.add_message(u'Object deleted.', type='success')
        if request.format == 'html':
            if request.is_xhr or request.format == 'xhr':
                return Response(content_type='text/plain')
            return exc.HTTPFound(location=request.fa_parent_url())
        return self.render(id=request.model_id)


    @factions.action('listing')
    def datatable(self, **kwargs):
        """listing page with datatables.net"""
        fanstatic_resources.datatables.need()

        page = self.get_page(**dict(kwargs, items_per_page=999999999))
        fs = self.get_grid()
        fs = fs.bind(instances=page, request=self.request)
        fs.readonly = True

        event = events.BeforeRenderEvent(self.request.model_class(), self.request, fs=fs, page=page)
        alsoProvides(event, events.IBeforeListingRenderEvent)
        zope.component.event.objectEventNotify(event)

        return self.render_grid(fs=fs, id=None)


    def pick_columns(self, fs, columns):
        # filter out unwanted columns

        for field_name in list(fs._render_fields):
            if field_name not in columns:
                del fs._render_fields[field_name]

        # rearrange the OrderedDict

        for field_name in columns:
            fs._render_fields[field_name] = fs._render_fields.pop(field_name)



from penelope.core.forms import project, customer, application, customer_request, timeentry, group, user, role, contract, kanbanboard, cost

def include_forms(config):
    project.configurate(config)
    customer.configurate(config)
    application.configurate(config)
    customer_request.configurate(config)
    timeentry.configurate(config)
    group.configurate(config)
    user.configurate(config)
    role.configurate(config)
    contract.configurate(config)
    kanbanboard.configurate(config)
    cost.configurate(config)

    config.override_asset(
        to_override="fa.bootstrap:templates/forms/",
        override_with="penelope.core.forms:templates/forms/")


class AttributeField(fields.AttributeField):
    """
    We are monkey patching formalchemy's AttributeField to add
    additional features like dynamic validators for
    unique columns, etc.
    """
    description = None

    def __init__(self, instrumented_attribute, parent):
        super(AttributeField, self).__init__(instrumented_attribute, parent)

        # add validator if column is unique
        if not self.is_collection and not self.is_readonly() and [c for c in self._columns if c.unique]:
            self.validators.append(unique)

fields.AttributeField = AttributeField


def unique(value, field=None):
    """Successful if value is unique"""
    msg = _('Broken ${value}', mapping={'value': value})
    if not field:
        raise ValidationError(msg)

    session = DBSession()

    filters = {}
    filters[field._column_name] = value
    records = session.query(field.model.__class__).filter_by(**filters)

    if records.count() > 0 and records.one() != field.model:
        msg = _("${value} already exists! Field '${field_column_name}' should be unique!",
                mapping={'value': value, 'field_column_name': field._column_name})
        raise ValidationError(msg)
    return value


def security_create(context, request):
    """
    In order to check properly security for Project-related objects,
    we are using this wrapper function.
    """
    project_id = request.params.get('%s--project_id' % request.model_name, '')
    project = request.session_factory().query(dashboard.Project).get(project_id)
    if project:
        request.challenge_item = project
    if has_permission('new', context, request):
        view = ModelView(context, request)
        return view.create()
    else:
        return exc.HTTPForbidden()


@cache_region('template_caching')
def set_template(body):
    return PageTemplate(body)


def cache_template_init(self, id, content="", alt="", permission=None, attrs=None, **rcontext):
    self.id = id
    self.attrs = attrs or {}
    self.permission = permission
    self.rcontext = rcontext
    if 'id' not in self.attrs:
        self.attrs['id'] = repr(id)
    self.update()
    attributes = u';'.join([u'%s %s' % v for v in self.attrs.items()])
    rcontext.update(attrs=self.attrs, attributes=attributes, id=id)
    body = self.body % self.rcontext
    rcontext.update(content=content, alt=alt)
    self.template = set_template(body)

factions.Action.__init__ = cache_template_init
