var tekken;
var tekkendata;

function drawChart(){
    function TimeEntriesEnd(data, rowNum){
        return Math.floor(data.getValue(rowNum, 0) / data.getValue(rowNum, 3) * 100)
    }
    function CR2Perc(data, rowNum){
        return Math.floor(data.getValue(rowNum, 1) / data.getValue(rowNum, 3) * 100)
    }
    function Filler2Perc(data, rowNum){
        return Math.floor(data.getValue(rowNum, 2) / data.getValue(rowNum, 3) * 100)
    }
    function CRTooltip(data, rowNum){
        return '<p id="first_tooltip" class="google-visualization-tooltip-item"><strong>Estimated CR:</strong> ' + data.getValue(rowNum,1) + ' days<br/><strong>Total project:</strong> ' + data.getValue(rowNum, 3) + ' days<br/><strong>Time entries:</strong> ' + data.getValue(rowNum, 0) + ' days</p>'
    }
    var view=new google.visualization.DataView(tekkendata);
    columns = [{calc: function() {return ''}, type: 'string'},
        {calc: CR2Perc, type: 'number'},
        {calc: function() {return 0}, type: 'number', role:'interval'},
        {calc: TimeEntriesEnd, type: 'number', role:'interval'},
        {calc: CRTooltip, type: 'string', role:'tooltip', 'properties': {'html':true}},
        {calc: Filler2Perc, type: 'number'},
        {calc: function() {return 'Filler CR'}, type: 'string', role:'tooltip'}
    ]
    view.setColumns(columns);
    tekken.draw(view,
        {title:"Tekken bar",
            width:800, height:90,
            legend: 'none',
            isStacked: true,
            colors: ['#468847', '#F89406'],
            animation:{
                duration: 1000,
                easing: 'out',
            },
            chartArea: {left:'0'},
            tooltip: {isHtml: true },
            hAxis: {viewWindowMode:'explicit',
                viewWindow:{
                    max:100.1,
                    min:0
                }
            }
        }
    );
}

function drawVisualization() {
    // Create and populate the data table.
    tekkendata = new google.visualization.DataTable();
    tekkendata.addColumn('number', 'Time Entries');
    tekkendata.addColumn('number', 'CR estimated');
    tekkendata.addColumn('number', 'CR filler');
    tekkendata.addColumn('number', 'Total project');
    tekkendata.addRows(1);
    tekken = new google.visualization.BarChart(document.getElementById('visualization'));
    google.visualization.events.addListener(tekken, 'onmouseover', refresh_te);
    google.visualization.events.addListener(tekken, 'onmouseout', refresh_te);
    google.visualization.events.addListener(tekken, 'select', refresh_te);
    google.visualization.events.addListener(tekken, 'ready', refresh_te);
    google.visualization.events.addListener(tekken, 'animationfinish', refresh_te);

    function refresh_te(){
        $('path').attr('stroke', 'lightgray').attr('stroke-width','2');
        $('#first_tooltip').parent().css('left', '-=220');
    };
    drawChart()
}

google.setOnLoadCallback(function() {
    drawVisualization();

    // update the total duration for a single table
    var update_project_totals = function($bgb_header) {
        var totals = {},
            total_estimate = 0,
            total_filler = 0,
            total_done = 0,
            total_days = 0,
            $bgb = $bgb_header.next('.bgb-project');

        $bgb.find('tr[data-contract]:visible').each(function() {
            total_done += parseInt($(this).data('duration-done'), 10);
            total_days = parseInt($(this).data('contract-days'), 10);
        });
        $bgb.find('tr[data-contract]:not([data-filler]):visible').each(function() {
            total_estimate += parseInt($(this).data('duration-estimate'), 10);
        });
        $bgb.find('tr[data-filler]:visible').each(function() {
            total_filler += parseInt($(this).data('duration-estimate'), 10);
        });
        return {
            total_estimate: Math.round(total_estimate / 60 / 60 / 8),
            total_filler: Math.round(total_filler / 60 / 60 / 8),
            total_done: Math.round(total_done / 60/ 60 / 8),
            total_days: total_days,
        };
    };

    // update the tekken bar
    var update_tekken = function() {
        var totals = update_project_totals($('.bgb-project-header'));
        console.log(totals);
        tekkendata.setValue(0, 0, totals.total_done);
        tekkendata.setValue(0, 1, totals.total_estimate);
        tekkendata.setValue(0, 2, totals.total_filler);
        tekkendata.setValue(0, 3, totals.total_days);
        drawChart();
    };

    $('#tekken-filter input').change(update_tekken);
    $('#tekken-filter select').change(update_tekken);
    update_tekken();

});
