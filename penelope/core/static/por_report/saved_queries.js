/*jslint undef: true */
/*global $, window, document, setTimeout */


$(document).ready(function (){
    "use strict";

    var $form_sq = $('form#saved_query_form');

    var $feedback = function(cls, msg) {
        return $('<div class="alert alert-'+cls+'"></div>').text(msg);
    };

    $form_sq.find('button').click(function on_click(ev) {
        $.post($form_sq.attr('action'),
               {
                  'query_string': window.location.search,
                  'query_meta': $form_sq.serialize(),
                  'submit_type': $(this).val()
                })
            .done(function (msg, textStatus, jqXHR) {
                      $form_sq.hide();
                      $feedback('success', msg).insertAfter($form_sq);
                     }
                  )
            .fail(function (jqXHR) {
                      var $fb = $feedback('error', jqXHR.responseText).insertAfter($form_sq);
                      setTimeout(function() {$fb.remove();}, 3000);
                     }
                  );
    });

    $form_sq.submit(function on_click(ev) {
        /* pressing ENTER equates to pressing the first button, which is either insert or edit */
        ev.preventDefault();
        $form_sq.find('button').first().click();
    });

});


