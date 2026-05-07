/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Interactive SVG Dental Odontogram
 * Crown paths: biomathcode/react-odontogram (MIT License)
 * Root paths: custom anatomical
 *
 * Features:
 * - Click unselected tooth → select + open shade popup
 * - Click selected tooth  → open shade popup to edit
 * - Each tooth stores 3 shades: incisal / tercio medio / cervical
 * - Defaults to the order's color_selected value
 * - Saves to tooth_shades JSON field (backward compatible)
 */

// ── Vita shade catalog ─────────────────────────────────────────────────────────
const VITA_SHADES = ['Ninguno','A1','A2','A3','A3.5','A4','B1','B2','B3','B4','C1','C2','C3','C4','D2','D3','D4','BL1','BL2','BL3','BL4'];

// Clinical approximations of Vita Classical shade colors (rGB/hex)
// A family: reddish-brownish/golden  B: yellowish  C: greyish  D: reddish-grey  BL: bleached
const SHADE_COLORS = {
    'Ninguno':'#EFEFEF',
    // Bleached (brightest, cool white)
    'BL1':'#F8F7F0', 'BL2':'#F5F1E5', 'BL3':'#F0EADA', 'BL4':'#EAE2CF',
    // A family — warm golden/amber tones
    'A1':'#F2E3BC', 'A2':'#EDD59C', 'A3':'#E3C478', 'A3.5':'#D6AF58', 'A4':'#C79838',
    // B family — pure yellowish tones (lighter/less warm than A)
    'B1':'#F5EDD0', 'B2':'#EDE0A8', 'B3':'#E3CC80', 'B4':'#D0B460',
    // C family — greyish/cool neutral
    'C1':'#E5DEC8', 'C2':'#D5CEB4', 'C3':'#C5BC98', 'C4':'#B0A87A',
    // D family — reddish-grey
    'D2':'#E4D4BA', 'D3':'#D2BE98', 'D4':'#BEA878',
};

function shadeColor(shade) { return SHADE_COLORS[shade] || '#f5f5f5'; }

// ── FDI Dental Nomenclature ──────────────────────────────────────────────────
// Last digit of FDI number (1-8) → anatomical name
const FDI_NAMES = {
    1: 'Incisivo Central',
    2: 'Incisivo Lateral',
    3: 'Canino',
    4: '1er Premolar',
    5: '2do Premolar',
    6: '1er Molar',
    7: '2do Molar',
    8: '3er Molar (Cordal)',
};
// Quadrant prefix
const FDI_QUADRANT = {
    1: 'Superior Derecho',
    2: 'Superior Izquierdo',
    3: 'Inferior Izquierdo',
    4: 'Inferior Derecho',
};
function toothName(n) {
    const q = Math.floor(n / 10);
    const pos = n % 10;
    const name = FDI_NAMES[pos] || '';
    const quad = FDI_QUADRANT[q] || '';
    return name ? `${name} · ${quad}` : '';
}

