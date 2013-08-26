# -*- coding: utf-8 -*-

import pkg_resources

from fanstatic import Group, Library, Resource
from js.jquery import jquery
from js.jqueryui import jqueryui, jqueryui_i18n
from js.jqueryui import overcast
from js.jquery_timepicker_addon import timepicker_it
from js.jquery_datatables import jquery_datatables_js    # jquery_datatables_css only contains a style for the demo table.
from js.bootstrap import bootstrap_js, bootstrap_responsive_css
from fa.bootstrap.fanstatic_resources import bootstrap
from js.socketio import socketio
from js.xeditable import bootstrap_editable


class ForeignLibrary(Library):
    """
    Let fanstatic get resources from an egg != the current one.
    Note that the library name must also be the package name, and must
    still be defined in the entry points.
    """
    def __init__(self, *args, **kw):
        super(ForeignLibrary, self).__init__(*args, **kw)
        self.path = pkg_resources.resource_filename(self.name, self.rootpath)



#----------------------
# Third party libraries
#----------------------


por_library = Library('por', 'static')

# mediaquery polyfills for IE
respond = Resource(por_library, 'respond/respond.src.js', minified='respond/respond.min.js')

# bricklayer for having columns in CSS
masonry = Resource(por_library, 'masonry/jquery.masonry.js', minified='masonry/jquery.masonry.min.js', depends=[jquery])

# JS templates
mustache = Resource(por_library, 'mustache/mustache.js', minified='mustache/mustache.min.js')

# spinner for ajax operations
spin = Resource(por_library, 'spin/spin.js')

jsonrpc = Resource(por_library, 'jquery.jsonrpc/jquery.jsonrpc.js')

jquery_pivot = Group([
                        Resource(por_library, 'jquery.pivot/jquery_pivot.js', depends=[jquery]),
                        Resource(por_library, 'jquery.pivot/jquery_pivot.css')
                    ])



#-------
# Deform
#-------

deform_library = ForeignLibrary('deform', 'static')
deform_bootstrap_library = ForeignLibrary('deform_bootstrap', 'static')

deform_bootstrap = Group([
        Resource(deform_bootstrap_library, 'chosen_bootstrap.css'),
        Resource(deform_bootstrap_library, 'deform_bootstrap.js'),        
        Resource(deform_bootstrap_library, 'jquery_chosen/chosen.css'),
        Resource(deform_bootstrap_library, 'jquery_chosen/chosen.jquery.js', depends=[jquery]),
        Resource(deform_library, 'scripts/jquery.form.js', depends=[jquery]),
        Resource(deform_library, 'scripts/deform.js', depends=[jquery]),
        ])


#----------
# Our stuff
#----------

dashboard_home = Group([
                        Resource(por_library, 'por_home/home.js', depends=[jquery, masonry]),
                        Resource(por_library, 'por_home/outstanding_tickets.js', depends=[jquery, mustache, spin]),
                        Resource(por_library, 'por_home/home.css')
                        ])

dashboard_js = Resource(por_library, 'js/dashboard.js', depends=[bootstrap_js, jqueryui, timepicker_it])
dashboard_css = Resource(por_library, 'css/dashboard.css', depends=[bootstrap_responsive_css, respond])

project_filter = Resource(por_library, 'por_report/select_project_filter.js')

subnav = Group([
                Resource(por_library, 'por_subnav/subnav.js', depends=[jquery]),
                Resource(por_library, 'por_subnav/subnav.css'),
               ])

report_all_entries = Group([
                            jquery_pivot,
                            Resource(por_library, 'por_report/all_entries.js', depends=[jquery, timepicker_it]),
                            Resource(por_library, 'por_report/all_entries.css'),
                            ])

saved_queries = Resource(por_library, 'por_report/saved_queries.js', depends=[jquery])

report_te_state_change = Group([
                                Resource(por_library, 'por_report/te_state_change.js', depends=[jquery, timepicker_it]),
                                Resource(por_library, 'por_report/te_state_change.css'),
                                ])

add_entry_from_ticket = Group([
                                Resource(por_library, 'por_add_entry/add_entry_from_ticket.js', depends=[jquery, mustache, timepicker_it, jsonrpc]),
                                Resource(por_library, 'por_add_entry/add_entry_from_ticket.css'),
                                ])

wizard = Group([ Resource(por_library, 'por_wizard/wizard.css') ])
fastticketing = Group([ Resource(por_library, 'por_fastticketing/fastticketing.css') ])

add_entry = Group([
                    Resource(por_library, 'por_add_entry/add_entry.js', depends=[jquery]),
                    Resource(por_library, 'por_add_entry/add_entry.css'),
                    Resource(por_library, 'por_add_entry/autocomplete.js', depends=[jquery]),
                    spin,
                   ])

backlog = Group([
                    Resource(por_library, 'por_backlog/backlog.js', depends=[jquery]),
                    Resource(por_library, 'por_backlog/backlog.css'),
                    ])

datatables = Group([
                    Resource(por_library, 'por_datatables/js/sorting.js'),
                    Resource(por_library, 'por_datatables/js/paging.js', depends=[jquery_datatables_js]),
                    Resource(por_library, 'por_datatables/css/paging.css'),
                   ])

angular = Resource(por_library, 'por_kanban/js/angular.min.js', depends=[jqueryui])

angular_dd = Resource(por_library,
                      'por_kanban/js/angular-dragdrop.js',
                      minified='por_kanban/js/angular-dragdrop.min.js',
                      depends=[jqueryui, angular])

angular_bootstrap_ui = Resource(por_library,
                      'por_kanban/js/ui-bootstrap-tpls-0.5.0.min.js',
                      depends=[bootstrap_js, angular])

angular_sortable = Resource(por_library,
                      'por_kanban/js/sortable.js',
                      depends=[jqueryui, angular])

js_md5 = Resource(por_library,
                  'por_kanban/js/md5.js',
                  minified='por_kanban/js/md5.min.js',)

kanban = Group([
                Resource(por_library, 'por_kanban/js/kanban.js', depends=[bootstrap_js, angular_sortable, socketio, angular, bootstrap_editable, js_md5, angular_bootstrap_ui]),
                Resource(por_library, 'por_kanban/css/kanban.css', depends=[bootstrap]),
    ])

dashboard = Group([jquery, deform_bootstrap, jqueryui, jqueryui_i18n, overcast, bootstrap, dashboard_js, dashboard_css, subnav])
