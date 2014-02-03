/*jslint undef: true */
/*global $, deform, document */

$penelope.controller("KanbanCtrl", function($scope, $socket_kanban, $log, $animate) {
    $scope.columns = [];
    $scope.filters = {name: ""};
    $scope.backlog = {tasks: [], loaded: false};
    $scope.emails = [];
    $scope.user = '';
    $scope.tickets = [];

    $scope.hash_tickets = function() {
        $scope.tickets = [];
        for (var i=0; i < $scope.columns.length; i++) {
            for (var j=0; j < $scope.columns[i].tasks.length; j++){
                if ($scope.columns[i].tasks[j] != undefined){
                    $scope.tickets.push($scope.columns[i].tasks[j]['id']);
                }
            }
        }
    };

    $scope.init = function(board_id, email){
        $scope.board_id = board_id;
        $socket_kanban.emit("join", { board_id: board_id, 
                                 email: email });
        $scope.user = email;
    };

    $scope.gravatar = function(email){
        return md5(email) + '?s=30';
    };

    $scope.addHistory = function(info){
        $socket_kanban.emit("history", { info: info,
                                    user: $scope.user });
    };

    $scope.getPriorityClass = function(task) {
        if (task.priority === true){
            return 'priority'
        }
        else if (["blocker", "critical"].indexOf(task.priority) > -1){
            return 'priority'
        }
        else {
            return ''
        }
    };

    $scope.getColor = function(project){
        return 'background: #' + md5(project).slice(0, 6);
    };

    $scope.getUserImages = function(emails){
        return '<img height="30" width="30" src="https://www.gravatar.com/avatar/'+ $scope.gravatar(emails[0])+'?s=30" />'
    };

    $scope.addColumn = function() {
        $scope.columns.push({'title': 'New column ' + $scope.columns.length,
                             'wip': 3,
                             'tasks': []});
        $scope.addHistory('New column created.');
        $scope.boardChanged();
    };

    $scope.removeColumn = function(item) {
        $scope.columns.splice(item, 1);
        $scope.addHistory('Column ' + (item + 1) + ' removed.');
        $scope.boardChanged();
    };

    $scope.sortableOptions = {
        placeholder: "ui-state-highlight",
        connectWith: ".task_pool",
        distance: 15,
        update: function(e, ui) {
           if(ui.sender){
               $scope.addHistory('Ticket moved between columns.');
               $scope.boardChanged();
               $scope.hash_tickets();
           }
           else{
               $scope.addHistory('Ticket order changed.');
               $scope.boardChanged();
           }
        },
    };

    $scope.boardChanged = function() {
        $socket_kanban.emit("board_changed", $scope.columns);
    };

    $socket_kanban.on('columns', function(data) {
        $scope.columns = data.value;
        $scope.hash_tickets();
        $socket_kanban.emit("get_backlog");
    });

    $socket_kanban.on('backlog', function(data) {
        $scope.backlog.tasks = data.value;
        $scope.backlog.loaded = true;
    });

    $socket_kanban.on('emails', function(data) {
        $scope.emails = data.value;
    });

    $socket_kanban.on("history", function(data) {
        info = '<img height="30" width="30" src="https://www.gravatar.com/avatar/'+ $scope.gravatar(data.user) +'?s=30" /> ' + data.info
        $.pnotify({
            title: 'Board updated',
            text: info,
            type: 'info',
            addclass: "stack-topleft",
            icon: false
        });
    });

    function update_ticket(ticket, data){
        for (var i=0; i < $scope.columns.length; i++) {
            for (var j=0; j < $scope.columns[i].tasks.length; j++){
                if ($scope.columns[i].tasks[j]['id'] == ticket){
                    angular.extend($scope.columns[i].tasks[j], data);
                }
            }
        };
        $scope.boardChanged();
    };

    $socket_kanban.on("ticket_changed", function(data){
        var tickets = Object.keys(data);
        for (var i=0; i < tickets.length; i++) {
            if ($scope.tickets.indexOf(tickets[i]) > -1){
                data[tickets[i]]['modified'] = new Date().getTime();
                update_ticket(tickets[i], data[tickets[i]]);
            }
        }
    });

  })

$penelope.controller("TaskController", function($scope, $http, $socket_kanban) {
    $scope.removeTask = function(index){
        $scope.column.tasks.splice(index,1);
        $scope.hash_tickets();
        $scope.boardChanged();
    };
})

$penelope.controller("BacklogController", function($scope) {
    $scope.isExcludedByFilter = applySearchFilter();
    $scope.$watch(
        "filters.name",
        function( newName, oldName ) {
            if ( newName === oldName ) {
                return;
            }
            applySearchFilter();
        }
    );
    $scope.isExcludedByFilter = applySearchFilter();
    function applySearchFilter() {

        var filter = $scope.filters.name.toLowerCase();
        var name = $scope.task.summary.toLowerCase();
        var isSubstring = ( name.indexOf( filter ) !== -1 );
        $scope.isExcludedByFilter = ! isSubstring;
    };

})

$penelope.directive('xeditable', function($timeout) {
    return {
        restrict: "A",
        require: "ngModel",
        link: function(scope, element, attrs, ngModel) {
            var loadXeditable = function() {
                angular.element(element).editable({
                    mode: 'inline',
                    validate: function(value) {
                        if($.trim(value) == '') {
                            return 'This field is required';
                        }
                    },
                    display: function(value, srcData) {
                        ngModel.$setViewValue(value);
                        scope.$apply();
                    },
                    success: function(response, newValue) {
                        scope.addHistory('Column modified.');
                        scope.boardChanged();
                    }
                });
            }
            $timeout(function() {
                loadXeditable();
            }, 10);

        }
    }
})

$penelope.factory("$socket_kanban", function($rootScope) {
  var socket = io.connect('/kanban');
  return {
    on: function (eventName, callback) {
      socket.on(eventName, function () {
        var args = arguments;
        $rootScope.$apply(function () {
          callback.apply(socket, args);
        });
      });
    },
    emit: function (eventName, data, callback) {
      socket.emit(eventName, data, function () {
        var args = arguments;
        $rootScope.$apply(function () {
          if (callback) {
            callback.apply(socket, args);
          }
        });
      })
    }
  };
})