// ── Crown paths (normalized ~56px tall) ──────────────────────────────────────
const CROWN_PATHS = [
    // 0: Central Incisor
    `M18.39 55.13C16.34 54.96 13.46 54.28 13.46 54.28C13.46 54.28 8.32 53.28 6.23 52.10C4.01 50.83 1.09 48.97 0.68 47.15C0.30 45.43 0.00 42.73 0.29 40.78L0.31 40.59C0.66 38.24 1.18 34.75 1.56 31.00C1.75 29.14 1.50 28.01 2.32 25.27C3.18 22.39 3.66 21.02 4.25 19.99C4.86 18.91 5.65 18.06 6.17 16.95C6.99 15.17 8.43 12.98 9.83 11.31C10.62 10.36 11.38 9.54 12.05 8.85C13.00 7.86 14.70 5.98 15.72 4.85C17.15 3.26 18.61 1.86 19.87 1.41C21.01 1.00 22.40 0.84 23.41 0.57C24.69 0.24 25.74 0.00 27.69 0.61C29.13 1.06 30.22 1.22 31.74 2.91C33.64 5.03 34.36 6.21 34.97 7.36C35.94 9.20 37.28 11.71 38.21 13.38C38.77 14.38 40.25 16.27 41.93 21.65C43.32 26.09 44.07 28.90 44.39 30.05C44.77 31.37 45.36 33.40 45.60 35.83C45.97 39.73 46.57 42.81 46.49 46.11C46.42 48.95 46.54 50.81 45.44 51.97C44.54 52.92 43.57 53.82 42.33 54.30C40.50 55.02 38.81 55.53 37.39 55.74C36.13 55.92 30.82 56.00 26.94 55.69C25.48 55.57 23.58 55.56 18.39 55.13Z`,
    // 1: Lateral Incisor
    `M16.62 5.08C19.56 2.85 23.42 0.35 25.22 0.24C29.49 0.00 33.08 2.23 35.23 5.93C39.35 13.02 41.77 21.04 43.71 28.96C44.57 32.46 48.92 44.99 44.65 47.88C38.47 55.98 13.64 56.00 6.91 50.02C0.00 43.89 2.07 29.40 4.80 21.78C7.06 15.50 11.33 9.08 16.62 5.08Z`,
    // 2: Canine
    `M0.70 36.77C0.88 34.86 1.28 18.16 11.70 4.87C14.73 1.01 25.46 0.00 29.44 3.08C36.71 8.70 39.80 28.83 36.69 37.49C35.21 41.63 23.18 56.00 17.24 53.31C11.66 50.79 0.00 44.23 0.70 36.77Z`,
    // 3: First Premolar
    `M12.41 8.31C6.87 12.28 3.07 36.73 3.01 36.91C3.02 38.29 0.00 46.85 20.35 55.59C21.30 56.00 22.38 55.47 23.10 55.06C23.89 54.61 25.55 53.46 28.24 50.78C29.89 49.14 36.52 42.31 36.63 37.77C36.69 35.68 36.32 31.50 35.92 27.34C35.53 23.19 34.21 15.88 33.31 13.09C32.44 10.40 27.72 0.00 12.41 8.31Z`,
    // 4: Second Premolar
    `M6.35 48.26C8.27 49.87 14.80 55.08 17.71 55.56C20.35 56.00 31.36 46.99 33.80 39.56C34.39 37.78 35.11 17.29 28.60 6.20C22.23 0.00 9.16 1.28 5.25 13.17C3.06 19.84 0.49 32.87 0.25 34.49C0.00 36.12 0.01 38.31 0.37 40.48C0.58 41.71 0.68 42.39 1.05 42.94C1.56 43.70 3.08 45.50 6.35 48.26Z`,
    // 5: First Molar
    `M7.46 41.01C9.12 42.32 23.29 56.00 38.45 40.31C39.48 39.24 48.19 25.00 39.31 7.44C38.34 5.52 37.68 3.75 36.82 2.82C35.53 1.44 34.87 0.74 33.30 0.65C31.94 0.56 30.54 1.03 27.36 1.81C25.75 2.20 24.68 2.45 21.77 1.31C20.72 0.90 19.20 0.17 17.28 0.07C15.73 0.00 14.67 0.06 13.39 0.92C11.41 2.24 9.94 3.87 8.77 6.31C8.43 7.02 7.64 8.30 6.23 11.13C5.34 12.92 4.18 15.42 3.26 17.71C2.34 20.00 1.64 22.01 1.25 23.47C0.64 25.76 0.00 28.06 0.53 30.19L0.53 30.21C0.86 31.50 1.33 33.40 2.62 35.33C3.97 37.34 5.52 39.47 7.46 41.01Z`,
    // 6: Second Molar
    `M3.46 25.72C2.66 28.12 0.00 50.30 28.74 54.67C44.27 56.00 50.80 40.18 51.13 37.67C53.42 31.26 51.23 17.68 49.99 14.60C48.39 10.63 47.30 8.13 46.52 6.97C44.95 4.66 43.68 2.71 42.85 2.33C41.67 1.80 39.68 0.46 35.38 2.08C32.42 3.20 29.97 2.93 27.40 2.17C24.39 1.27 20.39 0.00 18.86 0.28C17.84 0.47 16.76 0.49 15.93 1.35C14.74 2.60 13.35 4.24 10.89 9.28C9.67 11.77 7.75 15.68 6.81 17.84C5.24 21.45 4.14 23.67 3.46 25.72Z`,
    // 7: Third Molar
    `M24.54 55.69C25.67 56.00 27.71 55.77 28.16 55.80C28.47 55.83 31.35 55.67 33.31 55.12C35.92 54.18 37.70 53.49 38.63 52.80C40.36 51.54 43.03 49.31 45.26 46.45C46.85 44.42 48.19 42.01 49.23 39.24C49.98 37.25 50.59 35.38 50.75 32.41C50.84 30.48 50.85 27.77 50.58 24.66C50.31 21.54 49.78 18.13 49.20 15.54C48.63 12.94 48.03 11.20 47.40 9.69C46.76 8.18 46.08 6.93 45.72 6.20C45.07 4.87 44.58 3.65 43.71 2.84C41.95 1.22 40.59 0.56 39.22 0.31C38.04 0.10 36.23 0.12 35.02 0.55C33.29 1.16 32.37 1.87 29.73 1.89C26.15 1.92 24.20 0.42 21.96 0.27C18.24 0.00 16.23 0.03 15.01 0.70C14.04 1.23 12.81 2.07 10.33 5.63C9.60 6.67 8.83 8.01 7.20 11.51C6.06 13.96 4.37 17.69 3.46 19.67C2.45 21.86 1.43 23.80 0.68 26.96C0.16 29.20 0.00 31.93 0.58 34.91C0.98 36.94 1.72 39.71 4.20 42.91C6.87 46.36 8.80 48.63 9.87 49.48C10.83 50.23 11.82 50.97 13.19 51.58C14.96 52.36 16.59 53.55 18.71 54.18C21.16 54.90 22.64 55.17 24.54 55.69Z`,
];

