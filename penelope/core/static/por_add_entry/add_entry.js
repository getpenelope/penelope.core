/*jslint undef: true */
/*global document, $: false */

$(document).ready(function() {
    "use strict";

    var $input = $('#smartadd_text');

    var set_status = function(kw) {
        var i = 0,
            classes = ['error', 'warning', 'success', 'info'],
            $status = $('#smartadd_status').empty();
    
        for (i=0; i<classes.length; i+=1) {
            $status.removeClass('alert-'+classes[i]);
        }

        if (kw['class']) {
            $status.addClass('alert-'+kw['class']);
        }

        if (kw.text) {
            $status.text(kw.text);
            $status.show();
        } else if (kw.html) {
            $status.html(kw.html);
            $status.show();
        } else {
            $status.hide();
        }

        if (kw.hide_delay) {
            $status.delay(kw.hide_delay).hide('fast');
        }

    };


    var update_latest = function(success_cb) {
        $('#latest_entries').load('latest_entries',
                                  function() {
                                      if (success_cb) {
                                          success_cb();
                                     }
                                  });
    };


    var submit = function(cb) {
      $.post('smartadd_submit', $input.val())
          .done(function(msg, textStatus, jqXHR) {
                    // insertion successful; clear the errors and tell everything's alright
                    set_status({'class': 'success', 'text': msg, 'hide_delay': 10000});
                    update_latest(function() {
                        $input.val('');
                    });
                    cb();
                })
          .fail(function(jqXHR) {
                if (jqXHR.status === 400) {
                    // validation errors
                    set_status({'class': 'error', 'html': jqXHR.responseText});
                } else {
                    set_status({'class': 'error', 'text': 'Server error while performing the insertion (>_<)'});
                }
                cb();
          });
    };


    var apply_selected = function() {
        if (this.$menu.is(':hidden')) {
            return true;
        }
        this.fix_ie_selection();
        var $li = this.$menu.find('li.selected');
        var after_cursor = this.input.value.substr(this.input.selectionEnd);
        var before_cursor = this.input.value.substr(0, this.input.selectionStart);
        var matched_part = $li.html().match(/<strong>(.*?)<\/strong>/i)[1] || '';

        before_cursor = before_cursor.substr(0, before_cursor.length - matched_part.length);

        var selected_text = $li.text();

        var selected_number = selected_text.split(' - ')[0].match(/^\d+/);
        if (selected_number) {
            selected_text = selected_number[0];
        }

        this.input.value = before_cursor + selected_text + ' ' + after_cursor;

        this.$menu.hide();
        this.input.focus();
    };


    var days = ['today', 'yesterday'];

    var initialize_autocomplete = function(project_items) {
        var current_jqxhr = null;
        var config = {
            '.*@([^@ ]*)$': function handle_projects(data, cb) {
                    // the list of all projects does not depend on data (the typed text)
                    cb(project_items);
                },
            // see jasmine specs for the regexp
            '.*@.*#(?![0-9]+[ ]+)([^#]+)$': function handle_tickets(data, cb) {
                    // the tickets are contextual to the project and cannot be retrieved in advance
                    if (current_jqxhr) {
                        current_jqxhr.abort();
                    }
                    current_jqxhr = $.getJSON('smartadd_tickets', data, cb);
                },
            '.*!([^! ]*)$': function handle_days(data, cb) {
                    // get options for the days
                    cb(days);
                }
        };

        $input.autocomplete(config, submit);
        $input[0].context_autocomplete.apply_selected = apply_selected;
        update_latest();
    };


    $.getJSON('smartadd_projects', {'text': '@'}, function(project_items) {
        initialize_autocomplete(project_items);
    });

});

