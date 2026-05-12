# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_do_referencia_trabajo = fields.Char(
        string="Referencia del Trabajo",
        help="Número de caso, orden de trabajo, o referencia interna.",
    )
    l10n_do_doctor_referente = fields.Many2one(
        "res.partner",
        string="Doctor Referente",
        domain="[('is_company', '=', False)]",
        help="Médico que refirió el trabajo o paciente.",
    )
