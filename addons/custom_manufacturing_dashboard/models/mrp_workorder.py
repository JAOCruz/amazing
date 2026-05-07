# -*- coding: utf-8 -*-

import logging
from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class MrpWorkorderCustom(models.Model):
    _inherit = 'mrp.workorder'
    _description = 'Workorder Extended (Custom Manufacturing Dashboard)'

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
    ], string='Operación', required=True, index=True)

    time_status = fields.Selection(
        related='production_id.time_status',
        store=True,
        readonly=True,
    )

    time_priority = fields.Integer(
        related='production_id.time_priority',
        store=True,
        readonly=True,
    )   

    # ============================================
    # EMPLEADO ASIGNADO
    # ============================================

    user_id = fields.Many2one(
        'res.users',
        string='Empleado Asignado',
        help='Usuario asignado a esta operación'
    )

    # ============================================
    # TRACKING DE OPERACIONES
    # ============================================

    operation_start_date = fields.Datetime(
        string='Inicio de Operación',
        help='Fecha y hora de inicio de la operación',
        index=True
    )

    operation_time = fields.Float(
        string='Tiempo de Operación (horas)',
        compute='_compute_operation_time',
        store=False,  # Changed to False - recalculate in real-time
        help='Horas transcurridas desde el inicio de la operación'
    )

    alert_time_hours = fields.Float(
        string='Tiempo Estimado (horas)',
        default=1.0,  # Changed from 24.0 to 1.0 hour for more realistic testing
        required=True,
        help='Tiempo estimado para completar esta operación en horas'
    )

    # ============================================
    # ALERTAS DE OPERACIÓN
    # ============================================

    is_operation_delayed = fields.Boolean(
        string='OPERACIÓN RETRASADA',
        compute='_compute_operation_alert_status',
        store=False,  # Changed to False - recalculate in real-time based on operation_time
        index=False,  # Can't index computed non-stored fields
        help='La operación ha excedido el tiempo estimado'
    )

    is_operation_urgent = fields.Boolean(
        string='Operación Urgente',
        compute='_compute_operation_alert_status',
        store=False,  # Changed to False - recalculate in real-time based on operation_time
        index=False,  # Can't index computed non-stored fields
        help='La operación está cerca del tiempo estimado (>80%)'
    )

    # ============================================
    # GESTIÓN DE COLA
    # ============================================

    sequence_in_user_queue = fields.Integer(
        string='Secuencia en Cola del Usuario',
        default=10,
        help='Orden de prioridad en la cola del empleado asignado'
    )

    # ============================================
    # TRACKING DE ALERTAS
    # ============================================

    last_next_wo_waiting_alert = fields.Datetime(
        string='Última Alerta: WO Siguiente Esperando',
        help='Fecha y hora de la última alerta enviada sobre esta workorder esperando a iniciar'
    )

    duration_hours = fields.Float(
        string='Duración Real (Horas)',
        compute='_compute_duration_hours',
        store=False
    )

    @api.depends('duration', 'state', 'date_start')
    def _compute_duration_hours(self):
        for record in self:
            # Empezamos con la duración que ya está guardada "en firme"
            total_minutes = record.duration
            
            # TRUCO: Si está "En Progreso", sumamos el tiempo desde que inició hasta AHORA
            if record.state == 'progress' and record.date_start:
                now = fields.Datetime.now()
                # Calculamos la diferencia de tiempo
                diff = now - record.date_start
                # Convertimos esa diferencia a minutos y sumamos
                total_minutes += (diff.total_seconds() / 60)

            # Convertimos el gran total de minutos a Horas
            record.duration_hours = total_minutes / 60.0

    def button_start(self):
        for wo in self:
            if wo.production_id.state == 'test':
                raise UserError(
                    "Esta orden está en prueba médica y no puede ser trabajada."
                )
        return super().button_start()

    # ============================================
    # SEGURIDAD DE BORRADO Y CREACIÓN
    # ============================================

    def unlink(self):
        """
        Bloquea el botón de borrar (basura) para quien no sea Manager.
        """
        # Chequeamos si el usuario tiene el permiso de Manager
        is_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')
        
        # Si NO es manager, lanzamos una alerta roja
        if not is_manager:
            raise UserError("⛔ ACCESO DENEGADO: Solo los Managers pueden borrar órdenes de trabajo.")
            
        # CORRECCIÓN AQUÍ:
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        """
        Evita que usuarios no-managers creen órdenes de trabajo manualmente
        (Excepto si el sistema las crea automáticamente desde la BOM)
        """
        # Permitimos si es el sistema (superusuario) o si es manager
        is_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')
        is_system = self.env.su # El sistema creando desde BOM suele actuar como sudo/system
        
        # Nota: A veces Odoo crea WOs automáticamente con el usuario actual. 
        # Si esto bloquea la confirmación de la MO, puedes comentar esta validación de 'create'
        # y dejar solo la de 'unlink'.
        
        # if not is_manager and not is_system and not self._context.get('default_production_id'):
        #     raise UserError("Solo los Managers pueden crear líneas de trabajo manualmente.")

        return super(MrpWorkorderCustom, self).create(vals_list)

    # ============================================
    # COMPUTED FIELDS
    # ============================================

    @api.depends('operation_start_date')
    def _compute_operation_time(self):
        """Calcula las horas transcurridas desde el inicio de la operación"""
        for record in self:
            if record.operation_start_date:
                now = fields.Datetime.now()
                delta = now - record.operation_start_date
                record.operation_time = delta.total_seconds() / 3600.0  # Convertir a horas
            else:
                record.operation_time = 0.0

    @api.depends('operation_time', 'alert_time_hours', 'state', 'date_start')
    def _compute_operation_alert_status(self):
        """
        Calcula el estado de alertas de la operación.
        Corregido: Usa 'date_start' en lugar de 'date_planned_start'.
        """
        now = fields.Datetime.now()
        
        for record in self:
            # Si la orden está congelada o en estados irrelevantes, limpiamos flags
            if record.production_id.is_frozen or record.state in ['done', 'cancel', 'draft']:
                record.is_operation_delayed = False
                record.is_operation_urgent = False
                continue

            urgent_threshold = record.alert_time_hours * 0.8
            
            # --- CASO 1: RETRASO DE INICIO ---
            # En Odoo 17+, 'date_start' suele tener la fecha programada mientras el estado sea 'ready'/'waiting'.
            # Si debería haber empezado (fecha < ahora) y sigue esperando.
            is_late_to_start = False
            
            # Usamos getattr por seguridad, aunque date_start debería existir
            scheduled_date = record.date_start 
            
            if record.state in ['ready', 'waiting'] and scheduled_date and scheduled_date < now:
                is_late_to_start = True

            # --- CASO 2: RETRASO DE DURACIÓN ---
            # Ya está en proceso pero se pasó del tiempo
            is_overtime = False
            if record.state == 'progress' and record.operation_time > record.alert_time_hours:
                is_overtime = True

            # --- EVALUACIÓN FINAL ---
            
            if is_late_to_start or is_overtime:
                record.is_operation_delayed = True
                record.is_operation_urgent = False
            
            # Urgent: está cerca del tiempo estimado (>80%) - Solo si está en progreso
            elif record.state == 'progress' and record.operation_time > urgent_threshold:
                record.is_operation_delayed = False
                record.is_operation_urgent = True

            # Normal
            else:
                record.is_operation_delayed = False
                record.is_operation_urgent = False

    # ============================================
    # VALIDACIONES
    # ============================================

    @api.constrains('alert_time_hours')
    def _check_alert_time_hours(self):
        """Valida que el tiempo estimado sea positivo"""
        for record in self:
            if record.alert_time_hours <= 0:
                raise ValidationError('El tiempo estimado debe ser mayor a 0 horas.')

    @api.constrains('sequence_in_user_queue')
    def _check_sequence_in_user_queue(self):
        """Valida que la secuencia sea positiva"""
        for record in self:
            if record.sequence_in_user_queue < 0:
                raise ValidationError('La secuencia en cola debe ser un número positivo.')

    # ============================================
    # MÉTODOS DE NEGOCIO
    # ============================================

    def action_start_operation(self):
        """Inicia la operación estableciendo la fecha de inicio"""
        for record in self:
            if not record.operation_start_date:
                record.operation_start_date = fields.Datetime.now()
                _logger.info(f"Operation started for workorder {record.name}")

                # También iniciar la manufactura si no ha iniciado
                if record.production_id and not record.production_id.manufacturing_start_date:
                    record.production_id.manufacturing_start_date = fields.Datetime.now()

    def button_start(self):
        """
        Override button_start para validar:
        0. La orden no esté congelada
        1. Solo el usuario asignado (O UN MANAGER) puede iniciar su workorder
        2. Las workorders deben completarse en orden secuencial
        """
        # Verificamos si el usuario es manager
        is_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')

        for wo in self:
            # VALIDACIÓN 0: Orden congelada
            if wo.production_id.is_frozen:
                raise UserError(_(
                    "❄️ La orden de manufactura está CONGELADA.\n\n"
                    "No puedes iniciar operaciones hasta que sea descongelada."
                ))

            # VALIDACIÓN 1: Solo el usuario asignado O un Manager puede iniciar
            # Agregamos "and not is_manager" para permitir el paso a los jefes
            if wo.user_id and wo.user_id != self.env.user and not is_manager:
                raise UserError(_(
                    "❌ No puedes iniciar esta orden de trabajo.\n\n"
                    "Esta operación está asignada a: %s\n"
                    "Tú eres: %s\n\n"
                    "(Solo el asignado o un Manager pueden iniciarla)"
                ) % (wo.user_id.name, self.env.user.name))

            # VALIDACIÓN 2: Orden secuencial (Esto usualmente se mantiene incluso para managers para no romper el flujo,
            # pero si quieres que también se salten el orden, agrega "and not is_manager" aquí también)
            all_wos = wo.production_id.workorder_ids.sorted('sequence')
            previous_wos = all_wos.filtered(lambda w: w.sequence < wo.sequence)
            not_done = previous_wos.filtered(lambda w: w.state != 'done')

            if not_done:
                raise UserError(_(
                    "❌ No puedes iniciar esta orden de trabajo.\n\n"
                    "Debes finalizar primero la operación anterior:\n"
                    "• %s (asignada a: %s)"
                ) % (
                    not_done[0].name,
                    not_done[0].user_id.name if not_done[0].user_id else 'Sin asignar'
                ))

        return super().button_start()

    # Job Order Button History Pause

    def button_pending(self):
        """
        Override button_pending para validar que solo el usuario asignado puede pausar
        """
        is_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')

        for wo in self:
            # VALIDACIÓN: Solo el usuario asignado O un Manager puede pausar
            if wo.user_id and wo.user_id != self.env.user and not is_manager:
                raise UserError(_(
                    "❌ No puedes pausar esta orden de trabajo.\n\n"
                    "Esta operación está asignada a: %s\n"
                    "Tú eres: %s"
                ) % (wo.user_id.name, self.env.user.name))

        res = super().button_pending()
        
        # El resto de tu código de notificaciones sigue igual...
        for wo in self:
            wo.message_post(
                body=_("⏸️ <b>Orden de Trabajo Pausada</b><br/>User: %s")
                % self.env.user.name
            )
            wo.production_id.message_post(
                body=_("⏸️ Orden de Trabajo Pausada: %s") % wo.name
            )
        return res

    def button_finish(self):
        """
        Override button_finish para validar que solo el usuario asignado puede finalizar
        """
        is_manager = self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager')

        for wo in self:
            # VALIDACIÓN: Orden Congelada o no
            if wo.production_id.is_frozen:
                raise UserError("❄️ La orden está congelada.")
                # return super().button_finish()  <-- OJO: Tenías este return inalcanzable después del raise, bórralo
            
            # VALIDACIÓN: Solo el usuario asignado O un Manager puede finalizar
            if wo.user_id and wo.user_id != self.env.user and not is_manager:
                raise UserError(_(
                    "❌ No puedes finalizar esta orden de trabajo.\n\n"
                    "Esta operación está asignada a: %s\n"
                    "Tú eres: %s"
                ) % (wo.user_id.name, self.env.user.name))

        # Llamar al método original
        result = super().button_finish()

        # Post messages after finishing (Tu código existente...)
        for record in self:
            record.message_post(
                body=_("✅ Orden de Trabajo Finalizada"),
                subtype_xmlid='mail.mt_note'
            )
            if record.production_id:
                record.production_id.message_post(
                    body=_("✅ Orden de Trabajo Terminada: %s") % record.name,
                    subtype_xmlid='mail.mt_note'
                )

        return result

    def action_simulate_delay(self):
        """Botón de prueba: simula que esta operación comenzó hace 2 minutos"""
        for record in self:
            # Set start date to 2 minutes ago
            two_minutes_ago = fields.Datetime.now() - timedelta(minutes=2)
            record.operation_start_date = two_minutes_ago

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'⏰ Start date set to 2 minutes ago for testing',
                    'type': 'success',
                    'sticky': False,
                }
            }

    def action_check_alerts_now(self):
        """Botón de prueba: verifica alertas inmediatamente para ESTA operación"""
        for record in self:
            # Force recompute
            record.invalidate_recordset(['operation_time', 'is_operation_delayed', 'is_operation_urgent'])

            _logger.warning(f"🧪 MANUAL CHECK for {record.name}")
            _logger.warning(f"   - Alert time: {record.alert_time_hours} hours")
            _logger.warning(f"   - Elapsed time: {record.operation_time} hours")
            _logger.warning(f"   - Is Delayed: {record.is_operation_delayed}")
            _logger.warning(f"   - Is Urgent: {record.is_operation_urgent}")

            # Check for existing messages
            messages = record.message_ids.filtered(
                lambda m: '🔴 OPERACIÓN RETRASADA' in (m.body or '') or '⚠️ OPERACIÓN URGENTE' in (m.body or '')
            )

            _logger.warning(f"   - Previous alert messages: {len(messages)}")

            # Post delayed message if needed
            if record.is_operation_delayed and not any('🔴 OPERACIÓN RETRASADA' in (m.body or '') for m in messages):
                delay_hours = record.operation_time - record.alert_time_hours
                record.message_post(
                    body=_(
                        "🔴 <b>OPERACIÓN RETRASADA</b> (Test Manual)<br/>"
                        "Tiempo estimado: %.4f horas<br/>"
                        "Tiempo transcurrido: %.4f horas<br/>"
                        "Retraso: %.4f horas"
                    ) % (
                        record.alert_time_hours,
                        record.operation_time,
                        delay_hours
                    )
                )
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'🔴 RETRASADA: {delay_hours:.4f} horas de retraso',
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            # Post urgent message if needed
            elif record.is_operation_urgent and not any('⚠️ OPERACIÓN URGENTE' in (m.body or '') for m in messages):
                remaining_hours = record.alert_time_hours - record.operation_time
                percentage = (record.operation_time / record.alert_time_hours) * 100

                record.message_post(
                    body=_(
                        "⚠️ <b>Operación URGENTE</b> (Test Manual)<br/>"
                        "Progreso: %.1f%% del tiempo consumido<br/>"
                        "Tiempo restante: %.4f horas"
                    ) % (
                        percentage,
                        remaining_hours
                    )
                )
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'⚠️ URGENTE: {percentage:.1f}% del tiempo usado',
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'✅ OK: {record.operation_time:.4f}h / {record.alert_time_hours:.4f}h ({(record.operation_time/record.alert_time_hours*100):.1f}%)',
                        'type': 'success',
                        'sticky': False,
                    }
                }

    @api.model
    def get_employee_workload_dashboard(self, user_id=None):
        """
        Retorna datos para dashboard de empleado individual

        Args:
            user_id (int, optional): ID del usuario. Si no se proporciona, usa el usuario actual.

        Returns:
            dict: Estructura de datos con información del usuario y su cola de trabajo
        """
        
        if user_id is None:
            user = self.env.user
        else:
            user = self.env['res.users'].browse(user_id)

        # =================================================================
        # MODIFICACIÓN AQUÍ
        # Agregamos la condición para excluir 'laboratory'
        # =================================================================
        my_operations = self.search([
            ('user_id', '=', user.id),
            ('state', 'in', ['pending', 'ready', 'progress']),
            ('production_id.stage_custom', '!=', 'laboratory')  # <--- ESTA ES LA CLAVE
        ], order='sequence_in_user_queue, id')

        # Preparar datos de la cola
        queue_data = []
        for operation in my_operations:
            queue_data.append(operation._prepare_dashboard_data())

        # Obtener alertas en cascada
        cascade_alerts = self._get_cascade_alerts(user)

        return {
            'user': {
                'id': user.id,
                'name': user.name,
                'department': user.department if hasattr(user, 'department') else False,
                'workload_status': user.workload_status if hasattr(user, 'workload_status') else 'available',
            },
            'queue': queue_data,
            'cascade_alerts': cascade_alerts,
            'stats': {
                'total_operations': len(my_operations),
                'delayed_operations': len([op for op in my_operations if op.is_operation_delayed]),
                'urgent_operations': len([op for op in my_operations if op.is_operation_urgent]),
            }
        }

    # Job Order Button History Pause


    def _prepare_dashboard_data(self):
        """
        Prepara los datos de esta operación para el dashboard

        Returns:
            dict: Datos de la operación formateados para el dashboard
        """
        self.ensure_one()

        return {
            'id': self.id,
            'name': self.name,
            'workcenter': self.workcenter_id.name if self.workcenter_id else 'N/A',
            'production_id': self.production_id.id if self.production_id else False,
            'production_name': self.production_id.name if self.production_id else 'N/A',
            'patient_name': self.production_id.patient_name if self.production_id else 'N/A',
            'product': self.product_id.name if self.product_id else 'N/A',
            'state': self.state,
            'operation_time': round(self.operation_time, 2),
            'alert_time_hours': self.alert_time_hours,
            'is_operation_delayed': self.is_operation_delayed,
            'is_operation_urgent': self.is_operation_urgent,
            'sequence': self.sequence_in_user_queue,
            'is_vip': self.production_id.is_vip if self.production_id else False,
        }

    def _get_cascade_alerts(self, user):
        """
        Obtiene alertas en cascada: si una operación anterior está retrasada,
        todas las siguientes en la cadena están en riesgo

        Args:
            user (res.users): Usuario para quien obtener las alertas

        Returns:
            list: Lista de alertas en cascada
        """
        cascade_alerts = []

        # Buscar producciones donde el usuario tenga operaciones
        production_ids = self.search([
            ('user_id', '=', user.id),
            ('state', 'in', ['pending', 'ready', 'progress'])
        ]).mapped('production_id')

        for production in production_ids:
            # Obtener todas las operaciones de esta producción ordenadas
            all_operations = production.workorder_ids.sorted(key=lambda r: r.id)

            # Verificar si alguna operación anterior está retrasada
            for idx, operation in enumerate(all_operations):
                # Si esta operación está retrasada
                if operation.is_operation_delayed:
                    # Todas las siguientes están en riesgo
                    following_operations = all_operations[idx + 1:]

                    for following_op in following_operations:
                        # Si el usuario actual tiene alguna de las siguientes
                        if following_op.user_id.id == user.id:
                            cascade_alerts.append({
                                'production_name': production.name,
                                'blocked_by_operation': operation.name,
                                'blocked_by_user': operation.user_id.name if operation.user_id else 'N/A',
                                'affected_operation': following_op.name,
                                'delay_hours': round(operation.operation_time - operation.alert_time_hours, 2),
                            })

        return cascade_alerts

    # ============================================
    # NOTIFICACIONES INTERNAS
    # ============================================

    def notify_operation_assigned(self):
        """
        Notifica al empleado cuando se le asigna una nueva operación
        """
        for record in self:
            if not record.user_id:
                continue

            # Información de la orden de producción asociada
            production = record.production_id
            patient_info = f" - Paciente: {production.patient_name}" if production and production.patient_name else ""
            vip_badge = "⭐ CLIENTE VIP - PRIORIDAD ALTA" if production and production.is_vip else ""

            message = f"""
                <p><strong>🔔 Nueva Operación Asignada</strong></p>
                <ul>
                    <li><strong>Operación:</strong> {record.name}</li>
                    <li><strong>Centro de Trabajo:</strong> {record.workcenter_id.name if record.workcenter_id else 'N/A'}</li>
                    <li><strong>Orden de Producción:</strong> {production.name if production else 'N/A'}{patient_info}</li>
                    <li><strong>Tiempo Estimado:</strong> {record.alert_time_hours:.1f} horas</li>
                    <li><strong>Secuencia en Cola:</strong> {record.sequence_in_user_queue}</li>
                    {f'<li><strong>{vip_badge}</strong></li>' if vip_badge else ''}
                </ul>
                <p><a href="/web#id={record.id}&model=mrp.workorder&view_type=form">👉 Ver operación completa</a></p>
            """

            record.message_post(
                body=message,
                subject=f'🔔 Nueva operación asignada: {record.name}',
                message_type='notification',
                subtype_xmlid='mail.mt_note',
                partner_ids=[record.user_id.partner_id.id],
            )

            _logger.info(f"Assignment notification sent to {record.user_id.name} for workorder {record.name}")

    def notify_operation_urgent(self):
        """
        Notifica cuando la operación está cerca de exceder el tiempo estimado (>80%)
        """
        for record in self:
            if not record.is_operation_urgent or not record.user_id:
                continue

            # Calcular tiempo restante
            remaining_hours = record.alert_time_hours - record.operation_time
            percentage = (record.operation_time / record.alert_time_hours) * 100

            production = record.production_id
            patient_info = f"Paciente: {production.patient_name}" if production and production.patient_name else "N/A"

            message = f"""
                <p><strong>⚠️ OPERACIÓN URGENTE - Tiempo por Vencer</strong></p>
                <ul>
                    <li><strong>Operación:</strong> {record.name}</li>
                    <li><strong>Centro de Trabajo:</strong> {record.workcenter_id.name if record.workcenter_id else 'N/A'}</li>
                    <li><strong>Orden:</strong> {production.name if production else 'N/A'}</li>
                    <li><strong>{patient_info}</strong></li>
                    <li><strong>Progreso:</strong> {percentage:.1f}% del tiempo estimado consumido</li>
                    <li><strong>Tiempo restante:</strong> {remaining_hours:.1f} horas</li>
                    <li><strong>Tiempo estimado:</strong> {record.alert_time_hours:.1f} horas</li>
                </ul>
                <p><a href="/web#id={record.id}&model=mrp.workorder&view_type=form">👉 Ver operación y actualizar</a></p>
            """

            record.message_post(
                body=message,
                subject=f'⚠️ OPERACIÓN URGENTE: {record.name}',
                message_type='notification',
                subtype_xmlid='mail.mt_note',
                partner_ids=[record.user_id.partner_id.id],
            )

            # También notificar a managers
            managers = self.env.ref('custom_manufacturing_dashboard.group_manufacturing_manager').users
            if managers:
                record.message_post(
                    body=message,
                    subject=f'⚠️ OPERACIÓN URGENTE de {record.user_id.name}: {record.name}',
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                    partner_ids=managers.mapped('partner_id').ids,
                )

            _logger.warning(
                f"Urgent notification sent for workorder {record.name}. "
                f"Progress: {percentage:.1f}%. User: {record.user_id.name}"
            )

    def notify_operation_delayed(self):
        """
        Notifica cuando la operación ha excedido el tiempo estimado
        """
        for record in self:
            if not record.is_operation_delayed or not record.user_id:
                continue

            # Calcular exceso de tiempo
            delay_hours = record.operation_time - record.alert_time_hours

            production = record.production_id
            patient_info = f"Paciente: {production.patient_name}" if production and production.patient_name else "N/A"

            message = f"""
                <p><strong>🔴 OPERACIÓN RETRASADA</strong></p>
                <ul>
                    <li><strong>Operación:</strong> {record.name}</li>
                    <li><strong>Centro de Trabajo:</strong> {record.workcenter_id.name if record.workcenter_id else 'N/A'}</li>
                    <li><strong>Orden:</strong> {production.name if production else 'N/A'}</li>
                    <li><strong>{patient_info}</strong></li>
                    <li><strong>Retraso:</strong> {delay_hours:.1f} horas</li>
                    <li><strong>Tiempo estimado:</strong> {record.alert_time_hours:.1f} horas</li>
                    <li><strong>Tiempo transcurrido:</strong> {record.operation_time:.1f} horas</li>
                </ul>
                <p><strong>⚠️ Esta demora puede afectar operaciones siguientes en la cadena</strong></p>
                <p><a href="/web#id={record.id}&model=mrp.workorder&view_type=form">👉 Ver operación y resolver</a></p>
            """

            record.message_post(
                body=message,
                subject=f'🔴 OPERACIÓN RETRASADA: {record.name}',
                message_type='notification',
                subtype_xmlid='mail.mt_note',
                partner_ids=[record.user_id.partner_id.id],
            )

            # También notificar a managers
            managers = self.env.ref('custom_manufacturing_dashboard.group_manufacturing_manager').users
            if managers:
                record.message_post(
                    body=message,
                    subject=f'🔴 OPERACIÓN RETRASADA de {record.user_id.name}: {record.name}',
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                    partner_ids=managers.mapped('partner_id').ids,
                )

            _logger.error(
                f"Delayed notification sent for workorder {record.name}. "
                f"Delay: {delay_hours:.1f} hours. User: {record.user_id.name}"
            )

    def notify_cascade_alert(self):
        """
        Notifica a empleados afectados cuando una operación anterior está retrasada
        y sus operaciones están en riesgo (alerta en cascada)
        """
        for record in self:
            if not record.is_operation_delayed or not record.production_id:
                continue

            # Obtener todas las operaciones siguientes en esta producción
            all_operations = record.production_id.workorder_ids.sorted(key=lambda r: r.id)

            # Encontrar índice de la operación actual
            try:
                current_idx = list(all_operations).index(record)
            except ValueError:
                continue

            # Operaciones siguientes
            following_operations = all_operations[current_idx + 1:]

            for following_op in following_operations:
                if not following_op.user_id:
                    continue

                delay_hours = record.operation_time - record.alert_time_hours

                message = f"""
                    <p><strong>⛔ ALERTA EN CASCADA - Operación Bloqueada</strong></p>
                    <p>Una operación anterior está retrasada, afectando tu operación:</p>
                    <ul>
                        <li><strong>Tu Operación:</strong> {following_op.name}</li>
                        <li><strong>Bloqueada por:</strong> {record.name}</li>
                        <li><strong>Usuario bloqueante:</strong> {record.user_id.name if record.user_id else 'No asignado'}</li>
                        <li><strong>Orden:</strong> {record.production_id.name}</li>
                        <li><strong>Retraso causante:</strong> {delay_hours:.1f} horas</li>
                    </ul>
                    <p><strong>⚠️ Tu operación podría retrasarse. Coordina con {record.user_id.name if record.user_id else 'el equipo'}</strong></p>
                    <p><a href="/web#id={following_op.id}&model=mrp.workorder&view_type=form">👉 Ver tu operación</a></p>
                """

                following_op.message_post(
                    body=message,
                    subject=f'⛔ Alerta en Cascada: {following_op.name}',
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                    partner_ids=[following_op.user_id.partner_id.id],
                )

                _logger.warning(
                    f"Cascade alert sent to {following_op.user_id.name}. "
                    f"Affected operation: {following_op.name}. "
                    f"Blocked by: {record.name} (delay: {delay_hours:.1f}h)"
                )

    @api.model
    def check_and_send_operation_notifications(self):
        """
        Cron job: Verifica operaciones retrasadas/urgentes en tiempo real.
        """
        _logger.info("🔍 Checking for delayed/urgent operations...")

        # 1. Buscar operaciones activas
        active_operations = self.search([
            ('state', '=', 'progress'), # Solo nos interesan las que están corriendo para la alerta en vivo
            ('production_id.is_frozen', '=', False)
        ])

        if not active_operations:
            return True

        delayed_count = 0
        urgent_count = 0
        
        # Intervalo para REPETIR la alerta (ej: cada 30 minutos)
        # Si quieres que sea cada 1 minuto, pon minutes=1
        REMINDER_INTERVAL = timedelta(minutes=1) 
        now = fields.Datetime.now()

        for operation in active_operations:
            # Forzamos el recalculo accediendo al campo computed (asegurate que usas el nombre correcto)
            # En tu código anterior le llamamos 'duration_hours', aquí usas 'operation_time'.
            # Usa el que tenga la lógica de (Now - Start).
            elapsed_time = operation.duration_hours 
            limit_time = operation.alert_time_hours

            # Variables de estado
            # Asumiendo que is_operation_delayed compara elapsed_time > limit_time
            is_delayed = elapsed_time > limit_time if limit_time > 0 else False
            
            # Asumiendo que urgencia es al 80%
            is_urgent = (limit_time > 0) and (elapsed_time >= limit_time * 0.8) and not is_delayed

            if not is_delayed and not is_urgent:
                continue

            # 2. Buscar si YA enviamos una alerta RECIENTEMENTE
            # Buscamos en los últimos mensajes para no traer todo el historial
            last_alerts = operation.message_ids.filtered(
                lambda m: ('🔴 OPERACIÓN RETRASADA' in (m.body or '') or 
                           '⚠️ OPERACIÓN URGENTE' in (m.body or ''))
            ).sorted('date', reverse=True) # El más reciente primero

            should_send = False
            
            if not last_alerts:
                # Nunca se ha enviado alerta -> ENVIAR
                should_send = True
            else:
                last_msg_date = last_alerts[0].date
                # Si el último mensaje fue hace más tiempo que el intervalo -> ENVIAR DE NUEVO
                if now - last_msg_date > REMINDER_INTERVAL:
                    should_send = True

            if not should_send:
                continue

            # ---------------------------------------------------------
            # CASO 1: RETRASO
            # ---------------------------------------------------------
            if is_delayed:
                delay_hours = elapsed_time - limit_time
                _logger.warning(f"⚠️ Operation {operation.name} DELAYED. Sending alert.")

                # Usamos HTML para que se vea bonito en Odoo
                message_body = Markup(
                    "<b>🔴 [RETRASO] OPERACIÓN RETRASADA</b><br/><br/>"
                    "<ul>"
                    "<li><b>Operación:</b> %s</li>"
                    "<li><b>Límite:</b> %.2f h</li>"
                    "<li><b>Transcurrido:</b> %.2f h</li>"
                    "<li><b>Exceso:</b> <span style='color:red; font-weight:bold;'>%.2f h</span></li>"
                    "</ul>"
                    "<i>Esta operación requiere atención inmediata.</i>"
                ) % (operation.name, limit_time, elapsed_time, delay_hours)

                operation.message_post(
                    body=message_body,
                    subject=f"🔴 ALERTA: {operation.name}",
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                delayed_count += 1

            # ---------------------------------------------------------
            # CASO 2: URGENTE
            # ---------------------------------------------------------
            elif is_urgent:
                remaining = limit_time - elapsed_time
                percent = (elapsed_time / limit_time) * 100
                _logger.warning(f"⚠️ Operation {operation.name} URGENT. Sending alert.")

                message_body = Markup(
                    "<b>⚠️ [URGENTE] CERCA DEL LÍMITE</b><br/><br/>"
                    "<ul>"
                    "<li><b>Operación:</b> %s</li>"
                    "<li><b>Consumo:</b> %.1f%%</li>"
                    "<li><b>Restante:</b> %.2f h</li>"
                    "</ul>"
                ) % (operation.name, percent, remaining)

                operation.message_post(
                    body=message_body,
                    subject=f"⚠️ URGENTE: {operation.name}",
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                urgent_count += 1

        return True

    @api.model
    def check_next_workorder_waiting(self):
        """
        Cron job: Detecta workorders que están esperando a iniciar después de que
        la operación anterior terminó, y envía una alerta cada 20 minutos.
        """
        _logger.info("🔍 Checking for workorders waiting to start after previous completed...")

        # Buscar todas las workorders en estado pending o ready (no iniciadas)
        waiting_wos = self.search([
            ('state', 'in', ['pending', 'ready']),
            ('production_id.state', 'in', ['confirmed', 'progress']),
            ('production_id.is_frozen', '=', False)
        ])

        alert_count = 0
        now = fields.Datetime.now()

        for wo in waiting_wos:
            # Obtener todas las workorders de esta producción ordenadas por sequence
            all_wos = wo.production_id.workorder_ids.sorted('sequence')

            # Verificar si esta NO es la primera workorder
            if all_wos and all_wos[0].id == wo.id:
                # Esta ES la primera workorder, no enviar esta alerta
                # (ya se maneja con la otra alerta)
                continue

            # Buscar workorders anteriores (menor sequence)
            previous_wos = all_wos.filtered(lambda w: w.sequence < wo.sequence)

            if not previous_wos:
                continue

            # Verificar si la workorder inmediatamente anterior está terminada
            previous_wo = previous_wos[-1]  # Última de la lista (la más cercana)

            if previous_wo.state == 'done':
                # La anterior está terminada y esta sigue sin iniciar!
                # Verificar si ya pasaron 20 minutos desde la última alerta
                should_alert = False

                if not wo.last_next_wo_waiting_alert:
                    # Primera vez que detectamos esta condición
                    should_alert = True
                else:
                    # Verificar si pasaron 20 minutos desde la última alerta
                    time_since_last_alert = now - wo.last_next_wo_waiting_alert
                    minutes_since_alert = time_since_last_alert.total_seconds() / 60.0

                    if minutes_since_alert >= 20.0:
                        should_alert = True

                if should_alert:
                    # Calcular tiempo desde que la anterior terminó
                    if previous_wo.date_finished:
                        time_waiting = now - previous_wo.date_finished
                        minutes_waiting = time_waiting.total_seconds() / 60.0
                    else:
                        minutes_waiting = 0.0

                    message = _(
                        "⏭️ Siguiente Operación Esperando\n\n"
                        "La operación anterior fue completada pero esta operación aún no ha comenzado.\n\n"
                        "• Orden: %s\n"
                        "• Operación Actual: %s\n"
                        "• Asignada a: %s\n"
                        "• Operación Anterior: %s (Completada)\n"
                        "• Tiempo esperando: %.1f minutos\n"
                        "• Estado: %s\n\n"
                        "Por favor, iniciar esta operación para continuar la producción."
                    ) % (
                        wo.production_id.name,
                        wo.name,
                        wo.user_id.name if wo.user_id else 'Sin asignar',
                        previous_wo.name,
                        minutes_waiting,
                        dict(wo._fields['state'].selection).get(wo.state, wo.state)
                    )

                    wo.message_post(
                        body=message,
                        subject=f'⏭️ Siguiente Operación Esperando: {wo.name}',
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )

                    # También notificar a la orden de producción
                    if wo.production_id:
                        wo.production_id.message_post(
                            body=_(
                                "⏭️ Operación Esperando: %s\n"
                                "La operación anterior (%s) fue completada hace %.1f minutos."
                            ) % (wo.name, previous_wo.name, minutes_waiting),
                            subtype_xmlid='mail.mt_note',
                        )

                    # Actualizar timestamp de última alerta
                    wo.last_next_wo_waiting_alert = now
                    alert_count += 1

                    _logger.warning(
                        f"⏭️ ALERTA: Workorder {wo.name} - Esperando después de {previous_wo.name} "
                        f"({minutes_waiting:.1f} minutos esperando)"
                    )

        _logger.info(
            f"✅ Next workorder waiting check completed. New alerts sent: {alert_count}"
        )

        return True

    # ============================================
    # MÉTODOS OVERRIDE
    # ============================================

    def write(self, vals):
        """Override write para auto-iniciar operación cuando cambia a 'progress'"""
        # Detectar cambios en asignación de usuario
        old_user_ids = {}
        for record in self:
            old_user_ids[record.id] = record.user_id.id if record.user_id else False

        result = super(MrpWorkorderCustom, self).write(vals)

        # Auto-start operation cuando cambia a progreso
        if vals.get('state') == 'progress':
            for record in self:
                if not record.operation_start_date:
                    record.operation_start_date = fields.Datetime.now()

        # Enviar notificación de asignación si cambió el usuario
        for record in self:
            old_user_id = old_user_ids.get(record.id, False)

            # Si se asignó un usuario nuevo
            if record.user_id and record.user_id.id != old_user_id:
                record.notify_operation_assigned()

        # Note: Alert notifications (delayed/urgent) are now handled by the cron job
        # since the alert fields are non-stored and calculated in real-time

        return result

    def action_reopen_workorder(self):
        """ Force-reopen a WO bypassing Odoo's planning constraints """
        if not self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager'):
            raise UserError(_("Solo un manager puede reabrir operaciones."))

        for wo in self:
            # Forzamos los valores por SQL para saltar el método write() restrictivo
            self.env.cr.execute("""
                UPDATE mrp_workorder 
                SET state = 'ready', 
                    date_finished = NULL,
                    date_start = NULL,
                    date_planned_finished = NULL
                WHERE id = %s
            """, (wo.id,))
            
            # Limpiar caché
            wo.invalidate_recordset()
            
            # Si la MO estaba bloqueada para cierre, la devolvemos a progreso
            if wo.production_id.state == 'to_close':
                wo.production_id.write({'state': 'progress'})
            
            wo.message_post(body=_("Operación reabierta por Manager. Se eliminaron restricciones de planeación."))
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
