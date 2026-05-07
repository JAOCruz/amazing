# -*- coding: utf-8 -*-
# Part of Odoo Module Developed by Bizople Solutions Pvt. Ltd.
# See LICENSE file for full copyright and licensing details.

import odoo
from odoo import http, _
from odoo.osv import expression
from odoo.exceptions import UserError
import re
import math
import json
import os
import logging
import werkzeug
from datetime import datetime
from werkzeug.exceptions import NotFound
from odoo.addons.payment import utils as payment_utils
from odoo.addons.website.controllers.main import QueryURL
from odoo import http, SUPERUSER_ID, fields, tools
from odoo.http import request
from odoo.addons.website_sale.controllers import main
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website.controllers.main import Website
from odoo.addons.website_sale.controllers.main import TableCompute
from odoo.addons.website_sale.controllers.variant import WebsiteSaleVariantController
from odoo.addons.auth_oauth.controllers.main import OAuthLogin
from odoo.addons.web.controllers.home import Home
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.tools.json import scriptsafe as json_scriptsafe
from odoo.tools import lazy, SQL, float_round, groupby
from odoo.addons.web.controllers.utils import ensure_db
CREDENTIAL_PARAMS = ['login', 'password', 'type']
_logger = logging.getLogger(__name__)

class PortalUser(http.Controller):
    @http.route(['/update-image'], type='json', auth="user")
    def action_update_image(self,**post):
        datas_file = str(post['img_attachment']).split(',')
        datas_file = datas_file[1]
        user_id = request.env.user
        datas_file = ''
        if 'img_attachment' in post and post['img_attachment']:
            datas_file = str(post['img_attachment']).split(',')
            datas_file = datas_file[1]
            user_id.write({'image_1920':datas_file})
        values = {'user_id':user_id}
        return request.env['ir.ui.view']._render_template("theme_grocery_bizople.update_user_image",values)

    @http.route(['/update/mobilecart'], type='json', auth="public", website=True)
    def updateMobilecart(self):
        order = request.website.sale_get_order()
        value = request.env['ir.ui.view']._render_template("theme_grocery_bizople.mobile_bottom_cart", {
            'website_sale_order': order,
        })
        return value
        
    @http.route(['/update/menucart'], type='json', auth="public", website=True)
    def updatemenucart(self):
        order = request.website.sale_get_order()
        suggested_products = order._cart_accessories()
        value = request.env['ir.ui.view']._render_template("theme_grocery_bizople.cart_right", {
            'website_sale_order': order,
            'suggested_products': order._cart_accessories()
        })
        return value

class WebsiteSaleVariantController(WebsiteSaleVariantController):

    @http.route(['/product_code/get_combination_info'], type='json', auth="public", methods=['POST'], website=True)
    def get_combination_info_sku_website(self, product_template_id, product_id, combination, add_qty,parent_combination=None, **kw):
        product_template = request.env['product.template'].browse(
            product_template_id and int(product_template_id))

        combination_info = product_template._get_combination_info(
            combination=request.env['product.template.attribute.value'].browse(combination),
            product_id=product_id and int(product_id),
            add_qty=add_qty and float(add_qty) or 1.0,
            parent_combination=request.env['product.template.attribute.value'].browse(parent_combination),
        )
        return request.env['ir.ui.view']._render_template('theme_grocery_bizople.product_default_code', values={'default_code': combination_info['default_code']})

class Websitegoogle(http.Controller):

    @http.route('/theme_grocery_bizople/google_maps_api_key', type='json', auth='public', website=True)
    def google_maps_api_key(self):
        return json.dumps({
            'google_maps_api_key': request.website.google_maps_api_key or ''
        })
        
