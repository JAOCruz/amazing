# -- coding: utf-8 --
# See LICENSE file for full copyright and licensing details.
# Developed by Bizople Solutions Pvt. Ltd.

from odoo import api, fields, models
from odoo import http,_
from odoo.http import request
from odoo.tools import lazy, str2bool
from odoo.exceptions import ValidationError
from odoo.addons.website_sale.controllers.main import WebsiteSale

class WebsiteSale(WebsiteSale):
    @http.route(['/shop/checkout'], type='http', auth="public", website=True, sitemap=False)
    def shop_checkout(self, try_skip_step=None, **query_params):
        try_skip_step = str2bool(try_skip_step or 'false')
        order_sudo = request.website.sale_get_order()
        request.session['sale_last_order_id'] = order_sudo.id

        if redirection := self._check_cart_and_addresses(order_sudo):
            return redirection

        checkout_page_values = self._prepare_checkout_page_values(order_sudo, **query_params)

        can_skip_delivery = True  # Delivery is only needed for deliverable products.
        if order_sudo._has_deliverable_products():
            can_skip_delivery = False
            available_dms = order_sudo._get_delivery_methods()
            checkout_page_values['delivery_methods'] = available_dms
            if delivery_method := order_sudo._get_preferred_delivery_method(available_dms):
                rate = delivery_method.rate_shipment(order_sudo)
                if (
                    not order_sudo.carrier_id
                    or not rate.get('success')
                    or order_sudo.amount_delivery != rate['price']
                ):
                    order_sudo._set_delivery_method(delivery_method, rate=rate)

        if try_skip_step and can_skip_delivery:
            return request.redirect('/shop/confirm_order')
        
        store_data = request.env['store.location'].sudo().search([('is_published','=','true')])
        checkout_page_values.update({'store_data':store_data})

        return request.render('website_sale.checkout', checkout_page_values)

    @http.route(['/add_store_data'], type='json', auth='public', website="True")
    def addstoredata(self, **kw):
        pickup_id = int(kw.get('store_id'))
        if pickup_id:
            pickup_ids = request.env['store.location'].sudo().browse(pickup_id)
            if pickup_ids:
                order = request.website.sale_get_order()
                if order:
                    order.store_location_id = pickup_ids
        else:
            order = request.website.sale_get_order()
            order.store_location_id = False