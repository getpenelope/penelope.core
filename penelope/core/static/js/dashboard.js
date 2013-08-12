/*jslint undef: true */
/*global $, deform, document */

$(document).ready(function(){
    "use strict";

    //$(".collapse").collapse();
    $.datepicker.setDefaults($.datepicker.regional.it);
    $.timepicker.setDefaults($.datepicker.regional.it);

    /* set datepicker position to avoid covering the navigation bar */
    $.extend($.datepicker,{_checkOffset:function(inst,offset,isFixed){return offset;}});

    /* executes deform callbacks */
    if (typeof(deform) !== 'undefined') {
        deform.load();
    }

});


