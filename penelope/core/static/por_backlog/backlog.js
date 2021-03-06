/*jslint undef: true */
/*global $, document, console: false */

$(document).ready(function(){
    "use strict";

    var format_duration = function(secs) {
        var days = secs / 60 / 60 / 8;
        return (Math.round(days*100)/100).toFixed(2);
    };

    var fill_duration = function ($duration, secs) {
        // align visible digits at the decimal dot.
        // this is an horrible, horrible hack.
        var parts = format_duration(secs).split('.'),
            part_int = parts[0],
            part_dec = parts[1];

        if (isNaN(secs)) {
            $duration.empty();
            return;
        }

        if (part_dec === '00') {
            $duration.empty().append($('<span>'+part_int+'</span>')).append($('<span class="invisible">.00</span>'));
        } else {
            $duration.text(part_int+'.'+part_dec);
        }
    };

    var fill_done = function ($duration, secs, $me) {
        // align visible digits at the decimal dot.
        // this is an horrible, horrible hack.
        var parts = format_duration(secs).split('.'),
        part_int = parts[0],
        part_dec = parts[1];

        if (isNaN(secs)) {
            $duration.empty();
            return;
        }

        if (part_dec === '00') {
            var duration_text = $('<span>'+part_int+'</span>').append($('<span class="invisible">.00</span>'));
        } else {
            var duration_text = $('<span>' + part_int+'.'+part_dec+'</span>');
        }
        var report_url = "/reports/report_all_entries?_charset_=UTF-8&__formid__=all_entries&customer_id=&project_id=&__start__=customer_requests%3Asequence&customer_requests="+$me.data('crId')+"&__end__=customer_requests%3Asequence&__start__=contracts%3Asequence&__end__=contracts%3Asequence&date_from=&date_to=&__start__=users%3Asequence&__end__=users%3Asequence&groupbyfirst=project.contract.request.user.date&submit=submit"
        var estimations = $('<a target="_blank" href="'+report_url+'" title="Open report for that customer request"></a>').append(duration_text);
        $duration.empty().append(estimations);
    };

    var fill_estimated = function ($duration, secs, $me) {
        // align visible digits at the decimal dot.
        // this is an horrible, horrible hack.
        var parts = format_duration(secs).split('.'),
            part_int = parts[0],
            part_dec = parts[1];

        if (isNaN(secs)) {
            $duration.empty();
            return;
        }

        if (part_dec === '00') {
            var duration_text = $('<span>'+part_int+'</span>').append($('<span class="invisible">.00</span>'));
        } else {
            var duration_text = $('<span>' + part_int+'.'+part_dec+'</span>');
        }
        var estimations = $('<a href="#" rel="popover" data-original-title="Estimations"></a>').append(duration_text);
        $duration.empty().append(estimations);
        if (secs != 0) {
            estimations.popover({trigger: 'hover',
                                 html: true,
                                 "content": function(){
                                    var div_id =  "div-id-" + $.now();
                                    return details_in_popup($me.find('td:nth-child(1) a').attr('href')+'/estimations.html', div_id);
                                }});
        }
    };

    var details_in_popup = function(link, div_id){
        $.ajax({
            url: link,
            success: function(response){
                $('#'+div_id).html(response)}});
                return '<div id="'+ div_id +'">Loading...</div>'
    };

    var format_percentage = function(value) {
        return (Math.round(value*100)/100).toFixed(2);
    };

    var fill_percentage = function ($percentage, value) {
        // align visible digits at the decimal dot.
        // this is an horrible, horrible hack.
        var parts = format_percentage(value).split('.'),
            part_int = parts[0],
            part_dec = parts[1];

        if (isNaN(value)) {
            $percentage.empty();
            return;
        }

        if (part_dec === '00') {
            $percentage.empty().append($('<span>'+part_int+'</span>')).append($('<span class="invisible">.00</span>')).append($('<span>%</span>'));
        } else {
            $percentage.text(part_int+'.'+part_dec+'%');
        }
    };

    // fill duration 'estimate' column
    $('[data-duration-estimate]').each(function() {
                            var secs = parseInt($(this).data('duration-estimate'), 10),
                                $duration = $(this).find('td:nth-child(3)');
                            fill_estimated($duration, secs, $(this));
    });

    // fill duration 'done' column
    $('[data-duration-done]').each(function() {
                            var secs = parseInt($(this).data('duration-done'), 10),
                                $duration = $(this).find('td:nth-child(4)');
                            fill_done($duration, secs, $(this));
    });
    // fill duration 'percentage' column
    $('[data-duration-percentage]').each(function() {
                            var secs = parseInt($(this).data('duration-percentage'), 10),
                                $duration = $(this).find('td:nth-child(5)');
                            fill_percentage($duration, secs);
    });


    // checks if a given row is selected from the main filter
    var check_filter = function($tr) {
        var $chk_workflow = $('#workflow_'+$tr.data('workflow-state')),
            $chk_contract = $('#contract').val() === $tr.data('contract');
        return (
                  (($chk_workflow.length===0) || $chk_workflow.is(':checked')) && 
                  ($chk_contract)
        );
    };

    // update the total duration for a single table
    var update_project_totals = function($bgb_header) {
        var totals = {},
            total_estimate = 0,
            total_done = 0,
            percentages = new Array(),
            total_percentage = 0,
            matching_crs = 0,
            $bgb = $bgb_header.next('.bgb-project');

        $bgb.find('tr[data-workflow-state]').each(function() {
            if (check_filter($(this))) {
                total_estimate += parseInt($(this).data('duration-estimate'), 10);
                total_done += parseInt($(this).data('duration-done'), 10);
                percentages.push(parseInt($(this).data('duration-percentage'), 10));
                matching_crs += 1;
            }
        });
        if (total_done > 0 && total_estimate > 0){
            total_percentage = (total_done / total_estimate) * 100;
        }
        else {
            total_percentage = 0;
        }
        fill_duration($bgb_header.find('.total-estimate'), total_estimate);
        fill_duration($bgb_header.find('.total-done'), total_done);
        fill_percentage($bgb_header.find('.total-percentage'), total_percentage);

        // if there are no matching customer requests, hide the whole project.
        if (!matching_crs) {
            $bgb_header.hide();
            $bgb.hide();
        } else {
            $bgb_header.show();
            if (!$bgb.hasClass('hide')) {
                $bgb.show();
            }
        }

        return {
            total_estimate: total_estimate,
            total_done: total_done,
            total_percentage: total_percentage
        };
    };


    // update totals for all the tbodies
    var update_totals = function() {
        var bigtotal_estimate = 0,
            bigtotal_done = 0,
            percentages = new Array(),
            bigtotal_percentage = 0;
        $('.bgb-project-header').each(function() {
            var totals = update_project_totals($(this));
            bigtotal_estimate += (totals.total_estimate || 0);
            bigtotal_done += (totals.total_done || 0);
            if (totals.total_percentage != -1){
                percentages.push(totals.total_percentage || 0);
            }
        });
        if (percentages.length){
            bigtotal_percentage = (percentages.reduce(function(a, b) { return a + b }) / (percentages.length));
        } else {
            bigtotal_percentage = 0;
        }

        fill_duration($('.bigtotal-estimate'), bigtotal_estimate);
        fill_duration($('.bigtotal-done'), bigtotal_done);
        fill_percentage($('.bigtotal-percentage'), bigtotal_percentage);
    };

    // upon clicking the header, show/collapse the project's bgb
    // the header will not be clickable (no trigger class) if there is only one project in the page
    $('.bgb-project-trigger').click(function(ev) {
        var $bgb = $(this).next('.bgb-project');
        if ($bgb.is(':hidden')) {
            $(this).find('.icon-chevron-right').removeClass('icon-chevron-right').addClass('icon-chevron-down');
        } else {
            $(this).find('.icon-chevron-down').removeClass('icon-chevron-down').addClass('icon-chevron-right');
        }

        // toggle manually to use the 'hide' class as a visibility hint for the filter enforcer
        if ($bgb.hasClass('hide')) {
            $bgb.removeClass('hide');
            $bgb.show();
        } else {
            $bgb.addClass('hide');
            $bgb.hide();
        }

        update_totals();
        return false;
    });



    // update visibility of the customer requests
    var refresh_trs = function() {
        var matching = 0;
        $('tr[data-workflow-state]').each(function() {
            if (check_filter($(this))) {
                $(this).show();
                matching += 1;
            } else {
                $(this).hide();
            }
        });
        update_totals();
        if (matching===0) {
            $('.backlog-table-headers').hide();
            $('.backlog-no-rows').show();
            $('.bigtotal-estimate').hide();
            $('.bigtotal-done').hide();
            $('.bigtotal-percentage').hide();
        } else {
            $('.backlog-table-headers').show();
            $('.backlog-no-rows').hide();
            $('.bigtotal-estimate').show();
            $('.bigtotal-done').show();
            $('.bigtotal-percentage').show();
        }
    };

    $('#backlog-filter input').change(refresh_trs);
    $('#tekken-filter input').change(refresh_trs);
    $('#tekken-filter select').change(refresh_trs);
    refresh_trs();


    // Expand all projects
    $('#backlog-expand-all').click(function(ev) {
        $('.bgb-project-header').each(function(ev) {
            var $bgb = $(this).next('.bgb-project');
            if ($bgb.is(':hidden')) {
                $(this).click();
            }
        });
        return false;
    });

    // Collapse all projects
    $('#backlog-collapse-all').click(function(ev) {
        $('.bgb-project-header').each(function(ev) {
            var $bgb = $(this).next('.bgb-project');
            if (!$bgb.is(':hidden')) {
                $(this).click();
            }
        });
        return false;
    });

});

