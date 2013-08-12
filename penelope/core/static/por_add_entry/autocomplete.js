/*jslint undef: true */
/*global document, $, window, setTimeout, Spinner */

// - options[i].itemsgetter instead of options[i].items
// - lazy conversion of items to string
// - removed support for 'suffix' (now hardcoded, see below) and explicit regexp
// - fix for charCode vs keyCode (END=35, #=35) using e.which
//      see http://mozilla.pettay.fi/moztests/events/browser-keyCodes.htm
//          http://api.jquery.com/event.which/
// - jslint compliance.
// - added submit_callback


$(document).ready(function() {
    "use strict";

    var VK_ESC = 27,
        VK_DOWN = 40,
        VK_UP = 38,
        VK_TAB = 9,
        VK_RETURN = 13,
        VK_LEFT = 37,
        VK_RIGHT = 39,
        VK_HOME = 36,
        VK_END = 35,
        suffix = ' ';

    function is(type, obj) {
        return Object.prototype.toString.call(obj) === "[object "+ type +"]";
    }

    // function is_special_char(char_code) {
    //     return $.inArray(char_code, [VK_RETURN, VK_ESC, VK_UP, VK_DOWN,
    //         VK_LEFT, VK_RIGHT, VK_HOME, VK_END]) !== -1;
    // }

    function prepare_input_parameters(items) {
        var options = [], i;
        for (i in items) {
            if (items.hasOwnProperty(i)) {
                if (is('Array', items[i]) || is('Function', items[i])) {
                    options.push({
                        regex: new RegExp(i.length === 1 ? '\\' + i + '([^\\' + i + ']*)$' : i),
                        itemsgetter: items[i]
                    });
                } else {
                    options.push(items[i]);
                }
            }
        }
        return options;
    }

    function Context_Autocomplete(dom_input, options, submit_callback) {

        this.handle_special_char = function (char_code) {
            switch (char_code) {
                case VK_TAB:
                case VK_RETURN:
                    this.apply_selected();
                    return false;
                case VK_ESC:
                    this.$menu.hide();
                    return false;
                case VK_HOME:
                case VK_END:
                    this.$menu.find('li.selected').removeClass('selected');
                    this.$menu[0].firstChild[(char_code === VK_HOME ? 'first' : 'last') + 'Child'].className = 'selected';
                    return false;
                case VK_DOWN:
                case VK_UP:
                    var is_down_arrow = (char_code === VK_DOWN);
                    var siblingNode = is_down_arrow ? 'nextSibling' : 'previousSibling';
                    var limitNode = is_down_arrow ? 'first' : 'last';
                    var $li = this.$menu.find('li.selected');
                    if ($li.size() === 1) {
                        if ($li[0][siblingNode]) {
                            $($li[0][siblingNode]).addClass('selected');
                            $li.removeClass('selected');
                        }
                    } else {
                        this.$menu[0].firstChild[limitNode + 'Child'].addClass('selected');
                    }
                    return false;
                default:
                    return true;
            }
        };

        /**
         * returns count of items populated
         */
        this.populate_with_items = function (items, value) {
            var options = [], item, len = items.length, i, match_index;
            if (typeof value === 'undefined') {
                value = '';
            } else {
                value = value.toLowerCase();
            }
            var first = true;
            for (i = 0; i < len; i++) {
                item = items[i].toString();
                if (item) {
                    match_index = item.toLowerCase().indexOf(value);
                    if (match_index > -1) {
                        options.push('<li' + (first ? ' class="selected"' : '') +
                            ' onmouseover="jQuery(this).addClass(\'selected\').siblings(\'.selected\').removeClass(\'selected\')">' +
                            item.substr(0, match_index) + '<strong>' + item.substr(match_index, value.length) + '</strong>' +
                            item.substr(match_index + value.length) + '<\/li>');
                        first = false;
                    }
                }
            }
            this.$menu.html('<ul>' + options.join('') + '<\/ul>');
            return options.length;
        };

        this.update_position = function (matched_part) {
            var absolute_offset = {left: this.input.offsetLeft, top: this.input.offsetTop};
            var op = this.input;
            while (true) {
                op = op.offsetParent;
                if (!op) {
                    break;
                }
                absolute_offset.left += op.offsetLeft;
                absolute_offset.top += op.offsetTop;
            }
            this.fix_ie_selection();
            this.$fake_input.html(this.input.value
                .substr(0, this.input.selectionStart - matched_part.length)
                .replace(/ /g, '&nbsp;')
            );
            var cursor_offset = this.$fake_input.width();

            absolute_offset.left += cursor_offset;
            absolute_offset.top += this.$input.height();

            this.$menu.css(absolute_offset);
        };

        this.search_match = function(itemsgetter, value_for_match, foundcb) {
            var self = this;
            self.spin_on();
            itemsgetter(
                {'text': this.$input.val()},
                function filter_items(items) {
                    self.spin_off();
                    var j;
                    for (j in items) {
                        if (items.hasOwnProperty(j)) {
                            if ((items[j].toString()).toLowerCase().indexOf(value_for_match) !== -1) {
                                foundcb();
                                var length = self.populate_with_items(items, value_for_match);
                                if (length > 0 && self.$menu.is(':hidden')) {
                                    self.update_position(value_for_match);
                                    self.$menu.show();
                                } else if (length === 0 && self.$menu.is(':visible')) {
                                    self.$menu.hide();
                                }
                                break;
                            }
                        }
                    }
                }
            );
        };


        this.handle_literal_char = function (char_code) {
            var val = this.input.value.substr(0, this.input.selectionStart),
                items = false, value_for_match,
                len = this.options.length,
                i, res, found=false;

            var foundcb = function() {
                found = true;
            };

            for (i = 0; i<len; i++) {
                res = val.match(this.options[i].regex);
                if (res && res.length > 1) {
                    this.search_match(this.options[i].itemsgetter, res[1].toLowerCase(), foundcb);
                }
            }
            if (!found) {
                this.$menu.hide();
            }
        };

        this.handle_change = function (e) {
            var self = this;
            e = e || window.event;
            var char_code = e.keyCode || e.charCode;
            if (!char_code) {
                return true;
            }

            if (!e.charCode || char_code===VK_RETURN) {
                if (this.$menu.is(':visible') && !this.handle_special_char(char_code)) {
                    // RETURN picks a menu item
                    return false;
                } else if (char_code===VK_RETURN) {
                    // RETURN submits the form
                    if (this.submit_callback && e.type === 'keypress' && !self.spinning) {
                        // do not handle keydown (chrome gets here twice)
                        self.spin_on();
                        this.submit_callback(
                                    function(){
                                        self.spin_off();
                                    }
                        );
                    }
                    return true;
                }
            } else {
                setTimeout(function () {
                    self.fix_ie_selection();
                    self.handle_literal_char(char_code);
                }, 100);
            }
        };

        this.fix_ie_selection = function () {
            if (!$.browser.msie) {
                return false;
            }
            var r = this.input.createTextRange();
            try {
                r.setEndPoint('EndToStart', document.selection.createRange());
            } catch (e) {

            }
            this.input.selectionStart = r.text.length;
            this.input.selectionEnd = this.input.selectionStart + r.text.length;
            return true;
        };

        this.apply_selected = function () {
            if (this.$menu.is(':hidden')) {
                return true;
            }
            this.fix_ie_selection();
            var $li = this.$menu.find('li.selected');
            var after_cursor = this.input.value.substr(this.input.selectionEnd);
            var before_cursor = this.input.value.substr(0, this.input.selectionStart);
            var matched_part = $li.html().match(/<strong>(.*?)<\/strong>/i)[1] || '';

            before_cursor = before_cursor.substr(0, before_cursor.length -
                matched_part.length) + matched_part;

            this.input.value = before_cursor +
                $li.html().replace(/<strong>.*?<\/strong>/i, '') + suffix + after_cursor;

            this.$menu.hide();
            this.input.focus();
        };

        this.spin_on = function() {
            this.spinning = true;
            this.spinner.spin(this.input.parentNode);
        };

        this.spin_off = function() {
            this.spinning = false;
            this.spinner.stop();
        };

        this.init_fake_input = function () {
            var css = {}, $i = this.$input;
            $(['font-size', 'font-family', 'font-weight', 'border']).each(function (i, rule) {
                css[rule] = $i.css(rule);
            });
            return $('<div style="float: left; display: none;"><\/div>').css(css);
        };

        this.init = function (dom_input, options, submit_callback) {
            var self = this;

            this.spinner = new Spinner();
            this.spinning = false;
            this.submit_callback = submit_callback;
            this.options = options;
            this.input = dom_input;
            this.input.context_autocomplete = self;
            this.$input = $(dom_input);
            this.$menu = $('<div class="autocomplete_menu"><\/div>');
            this.$fake_input = this.init_fake_input();

            $('body').append(this.$fake_input).append(this.$menu);

            this.$input.attr('autocomplete', 'off');

            this.$menu.click(function () {
                self.apply_selected();
            });

            this.$input.blur(function () {
                setTimeout(function () {
                    self.$menu.hide();
                }, 200);
            });

            // todo: test old keypress
            var old_onkeypress = this.input.onkeypress;
            this.input.onkeypress = function (e) {
                var handled = self.handle_change(e);
                if (typeof handled === 'boolean') {
                    return handled;
                } else {
                    return $.isFunction(old_onkeypress) ? old_onkeypress(e) : true;
                }
            };

            // todo: test old keydown
            if (!$.browser.mozilla && !$.browser.opera) {
                var old_onkeydown = this.input.onkeydown;
                this.input.onkeydown = function (e) {
                    var handled = self.handle_change(e);
                    if (typeof handled === 'boolean') {
                        return handled;
                    } else {
                        return $.isFunction(old_onkeydown) ? old_onkeydown(e) : true;
                    }
                };
            }
        };

        this.init(dom_input, options, submit_callback);

    }

    /*
     * @param config should be Object with members - characters
     * example:
     * var options = {
     *     '#': ['tag1', 'tag2', 'tag3'], // popup when # sign is typed
     *     '@': ['place1', 'place2'],     // popup when @ sign is typed
     *      '^\\d+\\s+(.*)$': categories  // popup when regex /^\d+\s+(.*)$/i is matched
     * }
     */
    $.fn.autocomplete = function (config, submit_callback) {
        if (!config) {
            return this;
        }
        var options = prepare_input_parameters(config);
        return this.each(function () {
            var x = new Context_Autocomplete(this, options, submit_callback);
        });
    };
});
