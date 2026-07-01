# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ResUsersCustom(models.Model):
    _inherit = 'res.users'

    # ============================================
    # CAMPOS DE EMPLEADO - DEPARTAMENTO
    # ============================================

    department = fields.Selection(
        selection=[
            ('diseno', 'Diseño'),
            ('fresado', 'Fresado'),
            ('ceramica', 'Cerámica'),
            ('prensado', 'Prensado'),
            ('produccion', 'Producción'),
            ('maquillaje', 'Maquillaje'),
            ('sistema', 'Sistema'),
            ('printer', 'Printer'),
            ('mensajeria', 'Mensajería'),
            ('facturacion', 'Facturación'),
            ('seguimiento', 'Seguimiento'),
        ],
        string='Departamento',
        help='Departamento al que pertenece el empleado en el laboratorio dental',
        index=True
    )

    # ============================================
    # WORKLOAD STATUS (COMPUTED)
    # ============================================

    workload_status = fields.Selection(
        selection=[
            ('available', 'Disponible'),
            ('busy', 'Ocupado'),
            ('overloaded', 'Sobrecargado'),
        ],
        string='Estado de Carga',
        compute='_compute_workload_status',
        store=False,  # No almacenar, siempre calcular en tiempo real
        help='Estado actual de carga de trabajo del empleado basado en sus operaciones asignadas'
    )

    # Campos auxiliares para estadísticas
    active_operations_count = fields.Integer(
        string='Operaciones Activas',
        compute='_compute_workload_stats',
        help='Cantidad de operaciones activas asignadas al empleado'
    )

    delayed_operations_count = fields.Integer(
        string='Operaciones Retrasadas',
        compute='_compute_workload_stats',
        help='Cantidad de operaciones retrasadas del empleado'
    )

    urgent_operations_count = fields.Integer(
        string='Operaciones Urgentes',
        compute='_compute_workload_stats',
        help='Cantidad de operaciones urgentes del empleado'
    )

    # ============================================
    # COMPUTED FIELDS
    # ============================================

    def _compute_workload_stats(self):
        """Calcula estadísticas de carga de trabajo del empleado"""
        for user in self:
            # Buscar operaciones activas del usuario
            workorders = self.env['mrp.workorder'].search([
                ('user_id', '=', user.id),
                ('state', 'in', ['pending', 'ready', 'progress'])
            ])

            user.active_operations_count = len(workorders)
            user.delayed_operations_count = len(workorders.filtered(lambda w: w.is_operation_delayed))
            user.urgent_operations_count = len(workorders.filtered(lambda w: w.is_operation_urgent))

    @api.depends('active_operations_count', 'delayed_operations_count')
    def _compute_workload_status(self):
        """
        Calcula el estado de carga de trabajo basado en:
        - Cantidad de operaciones activas
        - Operaciones retrasadas
        - Operaciones urgentes

        Lógica:
        - Overloaded: >5 operaciones activas O >2 operaciones retrasadas
        - Busy: 2-5 operaciones activas O 1 OPERACIÓN RETRASADA
        - Available: 0-1 operaciones activas y sin retrasos
        """
        for user in self:
            # Recalcular workload stats primero
            user._compute_workload_stats()

            active_count = user.active_operations_count
            delayed_count = user.delayed_operations_count

            # Sobrecargado: demasiadas operaciones o muchas retrasadas
            if active_count > 5 or delayed_count > 2:
                user.workload_status = 'overloaded'

            # Ocupado: cantidad moderada de operaciones
            elif active_count >= 2 or delayed_count >= 1:
                user.workload_status = 'busy'

            # Disponible: pocas o ninguna operación
            else:
                user.workload_status = 'available'

    # ============================================
    # MÉTODOS DE UTILIDAD
    # ============================================

    def get_employee_summary(self):
        """
        Obtiene un resumen del estado del empleado

        Returns:
            dict: Resumen con información del empleado y sus operaciones
        """
        self.ensure_one()

        return {
            'id': self.id,
            'name': self.name,
            'department': self.department,
            'workload_status': self.workload_status,
            'stats': {
                'active_operations': self.active_operations_count,
                'delayed_operations': self.delayed_operations_count,
                'urgent_operations': self.urgent_operations_count,
            }
        }

    @api.model
    def get_department_overview(self, department=None):
        """
        Obtiene una vista general de empleados por departamento

        Args:
            department (str, optional): Filtrar por departamento específico

        Returns:
            list: Lista de empleados con sus estadísticas
        """
        domain = [('department', '!=', False)]
        if department:
            domain.append(('department', '=', department))

        employees = self.search(domain)

        overview = []
        for employee in employees:
            overview.append({
                'id': employee.id,
                'name': employee.name,
                'department': employee.department,
                'workload_status': employee.workload_status,
                'active_operations': employee.active_operations_count,
                'delayed_operations': employee.delayed_operations_count,
                'urgent_operations': employee.urgent_operations_count,
            })

        # Ordenar por carga de trabajo (sobrecargados primero)
        workload_order = {'overloaded': 0, 'busy': 1, 'available': 2}
        overview.sort(key=lambda x: (
            workload_order.get(x['workload_status'], 3),
            -x['delayed_operations'],
            -x['active_operations']
        ))

        return overview

    def action_view_my_workorders(self):
        """
        Acción para ver las operaciones asignadas a este usuario

        Returns:
            dict: Acción de ventana para abrir las operaciones del usuario
        """
        self.ensure_one()

        return {
            'name': f'Operaciones de {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workorder',
            'view_mode': 'kanban,tree,form',
            'domain': [
                ('user_id', '=', self.id),
                ('state', 'in', ['pending', 'ready', 'progress'])
            ],
            'context': {
                'default_user_id': self.id,
            },
        }

    @api.model
    def get_available_employees(self, department=None, max_workload='busy'):
        """
        Obtiene empleados disponibles para asignar nuevas operaciones

        Args:
            department (str, optional): Filtrar por departamento
            max_workload (str, optional): Máximo nivel de carga aceptable
                ('available', 'busy', 'overloaded')

        Returns:
            recordset: Empleados que cumplen los criterios
        """
        domain = [('department', '!=', False)]
        if department:
            domain.append(('department', '=', department))

        employees = self.search(domain)

        # Filtrar por workload
        workload_levels = {
            'available': ['available'],
            'busy': ['available', 'busy'],
            'overloaded': ['available', 'busy', 'overloaded'],
        }

        acceptable_levels = workload_levels.get(max_workload, ['available'])

        return employees.filtered(lambda e: e.workload_status in acceptable_levels)
