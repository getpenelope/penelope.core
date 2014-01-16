/*jslint undef: true */
/*global document, jQuery: false */

(function($) {
    "use strict";



var fill_select = function ($select, options) {
    // populates a select element with new options,
    // while keeping the old ones.
    //
    // options is a list of {'id':.., 'name'..'} objects

    // previous: all previously selected options, as a list
    var previous = $select.val();
    if (typeof(previous)==='string') {
        previous = [previous];
    }
    if (!previous) {
        previous = [];
    }

    // if there is an empty option, we retain it
    var $empty = $select.find('option[value=""]').clone();

    $select.empty();
    $select.append($empty);

    options.sort(function (a, b) {
                    var an=a.name.toLowerCase(),
                        bn=b.name.toLowerCase();
                    return (an>bn) - (an<bn);
                });

    $.each(options, function (i, e) {
                        var op = $('<option>').val(e.id).text(e.name);
                        if (previous.indexOf(e.id) !== -1) {
                            op.attr('selected', 'selected');
                        }
                        $select.append(op);
                    });

    // rebuild chosen
    $select.trigger("chosen:updated");
};



$(document).ready(function (ev) {
    // Deform applies a css_class on all the options.
    // New versions might apply it to the select as well, or in substitution.
    var $customer = $('.customer-select', this).closest('select');
    var $project = $('.project-select', this).closest('select');
    var $cr = $('.customer-request-select', this).closest('select');
    var $contract = $('.contract-select', this).closest('select');

    // retrieves the customer-project-request data
    $.ajax({
             url: '/reports/project_tree',
             cache: false,
             success: function (customers) {
                 // act upon customer change
                 $customer.chosen().change(function (ev) {
                     var customer_value = $customer.val();
                     if (customer_value===''){
                         return
                     };
                     var projects = [];
                     var customer_requests = [];
                     var contracts = [];
                     $.each(customers, function (i, c) {
                                          // if customer is empty, you might want to display all projects instead of none:
                                          // if (customer_value==='' || customer_value===c.id) {
                                          if (customer_value===c.id) {
                                              projects.push.apply(projects, c.projects);
                                          }
                                      });

                     $.each(projects, function (i, p) {
                                          customer_requests.push.apply(customer_requests, p.customer_requests);
                                          contracts.push.apply(contracts, p.contracts);
                                      });

                     fill_select($project, projects);
                     fill_select($cr, customer_requests);
                     fill_select($contract, contracts);
                 });


                 // acts upon project change
                 $project.chosen().change(function (ev) {
                     var project_value = $project.val();
                     if (project_value===''){
                         return
                     };
                     var customer_value = $customer.val();
                     var customer_requests = [];
                     var contracts = [];
                     $.each(customers, function (i, c) {
                                            $.each(c.projects, function (i, p) {
                                                if ((project_value==='' && (customer_value==='' || customer_value===c.id)) || project_value===p.id) {
                                                    customer_requests.push.apply(customer_requests, p.customer_requests);
                                                    contracts.push.apply(contracts, p.contracts);
                                                }
                                            });
                                      });

                     fill_select($cr, customer_requests);
                     fill_select($contract, contracts);
                 });


                 // apply filtering to pre-populated form
                 $customer.trigger('change');
                 $project.trigger('change');

             }
    });

});



}(jQuery));

