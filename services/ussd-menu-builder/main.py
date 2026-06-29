"""
USSD Menu Builder — Python microservice
Dynamic menu tree for POS operations (*384# style)
Generates USSD menu structures, validates navigation, and manages menu templates

Endpoints:
  GET  /menu                — Get the full menu tree
  POST /menu/navigate       — Navigate to a menu node by path
  POST /menu/render         — Render a menu screen for a given state
  GET  /menu/shortcuts      — Get shortcut codes (*384*1#, *384*2#, etc.)
  POST /menu/template       — Create a custom menu template
  GET  /menu/templates      — List all custom templates
  GET  /health              — Health check
"""

from flask import Flask, jsonify, request
import time
import uuid

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


app = Flask(__name__)

# ── Menu Tree Definition ─────────────────────────────────────────────────────

MENU_TREE = {
    "id": "root",
    "title": "54agent POS",
    "shortcode": "*384#",
    "children": [
        {
            "id": "cash_in",
            "title": "Cash In",
            "shortcode": "*384*1#",
            "action": "cash_in",
            "children": [
                {"id": "cash_in_amount", "title": "Enter Amount", "type": "input", "validation": "amount", "next": "cash_in_phone"},
                {"id": "cash_in_phone", "title": "Customer Phone", "type": "input", "validation": "phone", "next": "cash_in_pin"},
                {"id": "cash_in_pin", "title": "Enter PIN", "type": "pin", "next": "cash_in_confirm"},
                {"id": "cash_in_confirm", "title": "Confirm", "type": "confirm", "next": "cash_in_complete"},
                {"id": "cash_in_complete", "title": "Complete", "type": "end"},
            ]
        },
        {
            "id": "cash_out",
            "title": "Cash Out",
            "shortcode": "*384*2#",
            "action": "cash_out",
            "children": [
                {"id": "cash_out_amount", "title": "Enter Amount", "type": "input", "validation": "amount", "next": "cash_out_phone"},
                {"id": "cash_out_phone", "title": "Customer Phone", "type": "input", "validation": "phone", "next": "cash_out_pin"},
                {"id": "cash_out_pin", "title": "Enter PIN", "type": "pin", "next": "cash_out_confirm"},
                {"id": "cash_out_confirm", "title": "Confirm", "type": "confirm", "next": "cash_out_complete"},
                {"id": "cash_out_complete", "title": "Complete", "type": "end"},
            ]
        },
        {
            "id": "balance",
            "title": "Balance Inquiry",
            "shortcode": "*384*3#",
            "action": "balance",
            "children": [
                {"id": "balance_pin", "title": "Enter PIN", "type": "pin", "next": "balance_result"},
                {"id": "balance_result", "title": "Balance Result", "type": "end"},
            ]
        },
        {
            "id": "transfer",
            "title": "Transfer",
            "shortcode": "*384*4#",
            "action": "transfer",
            "children": [
                {"id": "transfer_amount", "title": "Enter Amount", "type": "input", "validation": "amount", "next": "transfer_recipient"},
                {"id": "transfer_recipient", "title": "Recipient Phone", "type": "input", "validation": "phone", "next": "transfer_pin"},
                {"id": "transfer_pin", "title": "Enter PIN", "type": "pin", "next": "transfer_confirm"},
                {"id": "transfer_confirm", "title": "Confirm", "type": "confirm", "next": "transfer_complete"},
                {"id": "transfer_complete", "title": "Complete", "type": "end"},
            ]
        },
        {
            "id": "airtime",
            "title": "Airtime Purchase",
            "shortcode": "*384*5#",
            "action": "airtime",
            "children": [
                {"id": "airtime_amount", "title": "Enter Amount", "type": "input", "validation": "amount", "next": "airtime_phone"},
                {"id": "airtime_phone", "title": "Phone Number", "type": "input", "validation": "phone", "next": "airtime_pin"},
                {"id": "airtime_pin", "title": "Enter PIN", "type": "pin", "next": "airtime_confirm"},
                {"id": "airtime_confirm", "title": "Confirm", "type": "confirm", "next": "airtime_complete"},
                {"id": "airtime_complete", "title": "Complete", "type": "end"},
            ]
        },
        {
            "id": "bills",
            "title": "Bill Payment",
            "shortcode": "*384*6#",
            "action": "bills",
            "children": [
                {"id": "bills_type", "title": "Select Bill Type", "type": "select", "options": ["Electricity", "Water", "Internet", "Cable TV", "School Fees"], "next": "bills_account"},
                {"id": "bills_account", "title": "Account Number", "type": "input", "validation": "account", "next": "bills_amount"},
                {"id": "bills_amount", "title": "Enter Amount", "type": "input", "validation": "amount", "next": "bills_pin"},
                {"id": "bills_pin", "title": "Enter PIN", "type": "pin", "next": "bills_confirm"},
                {"id": "bills_confirm", "title": "Confirm", "type": "confirm", "next": "bills_complete"},
                {"id": "bills_complete", "title": "Complete", "type": "end"},
            ]
        },
    ]
}

# ── Custom Templates Store ────────────────────────────────────────────────────

custom_templates = []

# ── Helper Functions ──────────────────────────────────────────────────────────

