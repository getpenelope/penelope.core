angular.module('kanban', ['ngDragDrop'])
  .controller("KanbanCtrl", function($scope, $http) {

    $scope.columns = [];
    $scope.init = function(board_id){
        $scope.board_id = board_id;
        $http.get(board_id + '/get_tickets.json')
             .success(function(data) {
                $scope.columns = data;
        });
    }

    $scope.addColumn = function() {
        $scope.columns.push({'title': 'New column ' + $scope.columns.length,
                             'wip': 0,
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
             .success(function(data){
                 console.log('updated');
             });
    };

    $scope.handleDrop = function(event, ui) {
        $scope.boardChanged();
    }

  })

.directive('xeditable', function($timeout) {
    return {
        restrict: "A",
        require: "ngModel",
        link: function(scope, element, attrs, ngModel) {
            var loadXeditable = function() {
                angular.element(element).editable({
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
