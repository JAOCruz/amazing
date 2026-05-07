# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json
from dateutil.relativedelta import relativedelta

PRODUCT_TYPE_SELECTION = [
    ('corona_zirconia', 'Corona Zirconia'),
    ('corona_zirconia_multicapa', 'Corona Zirconia Multicapa'),
    ('corona_emax', 'Corona E-max'),
    ('puente', 'Puente'),
    ('incrustacion', 'Incrustación'),
    ('carilla', 'Carilla'),
    ('protesis_parcial', 'Prótesis Parcial'),
    ('protesis_completa', 'Prótesis Completa'),
    ('provisional', 'Provisional'),
    ('encerado', 'Encerado'),
    ('planificacion', 'Planificación'),
    ('hibrida_metal', 'Híbrida Metal'),
    ('hibrida_zirconio', 'Híbrida Zirconio'),
    ('disilicato_monolitico', 'Disilicato Monolítico'),
    ('disilicato_estratificado', 'Disilicato Estratificado'),
    ('zirconio_monolitico', 'Zirconio Monolítico'),
    ('zirconio_estratificado', 'Zirconio Estratificado'),
    ('barra_blender', 'Barra Blender'),
    ('otro', 'Otro'),
]

class CreateOrderWizard(models.TransientModel):
    """
    Wizard para crear órdenes de manufactura de prótesis dentales
    con un flujo de 4 pasos, similar al NewOrderModal de React.
    """
    _name = 'create.order.wizard'
    _description = 'Wizard para Crear Orden de Manufactura'


    # ============================================
    # CONTROL DEL WIZARD
    # ============================================
    step = fields.Selection([
        ('1', 'Paso 1: Información Básica'),
        ('2', 'Paso 2: Dientes y Especificaciones'),
        ('3', 'Paso 3: Materiales Recibidos'),
        ('4', 'Paso 4: Operaciones'),
    ], string='Paso Actual', default='1', required=True)

    # ============================================
    # PASO 1: INFORMACIÓN BÁSICA
    # ============================================
    patient_name = fields.Char('Nombre del Paciente', required=True)
    doctor_id = fields.Many2one(
        'res.partner',
        string='Doctor/Odontólogo',
        required=True,
        help='Seleccione el doctor del CRM o cree uno nuevo'
    )
    clinic_id = fields.Many2one(
        'res.partner',
        string='Clínica/Hospital',
        required=True,
        help='Seleccione la clínica del CRM o cree una nueva'
    )

    # --- PRODUCTO 1 (OBLIGATORIO) ---
    product_type = fields.Selection(selection=PRODUCT_TYPE_SELECTION, 
                                    string='Tipo de Producto (Principal)', 
                                    required=True, 
                                    default='corona_zirconia')
    quantity = fields.Integer('Cant. 1', default=1, required=True)

    # --- PRODUCTO 2 (OPCIONAL) ---
    product_type_2 = fields.Selection(selection=PRODUCT_TYPE_SELECTION, 
                                      string='Tipo de Producto 2')
    quantity_2 = fields.Integer('Cant. 2', default=1)

    # --- PRODUCTO 3 (OPCIONAL) ---
    product_type_3 = fields.Selection(selection=PRODUCT_TYPE_SELECTION, 
                                      string='Tipo de Producto 3')
    quantity_3 = fields.Integer('Cant. 3', default=1)
    product_id = fields.Many2one('product.product', string='Producto Odoo',
                                  domain="[('type', 'in', ['product', 'consu'])]",
                                  help='Producto en el catálogo de Odoo')

    quantity = fields.Integer('Cantidad', default=1, required=True)

    priority = fields.Selection([
        ('normal', 'Normal'),
        ('vip', '⭐ VIP'),
        ('urgent', '🔴 Urgente'),
    ], string='Prioridad', default='normal', required=True)

    is_vip = fields.Boolean('Cliente VIP', compute='_compute_is_vip', store=True)

    # ============================================
    # PORCENTAJE EXTRA (VIP / URGENTE / CUSTOM)
    # ============================================
    extra_percentage = fields.Float(
        string='Porcentaje Extra (%)',
        default=0.0,
        help='Porcentaje adicional a cobrar sobre el precio base. Ej: 20 = +20%. No es impuesto — es un recargo manual por caso.'
    )
    extra_percentage_reason = fields.Char(
        string='Razón del Recargo',
        placeholder='Ej: VIP, Urgente, Fin de semana...',
        help='Descripción del motivo del recargo extra'
    )

    date_start = fields.Datetime(
        string='Fecha de Inicio Planificada',
        default=fields.Datetime.now,
        required=True,
        help="Fecha y hora en que se planea comenzar el trabajo."
    )
    
    date_deadline = fields.Datetime(
        string='Fecha de Entrega (Deadline)',
        default=lambda self: fields.Datetime.now() + relativedelta(days=7), # Por defecto 7 días después
        required=True,
        help="Fecha y hora límite para tener la orden lista."
    )

    deadline_days = fields.Integer('Deadline (días)', default=6, required=True,
                                    help='Tiempo límite en días para completar la orden')

    work_type = fields.Selection([
        ('digital', '💻 Digital'),
        ('analogo', '🖐️ Análogo'),
    ], string='Tipo de Trabajo', default='digital', required=True)

    # ============================================
    # PASO 2: DIENTES Y ESPECIFICACIONES
    # ============================================
    teeth_numbers = fields.Char('Números de Dientes (JSON)',
                                 help='Formato: ["18","17","16"]',
                                 default='[]')
    teeth_count = fields.Integer('Cantidad de Dientes', compute='_compute_teeth_count', store=True)
    teeth_display = fields.Char('Dientes Seleccionados', compute='_compute_teeth_count', store=True,
                                 help='Lista visual de dientes seleccionados')

    # Selección de dientes individuales (para facilitar el UI)
    # Arcada Superior
    tooth_18 = fields.Boolean('18')
    tooth_17 = fields.Boolean('17')
    tooth_16 = fields.Boolean('16')
    tooth_15 = fields.Boolean('15')
    tooth_14 = fields.Boolean('14')
    tooth_13 = fields.Boolean('13')
    tooth_12 = fields.Boolean('12')
    tooth_11 = fields.Boolean('11')
    tooth_21 = fields.Boolean('21')
    tooth_22 = fields.Boolean('22')
    tooth_23 = fields.Boolean('23')
    tooth_24 = fields.Boolean('24')
    tooth_25 = fields.Boolean('25')
    tooth_26 = fields.Boolean('26')
    tooth_27 = fields.Boolean('27')
    tooth_28 = fields.Boolean('28')

    # Arcada Inferior
    tooth_48 = fields.Boolean('48')
    tooth_47 = fields.Boolean('47')
    tooth_46 = fields.Boolean('46')
    tooth_45 = fields.Boolean('45')
    tooth_44 = fields.Boolean('44')
    tooth_43 = fields.Boolean('43')
    tooth_42 = fields.Boolean('42')
    tooth_41 = fields.Boolean('41')
    tooth_31 = fields.Boolean('31')
    tooth_32 = fields.Boolean('32')
    tooth_33 = fields.Boolean('33')
    tooth_34 = fields.Boolean('34')
    tooth_35 = fields.Boolean('35')
    tooth_36 = fields.Boolean('36')
    tooth_37 = fields.Boolean('37')
    tooth_38 = fields.Boolean('38')

    tooth_shades = fields.Char(
        string='Colores por Diente',
        default='{}',
        help='JSON con shades por tercio: {"11":{"incisal":"A1","middle":"A2","cervical":"A3"}}'
    )

    # Especificaciones de color y material
    color_scale = fields.Selection([
        ('vita_classical', 'Vita Classical'),
        ('vita_3d_master', 'Vita 3D-Master'),
        ('ivoclar', 'Ivoclar Chromascop'),
        ('otro', 'Otro'),
    ], string='Escala de Color', default='vita_classical')

    color_selected = fields.Selection([
        ('Ninguno', 'Ninguno'),
        ('BL1', 'BL1'),
        ('BL2', 'BL2'),
        ('BL3', 'BL3'),
        ('BL4', 'BL4'),
        ('A1', 'A1'),
        ('A2', 'A2'),
        ('A3', 'A3'),
        ('A3.5', 'A3.5'),
        ('A4', 'A4'),
        ('B1', 'B1'),
        ('B2', 'B2'),
        ('B3', 'B3'),
        ('B4', 'B4'),
        ('C1', 'C1'),
        ('C2', 'C2'),
        ('C3', 'C3'),
        ('C4', 'C4'),
        ('D2', 'D2'),
        ('D3', 'D3'),
        ('D4', 'D4'),
    ], string='Color Seleccionado', default='A2')

    material = fields.Selection([
        ('zirconia', 'Zirconia'),
        ('zirconia_multicapa', 'Zirconia Multicapa'),
        ('emax', 'Disilicato de Litio'),
        ('ceramica_feldespato', 'Porcelana Feldespática'),
        ('metal_ceramica', 'Metal-Cerámica'),
        ('pmma', 'PMMA'),
        ('otro', 'Otro'),
    ], string='Material', default='zirconia')

    translucency = fields.Selection([
        ('alta', 'Alta'),
        ('media', 'Media'),
        ('baja', 'Baja'),
        ('opaca', 'Opaca'),
    ], string='Translucidez', default='media')

    # ============================================
    # PASO 3: MATERIALES RECIBIDOS
    # ============================================
    qty_tibase = fields.Integer(' TIBASE', default=0)
    qty_analogo = fields.Integer(' Análogo', default=0)
    qty_tornillo = fields.Integer(' Tornillo', default=0)
    qty_transfer = fields.Integer(' Transfer', default=0)
    qty_calcinable = fields.Integer(' Calcinable', default=0)
    qty_mini_pilares = fields.Integer(' Mini Pilares', default=0)
    qty_antagonistas = fields.Integer(' Antagonistas', default=0)
    qty_encerado_superior = fields.Integer(' Encerado Superior', default=0)
    qty_encerado_inferior = fields.Integer(' Encerado Inferior', default=0)
    qty_modelo_superior = fields.Integer(' Modelo Superior', default=0)
    qty_modelo_inferior = fields.Integer(' Modelo Inferior', default=0)
    qty_mordida_superior = fields.Integer(' Mordida Superior', default=0)
    qty_mordida_inferior = fields.Integer(' Mordida Inferior', default=0)

    # Comentarios del doctor
    doctor_comments = fields.Text(
        string='Comentarios del Doctor',
        help='Instrucciones especiales o comentarios del doctor sobre el caso'
    )

    # Fotos adjuntas
    photo_ids = fields.Many2many(
        'ir.attachment',
        'wizard_order_photo_rel',
        'wizard_id',
        'attachment_id',
        string='Fotos del Caso',
        help='Fotografías del caso enviadas por el doctor'
    )

    # ============================================
    # PASO 4: OPERACIONES
    # ============================================
    operation_ids = fields.One2many('create.order.wizard.operation', 'wizard_id',
                                     string='Operaciones')

    # ============================================
    # COMPUTED FIELDS
    # ============================================
    @api.depends('priority')
    def _compute_is_vip(self):
        for wizard in self:
            wizard.is_vip = wizard.priority == 'vip'

    @api.depends('tooth_18', 'tooth_17', 'tooth_16', 'tooth_15', 'tooth_14', 'tooth_13',
                 'tooth_12', 'tooth_11', 'tooth_21', 'tooth_22', 'tooth_23', 'tooth_24',
                 'tooth_25', 'tooth_26', 'tooth_27', 'tooth_28', 'tooth_48', 'tooth_47',
                 'tooth_46', 'tooth_45', 'tooth_44', 'tooth_43', 'tooth_42', 'tooth_41',
                 'tooth_31', 'tooth_32', 'tooth_33', 'tooth_34', 'tooth_35', 'tooth_36',
                 'tooth_37', 'tooth_38')
    def _compute_teeth_count(self):
        for wizard in self:
            selected_teeth = []
            tooth_fields = [
                '18', '17', '16', '15', '14', '13', '12', '11',
                '21', '22', '23', '24', '25', '26', '27', '28',
                '48', '47', '46', '45', '44', '43', '42', '41',
                '31', '32', '33', '34', '35', '36', '37', '38'
            ]

            for tooth in tooth_fields:
                if getattr(wizard, f'tooth_{tooth}', False):
                    selected_teeth.append(int(tooth))

            wizard.teeth_numbers = json.dumps(selected_teeth)
            wizard.teeth_count = len(selected_teeth)
            # Crear lista visual de dientes seleccionados (ej: "18, 17, 16")
            wizard.teeth_display = ', '.join(str(t) for t in selected_teeth) if selected_teeth else 'Ninguno'

    # ============================================
    # MÉTODOS DE NAVEGACIÓN
    # ============================================
    def action_next_step(self):
        """Avanzar al siguiente paso"""
        self.ensure_one()

        # Validar paso actual antes de avanzar
        if self.step == '1':
            if not self.patient_name or not self.doctor_id or not self.product_type:
                raise UserError(_('Por favor complete todos los campos requeridos en Paso 1.'))
            self.step = '2'
        elif self.step == '2':
            self.step = '3'
        elif self.step == '3':
            self.step = '4'
            # Crear operaciones por defecto si no existen
            if not self.operation_ids:
                self._create_default_operations()

        return self._reopen_wizard()

    def action_previous_step(self):
        """Retroceder al paso anterior"""
        self.ensure_one()

        if self.step == '2':
            self.step = '1'
        elif self.step == '3':
            self.step = '2'
        elif self.step == '4':
            self.step = '3'

        return self._reopen_wizard()

    def _reopen_wizard(self):
        """Reabrir el wizard en el mismo registro"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_default_workcenter(self):
        # Intenta buscar el centro 'Assembly 1' que vi en tus fotos
        wc = self.env['mrp.workcenter'].search([('name', '=', 'Assembly 1')], limit=1)
        # Si no existe, agarra el primero que encuentre
        if not wc:
            wc = self.env['mrp.workcenter'].search([], limit=1)
        return wc

    # ============================================
    # CREACIÓN DE OPERACIONES POR DEFECTO
    # ============================================
    def _create_default_operations(self):
        """Crear operaciones por defecto basadas en el tipo de trabajo"""
        self.ensure_one()

        default_ops = [
            {'name': 'Cita por Bot', 'duration': 0.5, 'department': 'sistema'},
            {'name': 'Diseño STL', 'duration': 12, 'department': 'diseno'},
            {'name': 'Fresado CNC', 'duration': 24, 'department': 'fresado'},
            {'name': 'Área de Cerámica', 'duration': 18, 'department': 'ceramica'},
            {'name': 'Colado/Prensado', 'duration': 16, 'department': 'prensado'},
            {'name': 'Área de Metal', 'duration': 20, 'department': 'produccion'},
        ]

        sequence = 1
        for op_data in default_ops:
            self.env['create.order.wizard.operation'].create({
                'wizard_id': self.id,
                'name': op_data['name'],
                'duration': op_data['duration'],
                'department': op_data['department'],
                'sequence': sequence,
            })
            sequence += 1

    # ============================================
    # CREACIÓN DE ORDEN
    # ============================================
    def action_create_order(self):
        """Crear UNA sola orden de manufactura. Los productos extra se agregan como notas."""
        self.ensure_one()

        # 0. SEGURIDAD
        if not self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager'):
            raise AccessError("No tienes permisos para crear órdenes de manufactura.")

        # =========================================================
        # A. PREPARAR DESCRIPCIÓN DE PRODUCTOS EXTRA
        # =========================================================
        extra_products_info = []
        
        if self.product_type_2:
            prod_name_2 = dict(self._fields['product_type_2'].selection).get(self.product_type_2)
            extra_products_info.append(f"🔹 ADICIONAL: {prod_name_2} (Cant: {self.quantity_2})")
            
        if self.product_type_3:
            prod_name_3 = dict(self._fields['product_type_3'].selection).get(self.product_type_3)
            extra_products_info.append(f"🔹 ADICIONAL: {prod_name_3} (Cant: {self.quantity_3})")

        # Fusionamos notas
        final_notes = self.doctor_comments or ""
        if extra_products_info:
            final_notes += "\n\n--- 📦 OTROS PRODUCTOS EN ESTE CASO ---\n" + "\n".join(extra_products_info)


        # =========================================================
        # B. BUSCAR/CREAR EL PRODUCTO PRINCIPAL
        # =========================================================
        target_product_id = False
        if self.product_id:
            target_product_id = self.product_id
        else:
            product_name = f'{self.product_type.replace("_", " ").title()}'
            product = self.env['product.product'].search([('name', '=', product_name)], limit=1)
            if not product:
                product = self.env['product.product'].create({'name': product_name, 'type': 'consu'})
            target_product_id = product

        # Buscar BOM
        bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', target_product_id.product_tmpl_id.id)], limit=1)
        if not bom:
            bom = self.env['mrp.bom'].create({
                'product_tmpl_id': target_product_id.product_tmpl_id.id,
                'product_qty': 1.0,
                'type': 'normal',
            })

        # =========================================================
        # C. LOGICA DE PRIORIDAD
        # =========================================================
        val_priority = '0'
        val_is_vip = False
        val_manual_urgency = False

        if self.priority == 'vip':
            val_priority = '1'
            val_is_vip = True
        elif self.priority == 'urgent':
            val_priority = '1'
            val_manual_urgency = True

        # =========================================================
        # D. CREAR LA ÚNICA ORDEN DE MANUFACTURA
        # =========================================================
        production_vals = {
            'product_id': target_product_id.id,
            'product_qty': self.quantity,
            'bom_id': bom.id,
            'priority': val_priority,
            'is_vip': val_is_vip,
            'manual_urgency': val_manual_urgency,
            'patient_name': self.patient_name,
            'doctor_id': self.doctor_id.id,
            'clinic_id': self.clinic_id.id,
            'product_type': self.product_type,
            'work_type': self.work_type,
            'teeth_numbers': self.teeth_numbers,
            'teeth_count': self.teeth_count,
            'tooth_shades': self.tooth_shades or '{}',
            'color_scale': self.color_scale,
            'color_selected': self.color_selected,
            'material': self.material,
            'translucency': self.translucency,
            'qty_tibase': self.qty_tibase,
            'qty_analogo': self.qty_analogo,
            'qty_tornillo': self.qty_tornillo,
            'qty_transfer': self.qty_transfer,
            'qty_calcinable': self.qty_calcinable,
            'qty_mini_pilares': self.qty_mini_pilares,
            'qty_antagonistas': self.qty_antagonistas,
            'qty_encerado_superior': self.qty_encerado_superior,
            'qty_encerado_inferior': self.qty_encerado_inferior,
            'qty_modelo_superior': self.qty_modelo_superior,
            'qty_modelo_inferior': self.qty_modelo_inferior,
            'qty_mordida_superior': self.qty_mordida_superior,
            'qty_mordida_inferior': self.qty_mordida_inferior,
            'doctor_comments': final_notes, 
            'photo_ids': [(6, 0, self.photo_ids.ids)], 
            #'date_planned_start': self.date_start,
            'date_deadline': self.date_deadline,
            'date_start': self.date_start,
            #'deadline_days': self.deadline_days,
            'manufacturing_start_date': self.date_start,
            'stage_custom': 'laboratory',
            'extra_percentage': self.extra_percentage,
            'extra_percentage_reason': self.extra_percentage_reason,
        }

        production = self.env['mrp.production'].create(production_vals)
        production.action_confirm()

        # =========================================================
        # E. ACTUALIZAR WORKORDERS (CON CORRECCIÓN DE TIEMPO)
        # =========================================================
        for wizard_op in self.operation_ids:
            workorder = self.env['mrp.workorder'].search([
                ('production_id', '=', production.id),
                ('name', '=', wizard_op.name)
            ], limit=1)

            if not workorder:
                workorder = self.env['mrp.workorder'].create({
                    'production_id': production.id,
                    'name': wizard_op.name,
                    'workcenter_id': self._get_default_workcenter().id,
                    'product_id': production.product_id.id,
                    'product_uom_id': production.product_uom_id.id,
                    'state': 'pending', 
                })

            workorder.write({
                'user_id': wizard_op.employee_id.id if wizard_op.employee_id else False,
                # 👇 AQUÍ ESTÁ EL ARREGLO IMPORTANTE 👇
                'duration_expected': wizard_op.duration * 60.0, # Convertir horas a minutos para Odoo
                'alert_time_hours': wizard_op.duration,         # Guardar horas para tu dashboard
                'sequence_in_user_queue': wizard_op.sequence,
                # Fix: Set date_start explicitly to prevent Odoo's scheduler from
                # blocking creation when deadline < total operations duration.
                # We manage scheduling ourselves via the dashboard.
                'date_start': self.date_start,
            })

        # =========================================================
        # F. RETORNO
        # =========================================================
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'res_id': production.id,
            'view_mode': 'form',
            'target': 'current',
        }

class CreateOrderWizardOperation(models.TransientModel):
    """
    Líneas de operaciones para el wizard de creación de órdenes
    """
    _name = 'create.order.wizard.operation'
    _description = 'Operación del Wizard'
    _order = 'sequence, id'

    wizard_id = fields.Many2one('create.order.wizard', string='Wizard', required=True, ondelete='cascade')

    sequence = fields.Integer('Secuencia', default=10)
    name = fields.Selection([
        ('Cita por Bot', 'Cita por Bot'),
        ('Diseño STL', 'Diseño STL'),
        ('Fresado CNC', 'Fresado CNC'),
        ('Área de Cerámica', 'Área de Cerámica'),
        ('Colado/Prensado', 'Colado/Prensado'),
        ('Área de Metal', 'Área de Metal'),
        ('Maquillaje', 'Maquillaje'),
        ('Glaseado', 'Glaseado'),
        ('Terminado', 'Terminado'),
        ('Sistema', 'Sistema'),
        ('Printer', 'Printer'),
        ('Mensajería', 'Mensajería'),
        ('Pieza para cortar en blender', 'Pieza para cortar en blender'),
        ('Adaptado de Metal', 'Adaptado de Metal'),
        ('Adaptado de Zirconio Sobre T-BASE', 'Adaptado de Zirconio Sobre T-BASE'),
        ('Calibrado de metal', 'Calibrado de metal'),
        ('Calibrado de zirconio', 'Calibrado de zirconio'),
        ('Adaptación de Pilares', 'Adaptación de Pilares'),
        ('Personalización de pilares metales', 'Personalización de pilares metales'),
        ('Elección de pilares en biblioteca', 'Elección de pilares en biblioteca'),
    ], string='Nombre de Operación', required=True)
    duration = fields.Float('Duración Estimada (horas)', default=8.0, required=True)

    department = fields.Selection([
        ('diseno', 'Diseño'),
        ('fresado', 'Fresado'),
        ('ceramica', 'Cerámica'),
        ('prensado', 'Prensado'),
        ('produccion', 'Producción'),
        ('maquillaje', 'Maquillaje'),
        ('sistema', 'Sistema'),
        ('printer', 'Printer'),
        ('mensajeria', 'Mensajería'),
    ], string='Departamento')

    employee_id = fields.Many2one('res.users', string='Empleado Asignado')