def find_node(tree, node_id):
    """Find a node in the menu tree by ID"""
    if tree.get("id") == node_id:
        return tree
    for child in tree.get("children", []):
        result = find_node(child, node_id)
        if result:
            return result
    return None


def navigate_path(tree, path_parts):
    """Navigate the menu tree by a list of selection indices"""
    current = tree
    for idx_str in path_parts:
        try:
            idx = int(idx_str) - 1  # 1-indexed
            children = current.get("children", [])
            if 0 <= idx < len(children):
                current = children[idx]
            else:
                return None
        except (ValueError, IndexError):
            return None
    return current


def render_menu_screen(node):
    """Render a USSD text screen for a menu node"""
    if not node:
        return {"text": "END Invalid menu option", "continue": False}

    children = node.get("children", [])
    node_type = node.get("type", "menu")

    if node_type == "end":
        return {"text": f"END {node['title']}", "continue": False, "nodeId": node["id"]}

    if node_type == "input":
        validation = node.get("validation", "text")
        prompts = {
            "amount": "Enter amount (NGN):",
            "phone": "Enter phone number:",
            "account": "Enter account number:",
            "text": "Enter value:",
        }
        return {"text": f"CON {prompts.get(validation, 'Enter value:')}", "continue": True, "nodeId": node["id"], "validation": validation}

    if node_type == "pin":
        return {"text": "CON Enter your PIN:", "continue": True, "nodeId": node["id"], "validation": "pin"}

    if node_type == "confirm":
        return {"text": "CON 1. Confirm\n2. Cancel", "continue": True, "nodeId": node["id"]}

    if node_type == "select":
        options = node.get("options", [])
        lines = [f"CON {node['title']}"]
        for i, opt in enumerate(options, 1):
            lines.append(f"{i}. {opt}")
        return {"text": "\n".join(lines), "continue": True, "nodeId": node["id"]}

    # Default: show children as numbered menu
    if children:
        lines = [f"CON {node['title']}"]
        for i, child in enumerate(children, 1):
            lines.append(f"{i}. {child['title']}")
        return {"text": "\n".join(lines), "continue": True, "nodeId": node["id"]}

    return {"text": f"END {node['title']}", "continue": False, "nodeId": node["id"]}


def get_all_shortcuts(tree, prefix=""):
    """Recursively collect all shortcut codes"""
    shortcuts = []
    if "shortcode" in tree:
        shortcuts.append({
            "code": tree["shortcode"],
            "title": tree["title"],
            "id": tree["id"],
            "action": tree.get("action", None),
        })
    for child in tree.get("children", []):
        shortcuts.extend(get_all_shortcuts(child, prefix))
    return shortcuts


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/menu", methods=["GET"])
def get_menu():
    return jsonify(MENU_TREE)


@app.route("/menu/navigate", methods=["POST"])
def navigate_menu():
    data = request.get_json() or {}
    path = data.get("path", "")
    node_id = data.get("nodeId")

    if node_id:
        node = find_node(MENU_TREE, node_id)
    elif path:
        parts = [p for p in path.split("*") if p and p != "#"]
        # Skip the shortcode prefix (384)
        if parts and parts[0] == "384":
            parts = parts[1:]
        node = navigate_path(MENU_TREE, parts)
    else:
        node = MENU_TREE

    if not node:
        return jsonify({"error": "Menu node not found", "text": "END Invalid option"}), 404

    screen = render_menu_screen(node)
    return jsonify({**screen, "node": node})


@app.route("/menu/render", methods=["POST"])
def render_menu():
    data = request.get_json() or {}
    node_id = data.get("nodeId", "root")
    context = data.get("context", {})

    node = find_node(MENU_TREE, node_id)
    if not node:
        return jsonify({"error": "Node not found"}), 404

    screen = render_menu_screen(node)

    # Inject context into confirmation screens
    if node.get("type") == "confirm" and context:
        amount = context.get("amount", "0")
        phone = context.get("phone", "")
        tx_type = context.get("txType", "Transaction")
        confirm_text = f"CON Confirm {tx_type}\nAmount: NGN {amount}"
        if phone:
            confirm_text += f"\nPhone: {phone}"
        confirm_text += "\n1. Confirm\n2. Cancel"
        screen["text"] = confirm_text

    return jsonify(screen)


@app.route("/menu/shortcuts", methods=["GET"])
def get_shortcuts():
    shortcuts = get_all_shortcuts(MENU_TREE)
    return jsonify(shortcuts)


@app.route("/menu/template", methods=["POST"])
def create_template():
    data = request.get_json() or {}
    template = {
        "id": str(uuid.uuid4())[:8],
        "name": data.get("name", "Custom Menu"),
        "description": data.get("description", ""),
        "tree": data.get("tree", {}),
        "createdAt": int(time.time() * 1000),
        "active": True,
    }
    custom_templates.append(template)
    return jsonify(template), 201


@app.route("/menu/templates", methods=["GET"])
def list_templates():
    return jsonify(custom_templates)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "ussd-menu-builder",
        "version": "1.0.0",
        "menuNodes": count_nodes(MENU_TREE),
        "customTemplates": len(custom_templates),
    })


def count_nodes(tree):
    count = 1
    for child in tree.get("children", []):
        count += count_nodes(child)
    return count


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8112))
    print(f"[ussd-menu-builder] Starting on :{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
