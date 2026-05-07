/** @odoo-module **/
/**
 * TeethSelectorEditWidget
 * Renders as a compact button. On click, opens a full modal editor.
 * On save, writes back to teeth_numbers (JSON array) and tooth_shades (JSON object).
 * Binds to the `teeth_numbers` char field on mrp.production.
 */

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import {
    CROWN_PATHS, ROOT_PATHS, CROWN_W, CROWN_H, ROOT_H,
    UPPER_ORDER, LOWER_ORDER, shadeColor, buildLayout, toothIndex
} from "./teeth_selector";

const VITA_SHADES = ['Ninguno','A1','A2','A3','A3.5','A4','B1','B2','B3','B4','C1','C2','C3','C4','D2','D3','D4','BL1','BL2','BL3','BL4'];

const FDI_NAMES = { 1:'Incisivo Central',2:'Incisivo Lateral',3:'Canino',4:'1er Premolar',5:'2do Premolar',6:'1er Molar',7:'2do Molar',8:'3er Molar (Cordal)' };
const FDI_QUADRANT = { 1:'Superior Derecho',2:'Superior Izquierdo',3:'Inferior Izquierdo',4:'Inferior Derecho' };
function toothName(n) {
    const q = Math.floor(n / 10);
    const pos = n % 10;
    return FDI_NAMES[pos] ? `${FDI_NAMES[pos]} · ${FDI_QUADRANT[q]}` : '';
}

const GAP = 5;

export class TeethSelectorEditWidget extends Component {
    static template = "custom_manufacturing_dashboard.TeethSelectorEdit";
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({
            // modal open/close
            open: false,
            // working copies (only committed on save)
            selected: {},
            shades: {},
            popup: null,   // shade editor popup for a single tooth
        });
        onMounted(() => this._syncFromRecord());
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    _getDefaultColor() {
        return this.props.record.data['color_selected'] || 'A1';
    }

    _syncFromRecord() {
        const rec = this.props.record;
        // Load teeth_numbers (JSON array) from record
        const sel = {};
        try {
            const nums = JSON.parse(rec.data['teeth_numbers'] || '[]');
            for (const n of nums) sel[n] = true;
        } catch {}
        this.state.selected = sel;

        // Load tooth_shades — read from the field this widget is bound to (tooth_shades)
        // props.value is the current field value (tooth_shades char)
        try {
            const raw = this.props.value || rec.data['tooth_shades'] || '{}';
            this.state.shades = JSON.parse(raw);
        } catch { this.state.shades = {}; }
    }

    get selectedCount() { return Object.keys(this.state.selected).length; }

    // ── Modal open/close ─────────────────────────────────────────────────────

    openModal() {
        // refresh working copy from record before opening
        this._syncFromRecord();
        this.state.popup = null;
        this.state.open = true;
    }

    cancelModal() {
        this.state.open = false;
        this.state.popup = null;
    }

    saveModal() {
        // Commit working copies to the record
        const selectedNums = Object.keys(this.state.selected).map(Number).filter(Boolean);
        selectedNums.sort((a, b) => a - b);
        const shadesJson = JSON.stringify(this.state.shades);

        // Write tooth_shades via the widget's own update (bound field)
        this.props.record.update({ tooth_shades: shadesJson });
        // Write teeth_numbers separately (different field, same record)
        this.props.record.update({ teeth_numbers: JSON.stringify(selectedNums) });

        this.state.open = false;
        this.state.popup = null;
    }

    // ── Tooth click/shade logic ──────────────────────────────────────────────

    onToothClick(n) {
        if (this.state.selected[n]) {
            this._openShadePopup(n);
        } else {
            this.state.selected[n] = true;
            this._openShadePopup(n);
        }
    }

    _openShadePopup(n) {
        const def = this._getDefaultColor();
        const existing = this.state.shades[n] || {};
        this.state.popup = {
            n,
            incisal:  existing.incisal  || def,
            middle:   existing.middle   || def,
            cervical: existing.cervical || def,
        };
    }

    closeShadePopup() { this.state.popup = null; }

    deselectTooth(n) {
        delete this.state.selected[n];
        delete this.state.shades[n];
        this.state.popup = null;
    }

    saveShadePopup() {
        const p = this.state.popup;
        if (!p) return;
        this.state.shades[p.n] = { incisal: p.incisal, middle: p.middle, cervical: p.cervical };
        this.state.popup = null;
    }

    setShade(part, val) {
        if (this.state.popup) this.state.popup[part] = val;
    }

    // ── Color helpers ────────────────────────────────────────────────────────

    getIncisalColor(n) { const s = this.state.shades[n]; const d = this._getDefaultColor(); return shadeColor(s ? s.incisal||d : d); }
    getMiddleColor(n)  { const s = this.state.shades[n]; const d = this._getDefaultColor(); return shadeColor(s ? s.middle||d  : d); }
    getCervicalColor(n){ const s = this.state.shades[n]; const d = this._getDefaultColor(); return shadeColor(s ? s.cervical||d: d); }
    hasMixedShades(n)  { const s = this.state.shades[n]; return s ? (s.incisal !== s.middle || s.middle !== s.cervical) : false; }
    isLowerTooth(n)    { return n >= 31; }

    getToothFillColor(n) {
        const s = this.state.shades[n]; const d = this._getDefaultColor();
        if (!s) return shadeColor(d);
        return shadeColor(s.cervical || s.middle || s.incisal || d);
    }
    getToothStrokeColor(n) {
        const fill = this.getToothFillColor(n);
        try {
            const r = parseInt(fill.slice(1,3),16), g = parseInt(fill.slice(3,5),16), b = parseInt(fill.slice(5,7),16);
            const d = c => Math.round(c*0.65).toString(16).padStart(2,'0');
            return `#${d(r)}${d(g)}${d(b)}`;
        } catch { return '#999'; }
    }
    getToothShadeLabel(n) {
        const s = this.state.shades[n];
        if (!s) return this._getDefaultColor();
        if (s.incisal===s.middle && s.middle===s.cervical) return s.incisal;
        return '~';
    }

    // ── Layout helpers ───────────────────────────────────────────────────────

    getVitaShades()    { return VITA_SHADES; }
    shadeColor(s)      { return shadeColor(s); }
    toothName(n)       { return toothName(n); }
    getUpperLayout()   { return buildLayout(UPPER_ORDER); }
    getLowerLayout()   { return buildLayout(LOWER_ORDER); }
    getTotalWidth(layout) { const l = layout[layout.length-1]; return l.x + l.w + 4; }
    isSelected(n)      { return !!this.state.selected[n]; }
    getCrownPath(tooth){ return CROWN_PATHS[tooth.idx]; }
    getRootPaths(tooth){ return ROOT_PATHS[tooth.idx]; }
    getRootHeight(tooth){ return ROOT_H[tooth.idx]; }
    getCrownH()        { return CROWN_H; }
    getToothH(tooth)   { return CROWN_H + 4 + this.getRootHeight(tooth); }
    getMaxH(layout)    { return Math.max(...layout.map(t => this.getToothH(t))); }
    getPopupCrownPath() {
        if (!this.state.popup) return { path:'', w:47, h:56 };
        const idx = toothIndex(this.state.popup.n);
        return { path: CROWN_PATHS[idx], w: CROWN_W[idx], h: 56 };
    }
}

registry.category("fields").add("teeth_selector_edit", {
    component: TeethSelectorEditWidget,
    displayName: "Teeth Selector (Edit Modal)",
    supportedTypes: ["char"],
});
