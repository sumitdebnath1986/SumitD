# agentic_bot_complete.py
# End-to-end Agentic AI Procurement Bot with Claude + Streamlit

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import json

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

    conn.commit()
    conn.close()

init_db()

# ------------------------------
# 2. MOCK USER CONTEXT
# ------------------------------
def get_user_context(email):
    """Return user details from mock database. Case-insensitive email lookup."""
    users = {
        "alice@google.com": {"name": "Alice Chen", "company": "Google, Inc.", "entities": ["Data Center Operations", "Cloud Infrastructure"]},
        "bob@google.com": {"name": "Bob Miller", "company": "Google, Inc.", "entities": ["Global Logistics"]},
    }
    # Convert input email to lowercase for case-insensitive lookup
    email_lower = email.lower().strip()
    user_data = users.get(email_lower)
    if user_data:
        # Add email to user data
        user_data["email"] = email_lower
    return user_data

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
        return json.loads(row[0]), "Loaded"
    return None, "Not found"

def save_cart_to_db(email, cart_name, cart_data):
    """Persist a saved cart with 14-day expiry. Convert Pandas objects to native Python types."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    expiry = (datetime.now() + timedelta(days=14)).isoformat()
    
    # Convert cart data to JSON-serializable format (handle Pandas Series)
    clean_items = []
    for item in cart_data.get("items", []):
        if "error" not in item:
            clean_items.append({
                "mpn": str(item.get("mpn", "")),
                "supplier": str(item.get("supplier", "")),
                "material_desc": str(item.get("material_desc", "")),
                "qty": int(item.get("qty", 0)),
                "unit_price": float(item.get("unit_price", 0)),
                "lead_time": int(item.get("lead_time", 0)),
                "total_price": float(item.get("total_price", 0))
            })
    
    clean_cart_data = {
        "items": clean_items,
        "created_at": cart_data.get("created_at", datetime.now().isoformat()),
        "approved": cart_data.get("approved", True)
    }
    
    cursor.execute('''
        INSERT OR REPLACE INTO saved_carts (user_email, cart_name, cart_data, created_at, expiry_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (email, cart_name, json.dumps(clean_cart_data), datetime.now().isoformat(), expiry))
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

# ------------------------------
# 4. BOM PARSING
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
# 5. VENDOR PRESENTATION
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
        # Filter by available_qty >= needed
        available = df[df["available_qty"] >= qty_needed]
        if available.empty:
            results.append({"mpn": mpn, "error": f"Insufficient stock: max {df['available_qty'].max()} units available"})
            continue
        # Pick first (best match)
        best = available.iloc[0]
        results.append({
            "mpn": str(best["mpn"]),
            "supplier": str(best["supplier"]),
            "material_desc": str(best["material_desc"]),
            "qty": int(qty_needed),
            "unit_price": float(best["unit_price"]),
            "lead_time": int(best["lead_time_days"]),
            "total_price": float(qty_needed * best["unit_price"])
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
if "user_email" not in st.session_state:
    st.session_state.user_email = None
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
            st.session_state.user_email = user.get("email")
            # Fetch saved carts
            saved = get_saved_carts_for_user(st.session_state.user_email)
            st.session_state.saved_carts_list = saved
            welcome = f"Hello **{user['name']}**! Welcome back. You are from **{user['company']}**, authorised for: {', '.join(user['entities'])}. Is that correct?"
            bot_message(welcome)
            st.session_state.step = "confirm_company"
            st.rerun()
        else:
            st.error("User not found. Please use alice@google.com or bob@google.com")
            bot_message("I couldn't find your account. Please try again with one of the demo emails.")

# ------------------------------
# STEP 2: CONFIRM COMPANY
# ------------------------------
elif st.session_state.step == "confirm_company":
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
                cart_data, msg = load_saved_cart_by_name(st.session_state.user_email, selected)
                if cart_data:
                    st.session_state.active_cart = cart_data
                    bot_message(f"Loaded cart '{selected}'. Would you like to continue shopping or proceed to checkout?")
                    st.session_state.step = "continue_or_checkout"
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
    if input_type == "Type text":
        text_input = st.text_area("Enter one MPN and quantity per line (e.g., MPN1001 50 or MPN1001,50)")
        if st.button("Submit text"):
            items = parse_bom_from_text(text_input)
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
        items = st.session_state.current_bom_items
        results = get_supplier_for_items(items)
        st.session_state.vendor_results = results
        msg = "Searching supplier catalogue...\n\n"
        for r in results:
            if "error" in r:
                msg += f"❌ {r['mpn']}: {r['error']}\n"
            else:
                msg += f"✅ **{r['mpn']}** – {r['material_desc']}\n   Vendor: {r['supplier']} | Qty: {r['qty']} | Price: ${r['unit_price']:.2f} each | Lead time: {r['lead_time']} days\n"
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
            existing = [c["name"] for c in st.session_state.saved_carts_list]
            if cart_name in existing:
                st.error("Name already exists. Please choose another.")
            else:
                save_cart_to_db(st.session_state.user_email, cart_name, st.session_state.active_cart)
                st.session_state.saved_carts_list.append({"name": cart_name, "expiry": (datetime.now() + timedelta(days=14)).isoformat()})
                st.session_state.cart_name = cart_name
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
        bot_message(f"Redirecting you to the core system checkout with cart '{st.session_state.cart_name or 'your cart'}'...")
        st.session_state.step = "checkout"
        st.rerun()

# ------------------------------
# STEP 9: CHECKOUT REDIRECT
# ------------------------------
elif st.session_state.step == "checkout":
    st.markdown("### 🏢 Core System Checkout")
    st.info("Redirecting to core system checkout page...")
    
    # Display cart summary
    st.subheader("Cart Summary")
    if st.session_state.active_cart:
        cart_items = st.session_state.active_cart["items"]
        total_price = 0
        items_data = []
        
        for item in cart_items:
            if "error" not in item:
                items_data.append({
                    "MPN": item["mpn"],
                    "Description": item["material_desc"],
                    "Supplier": item["supplier"],
                    "Quantity": item["qty"],
                    "Unit Price": f"${item['unit_price']:.2f}",
                    "Total": f"${item['total_price']:.2f}"
                })
                total_price += item["total_price"]
        
        if items_data:
            df_display = pd.DataFrame(items_data)
            st.dataframe(df_display, use_container_width=True)
            st.markdown(f"**Grand Total: ${total_price:.2f}**")
    
    # Redirect message
    st.success("✅ Your cart is ready for checkout in the core system!")
    st.markdown(f"**Cart Name:** {st.session_state.cart_name}")
    st.markdown(f"**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Mock redirect to core system
    core_system_url = "https://core-system.example.com/checkout"
    st.markdown(f"[🔗 Continue to Core System Checkout]({core_system_url})")
    
    st.caption("In production, you would be automatically redirected to the real core system.")
    
    if st.button("Start new session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.step = "login"
        st.rerun()
