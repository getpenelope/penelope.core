/*jslint undef: true */
/*global document, $: false */

$(document).ready(function() {

    $("[rel='tooltip']").tooltip();
    $('.spark').sparkline('html',
        {
            type: 'bar',
            height: '50',
            chartRangeMin: 0,
            barWidth: 7,
            barColor: '#fff'}
    );
});

