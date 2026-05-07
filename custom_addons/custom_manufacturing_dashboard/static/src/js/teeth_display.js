/** @odoo-module **/
/**
 * TeethDisplayWidget — read-only anatomical dental chart for mrp.production
 * Imports ALL constants and utilities from teeth_selector.js to guarantee
 * identical rendering (same crown/root paths, same layout math).
 */
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import {
    CROWN_PATHS, ROOT_PATHS, CROWN_W, CROWN_H, ROOT_H,
    UPPER_ORDER, LOWER_ORDER, shadeColor, buildLayout, toothIndex,
} from "@custom_manufacturing_dashboard/js/teeth_selector";

export class TeethDisplayWidget extends Component {
    static template = "custom_manufacturing_dashboard.TeethDisplay";
    static props = {
        id: { optional: true },
        name: { type: String, optional: true },
        record: { type: Object },
        readonly: { type: Boolean, optional: true },
        className: { type: String, optional: true },
    };

    setup() {
        this.expanded = useState({ value: false });
    }

    toggleExpand() {
        this.expanded.value = !this.expanded.value;
    }

    // ── Data from record ────────────────────────────────────────────────────
    get teethNumbers() {
        try {
            const raw = this.props.record.data['teeth_numbers'] || '[]';
            return JSON.parse(raw.replace(/'/g, '"'));
        } catch { return []; }
    }

    get shades() {
        try {
            const raw = this.props.record.data['tooth_shades'] || '{}';
            return JSON.parse(raw);
        } catch { return {}; }
    }

    get defaultShade() {
        return this.props.record.data['color_selected'] || 'A2';
    }

    // ── Selection & shade helpers ───────────────────────────────────────────
    isSelected(n) { return this.teethNumbers.includes(n); }

    getIncisalColor(n) {
        const s = this.shades[n];
        return shadeColor(s ? s.incisal || this.defaultShade : this.defaultShade);
    }
    getMiddleColor(n) {
        const s = this.shades[n];
        return shadeColor(s ? s.middle || this.defaultShade : this.defaultShade);
    }
    getCervicalColor(n) {
        const s = this.shades[n];
        return shadeColor(s ? s.cervical || this.defaultShade : this.defaultShade);
    }
    hasMixedShades(n) {
        const s = this.shades[n];
        if (!s) return false;
        return s.incisal !== s.middle || s.middle !== s.cervical;
    }
    getShadeLabel(n) {
        const s = this.shades[n];
        const def = this.defaultShade;
        if (!s) return def;
        const parts = [s.incisal || def, s.middle || def, s.cervical || def];
        const unique = [...new Set(parts)];
        return unique.length === 1 ? unique[0] : unique.join('/');
    }
    getStrokeColor(n) {
        const s = this.shades[n];
        const shade = s ? s.middle || this.defaultShade : this.defaultShade;
        const dark = ['A3','A3.5','A4','B3','B4','C3','C4','D3','D4'];
        return dark.includes(shade) ? '#7a5c1e' : '#b8901a';
    }

    // ── Layout helpers (same as TeethSelectorWidget) ────────────────────────
    getCrownPath(tooth) { return CROWN_PATHS[tooth.idx]; }
    getRootPaths(tooth) { return ROOT_PATHS[tooth.idx]; }
    getCrownH() { return CROWN_H; }
    getRootHeight(tooth) { return ROOT_H[tooth.idx]; }
    getToothH(tooth) { return CROWN_H + 4 + ROOT_H[tooth.idx]; }
    getMaxH(layout) { return Math.max(...layout.map(t => this.getToothH(t))); }
    getUpperLayout() { return buildLayout(UPPER_ORDER); }
    getLowerLayout() { return buildLayout(LOWER_ORDER); }
    getTotalWidth(layout) { const l = layout[layout.length - 1]; return l.x + l.w + 4; }

    // ── Legend helpers ─────────────────────────────────────────────────────
    get usedShades() {
        const teeth = this.teethNumbers;
        const result = [];
        const seen = new Set();
        for (const n of teeth) {
            const label = this.getShadeLabel(n);
            const color = this.getMiddleColor(n);
            const stroke = this.getStrokeColor(n);
            const key = label + color;
            if (!seen.has(key)) {
                seen.add(key);
                result.push({ n, label, color, stroke });
            }
        }
        return result;
    }
}

registry.category("fields").add("teeth_display", {
    component: TeethDisplayWidget,
    displayName: "Teeth Display (Read-only)",
    supportedTypes: ["char"],
});
