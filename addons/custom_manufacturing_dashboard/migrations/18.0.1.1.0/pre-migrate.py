"""
Pre-migration: ensure tooth_shades column exists on mrp_production.
Runs BEFORE _auto_init(), so the column is guaranteed to exist when
Odoo validates field mappings. This avoids UndefinedColumn errors.
"""


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE mrp_production
        ADD COLUMN IF NOT EXISTS tooth_shades TEXT DEFAULT '{}';
    """)
