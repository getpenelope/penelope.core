/*jslint undef: true */
/*global $ */

/* DataTables.net sorting plugin for dates in european format */

(function(){

"use strict";

    var eu_split = function(d) {
        var sep = (d.indexOf('-') !== 1) ? '-' : '/';
        return d.split(sep);
    };

    $.fn.dataTableExt.oSort['eu_date-asc']  = function(a, b) {
        a = eu_split(a);
        b = eu_split(b);
        
        var x = a[2] + a[1] + a[0];
        var y = b[2] + b[1] + b[0];
        
        return ((x < y) ? -1 : ((x > y) ?  1 : 0));
    };
    
    $.fn.dataTableExt.oSort['eu_date-desc'] = function(a, b) {
        a = eu_split(a);
        b = eu_split(b);
        
        var x = a[2] + a[1] + a[0];
        var y = b[2] + b[1] + b[0];
        
        return ((x < y) ? 1 : ((x > y) ?  -1 : 0));
    };

}());

