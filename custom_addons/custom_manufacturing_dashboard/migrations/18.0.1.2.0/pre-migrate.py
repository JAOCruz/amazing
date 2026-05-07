"""
Pre-migration 1.2.0: ensure tooth_shades exists on create_order_wizard.
Re-adds the column that was removed when fixing a previous migration issue.
This allows the shade popup in the wizard to save per-tooth colors.
"""


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE create_order_wizard
        ADD COLUMN IF NOT EXISTS tooth_shades TEXT DEFAULT '{}';
    """)
    # Also ensure mrp_production has it (idempotent safety net)
    cr.execute("""
        ALTER TABLE mrp_production
        ADD COLUMN IF NOT EXISTS tooth_shades TEXT DEFAULT '{}';
    """)
