# -*- coding: utf-8 -*-
# Part of Odoo Module Developed by Bizople Solutions Pvt. Ltd.
# See LICENSE file for full copyright and licensing details.

import odoo
from odoo import http , _
from odoo.http import request
from odoo.osv import expression
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)

class DynamicCongifTool(http.Controller):

    @http.route('/config/product/data', type='json', auth='public', website=True)
    def config_product_data(self, **post):
        company = request.env.company
        products = request.env['product.template'].sudo().search([
            ('sale_ok', '=', True),
            ('is_published', '=', True),
            ('name', 'ilike', post.get('search')),
            ('id', 'not in', post.get('selectedlist')),
            '|',
            ('website_id', '=', request.website.id),
            ('website_id', '=', False),
            '|',
            ('company_id', '=', company.id),
            ('company_id', '=', False),
        ])
        now = datetime.timestamp(datetime.now())
        website = request.env['website'].get_current_website()
        pricelist = website.pricelist_id       
        if request.session.get('website_sale_pricelist_time', 0) < now - 60*60: # test: 1 hour in session        
            pricelist = website.pricelist_id
        searched_products_line_template = request.env['ir.ui.view']._render_template(
            "theme_grocery_bizople.searched_products_line", {
                'products': products,
                'pricelist': pricelist,
            }
        )
        values= {
            'searched_products_line_template': searched_products_line_template,
        }
        return values
    
    @http.route('/config/category/data', type='json', auth='public', website=True)
    def config_category_data(self, **post):
        company = request.env.company
        categories = request.env['product.public.category'].sudo().search([
            ('name', 'ilike', post.get('search')),
            ('product_tmpl_ids', '!=', False),
            ('id', 'not in', post.get('selectedlist')),
            '|',
            ('website_id', '=', request.website.id),
            ('website_id', '=', False),
        ])
        searched_category_line_template = request.env['ir.ui.view']._render_template(
            "theme_grocery_bizople.searched_category_line", {
                'categories': categories,
            }
        )
        values= {
            'searched_category_line_template': searched_category_line_template,
        }
        return values
    
    @http.route('/config/brand/data', type='json', auth='public', website=True)
    def config_brand_data(self, **post):
        company = request.env.company
        brands = request.env['product.brand'].sudo().search([
            ('name', 'ilike', post.get('search')),
            ('product_ids', '!=', False),
            ('id', 'not in', post.get('selectedlist')),
        ])
        searched_brand_line_template = request.env['ir.ui.view']._render_template(
            "theme_grocery_bizople.searched_brand_line", {
                'brands': brands,
            }
        )
        values= {
            'searched_brand_line_template': searched_brand_line_template,
        }
        return values
    
    @http.route('/config/blog/data', type='json', auth='public', website=True)
    def config_blog_data(self, **post):
        company = request.env.company
        blogs = request.env['blog.post'].sudo().search([
            ('name', 'ilike', post.get('search')),
            ('id', 'not in', post.get('selectedlist')),
        ])
        searched_blog_line_template = request.env['ir.ui.view']._render_template(
            "theme_grocery_bizople.searched_blog_line", {
                'blogs': blogs,
            }
        )
        values= {
            'searched_blog_line_template': searched_blog_line_template,
        }
        return values
    
    @http.route('/get/dynamic/config/selected/line', type='json', auth='public', website=True)
    def dynamic_config_selected_line(self, **post):
        company = request.env.company
        model = post.get('model')
        idlist = post.get('idlist')
        records = request.env[model].sudo().browse(idlist)
        if model == 'product.template':
            selected_line_template = request.env['ir.ui.view']._render_template(
                "theme_grocery_bizople.selected_products_line", {
                    'products': records,
                    'model': model,
                }
            )
        if model == 'product.public.category':
            selected_line_template = request.env['ir.ui.view']._render_template(
                "theme_grocery_bizople.selected_category_line", {
                    'categories': records,
                    'model': model,
                }
            )
        if model == 'product.brand':
            selected_line_template = request.env['ir.ui.view']._render_template(
                "theme_grocery_bizople.selected_brand_line", {
                    'brands': records,
                    'model': model,
                }
            )
        if model == 'blog.post':
            selected_line_template = request.env['ir.ui.view']._render_template(
                "theme_grocery_bizople.selected_blog_line", {
                    'blogs': records,
                    'model': model,
                }
            )
        values = {
            'selected_line_template': selected_line_template,
        }
        return values
    
    @http.route('/get/selected/record/data', type='json', auth='public', website=True)
    def get_selected_record_data(self, **post):
        model = post.get('model')
        record_ids = post.get('record_ids')
        records = request.env[model].sudo().search([
            ('id', 'in', record_ids),
        ])
        domain_value = []
        for record in records:
            record_data = {
                'id': record.id,
                'name': record.name,
            }
            domain_value.append(record_data)
        return domain_value

    @http.route('/get/domain/record', type='json', auth='public', website=True)
    def get_domain_record(self, **post):
        model = post.get('model')
        if not model:
            return {"error": "Model name is missing or invalid."}
        search = post.get('value')
        selected_records = post.get('selected_records')
        records = request.env[model].sudo().search([
            ('name', 'ilike', search),
            ('id', 'not in', selected_records)
        ])
        domain_record_list = request.env['ir.ui.view']._render_template(
            "theme_grocery_bizople.domain_record_list", {
                'records': records,
            }
        )
        values ={
            'domain_record_list': domain_record_list
        }
        return values

    @http.route('/get/dynamic/config', type='json', auth='public', website=True)
    def get_dynamic_config(self, **post):
        idlist = post.get('idlist')
        model = post.get('model')
        style = post.get('style')
        mode = post.get('mode')
        design_params = post.get('design_params')
        item_per_row = post.get('item_per_row')
        domain_list = post.get('domain_list')
        record_match = post.get('record_match')
        record_limit = post.get('record_limit')
        sortby = post.get('sortby') if post.get('sortby') != 'default' else 'default'
        orderby = post.get('orderby') if post.get('orderby') != 'default' else 'default'
        if sortby == 'default' and orderby == 'default':
            record_orderby = False
        if sortby == 'default' and orderby != 'default':
            record_orderby = orderby
        if orderby == 'default' and sortby != 'default':
            record_orderby = sortby
        if orderby != 'default' and sortby != 'default':
            sortby = str(sortby) if sortby is not None else ""
            orderby = str(orderby) if orderby is not None else ""
            record_orderby = sortby + ',' + orderby
        base_config_domain = []
        subdomains_list = []
        if domain_list:
            for domain in domain_list:
                subdomain = [tuple(domain)]
                subdomains_list.append(subdomain)
            if record_match == 'or':
                base_config_domain.append(expression.OR(subdomains_list))
            else:
                base_config_domain.append(expression.AND(subdomains_list))
        if idlist:
            base_config_domain = [[('id', 'in', idlist)]]
        if style is not None and mode is not None:
            template_name = "dynamic_config_" + model.replace('.', '_') + "_" + style + "_" + mode
        else:
            template_name = "dynamic_config_default_"
        templatecheck = request.env['ir.ui.view'].sudo().search([('key','=','theme_grocery_bizople.'+template_name)])
        if templatecheck:
            records = request.env[model].sudo().search(base_config_domain[0], limit=record_limit, order=record_orderby)
            dynamic_config_template = request.env['ir.ui.view']._render_template(
                "theme_grocery_bizople."+template_name, {
                    'records': records,
                    'design_params': design_params,
                    'item_per_row': item_per_row,
                }
            )
            values = {
                'dynamic_config_template': dynamic_config_template
            }
            return values
        else:
            values = {
                'dynamic_config_template': ''
            }
            return values