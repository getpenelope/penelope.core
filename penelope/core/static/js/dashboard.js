/*jslint undef: true */
/*global $, deform, document */

$(document).ready(function(){
    "use strict";

    //$(".collapse").collapse();
    $.datepicker.setDefaults($.datepicker.regional.it);
    $.timepicker.setDefaults($.datepicker.regional.it);

    /* set datepicker position to avoid covering the navigation bar */
    $.extend($.datepicker,{_checkOffset:function(inst,offset,isFixed){return offset;}});

    /* executes deform callbacks */
    if (typeof(deform) !== 'undefined') {
        deform.load();
    }

});

var WEB_SOCKET_SWF_LOCATION = '/fanstatic/por/por_kanban/js/WebSocketMain.swf'
var feedly = angular.module('feedly', [])

feedly.controller("FeedlyController", function($scope, $socketio, $log) {
    $scope.activities = [];
    $scope.unseen_activities = 0;
    $scope.init = function(user_id){
        $socketio.emit("join", { user_id: user_id });
        $scope.user = user_id;
    };

    $scope.mark_all_seen = function() {
        if ($scope.unseen_activities > 0){
            $scope.unseen_activities = 0;
            $socketio.emit("mark_all_seen", {user_id: $scope.user});
        };
    }

    $scope.gravatar = function(email){
        return md5(email) + '?s=45';
    };

    $socketio.on('activities', function(data) {
        $scope.activities = data['activities']
        $scope.unseen_activities = data['count_unseen']
    });

})

feedly.factory("$socketio", function($rootScope) {
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
