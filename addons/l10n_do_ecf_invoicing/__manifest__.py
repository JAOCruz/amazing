{
    "name": "Dominican Republic - Electronic Fiscal Invoicing (e-CF)",
    "summary": "Generate, sign, and send e-CF XML documents to DGII",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations",
    "author": "Arcova",
    "website": "https://github.com/JAOCruz/l10n-do-ecf-odoo18",
    "license": "LGPL-3",
    "depends": [
        "account",
        "l10n_latam_invoice_document",
        "l10n_do",
    ],
    "external_dependencies": {
        "python": [
            "lxml",
            "cryptography",
            "requests",
            "qrcode",
        ],
    },
    "data": [
        "data/l10n_do_document_types.xml",
        "data/ecf_sequences.xml",
        "data/cron_jobs.xml",
        "views/res_config_settings_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
