var WEB_SOCKET_SWF_LOCATION = '/fanstatic/por/por_kanban/js/WebSocketMain.swf'

angular.module('kanban', ['ui.sortable', 'ui.bootstrap'])
  .controller("KanbanCtrl", function($scope, $socketio, $log) {

    $scope.columns = [];
    $scope.backlog = { tasks: [],
        loaded: false};
    $scope.emails = [];
    $scope.user = '';
    $scope.filters = {
        name: ""
    };

    $scope.init = function(board_id, email){
        $scope.board_id = board_id;
        $socketio.emit("join", { board_id: board_id, 
                                 email: email });
        $scope.user = email;
    }

    $scope.gravatar = function(email){
        return md5(email) + '?s=30';
    }

    $scope.addHistory = function(info){
        $socketio.emit("history", { info: info,
                                    user: $scope.user });
    }

    $scope.getColor = function(project){
        return 'background: #' + md5(project).slice(0, 6);
    };

    $scope.getUserImages = function(emails){
        return '<img height="30" width="30" src="https://www.gravatar.com/avatar/'+ $scope.gravatar(emails[0])+'?s=30" />'
    }

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
           }
           else{
               $scope.addHistory('Ticket order changed.');
               $scope.boardChanged();
           }
        },
    };

    $scope.boardChanged = function() {
        $socketio.emit("board_changed", $scope.columns);
    };

    $socketio.on('columns', function(data) {
        $scope.columns = data.value;
        $socketio.emit("get_backlog");
    });

    $socketio.on('backlog', function(data) {
        $scope.backlog.tasks = data.value;
        $scope.backlog.loaded = true;
    });

    $socketio.on('emails', function(data) {
        $scope.emails = data.value;
    });

    $socketio.on("history", function(data) {
        info = '<img height="30" width="30" src="https://www.gravatar.com/avatar/'+ $scope.gravatar(data.user) +'?s=30" /> ' + data.info
        $.pnotify({
            title: 'Board updated',
            text: info,
            type: 'info',
            addclass: "stack-topleft",
            icon: false
        });
    });

    $socketio.on("ticket_changed", function(data){
        $log.log($scope.columns);
        $log.log(data);
    });

  })

.controller("TaskController", function($scope, $http, $socketio) {

})

.controller("BacklogController", function($scope) {

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
    }

})


.directive('xeditable', function($timeout) {
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

.factory("$socketio", function($rootScope) {
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
