/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";

/**
 * Patch FormController to support pager navigation from the manufacturing dashboard.
 *
 * When opening an MO from the dashboard, the action context includes `dashboard_res_ids`
 * with the full list of order IDs in the current filter. This patch injects those IDs
 * into the model CONFIG (via modelParams) so the root DataPoint is created with the
 * full resIds list from the start — enabling the native "1 / N < >" pager.
 *
 * Why modelParams? Because model.root doesn't exist during setup() — it's created
 * asynchronously during load(). By injecting resIds into the config, the root is
 * born with the correct list.
 */

// Capture the original getter before we replace it
const origModelParamsGetter = Object.getOwnPropertyDescriptor(
    FormController.prototype, 'modelParams'
).get;

patch(FormController.prototype, {
    get modelParams() {
        const params = origModelParamsGetter.call(this);
        const ctx = this.props.context || {};
        const resIds = ctx.dashboard_res_ids;
        if (resIds && resIds.length > 1) {
            params.config.resIds = resIds;
        }
        return params;
    },
});
