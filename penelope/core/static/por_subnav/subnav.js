/*jslint undef: true */
/*global $, window, document, setTimeout */


//
// sub navbar for contextual trac options, or other stuff - make it stick to the top when scrolled
//
$(document).ready(function() {
    "use strict";

    if (window.top !== window.self) {
        // inside iframe, don't touch anything
        return;
    }

    // fix sub nav on scroll
    // adapted & jslintified from the twitter bootstrap home page

    var $win = $(window),
         $nav = $('.subnav'),
         navTop = $('.subnav').length && $('.subnav').offset().top - 40,
         isFixed = 0;

    var processScroll = function() {
        var i, scrollTop = $win.scrollTop();
        if (scrollTop >= navTop && !isFixed) {
            isFixed = 1;
            $nav.addClass('subnav-fixed');
        } else if (scrollTop <= navTop && isFixed) {
            isFixed = 0;
            $nav.removeClass('subnav-fixed');
        }
    };

    processScroll();

    // hack sad times - holdover until rewrite for 2.1
    $nav.on('click', function () {
        if (!isFixed) {
            setTimeout(function () {
                $win.scrollTop($win.scrollTop() - 47);
            }, 10);
        }
    });
    $win.on('scroll', processScroll);
});

