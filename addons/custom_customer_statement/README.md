# Custom Customer Statement Module for Odoo 18

## Overview
This module generates branded customer account statements (Estado de Cuenta) directly from the invoice list in Odoo 18 Community Edition. Users can select multiple invoices from a single customer and generate a PDF statement or send it via email.

**Module Name:** `custom_customer_statement`  
**Version:** 18.0.1.0.0  
**Category:** Invoicing  
**License:** LGPL-3  
**Depends on:** `account` (Community Invoicing)

---

## Features

### 1. Generate PDF Statements
- Select 1+ invoices from same customer → generates professional PDF
- Uses company branding: logo, colors (#2e4159 navy, #f4a259 gold), layout
- PDF automatically uses company's `web.external_layout` (same as invoices)
- Includes transaction history with running balance

### 2. Email Delivery
- Attach PDF to email and send directly to customer
- Pre-fills customer email, subject, and greeting
- Uses Odoo's standard mail composition wizard

### 3. Statement Content
| Section | Details |
|---------|---------|
| Header | Period date range, auto-generated today's date |
| Customer Info | Name, address, VAT/RNC, email, phone |
| Transactions Table | Date, Due Date, Document #, Description, Debit, Credit, Running Balance |
| Row Colors | Red = overdue, Grey = paid, Default = pending |
| Summary | Total Billed, Total Paid, Current Balance, Overdue Balance |
| Footer | Generation date & disclaimer |

### 4. Filtering Options
- Optional date range (Statement From / Statement To)
- Include/exclude payments
- Auto-detects customer from selected invoices

---

## Installation

### Prerequisites
- Odoo 18 Community Edition
- Docker container with Odoo 18 (for Amazing Prosthetics)
- Access to `/mnt/extra-addons` directory

### Steps
1. Module is located at: `/home/jay/.openclaw/workspace/projects/amazing-prosthetics/extra-addons/custom_customer_statement/`
2. In Odoo UI: **Settings** → **Technical** → **Modules** → **Update Modules List**
3. Search for **"Estado de Cuenta"**
4. Click **Install**

---

## Usage

### Generate & Print Statement
1. Go to **Invoicing** → **Invoices** (list view)
2. Select **2 or more invoices from the same customer** (checkbox column)
3. Click **Action** dropdown → **"Estado de Cuenta del Cliente"**
4. Wizard opens with:
   - Customer auto-detected
   - Selected invoices shown
   - Optional date range filters
5. Click **"Imprimir PDF"** to download statement

### Send by Email
1. Same steps as above, but click **"Enviar por Email"**
2. Email compose dialog opens with:
   - Customer email pre-filled
   - PDF attached
   - Subject & greeting pre-filled
3. Edit if needed, then click **Send**

### Date Range Filtering
- Leave **Statement From/To** blank → shows all invoices for customer
- Set dates → shows only invoices within date range

---

## Module Structure

```
custom_customer_statement/
├── __init__.py                                    # Module initialization
├── __manifest__.py                                # Module metadata
├── models/
│   ├── __init__.py
│   └── res_partner.py                             # get_statement_data() method
├── wizard/
│   ├── __init__.py
│   ├── customer_statement_wizard.py                # Wizard model & logic
│   └── customer_statement_wizard_views.xml         # Wizard form UI
├── reports/
│   └── customer_statement_report.xml               # PDF templates + ir.actions.report
├── views/
│   └── account_move_actions.xml                    # Server action for invoice list
├── security/
│   └── ir.model.access.csv                         # Access rights
└── README.md                                       # This file
```

---

## Key Files & Classes

### `models/res_partner.py`
**Method:** `get_statement_data(move_ids=None, date_from=None, date_to=None)`
- Queries invoices/credits for partner
- Calculates running balance per transaction
- Flags overdue items
- Returns dict with statement data (partner, transactions, totals)

### `wizard/customer_statement_wizard.py`
**Model:** `customer.statement.wizard` (TransientModel)

**Fields:**
- `partner_id` (Many2one, auto-detected from selected invoices)
- `move_ids` (Many2many, the selected invoices)
- `date_from`, `date_to` (Date, optional filters)
- `include_payments` (Boolean, default True)

**Methods:**
- `default_get()` - auto-populate from context (selected invoice IDs)
- `action_print_pdf()` - trigger PDF report generation
- `action_send_email()` - open email compose with PDF attached

### `reports/customer_statement_report.xml`
**Templates:**
- `report_customer_statement_document` - the actual statement content (calls `web.external_layout`)
- `report_customer_statement` - container template (iterates over documents)

**ir.actions.report:**
- `action_report_customer_statement`
- Model: `customer.statement.wizard`
- Report name: `custom_customer_statement.report_customer_statement`

### `views/account_move_actions.xml`
**Server Action:**
- `action_customer_statement_from_invoices`
- Binding: `account.move` list view
- Opens wizard with selected invoice IDs in context

---

## Access Control

| Group | Can Use |
|-------|---------|
| `account.group_account_invoice` | Billing User ✓ |
| `account.group_account_user` | Accountant ✓ |
| Other users | ✗ |

Defined in `security/ir.model.access.csv`

---

## Technical Details

### Branding & Layout
- Uses Odoo's standard `web.external_layout` for PDF wrapper
- Automatically pulls from `res.company`:
  - Logo (base64 image)
  - Company name, address, phone, email
  - Report header/footer (HTML fields)
  - Document layout theme (boxed, striped, bold, standard, etc.)
- Colors are set in inline CSS within report template

### Statement Calculation Logic
1. Fetch all posted out_invoices + out_refunds for partner (within date range if specified)
2. For each invoice:
   - Debit = invoice total (for invoices)
   - Credit = refund total (for credit notes)
   - Calculate running balance
   - Check if overdue: due_date < today AND residual > 0
3. Sum totals: total_debit, total_credit, final_balance, overdue_balance

### Email Integration
- Uses `mail.compose.message` wizard (standard Odoo)
- PDF attachment created inline (not stored permanently)
- Email template references: customer email, salesperson email, company email

---

## Odoo Instance Information

### Installation Context
- **Database:** `amazing` (Amazing Prosthetics)
- **Version:** Odoo 18 (18.0-20260217)
- **Edition:** Community
- **Modules Installed:** 72 total (includes custom_customer_statement)

### Related Modules
- `account` - Core invoicing (Community, no enterprise needed)
- `l10n_do_ecf_invoicing` - Dominican Republic e-CF integration
- `custom_manufacturing_dashboard` - Dental lab manufacturing dashboard

### Server URLs
- **Local:** http://localhost:8069
- **Tailscale:** http://100.87.41.106:8069
- **Database Host:** `db` (Docker), port 5432 (mapped to 5433 on host)
- **Database User:** `odoo`
- **Database Name:** `amazing`

---

## Docker Setup

### Container Information
- **Image:** `odoo:18`
- **Container Name:** `odoo18`
- **Status:** Running (2+ weeks uptime)
- **Port Mapping:** 8069→8069
- **Addons Paths:**
  - `/usr/lib/python3/dist-packages/odoo/addons` (core)
  - `/var/lib/odoo/.local/share/Odoo/addons/18.0` (user installed)
  - `/mnt/extra-addons` (custom modules) ← custom_customer_statement is here
- **Dev Mode:** `--dev=all` (auto-reload enabled)
- **Log Level:** DEBUG

### Database Container
- **Image:** `postgres:16`
- **Container Name:** `odoo18_db`
- **Port Mapping:** 5433→5432 (host:container)
- **Health:** Healthy
- **User:** `odoo`
- **Password:** `odoo`

### Directory Mounting
```bash
/home/jay/.openclaw/workspace/projects/amazing-prosthetics/extra-addons
    ↓
/mnt/extra-addons (in container)
```

This is where Odoo loads custom modules like custom_customer_statement.

### Common Docker Commands

```bash
# Check container status
docker ps | grep odoo

# View Odoo logs (last 50 lines)
docker logs odoo18 | tail -50

# Restart Odoo
docker restart odoo18

# Execute command in container
docker exec odoo18 <command>

# Check database
docker exec odoo18_db psql -U odoo amazing -c "SELECT name, state FROM ir_module_module WHERE name='custom_customer_statement';"

# View container config
docker inspect odoo18
```

---

## Testing Checklist

- [ ] Module installed in Odoo
- [ ] Select 2+ invoices from same customer
- [ ] Action menu shows "Estado de Cuenta del Cliente"
- [ ] Wizard opens with correct customer
- [ ] Date range filtering works
- [ ] "Imprimir PDF" downloads statement with:
  - [ ] Company logo visible
  - [ ] Correct customer info
  - [ ] All transactions listed with running balance
  - [ ] Summary section with totals
  - [ ] Correct color coding (red = overdue)
- [ ] "Enviar por Email" opens compose with:
  - [ ] PDF attached
  - [ ] Customer email pre-filled
  - [ ] Subject pre-filled
  - [ ] Can send successfully

---

## Troubleshooting

### Module Not Showing in Apps
**Symptom:** Search "Estado de Cuenta" returns nothing
**Solution:**
1. Go to **Settings** → **Technical** → **Modules** → **Update Modules List**
2. Wait 30 seconds
3. Refresh browser
4. Search again

**If still missing:**
```bash
docker restart odoo18
# Wait 10 seconds
# Try again in UI
```

### "Action Not Found" When Clicking Action Menu
**Symptom:** No "Estado de Cuenta" option appears
**Solution:**
1. Module may not be installed (see above)
2. Check user permissions:
   - User must be in `account.group_account_invoice` or `account.group_account_user`
   - Go to user form → Groups tab
3. Clear browser cache: Ctrl+Shift+Delete

### PDF Shows Wrong Customer Info
**Symptom:** Statement shows different company branding
**Solution:**
- Check `Settings` → **Companies** → select company
- Verify logo, name, address, external_report_layout_id
- Document Layout can be changed at **Settings** → **Companies** → **Document Layout**

### Email Not Sending
**Symptom:** Error when clicking "Enviar por Email"
**Solution:**
1. Check outgoing mail server: **Settings** → **Technical** → **Email Servers**
2. Verify customer email is not empty: check `res.partner.email`
3. Check Odoo logs: `docker logs odoo18 | grep -i mail`

### Overdue Balance Showing 0
**Symptom:** Statement shows no overdue amount even with past-due invoices
**Solution:**
- Logic: overdue = invoice due_date < today AND residual > 0 (partially unpaid)
- Fully paid invoices don't count as overdue
- Check `account.move.amount_residual` in invoice form

---

## Future Enhancements

Possible improvements:
- [ ] Custom statement logo/footer per customer
- [ ] Scheduled statement generation (monthly, weekly)
- [ ] Statement template selection (detailed vs. summary)
- [ ] Multi-currency support
- [ ] Payment terms display on statement
- [ ] Aged balance report (30/60/90+ days)
- [ ] Portal access for customer to view statements

---

## Support & Contact

**Module Location:** `/home/jay/.openclaw/workspace/projects/amazing-prosthetics/extra-addons/custom_customer_statement/`

**Odoo Instance:** http://100.87.41.106:8069 (Tailscale)

**Database:** `amazing` on `odoo18_db` container

**Questions/Issues:** Check Odoo logs or Django debug mode for detailed errors.

---

**Last Updated:** 2026-05-06  
**Module Version:** 18.0.1.0.0  
**Odoo Version:** 18.0-20260217
