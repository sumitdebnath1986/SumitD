# 🤖 Agentic AI Procurement Bot

## Overview

An end-to-end **Agentic AI Procurement Bot** built with Streamlit, designed to automate procurement workflows for enterprise users. The bot guides users through a multi-step conversational interface to collect material requirements (BOMs), query supplier catalogs, and create shopping carts that redirect to your core system checkout.

## Features

✅ **Multi-Step Workflow** — Login → Company Confirmation → Cart Management → BOM Input → Supplier Matching → Checkout  
✅ **Persistent Carts** — Save carts with automatic 14-day expiry  
✅ **BOM Parsing** — Support text and CSV input formats  
✅ **Supplier Matching** — Automatically match requirements to vendors based on stock and pricing  
✅ **Cart Management** — Create, save, and load carts across sessions  
✅ **User Context** — Role-based entity authorization  
✅ **Core System Integration** — Direct redirect to your checkout page  

## Architecture

### Database Schema (SQLite)

- **supplier_catalog** — Available suppliers, MPNs, pricing, lead times
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
9. **Checkout** — Display cart summary and redirect to core system

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/sumitdebnath1986/SumitD.git
cd SumitD

# Install dependencies
pip install -r requirements.txt
```

## Running the App

```bash
streamlit run agentic_bot_complete.py
```

The app will open at `http://localhost:8501`

## Demo Credentials

Test with these accounts:

| Email | Name | Company | Entities |
|-------|------|---------|----------|
| `alice@google.com` | Alice Chen | Google, Inc. | Data Center Operations, Cloud Infrastructure |
| `bob@google.com` | Bob Miller | Google, Inc. | Global Logistics |

## Mock Supplier Catalog

| MPN | Supplier | Description | Stock | Lead Time | Price |
|-----|----------|-------------|-------|-----------|-------|
| MPN1001 | Vendor A | Server CPU | 120 | 5 days | $10.50 |
| MPN1001 | Vendor B | Server CPU | 80 | 3 days | $11.00 |
| MPN1002 | Vendor B | Memory Module | 200 | 2 days | $21.50 |
| MPN1002 | Vendor C | Memory Module | 50 | 4 days | $23.00 |
| MPN1003 | Vendor D | SSD Drive | 150 | 6 days | $30.00 |
| MPN1004 | Vendor A | Power Supply | 75 | 5 days | $14.50 |

## Example Usage

### Step 1: Login
```
Email: alice@google.com
→ Bot confirms company and entities
```

### Step 2: Create New Cart
```
Choose "Create new active cart"
→ Enter material requirements
```

### Step 3: Input BOM

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

### Step 4: Review & Approve
```
Bot shows supplier matches with pricing
→ Approve cart
→ Name cart (e.g., PROJ-001)
```

### Step 5: Checkout
```
View cart summary
→ Redirect to core system checkout
```

## Database Queries

### View Saved Carts
```bash
sqlite3 procurement_demo.db "SELECT * FROM saved_carts;"
```

### View Supplier Catalog
```bash
sqlite3 procurement_demo.db "SELECT * FROM supplier_catalog;"
```

## Configuration

### Core System Checkout URL
Update the checkout redirect URL in the code:

```python
core_system_url = "https://your-core-system.com/checkout"
```

### Cart Expiry Period
Modify the expiry duration (default: 14 days):

```python
expiry = (datetime.now() + timedelta(days=14)).isoformat()
```

## Future Enhancements

- 🤖 Claude AI integration for intelligent supplier recommendations
- 📊 Real-time inventory sync with ERP systems
- 🔐 SAML/SSO authentication
- 💳 Cost allocation and budget tracking
- 📧 Email notifications for cart status
- 🌍 Multi-currency support
- 📈 Advanced analytics and reporting
- 🛒 Order history and reordering

## Troubleshooting

### Bot doesn't recognize email
- Ensure you're using a demo email (alice@google.com or bob@google.com)
- Check spelling and case sensitivity

### CSV upload fails
- Verify CSV has exactly 2 columns: "MPN" and "Quantity" (case-sensitive)
- Ensure no extra spaces or empty rows

### Cart not saving
- Check that cart name is unique for your user
- Verify database file exists (procurement_demo.db)

### Checkout redirect not working
- Update `core_system_url` variable to your actual checkout page
- Verify URL is accessible and properly formatted

## Support

For issues or feature requests, please open a GitHub issue in the repository.

## License

MIT License — See LICENSE file for details

## Architecture Diagram

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────┐
│     Streamlit UI (Main App)              │
│  - Login / Company Confirmation          │
│  - Cart Management                       │
│  - BOM Input (Text/CSV)                  │
│  - Supplier Matching                     │
│  - Checkout Redirect                     │
└──────────────┬───────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
┌─────────────────┐  ┌──────────────────┐
│  SQLite DB      │  │  Core System     │
│ - Catalogs      │  │  Checkout Page   │
│ - Saved Carts   │  │                  │
└─────────────────┘  └──────────────────┘
```

## Quick Start (5 minutes)

1. **Install**: `pip install -r requirements.txt`
2. **Run**: `streamlit run agentic_bot_complete.py`
3. **Login**: Use `alice@google.com`
4. **Create Cart**: Enter `MPN1001 100` and `MPN1002 50`
5. **Approve & Save**: Name it `TEST-001`
6. **Checkout**: See cart summary and redirect link

---

**Made with ❤️ for procurement automation**