class WebsiteCategoyBizople(http.Controller):
    _per_page_category = 20
    _per_page_brand = 20
   
    @http.route([
        '/category',
        '/category/page/<int:page>',
        '/category/<model("product.public.category"):category_id>',
        '/category/<model("product.public.category"):category_id>/page/<int:page>'
    ], type='http', auth="public", website=True, sitemap=True)
    def product_category_data(self, page=1, category_id=None, search='', **post):
        if search:
            categories = [categ for categ in request.env['product.public.category'].search([
                ('name', 'ilike', search)]
            )]
        else:
            if category_id:
                categories = [categ for categ in request.env['product.public.category'].search([
                    ('parent_id', '=', category_id.id)]
                )]
            else:
                categories = [categ for categ in request.env['product.public.category'].search([
                    ('parent_id', '=', False)]
                )]
        if not categories and category_id:
            url = "/shop/category/%s" % request.env['ir.http']._slug(category_id)
            return request.redirect(url)
        else:
            pager = request.website.pager(
                url=request.httprequest.path.partition('/page/')[0],
                total=len(categories),
                page=page,
                step=self._per_page_category,
                url_args=post,
            )
            pager_begin = (page - 1) * self._per_page_category
            pager_end = page * self._per_page_category
            categories = categories[pager_begin:pager_end]
            return request.render('grocery_theme_common.website_sale_categoy_list_bizople', {
                'categories': categories,
                'pager': pager,
                'search': search
            })

    @http.route([
        '/category-search',
    ], type='http', auth="public", website=True, sitemap=False)
    def product_category_search_data(self, **post):
        return request.redirect('/category?&search=%s' % post['search'])

    @http.route([
        '/brand',
        '/brand/page/<int:page>',
        '/brand/<model("product.brand"):brand_id>',
        '/brand/<model("product.brand"):brand_id>/page/<int:page>'
    ], type='http', auth="public", website=True, sitemap=True)
    def product_brand_data(self, page=1, brand_id=None, search='', **post):
        if search:
            brands = [brand for brand in request.env['product.brand'].search([
                ('name', 'ilike', search)]
            )]
        else:
            if brand_id:
                brands = [brand for brand in request.env['product.brand'].search([
                    ('parent_id', '=', brand_id.id)]
                )]
            else:
                brands = [brand for brand in request.env['product.brand'].search([
                    ('parent_id', '=', False)]
                )]
        if not brands and brand_id:
            url = "/shop?brand=%s" % request.env['ir.http']._slug(brand_id)
            return request.redirect(url)
        else:
            pager = request.website.pager(
                url=request.httprequest.path.partition('/page/')[0],
                total=len(brands),
                page=page,
                step=self._per_page_brand,
                url_args=post,
            )
            pager_begin = (page - 1) * self._per_page_brand
            pager_end = page * self._per_page_brand
            brands = brands[pager_begin:pager_end]
            return request.render('grocery_theme_common.website_sale_brand_list_bizople', {
                'brands': brands,
                'pager': pager,
                'search': search
            })

    @http.route([
        '/brand-search',
    ], type='http', auth="public", website=True, sitemap=False)
    def brand_search_data(self, **post):
        return request.redirect('/brand?&search=%s' % post['search'])

