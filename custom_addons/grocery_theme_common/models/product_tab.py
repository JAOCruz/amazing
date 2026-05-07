# -*- coding: utf-8 -*-
# Part of Odoo Module Developed by Bizople Solutions Pvt. Ltd.
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo import models, fields
from odoo.http import request

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    tab_ids = fields.Many2many('product.tab','product_tab_table','tab_ids','product_ids',string="Tab")
    product_label_id = fields.Many2one('product.label.bizople',string="Product Label")
    nutrition_id = fields.Many2one('nutritional.facts',string="Nutritional Facts")
    highlights_ids = fields.Many2many("product.highlights",string="Website Highlights")
    hover_image = fields.Image(string="Product Hover Image")
    product_tag_ids = fields.Many2many("product.tag",string="Product Tag")
    biz_total_sale_count = fields.Integer('Total Sale Count')

    biz_is_discounted_product = fields.Boolean(compute="_compute_biz_is_discounted_product", search="_search_biz_is_discounted_product")

    def write(self, vals):
        for obj in self:
            vals['biz_total_sale_count'] = int(obj.sales_count)
            res = super(ProductTemplate, self).write(vals)
        return res

    @api.model
    def _search_get_detail(self, website, order, options):
        res = super(ProductTemplate, self)._search_get_detail(website=website, order=order, options=options)
        brand = options.get('brand_id')
        tag_list = request.httprequest.args.getlist('tag_list')
        old_domain = res['base_domain']
        if brand:
            old_domain.append([('brand_id', 'in', brand)])
        
        if tag_list:
            old_domain.append([('product_tag_ids', 'in', tag_list)])
        return res

    # [T2331] Fix - Discount Filter
    def _search_biz_is_discounted_product(self, operator, value):
        website = request.env['website'].sudo().search([('id', '=', self._context.get('website_id'))])
        pricelist = website._get_current_pricelist()
        if pricelist:
            products = request.env['product.template'].sudo().search([
                ('sale_ok', '=', True),
                ('is_published', '=', True),
                '|',
                ('website_id', '=', website.id),
                ('website_id', '=', False),
                '|',
                ('company_id', '=', request.env.company.id),
                ('company_id', '=', False),
            ])
            discounted_products = []
            for product in products:
                pricelist_data = product._get_combination_info(only_template=True)
                if pricelist_data.get('has_discounted_price'):
                    discounted_products.append(product.id)
            operator = 'in' if operator == '!=' else 'not in'
            return [('id', operator, discounted_products)]
        return []

    def _compute_biz_is_discounted_product(self):
        for product in self:
            product.biz_is_discounted_product = False

class Producttag(models.Model):
    _name = "product.tag"
    _inherit = ['website.multi.mixin', 'product.tag']
    _description = "Product Tag"

    name = fields.Char("Name")
    sequence = fields.Integer("Sequence")
    tag_image = fields.Binary("Icon Image")
    
class ProductTab(models.Model):
    _name = 'product.tab'
    _description = 'Product Tab'
    _rec_name = 'name'

    name = fields.Char(string="Name")
    sequence = fields.Integer(string="Sequence", default=1)
    content = fields.Html(string="Content")
    product_ids = fields.Many2many('product.template','product_tab_table','product_ids','tab_ids', string="product")

class ProductLabelBizople (models.Model):
     _name = 'product.label.bizople'
     _description = 'Product Label'
     
     _SELECTION_STYLE = [
        ('rounded', 'Rounded'),
        ('outlinesquare', 'Outline Square'),
        ('outlineround', 'Outline Rounded'),
        ('flat', 'Flat'),
    ]
     
     name = fields.Char(string="Name", translate=True, required=True)
     label_bg_color = fields.Char(string="Label Background Color", required=True,default="#f6513b")
     label_font_color = fields.Char(string="Label Font Color", required=True, default="#ffffff")
     label_style = fields.Selection(
        string='Label Style', selection=_SELECTION_STYLE, default='rounded')