/*jslint undef: true */
/*global document, $, window, Spinner, Mustache: false */

$(document).ready(function() {
    "use strict";

    var $active_popover = null;
    var activate_popover = function($target) {
        if ($active_popover) {
            if ($active_popover[0] === $target[0]) {
                $active_popover.popover('hide');
                $active_popover = null;
                return;
            }
            $active_popover.popover('hide');
            $active_popover = null;
        }
        $target.popover('show');
        $active_popover = $target;
    };

    var render_popover = function(tickets, query_url) {
        var shown_tickets = $.extend(true, [], tickets),        // deep copy
            show_max = 5,
            query_txt = '',
            tmpl = '<table class="outstanding-tickets-table">' +
                   '{{#tickets}}' +
                   '  <tr><td class="outstanding-priority-{{priority_value}}"><a href="{{href}}">{{id}} - {{summary}}</a></td></tr>' +
                   '{{/tickets}}' +
                   '</table>' +
                   '( <em><a href="{{query_url}}">{{query_txt}}</a></em> )';

        if (tickets.length > show_max) {
            shown_tickets = shown_tickets.splice(0, show_max);
            query_txt = 'and ' + (tickets.length - shown_tickets.length).toString() + ' other';
        } else {
            query_txt = 'go to query';
        }

        var ret = Mustache.to_html(tmpl, {'tickets': shown_tickets, 'query_txt': query_txt, 'query_url': query_url});

        return ret;
    };

    var show_badge = function(el, tickets, title, query_url, cls) {
        var $badge = null;

        if (!cls) {
            cls = '';
        }

        if (tickets.length) {
            $badge = $('<span class="badge ' + cls + '" style="cursor:pointer">')
                        .text(tickets.length)
                        .attr({
                            'title': title,
                            'data-content': render_popover(tickets, query_url)
                        }).popover({
                            'html': true,
                            'placement': 'bottom',
                            'trigger': 'manual'
                        });
            $badge.appendTo(el);
            $badge.click(function(ev) {
                activate_popover($(this));
            });
        }
    };

    $(document).mousedown(function(ev) {
        // close active popover when clicking outside it
        var el;
        if ($active_popover !== null) {
            for (el = ev.target; el !== null && !$(el).hasClass('popover'); el = el.parentNode)
                {}
            if (el === null) {
                $active_popover.popover('hide');
                $active_popover = null;
            }
        }
        return true;
    });


    var display_outstanding = function(el) {
        var spinner = new Spinner({'radius': 4, 'length': 4, 'width': 1, 'top': 2, 'left': 5, 'zIndex': 0}),
            trac_uri = $(el).data('trac-uri');
        spinner.spin(el);

        // use the same protocol to obey same-origin policy

        trac_uri = window.location.protocol + trac_uri.split(':').slice(1).join(':');

        $.ajax({
            'url': trac_uri + '/outstanding_tickets/'
        }).success(function(data) {
            spinner.stop();
            show_badge(el, data.tickets_own, 'your open tickets', data.query_url_own, 'badge-success');
            show_badge(el, data.tickets_unassigned, 'unassigned open tickets', data.query_url_unassigned, '');
        });
    };

    $('.outstanding-tickets').each(function() {
        display_outstanding($(this)[0]);
    });

});


