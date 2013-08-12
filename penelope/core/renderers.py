import csv
import os
import StringIO
import tempfile
import xlwt


class CSVReportRenderer(object):
    def __init__(self, info):
        pass

    def __call__(self, value, system):
        fout = StringIO.StringIO()
        writer = csv.writer(fout, delimiter=';', quoting=csv.QUOTE_ALL)

        writer.writerow(value['header'])
        writer.writerows(value['rows'])

        resp = system['request'].response
        resp.content_type = 'text/csv'
        resp.content_disposition = 'attachment;filename="report.csv"'
        return fout.getvalue()


class XLSReportRenderer(object):
    def __init__(self, info):
        pass

    def __call__(self, value, system):
        wb = xlwt.Workbook()
        ws = wb.add_sheet('report')

        style_header = xlwt.XFStyle()
        style_header.font = xlwt.Font()
        style_header.font.bold = True

        header = value['header']

        maxwidth = [0] * len(header)

        for idx, row in enumerate(value['rows']):
            for colnum, value in enumerate(row):
                ws.write(idx + 1, colnum, value)
                # crude attempt to get a sensible width
                maxwidth[colnum] = max(maxwidth[colnum], int((1 + len(unicode(value))) * 256))

        for colnum, colname in enumerate(header):
            ws.write(0, colnum, colname, style=style_header)
            ws.col(colnum).width = maxwidth[colnum]

        resp = system['request'].response
        resp.content_type = 'application/vnd.ms-excel'
        resp.content_disposition = 'attachment;filename="report.xls"'
        return self.wb_as_bytes(wb)


    @staticmethod
    def wb_as_bytes(wb):
        pathname = tempfile.mktemp()
        wb.save(pathname)
        ret = open(pathname, 'rb').read()
        os.unlink(pathname)
        return ret

