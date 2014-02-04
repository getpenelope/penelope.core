/*jslint undef: true */
/*global $, deform, document */

var WEB_SOCKET_SWF_LOCATION = '/fanstatic/por/por_kanban/js/WebSocketMain.swf'
var $penelope = angular.module('penelope', ['ui.sortable', 'ui.bootstrap', 'ngAnimate', 'angles']);

$penelope.controller("FeedlyController", function($scope, $socket_feedly, $log) {
    $scope.activities = [];
    $scope.unseen_activities = 0;
    $scope.init = function(user_id){
        $socket_feedly.emit("join", { user_id: user_id });
        $scope.user = user_id;
    };

    $scope.mark_all_seen = function() {
        if ($scope.unseen_activities > 0){
            $scope.unseen_activities = 0;
            $socket_feedly.emit("mark_all_seen", {user_id: $scope.user});
        };
    }

    $scope.gravatar = function(email){
        return md5(email) + '?s=45';
    };

    $socket_feedly.on('activities', function(data) {
        $scope.activities = data['activities']
        $scope.unseen_activities = data['count_unseen']
    });

})

$penelope.directive('animateOnChange', function($animate, $log) {
    return function(scope, elem, attr) {
        scope.$watch(attr.animateOnChange, function(nv,ov) {
            if (nv!=ov) {
                $animate.addClass(elem, 'newtask', function() {
                    $animate.removeClass(elem, 'newtask');
                });
            }
        })
    }
})

$penelope.factory("$socket_feedly", function($rootScope) {
  var socket = io.connect('/feedly');
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
