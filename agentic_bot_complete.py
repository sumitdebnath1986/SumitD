# agentic_bot_complete.py
# End-to-end Agentic AI Procurement Bot with Claude + Streamlit

import streamlit as st
import pandas as pd
import sqlite3
import re
import random
from datetime import datetime, timedelta
from anthropic import Anthropic
import os

# ------------------------------
# 1. DATABASE SETUP (SQLite)
# ------------------------------
DB_PATH = "procurement_demo.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Supplier catalog
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supplier_catalog (
            id INTEGER PRIMARY KEY,
            mpn TEXT,
            supplier TEXT,
            material_desc TEXT,
            available_qty INTEGER,
            lead_time_days INTEGER,
            unit_price REAL,
            shipping_countries TEXT
        )
    ''')

    # Master Blanket PO #123456
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS master_po (
            id INTEGER PRIMARY KEY,
            po_number TEXT,
            mpn TEXT,
            total_qty INTEGER,
            remaining_qty INTEGER,
            status TEXT
        )
    ''')

    # Branch POs (child POs)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS branch_po (
            id INTEGER PRIMARY KEY,
            branch_po_number TEXT,
            master_po_number TEXT,
            mpn TEXT,
            ordered_qty INTEGER,
            created_at TEXT,
            cart_name TEXT
        )
    ''')

    # Audit trail: branch PO entries under master PO
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS master_po_audit (
            id INTEGER PRIMARY KEY,
            master_po_number TEXT,
            branch_po_number TEXT,
            mpn TEXT,
            qty INTEGER,
            created_at TEXT
        )
    ''')

    # Saved carts (persistent across sessions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_carts (
            id INTEGER PRIMARY KEY,
            user_email TEXT,
            cart_name TEXT,
            cart_data TEXT,   -- JSON string
            created_at TEXT,
            expiry_date TEXT
        )
    ''')

    # Insert mock supplier catalog if empty
    cursor.execute("SELECT COUNT(*) FROM supplier_catalog")
    if cursor.fetchone()[0] == 0:
        mock_suppliers = [
            ("MPN1001", "Vendor A", "Server CPU", 120, 5, 10.50, "USA,EU"),
            ("MPN1001", "Vendor B", "Server CPU", 80, 3, 11.00, "USA,EU,APAC"),
            ("MPN1002", "Vendor B", "Memory Module", 200, 2, 21.50, "USA,EU"),
            ("MPN1002", "Vendor C", "Memory Module", 50, 4, 23.00, "EU"),
            ("MPN1003", "Vendor D", "SSD Drive", 150, 6, 30.00, "USA,EU,APAC"),
            ("MPN1004", "Vendor A", "Power Supply", 75, 5, 14.50, "USA"),
        ]
        cursor.executemany('''
            INSERT INTO supplier_catalog (mpn, supplier, material_desc, available_qty, lead_time_days, unit_price, shipping_countries)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', mock_suppliers)

    # Insert master PO #123456 if empty
    cursor.execute("SELECT COUNT(*) FROM master_po")
    if cursor.fetchone()[0] == 0:
        master_items = [
            ("123456", "MPN1001", 500, 500, "Open"),
            ("123456", "MPN1002", 300, 300, "Open"),
            ("123456", "MPN1003", 200, 200, "Open"),
            ("123456", "MPN1004", 100, 100, "Open"),
        ]
        cursor.executemany('''
            INSERT INTO master_po (po_number, mpn, total_qty, remaining_qty, status)
            VALUES (?, ?, ?, ?, ?)
        ''', master_items)

    conn.commit()
    conn.close()

init_db()

# ------------------------------
# 2. MOCK USER CONTEXT
# ------------------------------
def get_user_context(email):
    """Return user details from mock database."""
    users = {
        "alice@google.com": {"name": "Alice Chen", "company": "Google, Inc.", "entities": ["Data Center Operations", "Cloud Infrastructure"]},
        "bob@google.com": {"name": "Bob Miller", "company": "Google, Inc.", "entities": ["Global Logistics"]},
    }
    return users.get(email)

