
//
// The following regexp is used in add_entry.js
//

var exp = new RegExp('.*@.*#(?![0-9]+[ ]+)([^#]+)$');



describe("Quick Add Entry: Ticket Match", function() {
    it("does not match when no project has been selected yet (we wouldn't know where to look for tickets)", function() {
        expect('bla bla bla'.match(exp)).toBe(null);
    });

    it("does not match when a project is selected but there is no hash char", function() {
        expect('@project'.match(exp)).toBe(null);
    });

    it("does not match when there is a hash at the end of the line", function() {
        expect('@project #'.match(exp)).toBe(null);
    });

    it("matches when there is a hash followed by the beginning of a ticket number", function() {
        expect('@project #3'.match(exp)[1]).toBe('3');
    });

    it("does not match when there is a full ticket number followed by a space", function() {
        expect('@project #3 '.match(exp)).toBe(null);
    });

    it('does not match when where is a full ticket number followed by the rest of the text', function() {
        expect('@project #3 something'.match(exp)).toBe(null);
    });

    it("matches when there is a hash followed by a query string", function() {
        expect('@project #f'.match(exp)[1]).toBe('f');
    });

    it("matches when there is a hash followed by a single word query string", function() {
        expect('@project #foo'.match(exp)[1]).toBe('foo');
    });

    it("matches when there is a hash followed by a multiple word query string", function() {
        expect('@project #foo bar'.match(exp)[1]).toBe('foo bar');
    });

    it("matches when there is a hash followed by a ticket number, and another one with a multiple word query string", function() {
        expect('@project #34 bla bla #foo bar'.match(exp)[1]).toBe('foo bar');
    });

});

