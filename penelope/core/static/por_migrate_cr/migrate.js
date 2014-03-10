$(document).ready(function(){

    var migrate_filter = {'.date_column': {},
                          '.ticket_column': {}};

    function update_te(inputs, stat){
        inputs.each(function(){
            if ($(this).is(':checked')!=stat){
                $(this).attr('checked', stat);
                if (stat===true){
                    t = $(this).data('time');
                }
                else{
                    t = -Math.abs($(this).data('time'));
                }
                update_selected_tes(t);
            }
        });
    };

    function update_selected_tes(t){
        $('#selected_tes').html(function(i) { 
            val = $(this).data('total') + t;
            $(this).data('total', val);
            if (val<0.001){
                return ''
            }
            else {
                return (val).toFixed(2) + ' (days) selected'
            }
        });
    };

    $('input[name="te"]').click(function(){
        if ($(this).is(':checked')){
            t = $(this).data('time');
        }
        else {
            t = -Math.abs($(this).data('time'));
        };
        update_selected_tes(t);
    });

    $('input.check_all').click(function() {
        update_te($(this).closest('form').find('input[type=checkbox]:visible'), $(this).is(':checked'));
    });

    $("a[rel='tooltip']").tooltip();

    Date.prototype.addDays = function(days) {
        var dat = new Date(this.valueOf())
        dat.setDate(dat.getDate() + days);
        return dat;
    }

    function getDates(startDate, stopDate) {
        var dateArray = new Array();
        var currentDate = startDate;
        while (currentDate <= stopDate) {
            dateArray.push($.datepicker.formatDate('yy-mm-dd', currentDate));
            currentDate = currentDate.addDays(1);
        }
        return dateArray;
    }

    var update_entries = function(filter){
        $.extend(true, migrate_filter, filter)

        var date_column = migrate_filter['.date_column'];
        if (date_column) {
            if (date_column.from && date_column.to){
                migrate_filter['.date_column']['filter'] = getDates(new Date(date_column.from), new Date(date_column.to))
            }
            else{
                migrate_filter['.date_column']['filter'] = null;
            }
        }
        var jo = $("#fbody").find("tr");

        jo.hide();
        if (!migrate_filter['.date_column'].filter && !migrate_filter['.ticket_column'].filter){
            jo.show();
            return
        }

        jo.filter(function (i, v) {
            for (var filter in migrate_filter) {
                if (migrate_filter.hasOwnProperty(filter) && migrate_filter[filter]['filter']) {
                    var $t = $(this).find(filter)
                    var $check = migrate_filter[filter]['filter'];
                    if (jQuery.inArray($t.data('filter'), $check) > -1){
                        return true
                    }
                    else {
                        return false;
                    }
                }
            }
        })
        .show();
    };

    $('#new_cr').chosen();

    $('#filter_date_from').datepicker({
        dateFormat: 'yy-mm-dd',
        autoSize: false,
        showOn: 'both',
        buttonText: '',
        buttonImage: '/static/penelope/images/date.png',
        buttonImageOnly: true
    }).change(function(){
       update_entries({'.date_column': {from: $(this).val() }});
    });
    $('#filter_date_to').datepicker({
        dateFormat: 'yy-mm-dd',
        autoSize: false,
        showOn: 'both',
        buttonText: '',
        buttonImage: '/static/penelope/images/date.png',
        buttonImageOnly: true
    }).change(function(){
       update_entries({'.date_column': {to: $(this).val() }});
    });

    $("#filter_tickets").chosen().change(function(){
        update_entries({'.ticket_column': {'filter':  $(this).val()}});
    })

});
