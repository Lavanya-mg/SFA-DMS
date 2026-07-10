# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — Beat Calendar HTTP Controller
from odoo import http
from odoo.http import request, Response
import json


class BeatCalendarV19(http.Controller):

    @http.route('/beatcalendar/v19', auth='user')
    def beat_calendar(self, employee_id=None, **kwargs):
        return Response(f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Beat Calendar</title>
    <link href="/employee_dashboard_v19/static/lib/fullcalendar/main.min.css" rel="stylesheet">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f4f6f9; }}
        header {{ background: #0057d8; color: white; padding: 16px 24px; font-size: 15px;
                  font-weight: 600; }}
        #calendar-container {{ padding: 16px; }}
        #calendar {{ background: white; padding: 12px; border-radius: 10px;
                     box-shadow: 0 2px 8px rgba(0,0,0,.1); }}
    </style>
</head>
<body>
    <script>var EMPLOYEE_ID = {employee_id};</script>
    <header>Beat Calendar — Employee 360 (Odoo 19)</header>
    <div id="calendar-container">
        <div id="calendar"></div>
    </div>
    <script src="/employee_dashboard_v19/static/lib/fullcalendar/main.min.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", function () {{
            var calendarEl = document.getElementById("calendar");
            var calendar = new FullCalendar.Calendar(calendarEl, {{
                initialView: "dayGridMonth",
                height: "auto",
                events: {{
                    url: "/beatcalendar/v19/events",
                    method: "GET",
                    extraParams: {{ emp_id: EMPLOYEE_ID }},
                }},
            }});
            calendar.render();
        }});
    </script>
</body>
</html>""", status=200, mimetype='text/html')

    @http.route('/beatcalendar/v19/events', type='http', csrf=False)
    def beat_calendar_events(self, emp_id=0, **kwargs):
        records = request.env['beat.module'].sudo().search(
            [('employee_id', '=', int(emp_id))], order='beat_date asc')
        events = []
        for rec in records:
            if not rec.beat_date:
                continue
            events.append({
                'id': int(rec.id),
                'title': rec.beat_number or rec.name,
                'start': str(rec.beat_date)[:10],
                'allDay': True,
            })
        return Response(
            json.dumps(events), content_type='application/json;charset=utf-8')
