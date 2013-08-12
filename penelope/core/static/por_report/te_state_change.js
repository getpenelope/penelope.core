/*jslint undef: true */
/*global document, jQuery: false */

(function($) {
    "use strict";


$(document).ready(function(){
    var $checkboxes = $('input[type=checkbox][name^=te_]'),
        update_counter = function() {
            var count = $checkboxes.filter(':checked').length;
            $('#te_selected_counter').text( count + ' selected items' );
            if (count) {
                $('button[value=state_change]').removeAttr('disabled');
            } else {
                $('button[value=state_change]').attr('disabled', 'disabled');
            }
        };

    $checkboxes.click(function() { update_counter(); });

    $('input.check_ticket').click(function() {
                           $(this).closest('table').find('input[type=checkbox]').attr('checked', $(this).is(':checked'));
                           update_counter();
                        });

    $('input.check_all').click(function() {
                           $(this).closest('form').find('input[type=checkbox]').attr('checked', $(this).is(':checked'));
                           update_counter();
                        });

    $('select[name=new_state]').change(function() {
                            if ($(this).val() === 'invoiced') {
                                $('input[name=invoice_number]').show().focus();
                            } else {
                                $('input[name=invoice_number]').hide();
                            }
                        });

    $('tr.selectable').click(function(e) {
                            var $cb = $(this).find('input[type=checkbox]');
                            if ($cb[0] !== e.target) {
                                $cb.attr('checked', !$cb.attr('checked'));
                                update_counter();
                            }
                        });

    update_counter();
});


}(jQuery));

