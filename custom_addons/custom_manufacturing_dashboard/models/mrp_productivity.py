from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class MrpWorkcenterProductivityCustom(models.Model):
    _inherit = 'mrp.workcenter.productivity'

    # ▶️ CUANDO SE INICIA / REANUDA
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for rec in records:
            wo = rec.workorder_id
            if not wo:
                continue

            wo.message_post(
                body=(
                    "▶️ <b>Orden de Trabajo Iniciada</b><br/>"
                    "Usuario: %s"
                ) % rec.env.user.name
            )

            if wo.production_id:
                wo.production_id.message_post(
                    body="▶️ Orden de Trabajo Iniciada: %s" % wo.name
                )

        return records

    # ✅ CUANDO SE TERMINA (Disponible / Siguiente)
    # NOTE: action_end() is called when a productivity period ends, NOT when the workorder finishes.
    # The actual finish message is posted in mrp_workorder._finish_workorder()
    # Keeping this commented to avoid duplicate messages.
    # def action_end(self):
    #     _logger.warning("🔥 action_end CALLED (Trabajo terminado)")
    #
    #     for rec in self:
    #         wo = rec.workorder_id
    #         if not wo:
    #             continue
    #
    #         wo.message_post(
    #             body=(
    #                 "✅ <b>Orden de Trabajo Terminada</b><br/>"
    #                 "Usuario: %s<br/>"
    #                 "Duración: %.2f minutos"
    #             ) % (
    #                 self.env.user.name,
    #                 wo.duration or 0.0
    #             )
    #         )
    #
    #         if wo.production_id:
    #             wo.production_id.message_post(
    #                 body="✅ Orden de Trabajo Terminada: %s" % wo.name
    #             )
    #
    #     return super().action_end()
