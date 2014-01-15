# -*- coding: utf-8 -*-

"""
Common fields for all the reports, to be cloned before use.
"""

import colander
import deform

from colander import SchemaNode
from deform_bootstrap.widget import ChosenSingleWidget, ChosenMultipleWidget


customer_id = SchemaNode(typ=colander.String(),
                         widget=ChosenSingleWidget(css_class='customer-select',
                                                   placeholder=u'Select customer'),
                         missing=colander.null,
                         title=u'')

project_id =SchemaNode(typ=colander.String(),
                       widget=ChosenSingleWidget(css_class='project-select',
                                                 placeholder=u'Select project'),
                       missing=colander.null,
                       title=u'')

customer_requests = SchemaNode(colander.Set(),
                               widget=ChosenMultipleWidget(css_class='customer-request-select',
                                                           placeholder=u'Select customer requests'),
                               missing=colander.null,
                               title=u'')

contracts = SchemaNode(colander.Set(),
                       widget=ChosenMultipleWidget(css_class='contract-select',
                                                   placeholder=u'Select contract'),
                       missing=colander.null,
                       title=u'')

date_from = SchemaNode(typ=colander.Date(),
                       widget=deform.widget.DateInputWidget(size=11,
                                                            placeholder=u'from'),
                       missing=colander.null,
                       title=u'')

date_to = SchemaNode(typ=colander.Date(),
                     widget=deform.widget.DateInputWidget(size=11,
                                                          placeholder=u'to'),
                     missing=colander.null,
                     title=u'')

users = SchemaNode(colander.Set(),
                   widget=ChosenMultipleWidget(placeholder=u'Select people'),
                   missing=colander.null,
                   title=u'')


workflow_states = SchemaNode(colander.Set(),
                             widget=ChosenMultipleWidget(placeholder=u'State'),
                             missing=colander.null,
                             title=u'')

invoice_number = SchemaNode(typ=colander.String(),
                            missing=colander.null,
                            widget = deform.widget.TextInputWidget(placeholder=u'invoice nr.'),
                            title=u'')

searchtext = SchemaNode(colander.String(),
                        widget = deform.widget.TextInputWidget(css_class='xlarge',
                                                               placeholder=u'description'),
                        missing = colander.null,
                        title = u'')
