/*jslint undef: true */
/*global document, jQuery */

(function($) {
    "use strict";



$.fn.tpReport = function tpReport(oConf) {
    var id_tree = oConf.id_tree;
    var groupby = oConf.groupby;
    var sourcetable = oConf.sourcetable;

    var $form = $('form#all_entries');

    var active_jqXHR = null;
    var $active_popover = null;

    var activate_popover = function activate_popover($leaf) {
        var already_open = false;
        if ($active_popover) {
            if ($leaf && ($active_popover[0] === $leaf[0])) {
                already_open = true;
            }
            // close previous popover
            if (!$leaf || ($active_popover[0] !== $leaf[0])) {
                $active_popover.popover('hide');
                $active_popover.closest('table').find('tr.active-popover').removeClass('active-popover');
                $active_popover = null;
            }
        }
        if ($leaf && $leaf.length && !already_open) {
            $leaf.closest('tr').addClass('active-popover');
            $leaf.popover('show');
            $('<img src="/static/jquery.pivot/cancel.png" />').click(function remove_popover() {
                                                                    activate_popover(null);
                                                                }).appendTo($('.popover .title'));
            $active_popover = $leaf;
        }
    };

    //
    // Unwraps a branch of id_tree and returns a list of the contained ids
    //
    var flatten_obj = function flatten_obj(obj) {
        var ret = [],
            key,
            value;

        if (typeof obj.length !== 'undefined') {
            return obj;     // already an array
        }
        for (key in obj) {
            if (obj.hasOwnProperty(key)) {
                value = obj[key];
                ret.push.apply(ret, flatten_obj(value));
            }
        }
        return ret;
    };


    var handle_popover = function handle_popover($target, path) {
        var i,
            ids; // collection of time entry ids

        if (active_jqXHR) {
            // discard previous call, to avoid receiving out-of-order replies
            active_jqXHR.abort();
            active_jqXHR = null;
        }

        if ($target.attr('data-content')) {
            activate_popover($target);
        }

        ids = id_tree;
        for (i=0; i<path.length; i+=1) {
            if (path[i]) {
                ids = ids[path[i]];
            }
        }

        active_jqXHR = $.ajax({
                                url: '/reports/report_te_detail',
                                cache: true,
                                data: {'ids': flatten_obj(ids).join(',')},
                                success: function success(data) {
                                    $target.attr({
                                                 'title': path[path.length-3],
                                                 'data-content': data
                                               }).popover({
                                                 'html': true,
                                                 'placement': 'top',
                                                 'trigger': 'manual'
                                               });
                                    activate_popover($target);
                                    active_jqXHR = null;
                                }});
    };


    var onResultCellClicked = function(data, event) {
        var path=[],
            i,
            $target = $(event.target),
            $tr_target;

        for (i=0; i<data.groups.length; i+=1) {
            path.push(data.groups[i].groupbyval);
        }

        $tr_target = $target.closest('table.pivot tr.level'+(groupby.length-1));
        if ($tr_target.length) {
            // only activate completely unfolded rows
            handle_popover($target, path);
        } else if ($active_popover) {
            // close popovers when folding/clicking on table
            activate_popover(null);
        }
    };


    $('#report_pivoted').pivot({
                                source: sourcetable,
                                formatFunc: function(v) { return (v/60.0/60.0).toFixed(2); },
                                onResultCellClicked: onResultCellClicked
                            });

    $(document).click(function(event) {
        if ($active_popover && !$(event.target).hasClass('resultcell')) {
            // close popovers when folding/clicking on table
            activate_popover(null);
        }
    });


    //
    // The resultcells in aggregated rows are shown in bold.
    // Leaf resultcells are regular weight and clickable.
    // Since the tr.level number can change in regard to the number of displayed columns,
    // the CSS is dynamically generated and injected in the page.
    //
    $('<style type="text/css" rel="stylesheet">' +
      'table.pivot tr.level' + (groupby.length-1) + ' .resultcell {' +
      '    cursor: pointer; ' +
      '    font-weight: normal; ' +
      '    color: #0088CC;' +
      '}' +
      'table.pivot th.groupby.level' + (groupby.length-1) + ' {' +
      '    font-weight: bold; ' +
      '}' +
      '</style>').appendTo('head');

};


}(jQuery));