class BizopleWebsiteSale(WebsiteSale):

    @http.route('/get_prod_quick_view_details', type='json', auth='public', website=True)
    def get_product_qv_details(self, **kw):
        product_id = int(kw.get('prod_id', 0))
        if product_id > 0:
            product = http.request.env['product.template'].search([('id', '=', product_id)])
            pricelist = request.env['website'].get_current_website().pricelist_id
            from_currency = request.env.user.company_id.currency_id
            to_currency = pricelist.currency_id
            compute_currency = lambda price: from_currency.compute(price, to_currency)
            
            return request.env['ir.ui.view']._render_template("theme_grocery_bizople.get_product_qv_details_template", 
                   {'product': product, 'compute_currency': compute_currency or None,})
            
        else:
            
            return request.env['ir.ui.view']._render_template("theme_grocery_bizople.get_product_qv_details_template", 
                   {'error': _('some problem occurred product no loaded properly')})

    # select variant popup start
    @http.route('/get_prod_select_option_details', type='json', auth='public', website=True)
    def get_product_so_details(self, **kw):
        product_id = int(kw.get('prod_id', 0))
        if product_id > 0:
            product = http.request.env['product.template'].search([('id', '=', product_id)])
            pricelist = request.env['website'].get_current_website().pricelist_id
            from_currency = request.env.user.company_id.currency_id
            to_currency = pricelist.currency_id
            compute_currency = lambda price: from_currency.compute(price, to_currency)
            
            return request.env['ir.ui.view']._render_template("theme_grocery_bizople.get_product_so_details_template", 
                   {'product': product, 'compute_currency': compute_currency or None,})
            
        else:
            
            return request.env['ir.ui.view']._render_template("theme_grocery_bizople.get_product_so_details_template", 
                   {'error': _('some problem occurred product no loaded properly')})
    # select variant popup end

    @http.route(['/shop/pager_selection/<model("product.per.page.count.bizople"):pl_id>'], type='http', auth="public", website=True, sitemap=False)
    def product_page_change(self, pl_id, **post):
        request.session['default_paging_no'] = pl_id.name
        pl_id.sudo().update({
            'default_active_count' : True,
        })
        main.PPG = pl_id.name
        request.env['website'].get_current_website().sudo().shop_ppg = pl_id.name
        return request.redirect(request.httprequest.referrer or '/shop')

    @http.route([
        '/shop',
        '/shop/page/<int:page>',
        '/shop/category/<model("product.public.category"):category>',
        '/shop/category/<model("product.public.category"):category>/page/<int:page>',
        '/shop/brands',
    ], type='http', auth="public", website=True, sitemap=WebsiteSale.sitemap_shop)
    def shop(self, page=0, category=None, search='', min_price=0.0, max_price=0.0, ppg=False, **post):
        add_qty = int(post.get('add_qty', 1))
        Category = request.env['product.public.category']
        try:
            min_price = float(min_price)
        except ValueError:
            min_price = 0
        try:
            max_price = float(max_price)
        except ValueError:
            max_price = 0

        if category:
            category = Category.search([('id', '=', int(category))], limit=1)
            if not category or not category.can_access_from_current_website():
                raise NotFound()
        else:
            category = Category

        website = request.env['website'].get_current_website()
        if ppg:
            try:
                ppg = int(ppg)
                post['ppg'] = ppg
            except ValueError:
                ppg = False
        if not ppg:
            ppg = website.shop_ppg or 20

        ppr = website.shop_ppr or 4

        gap = website.shop_gap or "16px"

        attrib_list = request.httprequest.args.getlist('attribute_value')
        attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
        attributes_ids = {v[0] for v in attrib_values}
        attrib_set = {v[1] for v in attrib_values}
        domain = self._get_shop_domain(search, category, attrib_values)
        user_id = request.env.user
        current_user_id = user_id.id

        query_url_kwargs = self._shop_get_query_url_kwargs(category and int(category), search, min_price, max_price, **post)

        now = datetime.timestamp(datetime.now())
        pricelist = request.env['product.pricelist'].browse(request.session.get('website_sale_current_pl'))
        if not pricelist or request.session.get('website_sale_pricelist_time', 0) < now - 60*60: # test: 1 hour in session
            pricelist = website._get_current_pricelist()
            request.session['website_sale_pricelist_time'] = now
            request.session['website_sale_current_pl'] = pricelist.id

        request.update_context(pricelist=pricelist.id, partner=request.env.user.partner_id)

        filter_by_price_enabled = website.is_view_active('website_sale.filter_products_price')
        if filter_by_price_enabled:
            company_currency = website.company_id.sudo().currency_id
            conversion_rate = request.env['res.currency']._get_conversion_rate(
                company_currency, website.currency_id, request.website.company_id, fields.Date.today())
        else:
            conversion_rate = 1

        url = "/shop"
        if search:
            post["search"] = search
        if attrib_list:
            post['attribute_value'] = attrib_list

        options = self._get_search_options(
            category=category,
            attrib_values=attrib_values,
            pricelist=pricelist,
            min_price=min_price,
            max_price=max_price,
            conversion_rate=conversion_rate,
            **post
        )
        # GROCERY BRAND OPTIONS CODE START
        brand_list = request.httprequest.args.getlist('brand')
        brand_list = [int(request.env['ir.http']._unslug(x)[1]) for x in brand_list]
        brand_set = set([int(v) for v in brand_list])
        if brand_list:
            brandlistdomain = list(map(int, brand_list))
            options['brand_id'] = brandlistdomain
            bran = []
            brand_obj = request.env['product.brand'].sudo().search(
                [('id', 'in', brandlistdomain)])
            if brand_obj:
                for vals in brand_obj:
                    if vals.name not in bran:
                        bran.append((vals.name, vals.id))
                if bran:
                    request.session["brand_name"] = bran
        if not brand_list:
            request.session["brand_name"] = ''
        active_brand_list = list(set(brand_set))
        product_brands = request.env['product.brand'].search([('id', '=', active_brand_list)])
        # GROCERY BRAND OPTIONS CODE END
        
        fuzzy_search_term, product_count, search_product = self._shop_lookup_products(attrib_set, options, post, search, website)
        
        filter_by_price_enabled = website.is_view_active('website_sale.filter_products_price')
        if filter_by_price_enabled:
            # TODO Find an alternative way to obtain the domain through the search metadata.
            Product = request.env['product.template'].with_context(bin_size=True)
            domain = self._get_shop_domain(search, category, attrib_values)

            # This is ~4 times more efficient than a search for the cheapest and most expensive products
            query = Product._where_calc(domain)
            Product._apply_ir_rules(query, 'read')
            sql = query.select(
                SQL(
                    "COALESCE(MIN(list_price), 0) * %(conversion_rate)s, COALESCE(MAX(list_price), 0) * %(conversion_rate)s",
                    conversion_rate=conversion_rate,
                )
            )
            available_min_price, available_max_price = request.env.execute_query(sql)[0]

            if min_price or max_price:
                if min_price:
                    min_price = min_price if min_price <= available_max_price else available_min_price
                    post['min_price'] = min_price
                if max_price:
                    max_price = max_price if max_price >= available_min_price else available_max_price
                    post['max_price'] = max_price

        # tag search in shop page start
        active_tag = False
        tag_list = []

        if 'tag_list' in post and post['tag_list']:
            domain += [('product_tag_ids', 'in', tag_list)]
        tag_values = request.httprequest.args.getlist('tag_list')
        if tag_values:
            for t in tag_values:
                tag_list.append(int(t))
        product_tag_ids = request.env['product.tag'].search([])
        
        # tag search in shop page end
        
        website_domain = website.website_domain()
        categs_domain = [('parent_id', '=', False)] + website_domain
        if search:
            search_categories = Category.search(
                [('product_tmpl_ids', 'in', search_product.ids)] + website_domain
            ).parents_and_self
            categs_domain.append(('id', 'in', search_categories.ids))
        else:
            search_categories = Category
        categs = lazy(lambda: Category.search(categs_domain))

        if category:
            url = "/shop/category/%s" % request.env['ir.http']._slug(category)
    
        pager = website.pager(url=url, total=product_count, page=page, step=ppg, scope=7, url_args=post)
        offset = pager['offset']
        products = search_product[offset:offset + ppg]

        ProductAttribute = request.env['product.attribute']
        if products:
            # get all products without limit
            attributes = lazy(lambda: ProductAttribute.search([
                ('product_tmpl_ids', 'in', search_product.ids),
                ('visibility', '=', 'visible'),
            ]))
        else:
            attributes = lazy(lambda: ProductAttribute.browse(attributes_ids))

        layout_mode = request.session.get('website_sale_shop_layout_mode')
        if not layout_mode:
            if website.viewref('website_sale.products_list_view').active:
                layout_mode = 'list'
            else:
                layout_mode = 'grid'
            request.session['website_sale_shop_layout_mode'] = layout_mode

        if search:
            domain.append(("name", 'ilike', search.strip()))
        if not request.env.user.has_group('base.group_system'):
                domain.append(("website_published", '=', True))
        product_tmpl_ids = request.env['product.template'].sudo().search(domain).ids

        prod_dict_list = []
        for product in products:
            price_item_list = []
            min_qty = 0
            prod_price = 0
            pricelist_id = pricelist.id if pricelist else 0
            pricelist_items_obj = request.env['product.pricelist.item'].search([
            '|', ('product_tmpl_id', '=', product.id), ('product_id', 'in', product.product_variant_ids.ids),('pricelist_id','=',pricelist_id)],order="min_quantity asc")
            
            min_value_list =  []

            for price_items in pricelist_items_obj:

                min_value_list.append(price_items.fixed_price)
                
                if min_qty != 0:
                    price_item_list.append({
                        'qty':str(min_qty)+'-'+str(round(price_items.min_quantity)-1),
                        'price':str(prod_price)+" "+price_items.currency_id.symbol,
                        })
                    min_qty = round(price_items.min_quantity)
                    prod_price = price_items.fixed_price
                else:
                    min_qty = round(price_items.min_quantity)
                    prod_price = price_items.fixed_price

            if prod_price != 0:
                price_item_list.append({
                        'qty':str(min_qty)+"+",
                        'price':str(prod_price)+" "+price_items.currency_id.symbol,
                        })
                prod_price = 0
            prod_dict_list.append({'product_id':product.id,'product_items':price_item_list, 'product_min_price_list': min_value_list})
        
        # Try to fetch geoip based fpos or fallback on partner one
        fiscal_position_sudo = website.fiscal_position_id.sudo()
        products_prices = lazy(lambda: products._get_sales_prices(pricelist, fiscal_position_sudo))
        query_url_kwargs.update({'brand': brand_list,'tag_list':tag_list,})

        request_args = request.httprequest.args
        attrib_list = request_args.getlist('attribute_value')
        attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
        attributes_ids = {v[0] for v in attrib_values}
        attrib_set = {v[1] for v in attrib_values}
        if attrib_list:
            post['attribute_value'] = attrib_list
        filter_by_tags_enabled = website.is_view_active('website_sale.filter_products_tags')
        if filter_by_tags_enabled:
            tags = request_args.getlist('tags')
            # Allow only numeric tag values to avoid internal error.
            if tags and all(tag.isnumeric() for tag in tags):
                post['tags'] = tags
                tags = {int(tag) for tag in tags}
            else:
                post['tags'] = None
                tags = {}

        ProductTag = request.env['product.tag']
        if filter_by_tags_enabled and search_product:
            all_tags = ProductTag.search(
                expression.AND([
                    [('product_ids.is_published', '=', True), ('visible_on_ecommerce', '=', True)],
                    website_domain
                ])
            )
        else:
            all_tags = ProductTag
        products_prices = lazy(lambda: products._get_sales_prices(website))

        attributes_values = request.env['product.attribute.value'].browse(attrib_set)
        sorted_attributes_values = attributes_values.sorted('sequence')
        multi_attributes_values = sorted_attributes_values.filtered(lambda av: av.display_type == 'multi')
        single_attributes_values = sorted_attributes_values - multi_attributes_values
        grouped_attributes_values = list(groupby(single_attributes_values, lambda av: av.attribute_id.id))
        grouped_attributes_values.extend([(av.attribute_id.id, [av]) for av in multi_attributes_values])

        selected_attributes_hash = grouped_attributes_values and "#attribute_values=%s" % (
            ','.join(str(v[0].id) for k, v in grouped_attributes_values)
        ) or ''

        keep = QueryURL('/shop', **query_url_kwargs) 
        values = {
            'tag_list':tag_list,
            'active_tag': active_tag,
            'product_tag_ids': product_tag_ids,
            'search': fuzzy_search_term or search,
            'original_search': fuzzy_search_term and search,
            'order': post.get('order', ''),
            'category': category,
            'attrib_values': attrib_values,
            'attrib_set': attrib_set,
            'pager': pager,
            'products': products,
            'search_product': search_product,
            'search_count': product_count,  # common for all searchbox
            'bins': lazy(lambda: TableCompute().process(products, ppg, ppr)),
            'ppg': ppg,
            'ppr': ppr,
            'gap': gap,
            'categories': categs,
            'attributes': attributes,
            'keep': keep,
            'search_categories_ids': search_categories.ids,
            'selected_attributes_hash': selected_attributes_hash,
            'layout_mode': layout_mode,
            'products_prices': products_prices,
            'get_product_prices': lambda product: lazy(lambda: products_prices[product.id]),
            'float_round': float_round,
            'active_brand_list': active_brand_list,
            'brand_set': brand_set,
            'pricelist_items':prod_dict_list,
            'product_brands': product_brands,
        }
        if filter_by_price_enabled:
            values['min_price'] = min_price or available_min_price
            values['max_price'] = max_price or available_max_price
            values['available_min_price'] = float_round(available_min_price, 2)
            values['available_max_price'] = float_round(available_max_price, 2)
        if filter_by_tags_enabled:
            values.update({'all_tags': all_tags, 'tags': tags})
        if category:
            values['main_object'] = category
        values.update(self._get_additional_extra_shop_values(values, **post))
        return request.render("website_sale.products", values)

    @http.route(['/shop/cart/update_json'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def cart_update_json(
        self, product_id, line_id=None, add_qty=None, set_qty=None, display=True,
        product_custom_attribute_values=None, no_variant_attribute_values=None, **kw
    ):
        """
        This route is called :
            - When changing quantity from the cart.
            - When adding a product from the wishlist.
            - When adding a product to cart on the same page (without redirection).
        """
        order = request.website.sale_get_order(force_create=True)
        if order.state != 'draft':
            request.website.sale_reset()
            if kw.get('force_create'):
                order = request.website.sale_get_order(force_create=True)
            else:
                return {}

        if product_custom_attribute_values:
            product_custom_attribute_values = json_scriptsafe.loads(product_custom_attribute_values)

        if no_variant_attribute_values:
            no_variant_attribute_values = json_scriptsafe.loads(no_variant_attribute_values)

        values = order._cart_update(
            product_id=product_id,
            line_id=line_id,
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values,
            **kw
        )

        values['notification_info'] = self._get_cart_notification_information(order, [values['line_id']])
        values['notification_info']['warning'] = values.pop('warning', '')
        request.session['website_sale_cart_quantity'] = order.cart_quantity

        if not order.cart_quantity:
            request.website.sale_reset()
            return values

        values['cart_quantity'] = order.cart_quantity
        values['minor_amount'] = payment_utils.to_minor_currency_units(
            order.amount_total, order.currency_id
        ),
        values['amount'] = order.amount_total

        if not display:
            return values

        values['cart_ready'] = order._is_cart_ready()
        values['website_sale.cart_lines'] = request.env['ir.ui.view']._render_template(
            "website_sale.cart_lines", {
                'website_sale_order': order,
                'date': fields.Date.today(),
                'suggested_products': order._cart_accessories()
            }
        )
        values['website_sale.total'] = request.env['ir.ui.view']._render_template(
            "website_sale.total", {
                'website_sale_order': order,
            }
        )
        values['theme_grocery_bizople.cart_right'] = request.env['ir.ui.view']._render_template(
            "theme_grocery_bizople.cart_right", {
            'website_sale_order': order,
            'suggested_products': order._cart_accessories()
            }
        )

        values['theme_grocery_bizople.mobile_bottom_cart'] = request.env['ir.ui.view']._render_template(
            "theme_grocery_bizople.mobile_bottom_cart", {
            'website_sale_order': order,
            }
        )
        return values

class bizcommonSliderSettings(http.Controller):

    @http.route(['/theme_grocery_bizople/get_product_banner_details_js'], type='json', auth='public', website=True)
    def get_product_banner_details_js(self, **post):
        product = request.env['product.template'].search(
            [('id', '=', int(post.get('product_id')))])
        values = {
            'product_id': product.id,
            'product_name': product.name,
            'product_description': product.description_sale,
        }
        return values
        
    @http.route(['/theme_grocery_bizople/get_product_banner_details_xml'], type='http', auth='public', website=True, sitemap=False)
    def get_product_banner_details_xml(self, **post):
        if post.get('product_id'):
            product = request.env['product.template'].sudo().search(
                [('id', '=', int(post.get('product_id')))])
            values = {
                'product': product,
            }
            return request.render("theme_grocery_bizople.product_banner_dynamic_data", values)    

    @http.route(['/theme_grocery_bizople/hotspot_product_select'], type='json', auth="public", website=True)
    def dynamic_hotspot_product_select(self):
        product_options = []
        option = request.env['product.template'].search([],order="name asc")
        for record in option:
            product_options.append({'id': record.id,
                                   'name': record.name})
        return product_options

    @http.route(['/theme_grocery_bizople/get_dynamic_hotspot_product_select'], type='http', auth='public', website=True, sitemap=False)
    def get_dynamic_hotspot_product_select(self, **post):
        if post.get('select-product-id'):
            product_info = request.env['product.template'].sudo().search(
                [('id', '=', int(post.get('select-product-id')))])
            values = {
                'product_info': product_info
            }
            # values.update({
            #     'slider_details': slider_header.product_ids,
            # })
            return request.render("theme_grocery_bizople.dynamic_hotspot_product_data", values)

    @http.route(['/theme_grocery_bizople/get_dynamic_hotspot_product_select_two'], type='json', auth='public', website=True)
    def get_dynamic_hotspot_product_select_two(self, **post):
        product_data = request.env['product.template'].search(
            [('id', '=', int(post.get('product_id')))])
        values = {
            'p_id': product_data.id,
            'p_name': product_data.name,
            'p_data': product_data,
        }
        return values

    # ajax cart popup json call
    @http.route(['/shop/cart/update_custom'], type='json', auth="public", methods=['GET', 'POST'], website=True, csrf=False)
    def cart_update_custom(self, product_id, add_qty=1, set_qty=0, **kw):
        """This route is called when adding a product to cart (no options)."""
        sale_order = request.website.sale_get_order(force_create=True)
        if sale_order.state != 'draft':
            request.session['sale_order_id'] = None
            sale_order = request.website.sale_get_order(force_create=True)
        product_custom_attribute_values = None
        if kw.get('product_custom_attribute_values'):
            product_custom_attribute_values = json_scriptsafe.loads(kw.get('product_custom_attribute_values'))

        no_variant_attribute_values = None
        if kw.get('no_variant_attribute_values'):
            no_variant_attribute_values = json_scriptsafe.loads(kw.get('no_variant_attribute_values'))

        sale_order._cart_update(
            product_id=int(product_id),
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values
        )
        values = {
            'showCart': True,
        }

        request.session['website_sale_cart_quantity'] = sale_order.cart_quantity
        values['cart_quantity'] = sale_order.cart_quantity

        return values
    
class LoginSignupPopup(Home):

    @http.route('/ajax/web/login', type='json', auth="none")
    def ajax_web_login(self, **kwargs):
        ensure_db()
        request.params['login_success'] = False
        
        if request.env.uid is None:
            if request.session.uid is None:
                # no user -> auth=public with specific website public user
                request.env["ir.http"]._auth_method_public()
            else:
                # auth=user
                request.update_env(user=request.session.uid)
                
        values = request.params.copy()
        try:
            values['databases'] = http.db_list()
        except odoo.exceptions.AccessDenied:
            values['databases'] = None
            
        if request.httprequest.method == 'POST':
            try:
                credential = {key: value for key, value in request.params.items() if key in CREDENTIAL_PARAMS and value}
                credential.setdefault('type', 'password')
                request.session.authenticate(request.db, credential)
                request.params['login_success'] = True
                return request.params
            except odoo.exceptions.AccessDenied as e:
                if e.args == odoo.exceptions.AccessDenied().args:
                    values['error'] = _("Wrong login/password")
                else:
                    values['error'] = e.args[0]
                    
        else:
            if 'error' in request.params and request.params.get('error') == 'access':
                values['error'] = _('Only employees can access this database. Please contact the administrator.')
                             
        if 'login' not in values and request.session.get('auth_login'):
            values['login'] = request.session.get('auth_login')
            
        if not odoo.tools.config['list_db']:
            values['disable_database_manager'] = True 
               
        return values

    @http.route('/ajax/login/',type='json',auth="public")
    def ajax_login_templete(self,**kwargs):
        context = {}
        providers = OAuthLogin.list_providers(self)
        context.update(super().get_auth_signup_config())
        context.update({'providers':providers})
        
        try:
            context['databases'] = http.db_list()
        except odoo.exceptions.AccessDenied:
            context['databases'] = None
            
        signup_enabled = request.env['res.users']._get_signup_invitation_scope() == 'b2c'
        reset_password_enabled = request.env['ir.config_parameter'].sudo().get_param('auth_signup.reset_password') == 'True'
        get_temp_id = kwargs['theme_name'] + ".login_form_ajax_bizt"
        login_template = request.env['ir.ui.view']._render_template(get_temp_id,context)
        data = {'loginview':login_template}
        if(signup_enabled == True):
            get_temp_id = kwargs['theme_name'] + ".signup_form_ajax_bizt"
            signup_template = request.env['ir.ui.view']._render_template(get_temp_id,context)
            data.update({'signupview':signup_template})
        if(reset_password_enabled == True):
            get_temp_id = kwargs['theme_name'] + ".password_reset_ajax"
            reset_template = request.env['ir.ui.view']._render_template(get_temp_id,context)
            data.update({'resetview':reset_template})
        return data

    @http.route('/ajax/signup/',type="json",auth="public")
    def ajax_web_auth_signup(self,*args, **kw):
        qcontext = super(LoginSignupPopup,self).get_auth_signup_qcontext()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                super(LoginSignupPopup,self).do_signup(qcontext)
                return {'signup_success':True}
            except UserError as e:
                qcontext['error'] = e.args[0]
            except (SignupError, AssertionError) as e:
                if request.env['res.users'].sudo().search([('login', '=', qcontext.get('login'))]):
                    qcontext['error'] = _('Another user is already registered using this email address.')
                else:
                    _logger.error("%s", e)
                    qcontext['error'] = _('Could not create a new account.')
        return qcontext

    @http.route('/ajax/web/reset_password', type='json', auth='public', website=True, sitemap=False)
    def ajax_web_auth_reset_password(self, *args, **kw):
        qcontext = super(LoginSignupPopup,self).get_auth_signup_qcontext()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                login = qcontext.get('login')
                assert login, _('No login provided.')
                _logger.info(
                    'Password reset attempt for <%s> by user <%s> from %s',
                    login, request.env.user.login, request.httprequest.remote_addr)
                request.env['res.users'].sudo().reset_password(login)
                qcontext['message'] = _('An email has been sent with credentials to reset your password')
            except UserError as e:
                qcontext['error'] = e.args[0]
            except SignupError:
                qcontext['error'] = _('Could not reset your password')
                _logger.exception('error when resetting password')
            except Exception as e:
                qcontext['error'] = str(e)
        return qcontext

class PwaMain(http.Controller):
    
    def get_asset_urls(self, asset_xml_id):
        qweb = request.env['ir.qweb'].sudo()
        assets = qweb._get_asset_nodes(asset_xml_id, {}, True, True)
        urls = []
        for asset in assets:
            if asset[0] == 'link':
                urls.append(asset[1]['href'])
            if asset[0] == 'script':
                urls.append(asset[1]['src'])
        return urls

    @http.route('/service_worker.js', type='http', auth="public", sitemap=False)
    def service_worker(self):
        qweb = request.env['ir.qweb'].sudo()
        website_id = request.env['website'].sudo().get_current_website().id
        languages = request.env['website'].sudo().get_current_website().language_ids
        lang_code = request.env.lang
        current_lang = request.env['res.lang']._lang_get(lang_code)
        mimetype = 'text/javascript;charset=utf-8'
        content = qweb._render('grocery_theme_common.service_worker', {
            'website_id': website_id,
        })
        return request.make_response(content, [('Content-Type', mimetype)])

    @http.route('/pwa/enabled', type='json', auth="public")
    def enabled_pwa(self):
        if request.env['website'].sudo().get_current_website().theme_id.name == 'theme_grocery_bizople':
            enabled_pwa = request.env['website'].sudo().get_current_website().enable_pwa
            if enabled_pwa:
                return enabled_pwa
    
    @http.route('/grocery_theme_common/manifest/<int:website_id>', type='http', auth="public", website=True)
    def manifest(self, website_id=None):
        website = request.env['website'].search([('id', '=', website_id)]) if website_id else request.website
        app_name_pwa = website.app_name_pwa
        short_name_pwa = website.short_name_pwa
        description_pwa = website.description_pwa
        background_color_pwa = website.background_color_pwa
        theme_color_pwa = website.theme_color_pwa
        start_url_pwa = website.start_url_pwa
        image_192_pwa = "/web/image/website/%s/image_192_pwa/192x192" % (website.id)
        image_512_pwa = "/web/image/website/%s/image_512_pwa/512x512" % (website.id)
        
        qweb = request.env['ir.qweb'].sudo()
        mimetype = 'application/json;charset=utf-8'
        content = qweb._render('grocery_theme_common.manifest', {
            'app_name_pwa': app_name_pwa,
            'short_name_pwa': short_name_pwa,
            'start_url_pwa': start_url_pwa,
            'image_192_pwa': image_192_pwa,
            'image_512_pwa': image_512_pwa,
            'background_color_pwa': background_color_pwa,
            'theme_color_pwa': theme_color_pwa,
        })
        return request.make_response(content, [('Content-Type', mimetype)])

    @http.route('/grocery/search/product', type='http', auth='public', website=True, sitemap=False)
    def search_autocomplete(self, term=None, category=None, popupcateg=None):
        if category or popupcateg:
            if category:
                prod_category = request.env["product.public.category"].sudo().search([
                    ('id', '=', category)])

            else:
                prod_category = request.env["product.public.category"].sudo().search([
                    ('id', '=', popupcateg)])
            product_list = []
            for product in prod_category.product_tmpl_ids or prod_category.child_id.product_tmpl_ids:
                product_list.append(product.id)
            results = request.env["product.template"].sudo().search(
                [('name', 'ilike', term), ('id', 'in', product_list),('website_published', '=', True)])
            value = {
                'results': results

            }
            return request.render("theme_grocery_bizople.search_grocery", value)
        else:
            results = request.env["product.template"].sudo().search(
                [('name', 'ilike', term),('website_published', '=', True)])
            value = {
                'results': results
            }
            return request.render("theme_grocery_bizople.search_grocery",value)