const CROWN_H = 56;
const CROWN_W = [46.6, 48.9, 39.8, 36.7, 35.1, 48.2, 53.4, 50.8];

const ROOT_PATHS = [
    [`M 13.5,0 L 13.5,76 Q 23.3,84 33.1,76 L 33.1,0 Z`],
    [`M 15.2,0 L 15.2,70 Q 24.4,78 33.7,70 L 33.7,0 Z`],
    [`M 12.3,0 L 12.3,90 Q 19.9,98 27.5,90 L 27.5,0 Z`],
    [`M 2.9,0 L 2.9,48 Q 8.1,58 13.2,48 L 13.2,0 Z`, `M 22.8,0 L 22.8,44 Q 27.9,55 33.0,44 L 33.0,0 Z`],
    [`M 2.8,0 L 2.8,46 Q 7.7,56 12.6,46 L 12.6,0 Z`, `M 21.8,0 L 21.8,42 Q 26.7,54 31.6,42 L 31.6,0 Z`],
    [`M 1.9,0 L 1.9,42 Q 7.2,50 12.5,42 L 12.5,0 Z`, `M 18.8,0 L 18.8,46 Q 24.1,50 29.4,46 L 29.4,0 Z`, `M 34.7,0 L 34.7,40 Q 40.0,50 45.3,40 L 45.3,0 Z`],
    [`M 2.1,0 L 2.1,46 Q 8.0,54 13.9,46 L 13.9,0 Z`, `M 20.8,0 L 20.8,50 Q 26.7,54 32.6,50 L 32.6,0 Z`, `M 38.4,0 L 38.4,44 Q 44.3,54 50.2,44 L 50.2,0 Z`],
    [`M 2.0,0 L 2.0,40 Q 7.6,48 13.2,40 L 13.2,0 Z`, `M 19.8,0 L 19.8,44 Q 25.4,48 31.0,44 L 31.0,0 Z`, `M 36.6,0 L 36.6,38 Q 42.2,48 47.8,38 L 47.8,0 Z`],
];
const ROOT_H = [84, 78, 98, 58, 56, 50, 54, 48];