def get_saved_carts_for_user(email):
    """Retrieve saved carts from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT cart_name, expiry_date FROM saved_carts WHERE user_email = ?", (email,))
    rows = cursor.fetchall()
    conn.close()
    return [{"name": row[0], "expiry": row[1]} for row in rows]

def load_saved_cart_by_name(email, cart_name):
    """Load cart data (JSON) from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT cart_data, expiry_date FROM saved_carts WHERE user_email = ? AND cart_name = ?", (email, cart_name))
    row = cursor.fetchone()
    conn.close()
    if row:
        expiry = datetime.fromisoformat(row[1])
        if datetime.now() > expiry:
            return None, "Cart expired"
        import json
        return json.loads(row[0]), "Loaded"
    return None, "Not found"

def save_cart_to_db(email, cart_name, cart_data):
    """Persist a saved cart with 14-day expiry."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    expiry = (datetime.now() + timedelta(days=14)).isoformat()
    import json
    cursor.execute('''
        INSERT OR REPLACE INTO saved_carts (user_email, cart_name, cart_data, created_at, expiry_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (email, cart_name, json.dumps(cart_data), datetime.now().isoformat(), expiry))
    conn.commit()
    conn.close()

# ------------------------------
# 3. INTERNAL API FUNCTIONS
# ------------------------------
def query_supplier_catalog(mpn_list):
    """Return DataFrame with supplier info for given MPNs."""
    conn = sqlite3.connect(DB_PATH)
    placeholders = ','.join(['?'] * len(mpn_list))
    query = f"SELECT * FROM supplier_catalog WHERE mpn IN ({placeholders})"
    df = pd.read_sql_query(query, conn, params=mpn_list)
    conn.close()
    return df

def get_master_po_remaining(mpn):
    """Get remaining quantity in master PO for a given MPN."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT remaining_qty FROM master_po WHERE po_number = '123456' AND mpn = ?", (mpn,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def generate_branch_po(master_po, mpn, ordered_qty, cart_name):
    """Create branch PO, deduct quantity, log audit. Returns branch PO number."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get next branch PO number (e.g., 123456.1)
    cursor.execute("SELECT MAX(branch_po_number) FROM branch_po WHERE master_po_number = ?", (master_po,))
    max_branch = cursor.fetchone()[0]
    if max_branch:
        match = re.search(r'\.(\d+)$', max_branch)
        next_num = int(match.group(1)) + 1 if match else 1
    else:
        next_num = 1
    branch_po_number = f"{master_po}.{next_num}"

    # Insert branch PO record
    cursor.execute('''
        INSERT INTO branch_po (branch_po_number, master_po_number, mpn, ordered_qty, created_at, cart_name)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (branch_po_number, master_po, mpn, ordered_qty, datetime.now().isoformat(), cart_name))

    # Deduct from master PO
    cursor.execute('''
        UPDATE master_po
        SET remaining_qty = remaining_qty - ?
        WHERE po_number = ? AND mpn = ?
    ''', (ordered_qty, master_po, mpn))

    # Update status if zero
    cursor.execute('''
        UPDATE master_po SET status = 'Fulfilled'
        WHERE po_number = ? AND mpn = ? AND remaining_qty = 0
    ''', (master_po, mpn))

    # Audit trail
    cursor.execute('''
        INSERT INTO master_po_audit (master_po_number, branch_po_number, mpn, qty, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (master_po, branch_po_number, mpn, ordered_qty, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    return branch_po_number

# ------------------------------
# 4. BOM PARSING (no AI)
# ------------------------------
def parse_bom_from_text(text):
    """Extract MPN and quantity from plain text lines."""
    items = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        # CSV format: MPN, Qty
        if ',' in line:
            parts = line.split(',')
            if len(parts) == 2:
                mpn = parts[0].strip().upper()
                try:
                    qty = int(parts[1].strip())
                    items.append({"mpn": mpn, "qty": qty})
                except:
                    pass
        else:
            # Space-separated: MPN Qty
            parts = line.split()
            if len(parts) == 2:
                mpn = parts[0].strip().upper()
                try:
                    qty = int(parts[1].strip())
                    items.append({"mpn": mpn, "qty": qty})
                except:
                    pass
    return items

def parse_bom_from_csv(file):
    """Read uploaded CSV file with columns MPN, Quantity."""
    df = pd.read_csv(file)
    items = []
    for _, row in df.iterrows():
        mpn = str(row.iloc[0]).strip().upper()
        qty = int(row.iloc[1])
        items.append({"mpn": mpn, "qty": qty})
    return items

# ------------------------------
# 5. VENDOR PRESENTATION (no split, full availability)
# ------------------------------
def get_supplier_for_items(items):
    """For each MPN, find a supplier with sufficient stock. Return list of results."""
    results = []
    for item in items:
        mpn = item["mpn"]
        qty_needed = item["qty"]
        df = query_supplier_catalog([mpn])
        if df.empty:
            results.append({"mpn": mpn, "error": "No supplier found for this MPN"})
            continue
        # Filter by available_qty >= needed and in stock
        available = df[df["available_qty"] >= qty_needed]
        if available.empty:
            # Try partial? For demo we fail; could implement split but client said no splitting.
            results.append({"mpn": mpn, "error": f"Insufficient stock: max {df['available_qty'].max()} units available"})
            continue
        # Pick first (lowest price) for simplicity
        best = available.iloc[0]
        results.append({
            "mpn": mpn,
            "supplier": best["supplier"],
            "material_desc": best["material_desc"],
            "qty": qty_needed,
            "unit_price": best["unit_price"],
            "lead_time": best["lead_time_days"],
            "total_price": qty_needed * best["unit_price"]
        })
    return results

# ------------------------------
# 6. STREAMLIT UI (main app)
# ------------------------------
st.set_page_config(page_title="Agentic Procurement Bot", layout="wide")
st.title("🤖 Agentic AI Procurement Assistant")

# Session state initialization
if "step" not in st.session_state:
    st.session_state.step = "login"
if "user" not in st.session_state:
    st.session_state.user = None
if "saved_carts_list" not in st.session_state:
    st.session_state.saved_carts_list = []
if "active_cart" not in st.session_state:
    st.session_state.active_cart = None
if "current_bom_items" not in st.session_state:
    st.session_state.current_bom_items = []
if "vendor_results" not in st.session_state:
    st.session_state.vendor_results = []
if "cart_name" not in st.session_state:
    st.session_state.cart_name = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# Helper to add bot message
def bot_message(content):
    st.session_state.chat_messages.append({"role": "assistant", "content": content})

def user_message(content):
    st.session_state.chat_messages.append({"role": "user", "content": content})

# Display chat history
for msg in st.session_state.chat_messages:
    if msg["role"] == "user":
        st.markdown(f"**You:** {msg['content']}")
    else:
        st.info(f"🤖 **Bot:** {msg['content']}")

# ------------------------------
# STEP 1: LOGIN
# ------------------------------
if st.session_state.step == "login":
    st.subheader("Login")
    email = st.text_input("Email (demo: alice@google.com or bob@google.com)")
    if st.button("Login"):
        user = get_user_context(email)
        if user:
            st.session_state.user = user
            # Fetch saved carts
            saved = get_saved_carts_for_user(email)
            st.session_state.saved_carts_list = saved
            welcome = f"Hello **{user['name']}**! Welcome back. You are from **{user['company']}**, authorised for: {', '.join(user['entities'])}. Is that correct?"
            bot_message(welcome)
            st.session_state.step = "confirm_company"
            st.rerun()
        else:
            st.error("User not found. A ticket has been raised for onboarding.")
            bot_message("I couldn't find your account. A support ticket has been created. Please try again later.")
            st.stop()

# ------------------------------
# STEP 2: CONFIRM COMPANY
# ------------------------------
elif st.session_state.step == "confirm_company":
    # Show a Yes/No button
    col1, col2 = st.columns(2)
    if col1.button("Yes"):
        user = st.session_state.user
        saved_count = len(st.session_state.saved_carts_list)
        if saved_count > 0:
            msg = f"Great! You have {saved_count} saved cart(s) in your profile. Would you like to pick from a saved cart or create a new active cart?"
            bot_message(msg)
            st.session_state.step = "choose_saved_or_new"
        else:
            msg = "You have no saved carts. Let's create a new cart. Please provide your material requirements: you can type MPN and quantity (e.g., 'MPN1001 50') or upload a CSV file."
            bot_message(msg)
            st.session_state.step = "bom_input"
        st.rerun()
    if col2.button("No"):
        bot_message("Please select your company from the list or contact support.")
        # For demo simplicity, we go back to login
        st.session_state.step = "login"
        st.rerun()

# ------------------------------
# STEP 3: CHOOSE SAVED CART OR NEW
# ------------------------------
elif st.session_state.step == "choose_saved_or_new":
    col1, col2 = st.columns(2)
    if col1.button("📁 Pick from saved carts"):
        if st.session_state.saved_carts_list:
            cart_names = [c["name"] for c in st.session_state.saved_carts_list]
            selected = st.selectbox("Select a saved cart", cart_names)
            if st.button("Load this cart"):
                cart_data, msg = load_saved_cart_by_name(st.session_state.user["email"], selected)
                if cart_data:
                    st.session_state.active_cart = cart_data
                    bot_message(f"Loaded cart '{selected}'. You can now continue shopping or proceed to checkout.")
                    st.session_state.step = "post_cart_load"
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.warning("No saved carts found. Creating a new cart.")
            st.session_state.step = "bom_input"
            st.rerun()
    if col2.button("🆕 Create new active cart"):
        bot_message("Let's create a new cart. Please provide your material requirements: you can type MPN and quantity or upload a CSV file.")
        st.session_state.step = "bom_input"
        st.rerun()

# ------------------------------
# STEP 4: BOM INPUT
# ------------------------------
elif st.session_state.step == "bom_input":
    st.subheader("Enter your requirements")
    input_type = st.radio("Choose input method:", ["Type text", "Upload CSV"])
    bom_data = None
    if input_type == "Type text":
        text_input = st.text_area("Enter one MPN and quantity per line (e.g., MPN1001 50 or MPN1001,50)")
        if st.button("Submit text"):
            items = parse_bom_from_text(text_input)
            if items:
                st.session_state.current_bom_items = items
                # Show confirmation
                confirm_msg = "I found these items:\n"
                for it in items:
                    confirm_msg += f"- {it['mpn']}: {it['qty']} units\n"
                confirm_msg += "Is that correct? (Yes/No)"
                bot_message(confirm_msg)
                st.session_state.step = "confirm_bom"
                st.rerun()
            else:
                st.error("Could not parse. Use format like 'MPN1001 50' per line.")
    else:
        uploaded = st.file_uploader("Upload CSV with columns: MPN, Quantity", type=["csv"])
        if uploaded and st.button("Upload"):
            items = parse_bom_from_csv(uploaded)
            if items:
                st.session_state.current_bom_items = items
                confirm_msg = "I found these items:\n"
                for it in items:
                    confirm_msg += f"- {it['mpn']}: {it['qty']} units\n"
                confirm_msg += "Is that correct? (Yes/No)"
                bot_message(confirm_msg)
                st.session_state.step = "confirm_bom"
                st.rerun()
            else:
                st.error("Invalid CSV. Ensure columns: MPN, Quantity")

# ------------------------------
# STEP 5: CONFIRM BOM
# ------------------------------
elif st.session_state.step == "confirm_bom":
    col1, col2 = st.columns(2)
    if col1.button("Yes"):
        # Query supplier catalog
        items = st.session_state.current_bom_items
        results = get_supplier_for_items(items)
        st.session_state.vendor_results = results
        # Build presentation message
        msg = "Searching supplier catalogue...\n\n"
        for r in results:
            if "error" in r:
                msg += f"❌ {r['mpn']}: {r['error']}\n"
            else:
                msg += f"✅ **{r['mpn']}** – {r['material_desc']}\n   Vendor: {r['supplier']} | Qty: {r['qty']} | Price: ${r['unit_price']} each | Lead time: {r['lead_time']} days\n"
        msg += "\nPlease review and approve the cart. Do you approve? (Yes/No)"
        bot_message(msg)
        st.session_state.step = "approve_cart"
        st.rerun()
    if col2.button("No"):
        bot_message("Let's try again. Please provide the correct material list.")
        st.session_state.step = "bom_input"
        st.rerun()

# ------------------------------
# STEP 6: APPROVE CART
# ------------------------------
elif st.session_state.step == "approve_cart":
    col1, col2 = st.columns(2)
    if col1.button("Yes, approve"):
        # Create active cart in session
        st.session_state.active_cart = {
            "items": st.session_state.vendor_results,
            "created_at": datetime.now().isoformat(),
            "approved": True
        }
        bot_message("Cart approved. Please provide a unique name for this cart. Use format: ProjectCode + CartSerial (e.g., SGQ3-001)")
        st.session_state.step = "save_cart_name"
        st.rerun()
    if col2.button("No, reject"):
        bot_message("Cart rejected. You can start over with new BOM.")
        st.session_state.step = "bom_input"
        st.rerun()

# ------------------------------
# STEP 7: SAVE CART WITH NAME
# ------------------------------
elif st.session_state.step == "save_cart_name":
    cart_name = st.text_input("Cart name (unique, e.g., PROJ-001)")
    if st.button("Save cart"):
        if cart_name:
            # Check duplicate for this user
            existing = [c["name"] for c in st.session_state.saved_carts_list]
            if cart_name in existing:
                st.error("Name already exists. Please choose another.")
            else:
                # Persist to DB
                email = st.session_state.user["email"]
                save_cart_to_db(email, cart_name, st.session_state.active_cart)
                # Update saved carts list
                st.session_state.saved_carts_list.append({"name": cart_name, "expiry": (datetime.now() + timedelta(days=14)).isoformat()})
                bot_message(f"Cart saved as '{cart_name}'. It will expire in 14 days. Would you like to continue shopping or move to checkout?")
                st.session_state.step = "continue_or_checkout"
                st.rerun()
        else:
            st.warning("Please enter a name.")

# ------------------------------
# STEP 8: CONTINUE SHOPPING OR CHECKOUT
# ------------------------------
elif st.session_state.step == "continue_or_checkout":
    col1, col2 = st.columns(2)
    if col1.button("🛒 Continue shopping"):
        bot_message("Great! Let's add more items. Please provide additional material requirements.")
        st.session_state.step = "bom_input"
        st.rerun()
    if col2.button("✅ Proceed to checkout"):
        # Generate branch POs for each item in active cart
        master_po = "123456"
        branch_pos = []
        cart_items = st.session_state.active_cart["items"]
        cart_name = None  # we haven't stored cart_name in active_cart; retrieve from last saved name?
        # For demo, we use a default name
        for item in cart_items:
            if "error" in item:
                continue
            mpn = item["mpn"]
            qty = item["qty"]
            branch_po = generate_branch_po(master_po, mpn, qty, "DemoCart")
            branch_pos.append(branch_po)
        if branch_pos:
            st.success(f"Branch POs created: {', '.join(branch_pos)}")
            bot_message(f"Branch POs generated. Redirecting you to the core system checkout page...")
        else:
            bot_message("No valid items to checkout.")
        # Redirect to mock core system page and end conversation
        st.session_state.step = "redirect_checkout"
        st.rerun()

# ------------------------------
# STEP 9: REDIRECT TO CORE SYSTEM & END CHAT
# ------------------------------
elif st.session_state.step == "redirect_checkout":
    st.markdown("### 🏢 Core System Checkout Page")
    st.info("This is a mock of the core system's checkout page. Your cart has been passed successfully.")
    # Display branch PO summary
    conn = sqlite3.connect(DB_PATH)
    branch_df = pd.read_sql_query("SELECT * FROM branch_po ORDER BY id DESC LIMIT 5", conn)
    conn.close()
    st.dataframe(branch_df)
    st.success("Order placed! The chat bot has ended this session.")
    st.caption("In production, you would be redirected to the real core system. Click below to start a new session.")
    if st.button("Start new session"):
        # Clear session state except database
        for key in list(st.session_state.keys()):
            if key != "step":
                del st.session_state[key]
        st.session_state.step = "login"
        st.rerun()
    # Bot does not respond further