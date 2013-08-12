# -*- coding: utf-8 -*-

import colander


def validate_period(node, value):
    ### if a date is required...
    #if not value['date_from'] and not value['date_to']:
    #  raise colander.Invalid(node, 'devi selezionare almeno una data')
    if value['date_from'] and value['date_to'] and value['date_from'] > value['date_to']:
        raise colander.Invalid(node, 'data inizio deve essere <= data fine')
