# -- coding: utf-8 --
# See LICENSE file for full copyright and licensing details.
# Developed by Bizople Solutions Pvt. Ltd.

from odoo import fields,models,api,tools
import pytz
import datetime

ADDRESS_FIELDS = ('street', 'street2', 'zip', 'city', 'state_id', 'country_id')

class StoreLocation(models.Model):
    _name = "store.location"
    _description = "Store Location Details"

    name = fields.Char("Store Name", required=True)
    location_url = fields.Char('Store Location URL')
    street = fields.Char()
    street2 = fields.Char()
    zip = fields.Char(change_default=True)
    city = fields.Char()
    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict', domain="[('country_id', '=?', country_id)]")
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict')
    email = fields.Char()
    email_formatted = fields.Char(
        'Formatted Email', compute='_compute_email_formatted',
        help='Format email address "Name <email@domain>"')
    phone = fields.Char()
    is_published = fields.Boolean('Publish Store Address', default=False)
    
    contact_address = fields.Char(compute='_compute_contact_address', string='Complete Address')
    vat = fields.Char(string='Tax ID', index=True, help="The Tax Identification Number. Complete it if the contact is subjected to government taxes. Used in some legal statements.")
    
    @api.depends('name', 'email')
    def _compute_email_formatted(self):
        for partner in self:
            if partner.email:
                partner.email_formatted = tools.formataddr((partner.name or u"False", partner.email or u"False"))
            else:
                partner.email_formatted = ''

    @api.model
    def _address_fields(self):
        """Returns the list of address fields that are synced from the parent."""
        return list(ADDRESS_FIELDS)

    @api.model
    def _formatting_address_fields(self):
        """Returns the list of address fields usable to format addresses."""
        return self._address_fields()

    @api.model
    def _get_default_address_format(self):
        return "%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s"

    @api.model
    def _get_address_format(self):
        return self.country_id.address_format or self._get_default_address_format()

    def _display_address(self, without_company=False):

        '''
        The purpose of this function is to build and return an address formatted accordingly to the
        standards of the country where it belongs.

        :param address: browse record of the res.partner to format
        :returns: the address formatted in a display that fit its country habits (or the default ones
            if not country is specified)
        :rtype: string
        '''
        # get the information that will be injected into the display format
        # get the address format
        address_format = self._get_address_format()
        args = {
            'state_code': self.state_id.code or '',
            'state_name': self.state_id.name or '',
            'country_code': self.country_id.code or '',
            'country_name': self._get_country_name(),
        }
        for field in self._formatting_address_fields():
            args[field] = getattr(self, field) or ''
        return address_format % args

    def _display_address_depends(self):
        # field dependencies of method _display_address()
        return self._formatting_address_fields() + [
            'country_id.address_format', 'country_id.code', 'country_id.name',
            'state_id.code', 'state_id.name',
        ]

    @api.depends(lambda self: self._display_address_depends())
    def _compute_contact_address(self):
        for store in self:
            store.contact_address = store._display_address()

    def _get_country_name(self):
        return self.country_id.name or ''
    
    
    def publish_store_location(self):
        if self.is_published == False:
            self.is_published = True
        else:
            self.is_published = False

class SaleOrderField(models.Model):
    _inherit = "sale.order"

    store_location_id = fields.Many2one('store.location',string="Pickup Address")