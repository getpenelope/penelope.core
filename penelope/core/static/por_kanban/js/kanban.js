angular.module('kanban', ['ui.sortable'])
  .controller("KanbanCtrl", function($scope, $http) {

    $scope.columns = [];
    $scope.backlog = { tasks: []
                     };

    $scope.init = function(board_id){
        $scope.board_id = board_id;
        $http.get(board_id + '/get_columns.json')
             .success(function(data) {
                $scope.columns = data;
        });
        $http.get(board_id + '/get_backlog.json')
             .success(function(data) {
                $scope.backlog.tasks = data;
                $scope.backlog.loading = false;
        });
    }

    $scope.gravatar = function(email){
        return md5(email);
    }

    $scope.openModal = function(url){
        $('#ModalTicket').on('show', function () {
            $('.modal .preloader').show();
            $('iframe').hide();
            $('iframe').height('200');
            $('iframe').attr("src", url);
            $('iframe').one('load', function() {
                $('.modal .preloader').hide();
                $('iframe').height('650');
                $('iframe').show();
            });
        });
        $('#ModalTicket').modal({show:true})
    }

    $scope.getColor = function(project){
        return 'background: #' + md5(project).slice(0, 6);
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
        $http.post($scope.board_id + '/post_columns.json', $scope.columns)
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
