# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AppbotAppointment(models.Model):
    _name = 'appbot.appointment'
    _description = 'Cita AppBot'
    _order = 'date desc'
    _rec_name = 'client_name'

    appbot_id        = fields.Char('AppBot ID', required=True, index=True)
    doctor_id        = fields.Many2one('res.partner', string='Doctor/Odontólogo', index=True)
    client_name      = fields.Char('Nombre del Cliente')
    client_number    = fields.Char('WhatsApp del Cliente')
    service_name     = fields.Char('Servicio')
    date             = fields.Datetime('Fecha y Hora')
    date_end         = fields.Datetime('Hora de Fin')
    date_string      = fields.Char('Fecha (texto)')
    branch_name      = fields.Char('Sucursal')
    address          = fields.Char('Dirección / Ubicación')
    confirmation     = fields.Boolean('Confirmada', default=False)
    reminder_sent    = fields.Boolean('Recordatorio Enviado', default=False)
    active           = fields.Boolean('Activa', default=True)
    state            = fields.Selection([
        ('scheduled', 'Agendada'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='scheduled')
    raw_data         = fields.Text('Datos AppBot (JSON)')

    _sql_constraints = [
        ('appbot_id_uniq', 'UNIQUE(appbot_id)', 'Ya existe una cita con ese ID de AppBot.')
    ]

    @api.model
    def sync_from_appbot(self, appt_data: dict, doctor_partner_id: int = None):
        """Create or update an appbot.appointment record from API data."""
        import json
        from datetime import datetime

        appbot_id = appt_data.get('id', '')
        existing = self.search([('appbot_id', '=', appbot_id)], limit=1)

        def parse_dt(val):
            if not val:
                return False
            try:
                from dateutil.parser import parse
                return parse(val).replace(tzinfo=None)
            except Exception:
                return False

        vals = {
            'appbot_id':     appbot_id,
            'doctor_id':     doctor_partner_id or False,
            'client_name':   appt_data.get('client_name', ''),
            'client_number': str(appt_data.get('client_number', '')),
            'service_name':  appt_data.get('service_name', ''),
            'date':          parse_dt(appt_data.get('date')),
            'date_end':      parse_dt(appt_data.get('date_end')),
            'date_string':   appt_data.get('date_string', ''),
            'branch_name':   '',
            'address':       appt_data.get('address', '') or '',
            'confirmation':  appt_data.get('confirmation', False),
            'reminder_sent': appt_data.get('reminder_sent', False),
            'active':        appt_data.get('active', True),
            'raw_data':      json.dumps(appt_data, ensure_ascii=False),
        }

        # Pull location from extra_data.responses if address empty
        if not vals['address']:
            responses = (appt_data.get('extra_data') or {}).get('responses', {})
            vals['address'] = responses.get('Ubicacion', '') or responses.get('Descripcion del lugar', '')

        if existing:
            existing.write(vals)
            return existing
        else:
            return self.create(vals)
