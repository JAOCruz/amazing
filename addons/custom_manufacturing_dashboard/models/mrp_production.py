# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from markupsafe import Markup

_logger = logging.getLogger(__name__)

# ── Vita Shade Colors (mirror of JS teeth_selector.js) ───────────────────────
SHADE_COLORS_PY = {
    "Ninguno": "#EFEFEF",
    "BL1": "#F8F7F0", "BL2": "#F5F1E5", "BL3": "#F0EADA", "BL4": "#EAE2CF",
    "A1": "#F2E3BC", "A2": "#EDD59C", "A3": "#E3C478", "A3.5": "#D6AF58", "A4": "#C79838",
    "B1": "#F5EDD0", "B2": "#EDE0A8", "B3": "#E3CC80", "B4": "#D0B460",
    "C1": "#E5DEC8", "C2": "#D5CEB4", "C3": "#C5BC98", "C4": "#B0A87A",
    "D2": "#E4D4BA", "D3": "#D2BE98", "D4": "#BEA878",
}


class MrpProducciónCustom(models.Model):
    _inherit = 'mrp.production'
    _order = 'date_deadline asc, id desc'

    def _auto_init(self):
        """Ensure custom columns exist before Odoo validates field mappings."""
        super()._auto_init()
        self._cr.execute("""
            ALTER TABLE mrp_production
            ADD COLUMN IF NOT EXISTS tooth_shades TEXT DEFAULT '{}';
        """)

    active = fields.Boolean('Activo', default=True, help="Si está desactivado, permite ocultar la orden sin borrarla.")

    state = fields.Selection(
        selection_add=[
            ('test', 'En Prueba'),
        ],
    )

    date_test_sent = fields.Datetime(
        string='Enviado a Prueba',
        readonly=True,
        index=True,
        copy=False,
    )

    date_test_approved = fields.Datetime(
        string='Prueba Aprobada',
        readonly=True,
        index=True,
        copy=False,
    )

    time_status = fields.Selection([
        ('green', 'En tiempo'),
        ('yellow', 'Atención (3 días)'),
        ('orange', 'Prioridad (2 días)'), # Nuevo
        ('purple', 'Crítico (1 día)'),    # Nuevo
        ('late', 'Retrasado'),            # Esto será Rojo
        ('frozen', 'Congelado'),
    ], compute='_compute_alert_status', store=True)

    time_priority = fields.Integer(
    compute="_compute_alert_status",
    store=True,
    index=True)

    def cron_update_time_priority(self):
        orders = self.search([
            ('state','in',['confirmed','progress','to_close']),
            ('is_frozen','=',False),
        ])
        for o in orders:
            o._compute_time_status()
            o.write({
                'time_priority': o.time_priority,
                'time_status': o.time_status,
            })

    # ============================================
    # INFORMACIÓN BÁSICA DEL CASO
    # ============================================

    patient_name = fields.Char(
        string='Nombre del Paciente',
        required=False,
        index=True,
        help='Nombre del paciente para quien se fabrica la prótesis'
    )

    doctor_id = fields.Many2one(
        'res.partner',
        string='Doctor/Odontólogo',
        index=True,
        help='Doctor u odontólogo que solicitó el trabajo (desde Contactos/CRM)'
    )

    clinic_id = fields.Many2one(
        'res.partner',
        string='Clínica/Hospital',
        index=True,
        help='Clínica u hospital de origen (desde Contactos/CRM)'
    )

    product_type = fields.Selection(
        selection=[
            ('corona_zirconia', 'Corona Zirconia'),
            ('corona_zirconia_multicapa', 'Corona Zirconia Multicapa'),
            ('corona_emax', 'Corona E-max'),
            ('puente', 'Puente'),
            ('incrustacion', 'Incrustación'),
            ('carilla', 'Carilla'),
            ('protesis_parcial', 'Prótesis Parcial'),
            ('protesis_completa', 'Prótesis Completa'),
            ('provisional', 'Provisional'),
            ('otro', 'Otro'),
            ('encerado', 'Encerado'),
            ('planificacion', 'Planificación'),
            ('hibrida_metal', 'Híbrida Metal'),
            ('hibrida_zirconio', 'Híbrida Zirconio'),
            ('disilicato_monolitico', 'Disilicato Monolítico'),
            ('disilicato_estratificado', 'Disilicato Estratificado'),
            ('zirconio_monolitico', 'Zirconio Monolítico'),
            ('zirconio_estratificado', 'Zirconio Estratificado'),
            ('barra_blender', 'Barra Blender'),
        ],
        string='Tipo de Producto',
        default='corona_zirconia',
        help='Tipo de prótesis dental a fabricar'
    )

    work_type = fields.Selection(
        selection=[
            ('digital', 'Digital'),
            ('analogo', 'Análogo'),
        ],
        string='Tipo de Trabajo',
        default='digital',
        help='Método de trabajo: digital (CAD/CAM) o análogo (manual)'
    )

    # ============================================
    # DIENTES (SISTEMA FDI)
    # ============================================

    teeth_numbers = fields.Char(
        string='Números de Dientes',
        help='JSON string con array de números de dientes según sistema FDI. Ej: [18,17,16]'
    )

    teeth_count = fields.Integer(
        string='Cantidad de Dientes',
        compute='_compute_teeth_count',
        store=True,
        help='Cantidad total de dientes involucrados en la fabricación'
    )

    # ============================================
    # ESPECIFICACIONES DE COLOR Y MATERIAL
    # ============================================

    color_scale = fields.Selection(
        selection=[
            ('vita_classical', 'VITA Classical'),
            ('vita_3d_master', 'VITA 3D-Master'),
            ('ivoclar', 'Ivoclar'),
            ('otro', 'Otro'),
        ],
        string='Escala de Color',
        default='vita_classical',
        help='Sistema de escala de color utilizado'
    )

    color_selected = fields.Char(
        string='Color Seleccionado',
        help='Color específico seleccionado (ej: A1, A2, B1, etc.)'
    )

    tooth_shades = fields.Char(
        string='Colores por Diente',
        default='{}',
        help='JSON con el color por tercio de cada diente. Ej: {"11": {"incisal":"A1","middle":"A2","cervical":"A3"}}'
    )

    tooth_chart_svg = fields.Html(
        string='Diagrama de Dientes',
        compute='_compute_tooth_chart_svg',
        sanitize=False,
    )

    material = fields.Selection(
        selection=[
            ('zirconia', 'Zirconia'),
            ('zirconia_multicapa', 'Zirconia Multicapa'),
            ('emax', 'E-max (Disilicato de Litio)'),
            ('pmma', 'PMMA'),
            ('ceramica_feldespato', 'Cerámica Feldespato'),
            ('metal_ceramica', 'Metal-Cerámica'),
            ('composite', 'Composite'),
            ('resina', 'Resina'),
            ('otro', 'Otro'),
        ],
        string='Material',
        default='zirconia',
        help='Material principal de fabricación'
    )

    translucency = fields.Selection(
        selection=[
            ('alta', 'Alta Translucidez'),
            ('media', 'Media Translucidez'),
            ('baja', 'Baja Translucidez'),
            ('opaca', 'Opaca'),
        ],
        string='Translucidez',
        default='media',
        help='Nivel de translucidez del material'
    )

    # ============================================
    # MATERIALES RECIBIDOS DEL DOCTOR (CANTIDADES)
    # ============================================

    qty_tibase = fields.Integer(string=' TIBASE', default=0)
    qty_analogo = fields.Integer(string=' Análogo', default=0)
    qty_tornillo = fields.Integer(string=' Tornillo', default=0)
    qty_transfer = fields.Integer(string=' Transfer', default=0)
    qty_calcinable = fields.Integer(string=' Calcinable', default=0)
    qty_mini_pilares = fields.Integer(string=' Mini Pilares', default=0)
    
    qty_antagonistas = fields.Integer(string=' Antagonistas', default=0)
    qty_encerado_superior = fields.Integer(string=' Encerado Sup.', default=0)
    qty_encerado_inferior = fields.Integer(string=' Encerado Inf.', default=0)
    qty_modelo_superior = fields.Integer(string=' Modelo Sup.', default=0)
    qty_modelo_inferior = fields.Integer(string=' Modelo Inf.', default=0)
    qty_mordida_superior = fields.Integer(string=' Mordida Sup.', default=0)
    qty_mordida_inferior = fields.Integer(string=' Mordida Inf.', default=0)

    # ============================================
    # COMENTARIOS Y FOTOS
    # ============================================

    doctor_comments = fields.Text(
        string='Comentarios del Doctor',
        help='Instrucciones especiales o comentarios del doctor sobre el caso'
    )

    photo_ids = fields.Many2many(
        'ir.attachment',
        'production_photo_rel',
        'production_id',
        'attachment_id',
        string='Fotos del Caso',
        help='Fotografías del caso enviadas por el doctor'
    )

    # ============================================
    # TIMELINE Y TRACKING
    # ============================================

    deadline_days = fields.Integer(
        string="Días Restantes", 
        compute="_compute_deadline_days", 
        store=True  # Store=True para poder buscar/filtrar por este campo
    )

    @api.depends('date_deadline')
    def _compute_deadline_days(self):
        for record in self:
            if record.date_deadline and record.state not in ['done', 'cancel']:
                # Calculamos la diferencia entre el Deadline y AHORA mismo
                now = fields.Datetime.now()
                delta = record.date_deadline - now
                # Convertimos a días (puede ser negativo si ya pasó)
                record.deadline_days = int(delta.total_seconds() / 86400)
            else:
                record.deadline_days = 0

    manufacturing_start_date = fields.Datetime(
        string='Fecha de Inicio',
        help='Fecha y hora de inicio de la manufactura',
        index=True
    )

    manufacturing_time = fields.Float(
        string='Tiempo Transcurrido (horas)',
        compute='_compute_manufacturing_time',
        store=False,  # Changed to False - recalculate in real-time
        help='Horas transcurridas desde el inicio de la manufactura'
    )

    # ============================================
    # ALERTAS Y ESTADO
    # ============================================

    is_delayed = fields.Boolean(
        string='Retrasado',
        compute='_compute_alert_status',
        store=True,  # Changed to False - recalculate in real-time based on manufacturing_time
        index=False,  # Can't index computed non-stored fields
        help='La orden ha excedido el deadline establecido'
    )

    # 1. CAMPO NUEVO (Para guardar lo que dice el humano)
    manual_urgency = fields.Boolean(
        string='Forzar Urgencia', 
        default=False,
        help="Marcado manualmente como urgente al crear la orden."
    )

    # 2. TU CAMPO EXISTENTE (Mantenemos tu definición, actualizamos el depends)
    is_urgent = fields.Boolean(
        string='Urgente',
        compute='_compute_alert_status', # Usamos TU nombre de función
        store=True, 
        help='La orden es urgente por tiempo (>80%) o por decisión manual'
    )

    is_pending = fields.Boolean(
        string='Pendiente',
        compute='_compute_alert_status',
        store=True,  # Changed to False - recalculate in real-time based on manufacturing_time
        index=False,  # Can't index computed non-stored fields
        help='La orden está en progreso normal'
    )

    is_vip = fields.Boolean(
        string='Cliente VIP',
        default=False,
        index=True,
        help='Marcar como cliente VIP para priorización'
    )

    # ============================================
    # PORCENTAJE EXTRA DE FACTURACIÓN
    # ============================================
    extra_percentage = fields.Float(
        string='Recargo Extra (%)',
        default=0.0,
        help='Porcentaje adicional a cobrar sobre el precio base del caso. No es impuesto — recargo manual por VIP, urgencia, etc.'
    )
    extra_percentage_reason = fields.Char(
        string='Razón del Recargo',
        help='Motivo del recargo extra (ej: VIP, Urgente, Fin de semana)'
    )

    # ============================================
    # TRACKING DE ALERTAS
    # ============================================

    last_first_wo_not_started_alert = fields.Datetime(
        string='Última Alerta: Primera WO sin Iniciar',
        help='Fecha y hora de la última alerta enviada sobre la primera workorder sin iniciar'
    )

    # ============================================
    # ETAPA CUSTOM
    # ============================================

    stage_custom = fields.Selection(
        selection=[
            ('laboratory', 'Laboratorio'),
            ('production', 'Producción'),
            ('stopped', 'Detenidas'),
            ('testing', 'Prueba'),
        ],
        string='Etapa Custom',
        default='laboratory',
        required=True,
        index=True,
        help='Etapa actual del proceso de manufactura'
    )

    is_frozen = fields.Boolean(
    string="Orden congelada",
    default=False,
    index=True,
    help="Detiene timers, alertas y cálculo de retraso"
    )

    # ============================================
    # FACTURACIÓN
    # ============================================

    invoice_ids = fields.One2many(
        'account.move', 'production_id',
        string='Facturas',
        help='Facturas generadas desde esta orden de manufactura',
    )
    invoice_count = fields.Integer(
        string='Nro. Facturas',
        compute='_compute_invoice_count',
    )

    bill_ids = fields.One2many(
        'manufacturing.bill', 'production_id',
        string='Facturas de Manufactura',
    )
    bill_count = fields.Integer(
        string='Nro. Facturas Mfg',
        compute='_compute_bill_count',
    )

    def action_send_to_test(self):
        self.ensure_one()

        if not self.env.user.has_group(
            'custom_manufacturing_dashboard.group_manufacturing_manager'
        ):
            raise AccessError("Solo un gerente puede enviar una orden a prueba.")

        if self.stage_custom == 'testing':
            return False

        self.write({
            'state': 'test',
            'stage_custom': 'testing',
            'is_frozen': True,
            'date_test_sent': fields.Datetime.now(),
        })

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_approve_test(self):
        self.ensure_one()

        if not self.env.user.has_group(
            'custom_manufacturing_dashboard.group_manufacturing_manager'
        ):
            raise AccessError("Solo un gerente puede aprobar una prueba.")

        if self.stage_custom != 'testing':
            return False

        self.write({
            'state': 'progress',
            'stage_custom': 'production',
            'is_frozen': False,
            'date_test_approved': fields.Datetime.now(),
        })

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_add_billing_tracking_operations(self):
        """
        Agrega las operaciones de Facturación y Seguimiento a una orden
        de manufactura existente si aún no existen.
        """
        self.ensure_one()

        if not self.env.user.has_group(
            'custom_manufacturing_dashboard.group_manufacturing_manager'
        ):
            raise AccessError("Solo un gerente puede agregar operaciones a una orden.")

        default_workcenter = self.env['mrp.workcenter'].search([], limit=1)

        new_operations = [
            {'name': 'Facturación', 'duration': 2.0, 'sequence': 100},
            {'name': 'Seguimiento', 'duration': 1.0, 'sequence': 101},
        ]

        created = False
        for op_data in new_operations:
            existing = self.env['mrp.workorder'].search([
                ('production_id', '=', self.id),
                ('name', '=', op_data['name']),
            ], limit=1)
            if existing:
                continue

            self.env['mrp.workorder'].create({
                'production_id': self.id,
                'name': op_data['name'],
                'workcenter_id': default_workcenter.id if default_workcenter else False,
                'product_id': self.product_id.id,
                'product_uom_id': self.product_uom_id.id,
                'state': 'pending',
                'duration_expected': op_data['duration'] * 60.0,
                'alert_time_hours': op_data['duration'],
                'sequence_in_user_queue': op_data['sequence'],
                'date_start': self.date_start,
            })
            created = True

        message = (
            "Operaciones de Facturación y Seguimiento agregadas correctamente."
            if created else
            "Las operaciones de Facturación y Seguimiento ya existen en esta orden."
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if created else 'warning',
                'message': message,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    # ============================================
    # COMPUTED FIELDS
    # ============================================

    def _get_tooth_shades_parsed(self):
        """Returns tooth_shades as a sorted dict for use in QWeb reports."""
        try:
            raw = self.tooth_shades or '{}'
            data = json.loads(raw)
            if isinstance(data, dict):
                return dict(sorted(data.items(), key=lambda x: int(x[0])))
        except Exception:
            pass
        return {}

    def _generate_tooth_chart_svg(self, scale=1):
        """
        Generate anatomical SVG dental chart using the same crown/root paths
        as the browser TeethSelectorWidget. PDF-safe (fixed pixel dimensions).
        scale param kept for API compatibility but viewBox handles sizing now.
        """
        import json

        # ── Shade colors (Vita Classical) ────────────────────────────────────
        SHADE_COLORS = {
            'Ninguno':'#EFEFEF',
            'BL1':'#F8F7F0','BL2':'#F5F1E5','BL3':'#F0EADA','BL4':'#EAE2CF',
            'A1':'#F2E3BC','A2':'#EDD59C','A3':'#E3C478','A3.5':'#D6AF58','A4':'#C79838',
            'B1':'#F5EDD0','B2':'#EDE0A8','B3':'#E3CC80','B4':'#D0B460',
            'C1':'#E5DEC8','C2':'#D5CEB4','C3':'#C5BC98','C4':'#B0A87A',
            'D2':'#E4D4BA','D3':'#D2BE98','D4':'#BEA878',
        }
        DARK_SHADES = {'A3','A3.5','A4','B3','B4','C3','C4','D3','D4'}

        def shade_color(s):
            return SHADE_COLORS.get(s, '#f5f5f5')

        def stroke_color(s):
            return '#7a5c1e' if s in DARK_SHADES else '#b8901a'

        def darken_hex(hx, f=0.65):
            try:
                r,g,b = int(hx[1:3],16),int(hx[3:5],16),int(hx[5:7],16)
                return '#{:02x}{:02x}{:02x}'.format(int(r*f),int(g*f),int(b*f))
            except Exception:
                return '#888'

        # ── Anatomical paths (ported from teeth_selector.js) ─────────────────
        CROWN_PATHS = [
            "M18.39 55.13C16.34 54.96 13.46 54.28 13.46 54.28C13.46 54.28 8.32 53.28 6.23 52.10C4.01 50.83 1.09 48.97 0.68 47.15C0.30 45.43 0.00 42.73 0.29 40.78L0.31 40.59C0.66 38.24 1.18 34.75 1.56 31.00C1.75 29.14 1.50 28.01 2.32 25.27C3.18 22.39 3.66 21.02 4.25 19.99C4.86 18.91 5.65 18.06 6.17 16.95C6.99 15.17 8.43 12.98 9.83 11.31C10.62 10.36 11.38 9.54 12.05 8.85C13.00 7.86 14.70 5.98 15.72 4.85C17.15 3.26 18.61 1.86 19.87 1.41C21.01 1.00 22.40 0.84 23.41 0.57C24.69 0.24 25.74 0.00 27.69 0.61C29.13 1.06 30.22 1.22 31.74 2.91C33.64 5.03 34.36 6.21 34.97 7.36C35.94 9.20 37.28 11.71 38.21 13.38C38.77 14.38 40.25 16.27 41.93 21.65C43.32 26.09 44.07 28.90 44.39 30.05C44.77 31.37 45.36 33.40 45.60 35.83C45.97 39.73 46.57 42.81 46.49 46.11C46.42 48.95 46.54 50.81 45.44 51.97C44.54 52.92 43.57 53.82 42.33 54.30C40.50 55.02 38.81 55.53 37.39 55.74C36.13 55.92 30.82 56.00 26.94 55.69C25.48 55.57 23.58 55.56 18.39 55.13Z",
            "M16.62 5.08C19.56 2.85 23.42 0.35 25.22 0.24C29.49 0.00 33.08 2.23 35.23 5.93C39.35 13.02 41.77 21.04 43.71 28.96C44.57 32.46 48.92 44.99 44.65 47.88C38.47 55.98 13.64 56.00 6.91 50.02C0.00 43.89 2.07 29.40 4.80 21.78C7.06 15.50 11.33 9.08 16.62 5.08Z",
            "M0.70 36.77C0.88 34.86 1.28 18.16 11.70 4.87C14.73 1.01 25.46 0.00 29.44 3.08C36.71 8.70 39.80 28.83 36.69 37.49C35.21 41.63 23.18 56.00 17.24 53.31C11.66 50.79 0.00 44.23 0.70 36.77Z",
            "M12.41 8.31C6.87 12.28 3.07 36.73 3.01 36.91C3.02 38.29 0.00 46.85 20.35 55.59C21.30 56.00 22.38 55.47 23.10 55.06C23.89 54.61 25.55 53.46 28.24 50.78C29.89 49.14 36.52 42.31 36.63 37.77C36.69 35.68 36.32 31.50 35.92 27.34C35.53 23.19 34.21 15.88 33.31 13.09C32.44 10.40 27.72 0.00 12.41 8.31Z",
            "M6.35 48.26C8.27 49.87 14.80 55.08 17.71 55.56C20.35 56.00 31.36 46.99 33.80 39.56C34.39 37.78 35.11 17.29 28.60 6.20C22.23 0.00 9.16 1.28 5.25 13.17C3.06 19.84 0.49 32.87 0.25 34.49C0.00 36.12 0.01 38.31 0.37 40.48C0.58 41.71 0.68 42.39 1.05 42.94C1.56 43.70 3.08 45.50 6.35 48.26Z",
            "M7.46 41.01C9.12 42.32 23.29 56.00 38.45 40.31C39.48 39.24 48.19 25.00 39.31 7.44C38.34 5.52 37.68 3.75 36.82 2.82C35.53 1.44 34.87 0.74 33.30 0.65C31.94 0.56 30.54 1.03 27.36 1.81C25.75 2.20 24.68 2.45 21.77 1.31C20.72 0.90 19.20 0.17 17.28 0.07C15.73 0.00 14.67 0.06 13.39 0.92C11.41 2.24 9.94 3.87 8.77 6.31C8.43 7.02 7.64 8.30 6.23 11.13C5.34 12.92 4.18 15.42 3.26 17.71C2.34 20.00 1.64 22.01 1.25 23.47C0.64 25.76 0.00 28.06 0.53 30.19L0.53 30.21C0.86 31.50 1.33 33.40 2.62 35.33C3.97 37.34 5.52 39.47 7.46 41.01Z",
            "M3.46 25.72C2.66 28.12 0.00 50.30 28.74 54.67C44.27 56.00 50.80 40.18 51.13 37.67C53.42 31.26 51.23 17.68 49.99 14.60C48.39 10.63 47.30 8.13 46.52 6.97C44.95 4.66 43.68 2.71 42.85 2.33C41.67 1.80 39.68 0.46 35.38 2.08C32.42 3.20 29.97 2.93 27.40 2.17C24.39 1.27 20.39 0.00 18.86 0.28C17.84 0.47 16.76 0.49 15.93 1.35C14.74 2.60 13.35 4.24 10.89 9.28C9.67 11.77 7.75 15.68 6.81 17.84C5.24 21.45 4.14 23.67 3.46 25.72Z",
            "M24.54 55.69C25.67 56.00 27.71 55.77 28.16 55.80C28.47 55.83 31.35 55.67 33.31 55.12C35.92 54.18 37.70 53.49 38.63 52.80C40.36 51.54 43.03 49.31 45.26 46.45C46.85 44.42 48.19 42.01 49.23 39.24C49.98 37.25 50.59 35.38 50.75 32.41C50.84 30.48 50.85 27.77 50.58 24.66C50.31 21.54 49.78 18.13 49.20 15.54C48.63 12.94 48.03 11.20 47.40 9.69C46.76 8.18 46.08 6.93 45.72 6.20C45.07 4.87 44.58 3.65 43.71 2.84C41.95 1.22 40.59 0.56 39.22 0.31C38.04 0.10 36.23 0.12 35.02 0.55C33.29 1.16 32.37 1.87 29.73 1.89C26.15 1.92 24.20 0.42 21.96 0.27C18.24 0.00 16.23 0.03 15.01 0.70C14.04 1.23 12.81 2.07 10.33 5.63C9.60 6.67 8.83 8.01 7.20 11.51C6.06 13.96 4.37 17.69 3.46 19.67C2.45 21.86 1.43 23.80 0.68 26.96C0.16 29.20 0.00 31.93 0.58 34.91C0.98 36.94 1.72 39.71 4.20 42.91C6.87 46.36 8.80 48.63 9.87 49.48C10.83 50.23 11.82 50.97 13.19 51.58C14.96 52.36 16.59 53.55 18.71 54.18C21.16 54.90 22.64 55.17 24.54 55.69Z",
        ]
        CROWN_H = 56
        CROWN_W = [46.6, 48.9, 39.8, 36.7, 35.1, 48.2, 53.4, 50.8]
        ROOT_PATHS = [
            ["M 13.5,0 L 13.5,76 Q 23.3,84 33.1,76 L 33.1,0 Z"],
            ["M 15.2,0 L 15.2,70 Q 24.4,78 33.7,70 L 33.7,0 Z"],
            ["M 12.3,0 L 12.3,90 Q 19.9,98 27.5,90 L 27.5,0 Z"],
            ["M 2.9,0 L 2.9,48 Q 8.1,58 13.2,48 L 13.2,0 Z","M 22.8,0 L 22.8,44 Q 27.9,55 33.0,44 L 33.0,0 Z"],
            ["M 2.8,0 L 2.8,46 Q 7.7,56 12.6,46 L 12.6,0 Z","M 21.8,0 L 21.8,42 Q 26.7,54 31.6,42 L 31.6,0 Z"],
            ["M 1.9,0 L 1.9,42 Q 7.2,50 12.5,42 L 12.5,0 Z","M 18.8,0 L 18.8,46 Q 24.1,50 29.4,46 L 29.4,0 Z","M 34.7,0 L 34.7,40 Q 40.0,50 45.3,40 L 45.3,0 Z"],
            ["M 2.1,0 L 2.1,46 Q 8.0,54 13.9,46 L 13.9,0 Z","M 20.8,0 L 20.8,50 Q 26.7,54 32.6,50 L 32.6,0 Z","M 38.4,0 L 38.4,44 Q 44.3,54 50.2,44 L 50.2,0 Z"],
            ["M 2.0,0 L 2.0,40 Q 7.6,48 13.2,40 L 13.2,0 Z","M 19.8,0 L 19.8,44 Q 25.4,48 31.0,44 L 31.0,0 Z","M 36.6,0 L 36.6,38 Q 42.2,48 47.8,38 L 47.8,0 Z"],
        ]
        ROOT_H = [84, 78, 98, 58, 56, 50, 54, 48]
        TOOTH_IDX = {
            11:0,21:0,31:0,41:0, 12:1,22:1,32:1,42:1,
            13:2,23:2,33:2,43:2, 14:3,24:3,34:3,44:3,
            15:4,25:4,35:4,45:4, 16:5,26:5,36:5,46:5,
            17:6,27:6,37:6,47:6, 18:7,28:7,38:7,48:7,
        }
        GAP = 5
        UPPER_ORDER = [18,17,16,15,14,13,12,11,21,22,23,24,25,26,27,28]
        LOWER_ORDER = [48,47,46,45,44,43,42,41,31,32,33,34,35,36,37,38]

        # ── Data ─────────────────────────────────────────────────────────────
        try:
            shades = json.loads(self.tooth_shades or '{}')
        except Exception:
            shades = {}
        default_shade = self.color_selected or 'A2'
        try:
            selected = set(int(x) for x in json.loads(self.teeth_numbers or '[]'))
        except Exception:
            selected = set()

        def get_shade(n):
            s = shades.get(str(n), {})
            if not s:
                return default_shade, default_shade, default_shade
            d = default_shade
            return s.get('incisal', d), s.get('middle', d), s.get('cervical', d)

        def shade_label(n):
            i, m, c = get_shade(n)
            vals = list(dict.fromkeys([i, m, c]))
            return vals[0] if len(vals) == 1 else '/'.join(vals)

        # ── Build layout ──────────────────────────────────────────────────────
        def build_layout(nums):
            x = 0
            result = []
            for n in nums:
                idx = TOOTH_IDX.get(n, 0)
                w = CROWN_W[idx]
                result.append({'n': n, 'x': x, 'w': w, 'idx': idx})
                x += w + GAP
            return result

        upper = build_layout(UPPER_ORDER)
        lower = build_layout(LOWER_ORDER)

        PAD = 10
        NUM_H = 18
        SHD_H = 12
        max_upper_h = max(CROWN_H + 4 + ROOT_H[t['idx']] for t in upper)
        max_lower_h = max(CROWN_H + 4 + ROOT_H[t['idx']] for t in lower)
        total_upper_h = max_upper_h + NUM_H + SHD_H
        total_lower_h = max_lower_h + NUM_H + SHD_H
        mid_gap = 20
        label_h = 14
        total_w = upper[-1]['x'] + CROWN_W[upper[-1]['idx']] + PAD * 2
        total_h = PAD + label_h + total_upper_h + mid_gap + label_h + total_lower_h + PAD
        # viewBox = natural size, width=540 for PDF fit
        p = []
        # Fixed px width required — wkhtmltopdf does not support width="100%"
        # 340px fits in the 65% left column of A4 with margins
        svg_w = 340
        svg_h = round(svg_w * total_h / total_w)
        p.append('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                 'width="{}" height="{}" viewBox="0 0 {:.1f} {:.0f}" '
                 'style="display:block;margin:0 auto;">'.format(svg_w, svg_h, total_w, total_h))

        # Background
        p.append('<rect width="{:.1f}" height="{:.0f}" fill="#f8fafc" rx="6" '
                 'stroke="#e2e8f0" stroke-width="1"/>'.format(total_w, total_h))

        # Midline
        mid_x = PAD + 8 * (CROWN_W[0] + GAP) - GAP/2
        p.append('<line x1="{:.1f}" y1="{}" x2="{:.1f}" y2="{:.0f}" '
                 'stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="4,3"/>'.format(
                     mid_x, PAD, mid_x, total_h - PAD))

        def render_arch_upper(layout, base_y):
            # Arch label
            p.append('<text x="{}" y="{:.1f}" font-size="8" fill="#94a3b8" '
                     'font-weight="600" font-family="Arial,sans-serif">Superior</text>'.format(
                         PAD, base_y + label_h - 2))
            for t in layout:
                n, x, w, idx = t['n'], t['x'] + PAD, t['w'], t['idx']
                rh = ROOT_H[idx]
                sel = n in selected
                # y positions: roots at top, crown below
                root_y = base_y + label_h
                crown_y = root_y + rh + 4
                num_y = crown_y + CROWN_H + 10

                if sel:
                    si, sm, sc = get_shade(n)
                    ci_c, cm_c, cc_c = shade_color(si), shade_color(sm), shade_color(sc)
                    sk = stroke_color(sm)
                    gid = 'gu{}'.format(n)
                    # linearGradient: y=0=cervical(top), y=56=incisal(bottom) in path space
                    p.append('<defs><linearGradient id="{}" x1="0" y1="0" x2="0" y2="56" '
                             'gradientUnits="userSpaceOnUse">'
                             '<stop offset="0%" stop-color="{}"/>'
                             '<stop offset="33%" stop-color="{}"/>'
                             '<stop offset="33.1%" stop-color="{}"/>'
                             '<stop offset="66%" stop-color="{}"/>'
                             '<stop offset="66.1%" stop-color="{}"/>'
                             '<stop offset="100%" stop-color="{}"/>'
                             '</linearGradient></defs>'.format(gid, cc_c, cc_c, cm_c, cm_c, ci_c, ci_c))
                    # Roots
                    for rp in ROOT_PATHS[idx]:
                        p.append('<path d="{}" transform="translate({:.1f},{:.1f})" '
                                 'fill="{}" stroke="{}" stroke-width="0.6"/>'.format(
                                     rp, x, root_y, cm_c, darken_hex(sk)))
                    # Crown with gradient
                    p.append('<path d="{}" transform="translate({:.1f},{:.1f})" '
                             'fill="url(#{})" stroke="{}" stroke-width="0.8"/>'.format(
                                 CROWN_PATHS[idx], x, crown_y, gid, sk))
                    # Shade label
                    p.append('<text x="{:.1f}" y="{:.1f}" text-anchor="middle" font-size="5.5" '
                             'fill="{}" font-style="italic" font-family="Arial,sans-serif">{}</text>'.format(
                                 x + w/2, num_y + 10, darken_hex(sk, 0.7), shade_label(n)))
                else:
                    # Roots (grey)
                    for rp in ROOT_PATHS[idx]:
                        p.append('<path d="{}" transform="translate({:.1f},{:.1f})" '
                                 'fill="#e4e4e4" stroke="#bbb" stroke-width="0.6"/>'.format(rp, x, root_y))
                    # Crown (grey)
                    p.append('<path d="{}" transform="translate({:.1f},{:.1f})" '
                             'fill="#f7f7f7" stroke="#c0c0c0" stroke-width="0.8"/>'.format(
                                 CROWN_PATHS[idx], x, crown_y))

                # Tooth number
                fill_num = stroke_color(get_shade(n)[1]) if sel else '#94a3b8'
                p.append('<text x="{:.1f}" y="{:.1f}" text-anchor="middle" font-size="6.5" '
                         'fill="{}" font-weight="{}" font-family="Arial,sans-serif">{}</text>'.format(
                             x + w/2, num_y, fill_num, '700' if sel else '400', n))

        def render_arch_lower(layout, base_y):
            p.append('<text x="{}" y="{:.1f}" font-size="8" fill="#94a3b8" '
                     'font-weight="600" font-family="Arial,sans-serif">Inferior</text>'.format(
                         PAD, base_y + label_h - 2))
            for t in layout:
                n, x, w, idx = t['n'], t['x'] + PAD, t['w'], t['idx']
                rh = ROOT_H[idx]
                sel = n in selected
                # y positions: crown at top (flipped), roots below
                crown_y = base_y + label_h
                root_y = crown_y + CROWN_H + 4
                num_y = root_y + rh + 10

                if sel:
                    si, sm, sc = get_shade(n)
                    ci_c, cm_c, cc_c = shade_color(si), shade_color(sm), shade_color(sc)
                    sk = stroke_color(sm)
                    tx = x + w
                    ty = crown_y + CROWN_H
                    gid = 'gl{}'.format(n)
                    # For lower (flipped): y=0=cervical(bottom), y=56=incisal(top) visually
                    # gradient in path space: cervical→middle→incisal (same as upper, flip handles visual)
                    p.append('<defs><linearGradient id="{}" x1="0" y1="0" x2="0" y2="56" '
                             'gradientUnits="userSpaceOnUse">'
                             '<stop offset="0%" stop-color="{}"/>'
                             '<stop offset="33%" stop-color="{}"/>'
                             '<stop offset="33.1%" stop-color="{}"/>'
                             '<stop offset="66%" stop-color="{}"/>'
                             '<stop offset="66.1%" stop-color="{}"/>'
                             '<stop offset="100%" stop-color="{}"/>'
                             '</linearGradient></defs>'.format(gid, cc_c, cc_c, cm_c, cm_c, ci_c, ci_c))
                    # Crown flipped with gradient
                    p.append('<path d="{}" transform="translate({:.1f},{:.1f}) scale(-1,-1)" '
                             'fill="url(#{})" stroke="{}" stroke-width="0.8"/>'.format(
                                 CROWN_PATHS[idx], tx, ty, gid, sk))
                    # Roots
                    for rp in ROOT_PATHS[idx]:
                        p.append('<path d="{}" transform="translate({:.1f},{:.1f})" '
                                 'fill="{}" stroke="{}" stroke-width="0.6"/>'.format(
                                     rp, x, root_y, cm_c, darken_hex(sk)))
                    p.append('<text x="{:.1f}" y="{:.1f}" text-anchor="middle" font-size="5.5" '
                             'fill="{}" font-style="italic" font-family="Arial,sans-serif">{}</text>'.format(
                                 x + w/2, num_y + 10, darken_hex(sk, 0.7), shade_label(n)))
                else:
                    tx = x + w
                    ty = crown_y + CROWN_H
                    p.append('<path d="{}" transform="translate({:.1f},{:.1f}) scale(-1,-1)" '
                             'fill="#f7f7f7" stroke="#c0c0c0" stroke-width="0.8"/>'.format(
                                 CROWN_PATHS[idx], tx, ty))
                    for rp in ROOT_PATHS[idx]:
                        p.append('<path d="{}" transform="translate({:.1f},{:.1f})" '
                                 'fill="#e4e4e4" stroke="#bbb" stroke-width="0.6"/>'.format(rp, x, root_y))

                fill_num = stroke_color(get_shade(n)[1]) if sel else '#94a3b8'
                p.append('<text x="{:.1f}" y="{:.1f}" text-anchor="middle" font-size="6.5" '
                         'fill="{}" font-weight="{}" font-family="Arial,sans-serif">{}</text>'.format(
                             x + w/2, num_y, fill_num, '700' if sel else '400', n))

        upper_base = PAD
        lower_base = PAD + label_h + total_upper_h + mid_gap
        render_arch_upper(upper, upper_base)
        render_arch_lower(lower, lower_base)
        p.append('</svg>')
        return Markup(''.join(p))


    @api.depends('teeth_numbers', 'tooth_shades', 'color_selected')
    def _compute_tooth_chart_svg(self):
        for rec in self:
            rec.tooth_chart_svg = rec._generate_tooth_chart_svg()

    @api.depends('teeth_numbers')
    def _compute_teeth_count(self):
        """Calcula la cantidad de dientes desde el JSON string"""
        for record in self:
            if record.teeth_numbers:
                try:
                    teeth_list = json.loads(record.teeth_numbers)
                    if isinstance(teeth_list, list):
                        record.teeth_count = len(teeth_list)
                    else:
                        record.teeth_count = 0
                except (json.JSONDecodeError, TypeError):
                    _logger.warning(
                        f"Invalid JSON in teeth_numbers for MO {record.name}: {record.teeth_numbers}"
                    )
                    record.teeth_count = 0
            else:
                record.teeth_count = 0

    @api.depends('manufacturing_start_date')
    def _compute_manufacturing_time(self):
        """Calcula las horas transcurridas desde el inicio de manufactura"""
        for record in self:
            if record.manufacturing_start_date:
                now = fields.Datetime.now()
                delta = now - record.manufacturing_start_date
                record.manufacturing_time = delta.total_seconds() / 3600.0  # Convertir a horas
            else:
                record.manufacturing_time = 0.0

    @api.depends('date_deadline', 'manufacturing_start_date', 'workorder_ids.state')
    def _compute_alert_status(self):
        """
        Calcula estados basados en la FECHA REAL (date_deadline).
        Fuente de verdad: El calendario.
        """
        now = fields.Datetime.now()

        for record in self:
            # 1. LIMPIEZA (Si ya terminó o está cancelada)
            if record.state in ['draft', 'cancel', 'done']:
                record.is_delayed = False
                record.is_urgent = False
                record.is_pending = False
                record.time_status = False 
                record.time_priority = 0
                continue

            # 2. CONGELADAS / TEST
            if record.is_frozen or record.stage_custom == 'testing' or record.state == 'test':
                record.is_delayed = False
                record.is_urgent = False
                record.is_pending = False
                record.time_status = 'frozen'
                record.time_priority = 0
                continue

            # 3. CÁLCULO MAESTRO (Basado en el Calendario)
            if not record.date_deadline:
                # Si no hay fecha límite, asumimos que está bien
                record.is_delayed = False
                record.is_urgent = False
                record.time_status = 'green'
                continue

            # Calculamos horas restantes REALES (Fecha Fin - Ahora)
            delta = record.date_deadline - now
            remaining_hours = delta.total_seconds() / 3600.0
            remaining_days = remaining_hours / 24.0

            # --- 4. LÓGICA DE PRIORIDAD ---

            # A. RETRASADA (Tiempo Negativo) -> ROJO
            # Si remaining_hours es menor a 0, ya nos pasamos de la fecha
            if remaining_hours < 0:
                record.is_delayed = True
                record.is_urgent = False
                record.is_pending = False
                record.time_status = 'late' # 🔴 Rojo
                record.time_priority = 4
                continue

            # B. URGENTE (Escala por días restantes)
            has_urgent_wo = any(record.workorder_ids.filtered(lambda wo: wo.is_operation_urgent and wo.state in ['pending', 'ready', 'progress']))
            
            # Si faltan 3 días o menos, es crítico
            is_time_critical = (remaining_days <= 3.0)

            if record.manual_urgency or has_urgent_wo or is_time_critical:
                record.is_delayed = False
                record.is_urgent = True
                record.is_pending = False
                record.time_priority = 2
                
                # Escala de colores según cercanía a la fecha
                if remaining_days <= 1.0:
                    record.time_status = 'purple' # 🟣 Menos de 24h
                elif remaining_days <= 2.0:
                    record.time_status = 'orange' # 🟠 Menos de 48h
                else:
                    record.time_status = 'yellow' # 🟡 Menos de 72h
                continue

            # C. NORMAL -> VERDE
            record.is_delayed = False
            record.is_urgent = False
            record.is_pending = True
            record.time_status = 'green' # 🟢 Verde (Más de 3 días)
            record.time_priority = 1

    # ============================================
    # VALIDACIONES
    # ============================================

    @api.constrains('teeth_numbers')
    def _check_teeth_numbers_format(self):
        """Valida que teeth_numbers sea un JSON válido"""
        for record in self:
            if record.teeth_numbers:
                try:
                    teeth_list = json.loads(record.teeth_numbers)
                    if not isinstance(teeth_list, list):
                        raise ValidationError(
                            'El campo "Números de Dientes" debe ser un array JSON válido. Ej: [18,17,16]'
                        )
                    # Validar que todos los elementos sean números
                    if not all(isinstance(tooth, int) for tooth in teeth_list):
                        raise ValidationError(
                            'Todos los números de dientes deben ser enteros.'
                        )
                except json.JSONDecodeError:
                    raise ValidationError(
                        'El campo "Números de Dientes" debe ser un JSON válido. Ej: [18,17,16]'
                    )

    # ============================================
    # MÉTODOS DE NEGOCIO
    # ============================================

    def action_start_manufacturing(self):
        """Inicia la manufactura estableciendo la fecha de inicio"""
        for record in self:
            if not record.manufacturing_start_date:
                record.manufacturing_start_date = fields.Datetime.now()
                _logger.info(f"Manufacturing started for {record.name}")

    def action_start_manufacturing(self):
        """Inicia la manufactura estableciendo la fecha de inicio"""
        for record in self:
            if not record.manufacturing_start_date:
                record.manufacturing_start_date = fields.Datetime.now()
                _logger.info(f"Manufacturing started for {record.name}")

    # =================================================================
    # NUEVA FUNCIÓN HELPER (FUENTE ÚNICA DE VERDAD)
    # =================================================================
    def _get_employee_base_domain(self):
        """ Filtro exacto para empleados: Mis WOs activas, No congeladas, No laboratorio """
        user = self.env.user
        my_pending_wos = self.env['mrp.workorder'].search([
            ('user_id', '=', user.id),
            ('state', 'in', ['pending', 'ready', 'progress'])
        ])
        my_mo_ids = my_pending_wos.mapped('production_id').ids
        return [
            ('id', 'in', my_mo_ids),
            ('state', 'in', ['confirmed', 'progress', 'to_close']),
            ('active', '=', True),
            ('is_frozen', '=', False),
            ('stage_custom', '!=', 'laboratory')
        ]

    @api.model
    def action_open_employee_active_orders(self):
        is_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')
        # Si es manager ve todo, si es empleado usa el helper
        domain = [('state', 'in', ['confirmed', 'progress', 'to_close'])] if is_manager else self._get_employee_base_domain()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Órdenes Activas',
            'res_model': 'mrp.production',
            'view_mode': 'kanban,tree,form',
            'domain': domain,
            'target': 'current',
            'context': {'create': False}
        }

    @api.model
    def action_open_dashboard_list(self, filter_type, stage=False):
        """
        Función ÚNICA para abrir listas desde el dashboard.
        Garantiza que lo que se abre coincide con lo que se contó.
        """
        is_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')
        
        # 1. Reconstruir el dominio base del empleado
        if is_manager:
            base_domain = [('state', 'in', ['confirmed', 'progress', 'to_close']), ('active', '=', True)]
        else:
            user_id = self.env.user.id
            # Buscamos órdenes donde el empleado tiene trabajo pendiente
            my_wos = self.env['mrp.workorder'].search([
                ('user_id', '=', user_id),
                ('state', 'in', ['pending', 'ready', 'progress'])
            ])
            my_mo_ids = my_wos.mapped('production_id').ids
            
            base_domain = [
                ('id', 'in', my_mo_ids),
                ('state', 'in', ['confirmed', 'progress', 'to_close']),
                ('active', '=', True),
                ('is_frozen', '=', False),
                ('stage_custom', '!=', 'laboratory')
            ]

        # 2. Aplicar el filtro específico solicitado por el JS
        final_domain = base_domain
        name = "Órdenes"

        if filter_type == 'stage':
            if stage == 'production':
                # Al abrir producción, excluimos laboratorio, testing y detenidas
                final_domain = base_domain + [('stage_custom', 'not in', ['laboratory', 'testing', 'stopped'])]
            elif stage == 'test':
                final_domain = base_domain + [('stage_custom', '=', 'testing')]
            else:
                final_domain = base_domain + [('stage_custom', '=', stage)]
            name = f'Etapa: {stage.capitalize()}'
            
        elif filter_type == 'vip':  # <--- NUEVO CASO AGREGADO
            final_domain = base_domain + [('is_vip', '=', True)]
            name = "Órdenes VIP"

        elif filter_type == 'active':
            name = "Órdenes Activas"
        
        elif filter_type == 'delayed':
            final_domain = base_domain + [('time_priority', '=', 4)]
            name = "Órdenes Retrasadas"
        
        elif filter_type == 'urgent':
            final_domain = base_domain + [('is_urgent', '=', True)]
            name = "Órdenes Urgentes"

        elif filter_type == 'pending':
            final_domain = base_domain + [('time_priority', '=', 1), ('is_urgent', '=', False)]
            name = "Órdenes Pendientes"
            
        elif filter_type == 'frozen':
             # Caso especial para la tarjeta congelada, si la tienes
             final_domain = base_domain + [('time_status', '=', 'frozen')]
             name = "Órdenes Congeladas"

        elif filter_type == 'delayed_wo':
            # Caso especial para abrir LISTA DE OPERACIONES (Work Orders)
            # 1. Buscar candidatos (Stored fields)
            base_wo_domain = [
                ('state', 'in', ['ready', 'progress']),
                ('production_id.state', 'in', ['confirmed', 'progress']),
                ('production_id.active', '=', True),
            ]
            all_wos = self.env['mrp.workorder'].search(base_wo_domain)
            
            # 2. Filtrar en Python (Non-stored field)
            delayed_wos = all_wos.filtered(lambda w: w.is_operation_delayed)
            
            if not is_manager:
                delayed_wos = delayed_wos.filtered(lambda w: 
                    w.user_id.id == self.env.user.id and 
                    w.production_id.stage_custom != 'laboratory'
                )

            return {
                'type': 'ir.actions.act_window',
                'name': 'Operaciones Retrasadas',
                'res_model': 'mrp.workorder',
                'views': [[False, 'list'], [False, 'form']],
                'view_mode': 'list,form',
                'domain': [('id', 'in', delayed_wos.ids)],
                'target': 'current',
                'context': {'create': False}
            }

        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'mrp.production',
            'views': [[False, 'kanban'], [False, 'list'], [False, 'form']],
            'view_mode': 'kanban,list,form',
            'domain': final_domain,
            'target': 'current',
            'context': {'create': False}
        }

    @api.model
    def get_dashboard_data(self):
        """
        Dashboard principal de Manufactura (Odoo 18).
        Versión: Filtrado estricto (Sin congeladas, detenidas ni laboratorio en listas operativas).
        NOTE: Wrapped in try/except so frontend always gets a usable response even on partial errors.
        """
        try:
            return self._get_dashboard_data_inner()
        except Exception as e:
            _logger.exception("\u274c get_dashboard_data failed: %s", str(e))
            return {
                'summary': {'laboratory':0,'production':0,'stopped':0,'test':0,'completed':0,'vip':0},
                'alerts': {'delayed':0,'urgent':0,'frozen':0,'pending':0},
                'delayed_details': [],
                'delayed_wo_details': [],
                'ready_wo_details': [],
                'upcoming_mo_details': [],
                'is_manager': False,
                'metrics': {'avg_time': 0.0},
                'error': str(e),
            }

    @api.model
    def _get_dashboard_data_inner(self):
        """Inner implementation. Called by get_dashboard_data."""
        user = self.env.user
        is_manager = user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')
        
        # Variables de tiempo
        now_dt = fields.Datetime.now()
        today = fields.Date.today()
        three_days_limit = today + timedelta(days=3)
        
        # ============================================
        # 1. VISIBILIDAD GENERAL Y SEGURIDAD
        # ============================================
        is_doctor = user.has_group('custom_manufacturing_dashboard.group_dental_doctor')
        
        if is_manager:
            # Manager: Ve todo lo activo para los contadores generales
            base_domain = [('state', 'in', ['confirmed', 'progress', 'to_close']), ('active', '=', True)]
            domain_active = [('state', 'not in', ['done', 'cancel']), ('active', '=', True)]
            security_domain = [] 
        elif is_doctor:
            # Doctor: Solo ve sus propios casos
            doctor_domain = [('doctor_id', '=', user.partner_id.id)]
            base_domain = doctor_domain + [('state', 'in', ['confirmed', 'progress', 'to_close']), ('active', '=', True)]
            domain_active = doctor_domain + [('state', 'not in', ['done', 'cancel']), ('active', '=', True)]
            security_domain = doctor_domain
        else:
            # Empleado: Solo ve órdenes asociadas a sus WOs
            user_id = user.id
            my_wos = self.env['mrp.workorder'].search([
                ('user_id', '=', user_id),
                ('state', 'in', ['pending', 'ready', 'progress'])
            ])
            my_mo_ids = my_wos.mapped('production_id').ids
            
            # Filtro base para contadores del empleado
            base_domain = [
                ('id', 'in', my_mo_ids),
                ('state', 'in', ['confirmed', 'progress', 'to_close']),
                ('active', '=', True),
                ('is_frozen', '=', False),
                ('stage_custom', '!=', 'laboratory')
            ]
            domain_active = base_domain
            security_domain = [('id', 'in', my_mo_ids), ('stage_custom', '!=', 'laboratory')]

        # ============================================
        # 2. RESUMEN SUPERIOR (KPIs)
        # ============================================
        summary = {
            'laboratory': self.search_count(domain_active + [('stage_custom', '=', 'laboratory')]),
            'production': self.search_count(domain_active + [('stage_custom', 'not in', ['laboratory', 'testing', 'stopped'])]),
            'stopped': self.search_count(domain_active + [('stage_custom', '=', 'stopped')]),
            'test': self.search_count(domain_active + [('stage_custom', '=', 'testing')]),
            'completed': self.search_count([('state', '=', 'done')] + security_domain),
            'vip': self.search_count(domain_active + [('is_vip', '=', True)]),
        }

        # Alertas de estado
        alerts = {
            'delayed': self.search_count(base_domain + [('time_priority', '=', 4)]),
            'urgent': self.search_count(base_domain + [('is_urgent', '=', True)]),
            'frozen': self.search_count(base_domain + [('time_status', '=', 'frozen')]),
            'pending': self.search_count(base_domain + [('time_priority', '=', 1), ('is_urgent', '=', False)]),
        }

        # Early return for doctors to avoid 403 on details using mrp.workorder
        if is_doctor:
            return {
                'summary': summary,
                'alerts': alerts,
                'delayed_details': [],
                'delayed_wo_details': [],
                'ready_wo_details': [],
                'upcoming_mo_details': [],
                'is_manager': False,
                'metrics': {'avg_time': self._get_avg_manufacturing_time() or 0.0},
            }

        # ============================================
        # 3. TABLA: MO RETRASADAS
        # ============================================
        # Aquí sí mostramos congeladas/detenidas porque es importante saber que están tarde
        delayed_orders = self.search(
            base_domain + [('time_priority', '=', 4)],
            order='manufacturing_start_date asc', limit=50
        )
        delayed_details = []
        for order in delayed_orders:
            time_elapsed = 0.0
            if order.manufacturing_start_date:
                delta = now_dt - order.manufacturing_start_date
                time_elapsed = round(delta.total_seconds() / 3600, 2)

            assigned = order.workorder_ids.mapped('user_id.name')
            assigned = [e for e in assigned if e]
            employee_display = assigned[0] if len(assigned) == 1 else f"{assigned[0]} +{len(assigned)-1}" if assigned else 'Sin asignar'

            deadline_val = 0
            if order.date_deadline:
                diff = order.date_deadline - now_dt
                deadline_val = round(diff.total_seconds() / 3600, 1)

            delayed_details.append({
                'id': order.id,
                'name': order.name,
                'assigned_employee': employee_display,
                'product': order.product_id.name or 'N/A',
                'patient': order.patient_name or 'N/A',
                'doctor': order.doctor_id.name or 'N/A',
                'stage': order.stage_custom,
                'time': time_elapsed,
                'deadline': deadline_val,
                'is_vip': order.is_vip,
            })

        # ============================================
        # 4. TABLA: WO RETRASADAS (Operaciones)
        # ============================================
        wo_domain = [
            ('state', 'in', ['ready', 'progress']),
            ('is_operation_delayed', '=', True),
            ('production_id.state', 'in', ['confirmed', 'progress']),
            ('production_id.active', '=', True),
            # NOTA: Aquí no filtramos congeladas a propósito para que salten a la vista si están tarde
        ]
        if not is_manager:
            wo_domain.append(('user_id', '=', user.id))
            # Empleados no ven lab
            wo_domain.append(('production_id.stage_custom', '!=', 'laboratory')) 

        if is_doctor:
            delayed_workorders = self.env['mrp.workorder']
        else:
            # 1. Buscar TODAS las candidatas (sin filtrar por retraso aún)
            candidate_wos = self.env['mrp.workorder'].search(wo_domain, order='operation_start_date asc')
            
            # 2. Filtrar en Python (Computed field)
            delayed_workorders = candidate_wos.filtered(lambda w: w.is_operation_delayed)
            
            # 3. Aplicar límite manual
            delayed_workorders = delayed_workorders[:50]
            
        delayed_wo_details = []
        
        for wo in delayed_workorders:
            # Cálculo preciso de retraso
            current_delay = 0.0
            if wo.state == 'progress' and wo.operation_time > wo.alert_time_hours:
                current_delay = wo.operation_time - wo.alert_time_hours
            elif wo.state == 'ready' and wo.date_start and wo.date_start < now_dt:
                delta = now_dt - wo.date_start
                current_delay = delta.total_seconds() / 3600.0
            
            if current_delay < 0.02: continue

            delayed_wo_details.append({
                'id': wo.id,
                'name': wo.name,
                'production_id': wo.production_id.id,
                'production_name': wo.production_id.name,
                'doctor_name': wo.production_id.doctor_id.name or 'Sin Doctor',
                'workcenter': wo.workcenter_id.name or 'N/A',
                'patient': wo.production_id.patient_name or 'N/A',
                'employee': wo.user_id.name or 'Sin asignar',
                'state': dict(wo._fields['state'].selection).get(wo.state, wo.state),
                'time_elapsed': round(wo.operation_time, 2),
                'time_expected': round(wo.alert_time_hours, 2),
                'delay': round(current_delay, 2),
                'is_vip': wo.production_id.is_vip,
            })

        # ============================================
        # 5. TABLA: LISTAS PARA INICIAR (Ready)
        # ============================================
        ready_wo_domain = [
            ('state', '=', 'ready'),
            ('production_id.active', '=', True),
            ('production_id.is_frozen', '=', False),
            ('production_id.stage_custom', 'not in', ['stopped', 'laboratory'])
        ]
        
        if not is_manager:
            ready_wo_domain.append(('user_id', '=', user.id))
        
        if is_doctor:
            ready_wos = self.env['mrp.workorder']
        else:
            ready_wos = self.env['mrp.workorder'].search(ready_wo_domain, limit=20)
        ready_wo_details = []
        
        for rwo in ready_wos:
            # Formato de deadline
            dd_str = 'N/A'
            if rwo.production_id.date_deadline:
                 dd_str = fields.Date.to_string(rwo.production_id.date_deadline)

            ready_wo_details.append({
                'id': rwo.id,
                'name': rwo.name, # Nombre de la operación
                'production_id': rwo.production_id.id,
                'production_name': rwo.production_id.name,
                'doctor_name': rwo.production_id.doctor_id.name or 'Sin Doctor', # NUEVO
                'patient': rwo.production_id.patient_name or 'N/A',
                'employee': rwo.user_id.name or 'Sin asignar',
                'product': rwo.production_id.product_id.name or 'N/A', # NUEVO
                'deadline': dd_str, # NUEVO
            })

        # ============================================
        # 6. TABLA: MO PRÓXIMAS A VENCER (3 Días)
        # ============================================
        mo_deadline_domain = [
            ('state', 'not in', ['done', 'cancel']),
            ('date_deadline', '!=', False),
            ('date_deadline', '<=', three_days_limit),
            ('date_deadline', '>=', today),
            ('active', '=', True),
            ('is_frozen', '=', False),
            ('stage_custom', 'not in', ['stopped', 'laboratory'])
        ]
        
        upcoming_mos = self.search(mo_deadline_domain, order='date_deadline asc', limit=20)
        
        if not is_manager:
            upcoming_mos = upcoming_mos.filtered(
                lambda mo: any(wo.user_id == user and wo.state != 'done' for wo in mo.workorder_ids)
            )

        upcoming_mo_details = []
        for umo in upcoming_mos:
            # Buscar la operación actual (la primera que no esté hecha) para mostrar info relevante
            current_wo = umo.workorder_ids.filtered(lambda w: w.state not in ['done', 'cancel'])
            current_wo = current_wo[0] if current_wo else False

            upcoming_mo_details.append({
                'id': umo.id,
                'name': umo.name, # Referencia MO
                'doctor_name': umo.doctor_id.name or 'Sin Doctor', # NUEVO
                'patient': umo.patient_name or 'N/A',
                'product_name': umo.product_id.name or 'N/A',
                'deadline': fields.Date.to_string(umo.date_deadline),
                # Datos de la operación actual para llenar las columnas
                'operation_name': current_wo.name if current_wo else 'Sin operación', # NUEVO
                'employee': current_wo.user_id.name if current_wo and current_wo.user_id else 'Sin asignar', # NUEVO
            })

        # ============================================
        # 7. RETORNO DE DATOS
        # ============================================
        return {
            'summary': summary,
            'alerts': alerts,
            'delayed_details': delayed_details,
            'delayed_wo_details': delayed_wo_details,
            'ready_wo_details': ready_wo_details,
            'upcoming_mo_details': upcoming_mo_details,
            'is_manager': is_manager,
            'metrics': {'avg_time': self._get_avg_manufacturing_time() or 0.0},
        }

    def _get_delayed_details(self):
        """
        Obtiene detalles de las órdenes retrasadas

        Note: Since is_delayed and manufacturing_time are non-stored fields,
        we need to load all active orders and filter/sort in Python.

        Returns:
            list: Lista de diccionarios con información de cada orden retrasada
        """
        # Get all active orders with manufacturing_start_date
        active_orders = self.search([
            ('manufacturing_start_date', '!=', False),
            ('state', 'in', ['confirmed', 'progress', 'to_close'])
        ])

        # Filter delayed orders in Python
        delayed_orders = []
        for order in active_orders:
            if order.is_delayed:
                delayed_orders.append({
                    'order': order,
                    'time': order.manufacturing_time,
                })

        # Sort by manufacturing_time descending (most delayed first)
        delayed_orders.sort(key=lambda x: x['time'], reverse=True)

        # Limit to 50 and prepare details
        details = []
        for item in delayed_orders[:50]:
            order = item['order']
            # Get assigned employees from workorders
            assigned_employees = order.workorder_ids.mapped('user_id.name')
            assigned_employees = [emp for emp in assigned_employees if emp]  # Remove empty

            if assigned_employees:
                employee_display = assigned_employees[0] if len(assigned_employees) == 1 else f"{assigned_employees[0]} +{len(assigned_employees)-1}"
            else:
                employee_display = 'Sin asignar'

            details.append({
                'id': order.id,
                'name': order.name,
                'assigned_employee': employee_display,
                'product': order.product_id.name if order.product_id else 'N/A',
                'patient': order.patient_name or 'N/A',
                'doctor': order.doctor_id.name if order.doctor_id else 'N/A',
                'clinic': order.clinic_id.name if order.clinic_id else 'N/A',
                'stage': order.stage_custom,
                'time': round(order.manufacturing_time, 2),
                'deadline': order.deadline_days * 24,
                'is_vip': order.is_vip,
                'teeth_count': order.teeth_count,
                'product_type': order.product_type,
            })

            _logger.debug(
                "Delayed order %s assigned_employee: %s",
                order.name,
                order.user_id.name if order.user_id else "None"
            )

        return details

    def _get_avg_manufacturing_time(self):
        completed_orders = self.search([
            ('state', '=', 'done'),
            ('manufacturing_start_date', '!=', False)
        ], limit=100)

        if not completed_orders:
            return 0.0

        valid_orders = [
            o for o in completed_orders
            if o.manufacturing_time and o.manufacturing_time > 0
        ]

        if not valid_orders:
            return 0.0

        total_time = sum(o.manufacturing_time for o in valid_orders)
        avg_time = total_time / len(valid_orders)

        return round(avg_time, 2)

    # ============================================
    # NOTIFICACIONES INTERNAS
    # ============================================

    def send_delayed_notification(self):
        """
        Envía notificación interna cuando la orden se marca como retrasada
        Notifica a managers y usuarios asignados a las operaciones
        """
        for record in self:
            if not record.is_delayed:
                continue

            # Obtener managers del grupo de manufactura
            managers = self.env.ref('custom_manufacturing_dashboard.group_manufacturing_manager').users

            # Obtener usuarios asignados a las operaciones de esta orden
            assigned_users = record.workorder_ids.mapped('user_id')

            # Combinar ambos grupos (sin duplicados)
            partners_to_notify = (managers | assigned_users).mapped('partner_id')

            if not partners_to_notify:
                continue

            # Calcular exceso de tiempo
            deadline_hours = record.deadline_days * 24.0
            delay_hours = record.manufacturing_time - deadline_hours

            # Check existing messages
            messages = record.message_ids

            # Crear mensaje de notificación (formato simple)
            vip_badge = '⭐ CLIENTE VIP\n' if record.is_vip else ''
            message = f"""🔴 ORDEN DE MANUFACTURA RETRASADA

Orden: {record.name}
Paciente: {record.patient_name or 'N/A'}
Producto: {record.product_id.name if record.product_id else 'N/A'}
Retraso: {delay_hours:.1f} horas
Deadline: {record.deadline_days} días ({deadline_hours:.0f} horas)
Tiempo transcurrido: {record.manufacturing_time:.1f} horas
Etapa: {record.stage_custom}
{vip_badge}
Esta orden requiere atención inmediata."""

            # Enviar notificación
            record.message_post(
                body=message,
                subject=f'🔴 Orden Retrasada: {record.name}',
                message_type='comment',
                subtype_xmlid='mail.mt_note',
                # partner_ids=partners_to_notify.ids,
            )

            _logger.warning(
                f"Delayed notification sent for {record.name}. "
                f"Delay: {delay_hours:.1f} hours. Notified {len(partners_to_notify)} users."
            )

    def send_urgent_notification(self):
        """
        Envía notificación interna cuando la orden llega a estado urgente (>80% del deadline)
        Notifica a managers y usuarios asignados
        """
        for record in self:
            if not record.is_urgent:
                continue

            # Obtener managers y usuarios asignados
            managers = self.env.ref('custom_manufacturing_dashboard.group_manufacturing_manager').users
            assigned_users = record.workorder_ids.mapped('user_id')
            partners_to_notify = (managers | assigned_users).mapped('partner_id')

            if not partners_to_notify:
                continue

            # Calcular tiempo restante
            deadline_hours = record.deadline_days * 24.0
            remaining_hours = deadline_hours - record.manufacturing_time
            percentage = (record.manufacturing_time / deadline_hours) * 100

            vip_badge = '⭐ CLIENTE VIP\n' if record.is_vip else ''
            message = f"""⚠️ ORDEN DE MANUFACTURA URGENTE

Orden: {record.name}
Paciente: {record.patient_name or 'N/A'}
Producto: {record.product_id.name if record.product_id else 'N/A'}
Progreso: {percentage:.1f}% del tiempo consumido
Tiempo restante: {remaining_hours:.1f} horas
Deadline: {record.deadline_days} días
Etapa: {record.stage_custom}
{vip_badge}
Esta orden está cerca de su deadline. Requiere atención prioritaria."""

            record.message_post(
                body=message,
                subject=f'⚠️ Orden Urgente: {record.name}',
                message_type='comment',
                subtype_xmlid='mail.mt_note',
                # partner_ids=partners_to_notify.ids,
            )

            _logger.info(
                f"Urgent notification sent for {record.name}. "
                f"Progress: {percentage:.1f}%. Remaining: {remaining_hours:.1f} hours."
            )

    def notify_assigned_users(self):
        """
        Notifica a los empleados cuando se les asigna operaciones en esta orden
        Llamar este método después de asignar usuarios a las operaciones
        """
        for record in self:
            assigned_users = record.workorder_ids.mapped('user_id')

            for user in assigned_users:
                # Obtener operaciones de este usuario en esta orden
                user_workorders = record.workorder_ids.filtered(lambda w: w.user_id == user)

                if not user_workorders:
                    continue

                # Crear lista de operaciones (plain text)
                operations_list = []
                for wo in user_workorders:
                    operations_list.append(f"  • {wo.name} - {wo.workcenter_id.name if wo.workcenter_id else 'N/A'}")
                operations_text = '\n'.join(operations_list)

                # VIP badge
                vip_badge = '⭐ CLIENTE VIP - PRIORIDAD ALTA\n' if record.is_vip else ''

                message = f"""📋 NUEVA ORDEN ASIGNADA

Orden: {record.name}
Paciente: {record.patient_name or 'N/A'}
Producto: {record.product_id.name if record.product_id else 'N/A'}
Deadline: {record.deadline_days} días
{vip_badge}
Tus operaciones asignadas:
{operations_text}

Por favor, revisa la orden y comienza a trabajar cuando estés listo."""

                record.message_post(
                    body=message,
                    subject=f'📋 Nueva orden asignada: {record.name}',
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                    # partner_ids=[user.partner_id.id],
                )

                _logger.info(
                    f"Assignment notification sent to {user.name} for {record.name}. "
                    f"Workorders: {len(user_workorders)}"
                )
                
    @api.model
    def check_first_workorder_not_started(self):
        """
        Cron job: Verifica si la primera operación de una orden no ha sido iniciada
        después de un tiempo razonable desde la fecha de inicio planificada.
        Envía alertas por chatter si detecta retrasos.
        """
        _logger.info("🔍 Checking for manufacturing orders with first WO not started...")
        now = fields.Datetime.now()
        threshold_hours = 4  # Alertar si lleva más de 4 horas sin iniciar

        active_orders = self.search([
            ('state', 'in', ['confirmed', 'progress']),
            ('active', '=', True),
            ('is_frozen', '=', False),
            ('stage_custom', 'not in', ['laboratory', 'stopped', 'testing']),
        ])

        for order in active_orders:
            first_wo = order.workorder_ids.filtered(
                lambda w: w.state in ['pending', 'ready']
            )
            if not first_wo:
                continue
            first_wo = first_wo[0]
            if first_wo.date_start and first_wo.date_start < now:
                delta_hours = (now - first_wo.date_start).total_seconds() / 3600
                if delta_hours >= threshold_hours:
                    try:
                        order.message_post(
                            body=f"⚠️ Primera operación <b>{first_wo.name}</b> lleva "
                                 f"{delta_hours:.1f}h sin iniciar (asignado: {first_wo.user_id.name or 'sin asignar'}).",
                            message_type='comment',
                            subtype_xmlid='mail.mt_note',
                        )
                    except Exception:
                        pass
        return True

    @api.model
    def check_and_send_notifications(self):
        """
        Cron job: Envía alertas.
        Intervalo ajustado a 30 minutos para evitar spam.
        """
        _logger.info("🔍 Checking for delayed/urgent manufacturing orders...")

        active_orders = self.search([
            ('manufacturing_start_date', '!=', False),
            ('state', 'in', ['confirmed', 'progress', 'to_close']),
            ('is_frozen', '=', False)
        ])

        if not active_orders:
            return True

        # ========================================================
        # INTERVALO REAL: 30 MINUTOS
        # ========================================================
        REMINDER_INTERVAL = timedelta(minutes=30) 
        now = fields.Datetime.now()

        delayed_count = 0
        urgent_count = 0

        for order in active_orders:
            elapsed_time = order.manufacturing_time
            is_delayed = order.is_delayed
            is_urgent = order.is_urgent

            # Datos Comunes
            deadline_hours = order.deadline_days * 24.0
            remaining_hours = deadline_hours - elapsed_time
            remaining_days = remaining_hours / 24.0
            
            doctor_display = order.doctor_id.name or 'Sin Doctor'
            patient_display = order.patient_name or 'Sin Paciente'
            vip_text = "<b>⭐ CLIENTE VIP</b><br/>" if order.is_vip or order.priority == '1' else ""

            # --- 1. ALERTA DE RETRASO ---
            if is_delayed:
                # Check Anti-Spam (Solo enviamos si NO hay mensaje reciente de retraso)
                last_mo_msgs = order.message_ids.filtered(
                    lambda m: '🔴' in (m.body or '')
                ).sorted('date', reverse=True)
                
                should_send = False
                if not last_mo_msgs:
                    should_send = True
                elif (now - last_mo_msgs[0].date) > REMINDER_INTERVAL:
                    should_send = True

                if should_send:
                    # CASO A: MO VENCIDA (Prioridad sobre WO)
                    if remaining_hours < 0:
                        delay_hours = abs(remaining_hours)
                        message = Markup(
                            "<b>🔴 ORDEN DE MANUFACTURA RETRASADA</b><br/><br/>"
                            "<ul>"
                            "<li><b>Doctor:</b> %s</li>"
                            "<li><b>Paciente:</b> %s</li>"
                            "<li><b>Retraso Total:</b> %.2f horas</li>"
                            "<li><b>Estatus:</b> <span style='color:red'>DEADLINE VENCIDO</span></li>"
                            "</ul>"
                            "%s"
                            "<i>La orden completa ha excedido su fecha límite.</i>"
                        ) % (doctor_display, patient_display, delay_hours, Markup(vip_text))
                        
                        order.message_post(body=message, subject=f'🔴 MO Retrasada: {patient_display}', message_type='comment', subtype_xmlid='mail.mt_note')
                        delayed_count += 1
                    
                    # CASO B: MO BIEN, PERO WO RETRASADA
                    else:
                        delayed_wos = order.workorder_ids.filtered(lambda w: w.is_operation_delayed and w.state in ['progress', 'ready'])
                        for wo in delayed_wos:
                             # Mensaje de WO (sin cambios, ya funcionaba bien)
                            wo_delay = 0
                            if wo.state == 'progress':
                                wo_delay = wo.duration_hours - wo.alert_time_hours
                            
                            message = Markup(
                                "<b>🔴 ORDEN DE TRABAJO RETRASADA</b><br/><br/>"
                                "<ul>"
                                "<li><b>Operación:</b> %s</li>"
                                "<li><b>Responsable:</b> %s</li>"
                                "<li><b>Retraso WO:</b> <span style='color:red'>%.2f horas</span></li>"
                                "</ul>"
                                "%s"
                            ) % (wo.name, wo.user_id.name or 'Sin Asignar', wo_delay, Markup(vip_text))

                            order.message_post(body=message, subject=f'🔴 WO Retrasada: {wo.name}', message_type='comment', subtype_xmlid='mail.mt_note')
                            delayed_count += 1

            # --- 2. ALERTA DE URGENCIA ---
            elif is_urgent and not is_delayed:
                # Check Anti-Spam
                last_urg_msgs = order.message_ids.filtered(lambda m: '⚠️' in (m.body or '')).sorted('date', reverse=True)
                should_send = False
                if not last_urg_msgs: should_send = True
                elif (now - last_urg_msgs[0].date) > REMINDER_INTERVAL: should_send = True

                if should_send:
                    urgency_title = "URGENTE"
                    color_style = "color:#bfa900; font-weight:bold;"
                    note_text = "Quedan 3 días o menos."

                    # Aseguramos que no sea negativo (aunque el if is_delayed debería evitarlo)
                    if 0 <= remaining_days <= 1.0:
                        urgency_title = "CRÍTICO (1 DÍA)"
                        color_style = "color:purple; font-weight:bold;"
                        note_text = "Queda menos de 1 día."
                    elif 1.0 < remaining_days <= 2.0:
                        urgency_title = "ALTA PRIORIDAD (2 DÍAS)"
                        color_style = "color:#e65100; font-weight:bold;"
                        note_text = "Quedan menos de 2 días."

                    message = Markup(
                        "<b>⚠️ ORDEN DE MANUFACTURA %s</b><br/><br/>"
                        "<ul>"
                        "<li><b>Doctor:</b> %s</li>"
                        "<li><b>Paciente:</b> %s</li>"
                        "<li><b>Estado:</b> <span style='%s'>%s</span></li>"
                        "<li><b>Tiempo Restante:</b> %.1f horas (%.1f días)</li>"
                        "</ul>"
                        "%s"
                        "<i>Planifique con prioridad.</i>"
                    ) % (urgency_title, doctor_display, patient_display, color_style, note_text, remaining_hours, remaining_days, Markup(vip_text))

                    order.message_post(body=message, subject=f'⚠️ {urgency_title}: {patient_display}', message_type='comment', subtype_xmlid='mail.mt_note')
                    urgent_count += 1

        _logger.info(f"✅ Check completed. Alerts sent: {delayed_count} Delayed, {urgent_count} Urgent")
        return True

    # ============================================
    # MÉTODOS OVERRIDE
    # ============================================

    def write(self, vals):
        """Override write para auto-iniciar manufactura cuando cambia a 'confirmed'"""
        result = super(MrpProducciónCustom, self).write(vals)

        # Auto-start manufacturing cuando se confirma la orden
        if vals.get('state') == 'confirmed':
            for record in self:
                if not record.manufacturing_start_date:
                    record.manufacturing_start_date = fields.Datetime.now()

        # Note: Alert notifications (delayed/urgent) are now handled by the cron job
        # since the alert fields are non-stored and calculated in real-time

        return result

    # Class-level flag so column check only runs once per server process
    _tooth_shades_ensured = False

    @api.model
    def create(self, vals):
        """Override create para establecer valores por defecto"""
        # Ensure tooth_shades column exists (Odoo auto-migration skips it on this instance)
        if not MrpProducciónCustom._tooth_shades_ensured:
            try:
                self._cr.execute(
                    "ALTER TABLE mrp_production "
                    "ADD COLUMN IF NOT EXISTS tooth_shades TEXT DEFAULT '{}';"
                )
                MrpProducciónCustom._tooth_shades_ensured = True
            except Exception:
                MrpProducciónCustom._tooth_shades_ensured = True  # don't retry endlessly

        # Si se crea en estado confirmado, establecer fecha de inicio
        if vals.get('state') == 'confirmed' and not vals.get('manufacturing_start_date'):
            vals['manufacturing_start_date'] = fields.Datetime.now()

        return super(MrpProducciónCustom, self).create(vals)

    def _plan_workorders(self, replan=False):
        """
        Override Odoo's native workorder scheduling to prevent 'Impossible to plan workorder'
        errors when a short deadline (≤ 3 days) is set. Our dashboard manages scheduling
        independently, so we skip the native calendar-based planner.
        """
        self.ensure_one()
        if not self.workorder_ids:
            self.is_planned = True
            return
        # Mark as planned without running the native calendar scheduler
        # This allows any deadline, including same-day or 1-3 day urgent orders
        self.is_planned = True

    def action_toggle_freeze(self):
        for mo in self:
            mo.is_frozen = not mo.is_frozen
            
            estado = "CONGELADA ❄️" if mo.is_frozen else "DESCONGELADA 🔥"
            # USAR Markup para que Odoo interprete el HTML
            mensaje = Markup("La orden ha sido <b>{}</b> por el usuario.").format(estado)
            mo.message_post(body=mensaje)
            
            if mo.is_frozen:
                mo.time_status = 'frozen'
                mo.time_priority = 0

    def button_mark_done(self):
        for mo in self:
            if mo.is_frozen:
                raise ValidationError("❄️ La orden está congelada.")
        return super().button_mark_done()

    # ============================================
    # FACTURACIÓN - MÉTODOS
    # ============================================

    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = len(record.invoice_ids)

    def _compute_bill_count(self):
        for record in self:
            record.bill_count = len(record.bill_ids)

    def action_create_bill(self):
        """Create a new manufacturing bill pre-populated from this MO."""
        self.ensure_one()

        # Build suggested line items based on MO data
        line_vals = []
        pt = self.product_type or 'otro'

        if self.teeth_numbers:
            try:
                teeth_list = json.loads(self.teeth_numbers)
                if isinstance(teeth_list, list) and teeth_list:
                    seq = 10
                    for tooth in teeth_list:
                        line_vals.append((0, 0, {
                            'sequence': seq,
                            'product_type': pt,
                            'name': 'Diente %s' % tooth,
                            'quantity': 1.0,
                            'price_unit': 0.0,
                        }))
                        seq += 10
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback: if no teeth lines were created, add a single line
        if not line_vals:
            qty = self.product_qty if self.product_qty > 0 else 1.0
            line_vals.append((0, 0, {
                'sequence': 10,
                'product_type': pt,
                'quantity': qty,
                'price_unit': 0.0,
            }))

        # Create the bill
        bill = self.env['manufacturing.bill'].create({
            'production_id': self.id,
            'partner_id': self.doctor_id.id if self.doctor_id else (self.clinic_id.id if self.clinic_id else False),
            'patient_name': self.patient_name or '',
            'date_bill': fields.Date.context_today(self),
            'line_ids': line_vals,
        })

        # Open the new bill in form view
        return {
            'type': 'ir.actions.act_window',
            'name': 'Factura de Manufactura',
            'res_model': 'manufacturing.bill',
            'res_id': bill.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_bills(self):
        """Open linked manufacturing bills."""
        self.ensure_one()
        bills = self.bill_ids
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Facturas de Manufactura',
            'res_model': 'manufacturing.bill',
            'view_mode': 'list,form',
            'domain': [('id', 'in', bills.ids)],
        }
        if len(bills) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = bills.id
        return action

    def action_open_billing_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Crear Factura',
            'res_model': 'create.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_id': self.id,
                'default_partner_id': self.doctor_id.id if self.doctor_id else False,
            },
        }

    def action_view_invoices(self):
        self.ensure_one()
        invoices = self.invoice_ids
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Facturas',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', invoices.ids)],
            'context': {'default_move_type': 'out_invoice'},
        }
        if len(invoices) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = invoices.id
        return action

    is_manager = fields.Boolean(
        string='Es Manager',
        compute='_compute_is_manager',
        store=False # No se guarda en DB, se calcula al vuelo
    )

    def _compute_is_manager(self):
        # Verifica si el usuario actual tiene el grupo de Manager
        user_is_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')
        for record in self:
            record.is_manager = user_is_manager

    def unlink(self):
        # 1. Chequeo de seguridad (tu lógica existente)
        for record in self:
            if not self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager'):
                raise AccessError("⛔ ACCESO DENEGADO: Solo los Managers pueden eliminar órdenes de manufactura.")
        
        # 2. Llamada al método original (CORREGIDA)
        # Python 3 detecta automáticamente la clase, no pongas nombres dentro del paréntesis.
        return super().unlink()

    # =================================================================
    # ACCIONES DE APERTURA (REQUERIDAS POR EL DASHBOARD JS)
    # =================================================================

    @api.model
    def action_open_employee_active_orders(self):
        is_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')
        # MANAGER ve todo lo activo | EMPLEADO usa el helper estricto
        domain = [('state', 'in', ['confirmed', 'progress', 'to_close']), ('active', '=', True)] if is_manager else self._get_employee_base_domain()
        return self._get_action_response('Órdenes Activas', domain)

    @api.model
    def action_open_employee_delayed_orders(self):
        is_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')
        base = [('state', 'in', ['confirmed', 'progress', 'to_close']), ('active', '=', True)] if is_manager else self._get_employee_base_domain()
        # Sumamos el filtro de retraso al dominio base ya filtrado
        return self._get_action_response('Órdenes Retrasadas', base + [('time_priority', '=', 4)])

    @api.model
    def action_open_employee_urgent_orders(self):
        is_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')
        base = [('state', 'in', ['confirmed', 'progress', 'to_close']), ('active', '=', True)] if is_manager else self._get_employee_base_domain()
        # Sumamos el filtro de urgencia al dominio base ya filtrado
        return self._get_action_response('Órdenes Urgentes', base + [('is_urgent', '=', True)])

    @api.model
    def action_open_employee_pending_orders(self):
        """ Abre la lista de órdenes pendientes (Prioridad 1) """
        is_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')
        base = [('state', 'in', ['confirmed', 'progress', 'to_close']), ('active', '=', True)] if is_manager else self._get_employee_base_domain()
        return self._get_action_response('Órdenes Pendientes', base + [('time_priority', '=', 1), ('is_urgent', '=', False)])

    def _get_action_response(self, name, domain):
        """ Estructura técnica de la acción de ventana para evitar error .map() en JS """
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'mrp.production',
            'views': [[False, 'kanban'], [False, 'list'], [False, 'form']],
            'view_mode': 'kanban,list,form',
            'domain': domain,
            'target': 'current',
            'context': {'create': False}
        }

    @api.model
    def get_dashboard_order_list(self, filter_type, stage_arg=False):
        """
        Devuelve una lista de diccionarios con la info de las órdenes
        para renderizarlas directamente en el Dashboard (estilo SPA).
        """
        department_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')
        base_domain = [('state', 'in', ['confirmed', 'progress', 'to_close']), ('active', '=', True)]
        
        if not department_manager:
            # Empleados: solo ven lo asignado a ellos
            base_domain = self._get_employee_base_domain()

        domain = base_domain.copy()

        # --- Lógica de Filtros (Copiada de action_open_dashboard_list) ---
        if filter_type == 'stage':
            domain.append(('stage_custom', '=', stage_arg))
        elif filter_type == 'active':
            pass # Ya es el base_domain
        elif filter_type == 'delayed':
             domain.append(('time_priority', '=', 4))
        elif filter_type == 'urgent':
             domain.append(('is_urgent', '=', True))
        elif filter_type == 'pending':
             domain.append(('time_priority', '=', 1))
             domain.append(('is_urgent', '=', False))
        elif filter_type == 'vip':
             domain.append(('is_vip', '=', True))
        elif filter_type == 'frozen':
             # Caso especial: Congeladas pueden no estar en 'confirmed' o active?
             # Normalmente están en base_domain pero con is_frozen=True
             # Ajustamos para buscar congeladas REALES (is_frozen=True)
             # Limpiamos parte del dominio base que excluye 'to_close' si fuera necesario, 
             # pero asumimos que congeladas siguen "activas" en sistema.
             # OJO: MrpProducciónCustom.cron_update_time_priority excluye congeladas
             domain = [('is_frozen', '=', True)] 
             if not department_manager:
                 # Si empleado solo ve las suyas congeladas?
                 # Por ahora manager ve todas, empleado las suyas
                  domain += [('user_id', '=', self.env.user.id)]
        elif filter_type == 'completed':
             # Override base domain as completed orders are not 'active' in the sense of production
             domain = [('state', '=', 'done')]
             if not department_manager:
                  domain += [('user_id', '=', self.env.user.id)]

        orders = self.search(domain, order='date_deadline asc, id desc')
        
        result = []
        for o in orders:
            # Determinar clase del badge de etapa (Status Label)
            badge_class = 'badge-secondary'
            if o.stage_custom == 'laboratory': badge_class = 'badge-info'
            elif o.stage_custom == 'production': badge_class = 'badge-warning'
            elif o.stage_custom == 'testing': badge_class = 'badge-success'
            elif o.stage_custom == 'stopped': badge_class = 'badge-danger'

            # Determinar clase de color de tarjeta (Background/Border)
            # Logic matching workorder_kanban.scss
            color_class = 'o_time_green' # Default
            if o.is_frozen:
                color_class = 'o_time_frozen'
            elif o.is_delayed or (o.deadline_days is not None and o.deadline_days < 0):
                color_class = 'o_time_late'
            elif o.is_urgent:
                 color_class = 'o_time_purple' # Urgentes suelen ser críticos
            elif o.deadline_days is not None:
                if o.deadline_days <= 1:
                    color_class = 'o_time_purple'
                elif o.deadline_days <= 2:
                    color_class = 'o_time_orange'
                elif o.deadline_days <= 3:
                     color_class = 'o_time_yellow'
            
            result.append({
                'id': o.id,
                'name': o.name,
                'patient': o.patient_name or 'N/A',
                'product': o.product_id.name or 'N/A',
                'doctor': o.doctor_id.name or 'N/A',
                'stage': o.stage_custom,
                'stage_label': dict(o._fields['stage_custom'].selection).get(o.stage_custom, o.stage_custom),
                'stage_badge_class': badge_class,
                'color_class': color_class, # Nuevo campo para el dashboard
                'deadline': o.deadline_days,
                'is_vip': o.is_vip,
                'is_delayed': o.is_delayed,
                'is_urgent': o.is_urgent,
                'time_elapsed': round(o.manufacturing_time, 1),
                'teeth_count': o.teeth_count,
            })
            
        return result
