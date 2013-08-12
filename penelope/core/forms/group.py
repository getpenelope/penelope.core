# -*- coding: utf-8 -*-
from copy import deepcopy

from zope.interface import implements
from webhelpers.html import HTML
from fa.bootstrap import actions
from pyramid_formalchemy import resources
from formalchemy import fields

from penelope.core.forms import ModelView
from penelope.core.interfaces import IManageView

def configurate(config):
    config.formalchemy_model_view('admin',
        renderer='penelope.core.forms:templates/group_listing.pt',
        context=ModelListing,
        attr='datatable',
        request_method='GET',
        permission='listing',
        model='penelope.core.models.dashboard.Group',
        view=GroupModelView)

    config.formalchemy_model_view('admin',
        request_method='POST',
        permission='delete',
        name='delete',
        attr='delete',
        renderer='fa.bootstrap:templates/admin/edit.pt',
        model='penelope.core.models.dashboard.Group',
        view=GroupModelView)


class GroupLinkRenderer(fields.FieldRenderer):
    def render_readonly(self, **kwargs):
        group_id = self.field.value
        return HTML.A(u'edit', href=self.request.fa_url('Group', group_id, 'edit'))


class GroupModelView(ModelView):
    defaults_actions = deepcopy(actions.defaults_actions)
    defaults_actions.update(listing_buttons=actions.Actions())


    @actions.action('listing')
    def datatable(self, **kwargs):
        result = super(GroupModelView, self).datatable(**kwargs)

        fs = result['fs']
        fs['id'].is_raw_foreign_key = False       # formalchemy would not include foreign keys
        fs.configure(pk=True, readonly=True)

        fs._render_fields['id']._get_renderer = lambda: GroupLinkRenderer(fs._render_fields['id'])

        columns = ['project', 'roles', 'users', 'id']
        self.pick_columns(fs, columns)

        return dict(result,
                    columns=columns)

    def delete(self):
        """
        For Group we are always forcing to delete.
        No additional validation
        """
        return self.force_delete()


class ModelListing(resources.ModelListing):
    implements(IManageView)
