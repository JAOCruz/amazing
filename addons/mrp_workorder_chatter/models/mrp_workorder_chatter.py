from odoo import models

class MrpWorkorderChatter(models.Model):
    _name = 'mrp.workorder'
    _inherit = ['mrp.workorder', 'mail.thread', 'mail.activity.mixin']
    _description = "Add Chatter support to MRP Workorder"
