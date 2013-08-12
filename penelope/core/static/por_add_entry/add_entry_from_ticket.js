/*jslint undef: true */
/*global document, $, window, setTimeout, Mustache: false */

$(document).ready(function() {
    "use strict";

    var $breadcrumbs = $('#trac-before-subnav .breadcrumb li'),

        // customer name / project name
        project_fullname = $breadcrumbs.slice(1, 3).text().replace(/[\/\s]+/, ''),

        // ['http', '', 'localhost', '8081', 'trac', 'penelope', 'ticket', '48']
        ticket_parts = window.location.href.split('/'),

        // ticket number inside the project, throw away hashes and the rest of the query
        ticket_number = ticket_parts[ticket_parts.length-1].match(/\d+/),
        ticket_number = (ticket_number === null) ? null : ticket_number[0],

        // project primary key
        project_id = ticket_parts[ticket_parts.length-3],

        ticket_summary = $('h2.summary').text(),

        trigger_tmpl = '<li class="pull-left">' +
                       '  <a class="btn btn-info"' +
                       '     href="#"' +
                       '     id="add-entry-from-ticket-trigger">' +
                       '    <i class="icon-white icon-time"></i>' +
                       '    {{submit_label}}' +
                       '  </a>' +
                       '</li>',

        dialog_tmpl = '<div class="modal hide fade" id="add-entry-from-ticket-dialog" style="display: none;">' +
                      '  <div class="modal-header">' +
                      '    <button data-dismiss="modal" class="close" type="button">×</button>' +
                      '    <h3>New Time Entry</h3>' +
                      '  </div>' +
                      '  <div class="modal-body">' +
                      '  <form class="form-horizontal">' +
                      '    <div class="control-group">' +
                      '      <label class="control-label">{{project_label}}</label>' +
                      '      <div class="controls">' +
                      '        <select name="project_id"><option value="{{project_id}}">{{project_name}}</option></select>' +
                      '      </div>' +
                      '    </div>' +
                      '    <div class="control-group">' +
                      '      <label class="control-label">{{ticket_label}}</label>' +
                      '      <div class="controls">' +
                      '        <input type="text" class="input-xlarge disabled" value="#{{ticket_number}}: {{ticket_summary}}" disabled="disabled">' +
                      '      </div>' +
                      '    </div>' +
                      '    <div class="control-group">' +
                      '      <label class="control-label">{{date_label}}</label>' +
                      '      <div class="controls">' +
                      '        <input type="text" name="date" class="input-small" size="11" />' +
                      '        <span id="add-entry-daily-subtotal-label"></span>' +
                      '        <span id="add-entry-daily-subtotal-value"></span>' +
                      '      </div>' +
                      '    </div>' +
                      '    <div class="control-group">' +
                      '      <label class="control-label">{{duration_label}}</label>' +
                      '      <div class="controls">' +
                      '        <input type="text" name="duration" class="input-small" size="11" />' +
                      '      </div>' +
                      '    </div>' +
                      '    <div class="control-group">' +
                      '      <label class="control-label">{{description_label}}</label>' +
                      '      <div class="controls">' +
                      '        <textarea name="description" class="input-xlarge" rows="5" value=""></textarea>' +
                      '      </div>' +
                      '    </div>' +
                      '    <div class="control-group">' +
                      '      <label class="control-label">{{location_label}}</label>' +
                      '      <div class="controls">' +
                      '        <input type="text" name="location" class="input-xlarge" value="{{location_value}}" />' +
                      '      </div>' +
                      '    </div>' +
                      '  </form>' +
                      '  <div class="modal-footer">' +
                      '    <a class="btn btn-primary pull-left" id="add-entry-from-ticket-submit" href="#"><i class="icon-white icon-ok"></i> {{submit_label}}</a>' +
                      '    <a data-dismiss="modal" class="btn pull-left" href="#">{{cancel_label}}</a>' +
                      '    <div class="pull-right" id="add-entry-from-ticket-error"></div>' +
                      '  </div>' +
                      '</div>';

      
    if (ticket_number === null) {
        // 'new ticket' page
        return;
    }

    // put the button trigger in place
    $('#add-entry-from-ticket-trigger-container').html(
        Mustache.to_html(trigger_tmpl, {'submit_label': 'Add Time'})
    );


    // put the dialog form in place, hidden

    var $dialog_container = $('#add-entry-from-ticket-dialog-container');

    $dialog_container.html(
        Mustache.to_html(dialog_tmpl, {
                                        'submit_label': 'Insert Time Entry',
                                        'cancel_label': 'Cancel',
                                        'project_label': 'Project',
                                        'project_name': project_fullname,
                                        'ticket_label': 'Ticket',
                                        'ticket_number': ticket_number,
                                        'ticket_summary': ticket_summary,
                                        'date_label': 'Date',
                                        'duration_label': 'Duration',
                                        'description_label': 'Description',
                                        'location_label': 'Location',
                                        'location_value': 'RedTurtle'
                                    })
    );


    // activate the trigger
    var $dialog = $('#add-entry-from-ticket-dialog'),
        $date_field = $dialog.find('input[name=date]');

    $dialog.find('select').chosen({disable_search_threshold: 5});
    $date_field.datepicker({
                            dateFormat: 'yy-mm-dd',
                            autoSize: true,
                            showOn: 'both',
                            buttonText: '',
                            buttonImage: '/static/images/date.png',   // XXX get absolute application url here
                            buttonImageOnly: true
                            });

    $.jsonRPC.setup({
        endPoint: '/apis/json/dashboard',
        namespace: ''
    });


    var update_total_duration = function() {
        //
        // query the server and display the sum of te durations for the selected day 
        //
        var $duration_label = $('#add-entry-daily-subtotal-label'),
            $duration_value = $('#add-entry-daily-subtotal-value');

        var duration_error = function(message) {
            $duration_label.text(message);
            $duration_value.text('');
        };

        var duration_ok = function(duration) {
            $duration_label.text('daily total:');
            $duration_value.text(duration);
        };

        $.jsonRPC.request('time_entry_total_duration', {
                            params: [$date_field.val()],
                            success: function(jsonp) {
                                if (jsonp.result.status) {
                                    duration_ok(jsonp.result.duration);
                                } else {
                                    duration_error(jsonp.result.message);
                                }
                            },
                            error: function(jsonp) {
                                duration_error(jsonp.error.message);
                            }
                        }
                       );
    };


    // update total duration when the date changes
    $date_field.change(function() {update_total_duration();});

    // set default date as today.
    $date_field.datepicker('setDate', new Date());


    $('#add-entry-from-ticket-submit').click(function(ev) {
        var entry_ticket = ticket_number,
            entry_date = $date_field.val(),
            entry_description = $dialog.find('textarea[name=description]').val(),
            entry_location = $dialog.find('input[name=location]').val(),
            entry_project = project_id,
            entry_hours = $dialog.find('input[name=duration]').val();

        var feedback_error = function(message) {
            // displays the feedback inside the modal
            //
            var $error_container = $('#add-entry-from-ticket-error');
            $('<div class="alert alert-error pull-right">')
                    .append('<button data-dismiss="alert" class="close" type="button">×</button>')
                    .append(message)
                    .appendTo($error_container.empty())
                    .delay(4000)
                    .fadeOut(0);
        };


        var feedback_ok = function(message) {
            // closes the modal, and temporarily replaces the subnav content with a positive feedback
            //
            var $nav = $('.subnav .nav'),
                $navcontent = $('.subnav .nav>*'),
                $alert = $('<div class="alert alert-success">')
                                .append(message).appendTo('<li>');

            // clear fields for another entry
            $dialog.find('input[name=duration]').val('');
            $dialog.find('textarea[name=description]').val('');

            // show feedback, wait a while, restore subnav
            $navcontent.hide();
            $alert.appendTo($nav);
            $dialog.modal('toggle');
            setTimeout(function() { $alert.remove(); $navcontent.show(); }, 3000);
        };


        $.jsonRPC.request('create_new_simple_time_entry', {
                            params: [entry_ticket, entry_date, entry_hours, entry_description, entry_location, entry_project],
                            success: function(jsonp) {
                                if (jsonp.result.status) {
                                    feedback_ok(jsonp.result.message);
                                } else {
                                    feedback_error(jsonp.result.message);
                                }
                            },
                            error: function(jsonp) {
                                feedback_error(jsonp.error.message);
                            }
                        }
                       );

        ev.preventDefault();
    });


    $('#add-entry-from-ticket-trigger').click(function(ev) {
        ev.preventDefault();
        $dialog.modal('toggle');
        // manually trigger the total duration update
        $date_field.change();
    });

});


