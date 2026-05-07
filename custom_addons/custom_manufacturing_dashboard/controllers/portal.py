from odoo import http, _
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class DentalPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        """ Calcula los datos para las Tarjetas del Home """
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        Production = request.env['mrp.production']
        
        # 1. CORRECCIÓN DE SINTAXIS AQUÍ (Ya borré el texto del CSV que se coló)
        domain = [('doctor_id', '=', partner.id), ('state', 'not in', ['cancel'])]
        values['dental_count'] = Production.search_count(domain)

        # AppBot appointment count for home portal card
        Appointment = request.env['appbot.appointment']
        values['appointment_count'] = Appointment.search_count([
            ('doctor_id', '=', partner.id), ('active', '=', True)
        ])
        
        # Disable default sidebar for doctors
        if request.env.user.has_group('custom_manufacturing_dashboard.group_dental_doctor'):
            values['my_details'] = False

        # 2. Datos para el Dashboard (summary_data)
        summary_data = {
            'laboratory': Production.search_count([('doctor_id', '=', partner.id), ('stage_custom', '=', 'laboratory'), ('state', 'not in', ['done', 'cancel'])]),
            'production': Production.search_count([('doctor_id', '=', partner.id), ('stage_custom', '=', 'production'), ('state', 'not in', ['done', 'cancel'])]),
            'test': Production.search_count([('doctor_id', '=', partner.id), ('stage_custom', '=', 'testing'), ('state', 'not in', ['done', 'cancel'])]),
            'stopped': Production.search_count([('doctor_id', '=', partner.id), ('stage_custom', '=', 'stopped'), ('state', 'not in', ['done', 'cancel'])]),
            'done': Production.search_count([('doctor_id', '=', partner.id), ('state', '=', 'done')]),
        }
        
        values['summary_data'] = summary_data
        return values

    @http.route(['/my/dental_cases', '/my/dental_cases/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_dental_cases(self, page=1, date_begin=None, date_end=None, sortby=None, filter_stage=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Production = request.env['mrp.production']

        # 1. Dominio Base
        domain = [
            ('doctor_id', '=', partner.id),
            ('state', 'not in', ['cancel'])
        ]

        # 2. Lógica del Filtro
        if filter_stage:
            if filter_stage == 'done':
                domain.append(('state', '=', 'done'))
            elif filter_stage == 'vip':
                domain.append(('is_vip', '=', True))
            else:
                domain.append(('stage_custom', '=', filter_stage))
                domain.append(('state', '!=', 'done'))

        # 3. Paginación
        cases_count = Production.search_count(domain)
        
        # --- DEBUG START ---
        _logger.info("=== DENTAL PORTAL DEBUG ===")
        _logger.info(f"Domain used: {domain}")
        _logger.info(f"Count (search_count): {cases_count}")
        
        # Check actual IDs without limit
        all_ids = Production.search(domain).ids
        _logger.info(f"All IDs matching domain ({len(all_ids)}): {all_ids}")
        # --- DEBUG END ---

        pager = portal_pager(
            url="/my/dental_cases",
            url_args={'filter_stage': filter_stage},
            total=cases_count,
            page=page,
            step=10
        )
        
        orders = Production.search(domain, limit=10, offset=pager['offset'], order='date_deadline asc')
        _logger.info(f"Orders found in current page (limit=10): {len(orders)}")
        _logger.info(f"Page orders IDs: {orders.ids}")

        # 4. CALCULAR DATOS DEL DASHBOARD
        # CORRECCIÓN: Agregué 'stopped' aquí también para evitar Error 500
        dashboard_data = {
            'lab': Production.search_count([('doctor_id', '=', partner.id), ('stage_custom', '=', 'laboratory'), ('state', 'not in', ['done', 'cancel'])]),
            'prod': Production.search_count([('doctor_id', '=', partner.id), ('stage_custom', '=', 'production'), ('state', 'not in', ['done', 'cancel'])]),
            'test': Production.search_count([('doctor_id', '=', partner.id), ('stage_custom', '=', 'testing'), ('state', 'not in', ['done', 'cancel'])]),
            'stopped': Production.search_count([('doctor_id', '=', partner.id), ('stage_custom', '=', 'stopped'), ('state', 'not in', ['done', 'cancel'])]),
            'done': Production.search_count([('doctor_id', '=', partner.id), ('state', '=', 'done')]),
        }

        values.update({
            'orders': orders,
            'page_name': 'dental_cases',
            'pager': pager,
            'default_url': '/my/dental_cases',
            'searchbar_filters': {},
            'filter_stage': filter_stage,
            'dashboard_data': dashboard_data,
        })
        
        return request.render("custom_manufacturing_dashboard.portal_my_dental_cases", values)

    @http.route(['/my/dental_cases/<model("mrp.production"):order>'], type='http', auth="user", website=True)
    def portal_dental_case_detail(self, order, **kw):
        # Seguridad extra
        if order.doctor_id.id != request.env.user.partner_id.id:
            return request.redirect('/my')
            
        return request.render("custom_manufacturing_dashboard.portal_my_dental_case_page", {
            'order': order.sudo(),
            'page_name': 'dental_cases',
        })
    @http.route(['/my/appointments', '/my/appointments/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_appointments(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Appointment = request.env['appbot.appointment']

        domain = [('doctor_id', '=', partner.id), ('active', '=', True)]
        total = Appointment.search_count(domain)

        pager = portal_pager(
            url="/my/appointments",
            total=total,
            page=page,
            step=15
        )

        appointments = Appointment.search(domain, limit=15, offset=pager['offset'], order='date desc')

        values.update({
            'appointments': appointments,
            'page_name': 'appointments',
            'pager': pager,
        })
        return request.render("custom_manufacturing_dashboard.portal_my_appointments", values)
