$penelope.controller("UserStatsController", function($scope, $http) {

    $scope.init = function () {
        $http.get("user_stats.json")
            .success(function(data) {
                console.log(data);
                $scope.last_week_hours = data['last_week_hours'];
                $scope.last_week_hours_legend = data['last_week_hours_legend'];
                $scope.last_week_dow = data['last_week_dow'];
                $scope.last_week_tickets = data['last_week_tickets'];
                $scope.last_week_tickets_legend = data['last_week_tickets_legend'];
            })
    }

    $scope.init();

});
