# 🤖 Agentic AI Procurement Bot

## Overview

An end-to-end **Agentic AI Procurement Bot** built with Streamlit and Claude, designed to automate procurement workflows for enterprise users. The bot guides users through a multi-step conversational interface to collect material requirements (BOMs), query supplier catalogs, and generate purchase orders.

## Features

✅ **Multi-Step Workflow** — Login → Company Confirmation → Cart Management → BOM Input → Supplier Matching → Checkout  
✅ **Persistent Carts** — Save carts with automatic 14-day expiry  
✅ **BOM Parsing** — Support text and CSV input formats  
✅ **Supplier Matching** — Automatically match requirements to vendors based on stock and pricing  
✅ **Purchase Order Management** — Generate branch POs from master blanket PO (#123456)  
✅ **Audit Trail** — Complete logging of all procurement activities  
✅ **User Context** — Role-based entity authorization  

## Architecture

### Database Schema (SQLite)

- **supplier_catalog** — Available suppliers, MPNs, pricing, lead times
- **master_po** — Master blanket PO (123456) with remaining quantities
- **branch_po** — Child POs generated from master blanket
- **master_po_audit** — Audit trail of all PO activities
- **saved_carts** — User cart persistence with 14-day TTL

### Workflow Steps

1. **Login** — Authenticate user with email
2. **Company Confirmation** — Verify user's organization and authorized entities
3. **Cart Selection** — Load saved cart or create new
4. **BOM Input** — Upload material requirements (text or CSV)
5. **BOM Confirmation** — Parse and validate items
6. **Supplier Search** — Find best vendor matches
7. **Cart Approval** — Review and approve vendor selections
8. **Cart Naming** — Save cart with unique identifier
9. **Checkout** — Generate branch POs and redirect to core system

## Installation

```bash
pip install -r requirements.txt
```

## Running the App

```bash
streamlit run agentic_bot_complete.py
```

## Demo Credentials

Test with these accounts:

- **Alice Chen** (alice@google.com) — Data Center Operations, Cloud Infrastructure
- **Bob Miller** (bob@google.com) — Global Logistics

## Mock Supplier Catalog

| MPN | Supplier | Description | Stock | Lead Time | Price |
|-----|----------|-------------|-------|-----------|-------|
| MPN1001 | Vendor A/B | Server CPU | 120 / 80 | 5 / 3 days | $10.50 / $11.00 |
| MPN1002 | Vendor B/C | Memory Module | 200 / 50 | 2 / 4 days | $21.50 / $23.00 |
| MPN1003 | Vendor D | SSD Drive | 150 | 6 days | $30.00 |
| MPN1004 | Vendor A | Power Supply | 75 | 5 days | $14.50 |

## Example BOM Input

**Text Format:**
```
MPN1001 100
MPN1002 50
MPN1003 30
```

**CSV Format:**
```
MPN,Quantity
MPN1001,100
MPN1002,50
MPN1003,30
```

## Database Queries

### View All Branch POs
```sql
SELECT * FROM branch_po ORDER BY created_at DESC;
```

### View Master PO Status
```sql
SELECT mpn, total_qty, remaining_qty, status FROM master_po WHERE po_number = '123456';
```

### View Audit Trail
```sql
SELECT * FROM master_po_audit ORDER BY created_at DESC;
```

## Future Enhancements

- 🔧 Claude AI integration for intelligent supplier recommendation
- 📊 Real-time inventory sync with ERP systems
- 🔐 SAML/SSO authentication
- 💳 Cost allocation and budget tracking
- 📧 Email notifications for PO status
- 🌍 Multi-currency support
- 📈 Advanced analytics and reporting

## License

MIT License — See LICENSE file for details

## Support

For issues or feature requests, please open a GitHub issue.