// ── FDI mapping ───────────────────────────────────────────────────────────────
function toothIndex(n) {
    const map = {
        11:0,21:0,31:0,41:0, 12:1,22:1,32:1,42:1,
        13:2,23:2,33:2,43:2, 14:3,24:3,34:3,44:3,
        15:4,25:4,35:4,45:4, 16:5,26:5,36:5,46:5,
        17:6,27:6,37:6,47:6, 18:7,28:7,38:7,48:7,
    };
    return map[n] ?? 0;
}

const GAP = 5;
const UPPER_ORDER = [18,17,16,15,14,13,12,11,21,22,23,24,25,26,27,28];
const LOWER_ORDER = [48,47,46,45,44,43,42,41,31,32,33,34,35,36,37,38];

function buildLayout(nums) {
    let x = 0;
    return nums.map(n => {
        const idx = toothIndex(n);
        const w = CROWN_W[idx];
        const r = { n, x, w, idx };
        x += w + GAP;
        return r;
    });
}

// ── OWL Component ─────────────────────────────────────────────────────────────
export class TeethSelectorWidget extends Component {
    static template = "custom_manufacturing_dashboard.TeethSelector";
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({
            selected: {},
            shades: {},     // { 11: {incisal:'A1', middle:'A1', cervical:'A1'}, ... }
            popup: null,    // { n, incisal, middle, cervical } — current popup tooth
        });
        onMounted(() => this._loadFromRecord());
    }

    _getDefaultColor() {
        // Use the order's color_selected as default shade
        return this.props.record.data['color_selected'] || 'A1';
    }

    _loadFromRecord() {
        const rec = this.props.record;
        const sel = {};
        for (let q = 1; q <= 4; q++)
            for (let t = 1; t <= 8; t++) {
                const n = q * 10 + t;
                if (rec.data[`tooth_${n}`]) sel[n] = true;
            }
        this.state.selected = sel;

        // Load tooth_shades JSON
        try {
            const raw = rec.data['tooth_shades'] || '{}';
            this.state.shades = JSON.parse(raw);
        } catch { this.state.shades = {}; }
    }

    _saveShades() {
        if (this.props.record.fields['tooth_shades']) {
            this.props.record.update({ tooth_shades: JSON.stringify(this.state.shades) });
        }
    }

    onToothClick(n) {
        if (this.state.selected[n]) {
            // Already selected → open shade popup
            this._openPopup(n);
        } else {
            // Not selected → select it, then open popup
            this.state.selected[n] = true;
            const fn = `tooth_${n}`;
            if (this.props.record.fields[fn]) this.props.record.update({ [fn]: true });
            this._openPopup(n);
        }
    }

    _openPopup(n) {
        const def = this._getDefaultColor();
        const existing = this.state.shades[n] || {};
        this.state.popup = {
            n,
            incisal:  existing.incisal  || def,
            middle:   existing.middle   || def,
            cervical: existing.cervical || def,
        };
    }

    closePopup() { this.state.popup = null; }

    deselectTooth(n) {
        delete this.state.selected[n];
        delete this.state.shades[n];
        const fn = `tooth_${n}`;
        if (this.props.record.fields[fn]) this.props.record.update({ [fn]: false });
        this._saveShades();
        this.state.popup = null;
    }

    savePopup() {
        const p = this.state.popup;
        if (!p) return;
        this.state.shades[p.n] = { incisal: p.incisal, middle: p.middle, cervical: p.cervical };
        this._saveShades();
        this.state.popup = null;
    }

    setShade(part, val) {
        if (this.state.popup) this.state.popup[part] = val;
    }

    // Per-section color helpers for main chart (used with clipPath 3-section rendering)
    getIncisalColor(n) {
        const s = this.state.shades[n];
        const def = this._getDefaultColor();
        return shadeColor(s ? s.incisal || def : def);
    }
    getMiddleColor(n) {
        const s = this.state.shades[n];
        const def = this._getDefaultColor();
        return shadeColor(s ? s.middle || def : def);
    }
    getCervicalColor(n) {
        const s = this.state.shades[n];
        const def = this._getDefaultColor();
        return shadeColor(s ? s.cervical || def : def);
    }
    // true if tooth has 3 different shade sections
    hasMixedShades(n) {
        const s = this.state.shades[n];
        if (!s) return false;
        return s.incisal !== s.middle || s.middle !== s.cervical;
    }
    // Lower arch teeth (31-48) need reversed clip positions due to scale(-1,-1)
    isLowerTooth(n) { return n >= 31; }

    // Helpers for template
    getVitaShades() { return VITA_SHADES; }
    shadeColor(s) { return shadeColor(s); }
    toothName(n) { return toothName(n); }
    get selectedCount() { return Object.keys(this.state.selected).length; }
    getUpperLayout() { return buildLayout(UPPER_ORDER); }
    getLowerLayout() { return buildLayout(LOWER_ORDER); }
    getTotalWidth(layout) { const l = layout[layout.length-1]; return l.x + l.w + 4; }
    isSelected(n) { return !!this.state.selected[n]; }
    getCrownPath(tooth) { return CROWN_PATHS[tooth.idx]; }
    getRootPaths(tooth) { return ROOT_PATHS[tooth.idx]; }
    getRootHeight(tooth) { return ROOT_H[tooth.idx]; }
    getCrownH() { return CROWN_H; }
    getToothH(tooth) { return CROWN_H + 4 + this.getRootHeight(tooth); }
    getMaxH(layout) { return Math.max(...layout.map(t => this.getToothH(t))); }

    // Returns the fill color for a selected tooth (Vita color or default order color)
    getToothFillColor(n) {
        const s = this.state.shades[n];
        const defaultShade = this._getDefaultColor();
        if (!s) return shadeColor(defaultShade);
        // Use cervical shade as dominant (most visible in chart)
        const dominant = s.cervical || s.middle || s.incisal || defaultShade;
        return shadeColor(dominant);
    }

    // Slightly darken the fill color for roots/stroke (multiply hex by 0.75)
    getToothStrokeColor(n) {
        const fill = this.getToothFillColor(n);
        // Parse hex and darken ~25%
        try {
            const r = parseInt(fill.slice(1,3),16);
            const g = parseInt(fill.slice(3,5),16);
            const b = parseInt(fill.slice(5,7),16);
            const d = (c) => Math.round(c * 0.65).toString(16).padStart(2,'0');
            return `#${d(r)}${d(g)}${d(b)}`;
        } catch { return '#999'; }
    }

    // For selected teeth: show their dominant shade label on the diagram
    getToothShadeLabel(n) {
        const s = this.state.shades[n];
        if (!s) return this._getDefaultColor();
        if (s.incisal === s.middle && s.middle === s.cervical) return s.incisal;
        return '~'; // Mixed shades indicator
    }

    // For popup tooth SVG — builds 3-section colored tooth
    getPopupCrownPath() {
        if (!this.state.popup) return { path: '', w: 47, h: 56 };
        const idx = toothIndex(this.state.popup.n);
        return { path: CROWN_PATHS[idx], w: CROWN_W[idx], h: 56 };
    }
}

registry.category("fields").add("teeth_selector", {
    component: TeethSelectorWidget,
    displayName: "Teeth Selector",
    supportedTypes: ["boolean"],
});

// Export shared constants and utilities for teeth_display.js
export { CROWN_PATHS, ROOT_PATHS, CROWN_W, CROWN_H, ROOT_H, UPPER_ORDER, LOWER_ORDER, shadeColor, buildLayout, toothIndex };
