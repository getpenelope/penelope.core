angular.module('kanban', ['ui.sortable'])
  .controller("KanbanCtrl", function($scope, $http) {

    $scope.columns = [];
    $scope.init = function(board_id){
        $scope.board_id = board_id;
        $http.get(board_id + '/get_tickets.json')
             .success(function(data) {
                $scope.columns = data;
        });
    }

    $scope.gravatar = function(email){
        return md5(email);
    }

    $scope.getWIP = function(column_id){
        console($scope.columns[column_id].tasks.length, $scope.columns[column_id].wip)
        if ($scope.columns[column_id].tasks.length >= $scope.columns[column_id].wip){
            return 'blabla'
        }
    };

    $scope.getColor = function(column_id, task_id){
        return 'background: #' + md5($scope.columns[column_id].tasks[task_id].project).slice(0, 6);
    };

    $scope.addColumn = function() {
        $scope.columns.push({'title': 'New column ' + $scope.columns.length,
                             'wip': 3,
                             'tasks': []});
        $scope.boardChanged();
    };

    $scope.removeColumn = function(item) {
        if (item != 0){
          $scope.columns.splice(item, 1);
          $scope.boardChanged();
       };
    };

    $scope.boardChanged = function() {
        $http.post($scope.board_id + '/post_tickets.json',
                   $scope.columns.slice(1, $scope.columns.length))
    };

    $scope.sortableOptions = {
        placeholder: "ui-state-highlight",
        connectWith: ".task_pool",
        update: function(e, ui) {
           $scope.boardChanged();
        },
    };

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
