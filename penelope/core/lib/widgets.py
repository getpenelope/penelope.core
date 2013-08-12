# -*- coding: utf-8 -*-

"""
Deform widgets for penelope.core
"""

from pkg_resources import resource_filename

import deform


class DeleteButton(deform.form.Button):
    icon_class = 'icon-trash'


class DownloadButton(deform.form.Button):
    icon_class = 'icon-white icon-download'


class FavoriteButton(deform.form.Button):
    icon_class = 'icon-white icon-star'


class RenameButton(deform.form.Button):
    icon_class = 'icon-white icon-edit'


class SearchButton(deform.form.Button):
    icon_class = 'icon-white icon-search'


class SubmitButton(deform.form.Button):
    icon_class = 'icon-white icon-ok'


class ResetButton(deform.form.Button):
    icon_class = 'icon-gray icon-remove'
    type = 'reset'


class PorInlineForm(deform.Form):
    default_renderer = deform.ZPTRendererFactory([
                            resource_filename('penelope.core', 'deform_templates'),
                            resource_filename('deform_bootstrap', 'templates'),
                            resource_filename('deform', 'templates'),
                            ])

    inline_form = True
    bootstrap_form_style = 'form-inline'
    css_class = u'well'


class WizardForm(deform.Form):
    default_renderer = deform.ZPTRendererFactory([
                            resource_filename('penelope.core', 'wizard_templates'),
                            resource_filename('penelope.core', 'deform_templates'),
                            resource_filename('deform_bootstrap', 'templates'),
                            resource_filename('deform', 'templates'),
                            ])

    inline_form = False
    bootstrap_form_style = 'form-inline'
    css_class = u'well'

