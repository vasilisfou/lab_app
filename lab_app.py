from flask import Flask, request, jsonify, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///lab_inventory.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Models
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    barcode = db.Column(db.String(100), unique=True, nullable=False)
    quantity = db.Column(db.Integer, default=0)  # Present quantity
    absent_quantity = db.Column(db.Integer, default=0)  # Absent quantity
    location = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # IN or OUT
    quantity = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize DB
with app.app_context():
    db.create_all()

# Home Page
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

# Add Inventory
@app.route("/inventory/add", methods=["POST"])
def add_inventory():
    if request.is_json:
        data = request.get_json()
        barcode = data.get("barcode")
        name = data.get("name")
        quantity = int(data.get("quantity", 0))
        location = data.get("location")
    else:
        barcode = request.form.get("barcode")
        name = request.form.get("name")
        quantity = int(request.form.get("quantity", 0))
        location = request.form.get("location")

    if not barcode or not name or quantity <= 0:
        return jsonify({"error": "Invalid input"}), 400

    item = Item.query.filter_by(barcode=barcode).first()
    if item:
        item.quantity += quantity
    else:
        item = Item(name=name, barcode=barcode, quantity=quantity, location=location)
        db.session.add(item)

    db.session.flush()
    txn = Transaction(item_id=item.id, type="IN", quantity=quantity)
    db.session.add(txn)
    db.session.commit()

    return redirect("/inventory") if not request.is_json else jsonify({
        "message": "Item added",
        "item": {"name": item.name, "barcode": item.barcode, "quantity": item.quantity}
    }), 200

# Remove Inventory (Move to Absent)
@app.route("/inventory/remove", methods=["POST"])
def remove_inventory():
    barcode = request.form.get("barcode")
    quantity = int(request.form.get("quantity", 0))

    item = Item.query.filter_by(barcode=barcode).first()
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item.quantity < quantity:
        return jsonify({"error": "Not enough stock"}), 400

    item.quantity -= quantity
    item.absent_quantity += quantity

    txn = Transaction(item_id=item.id, type="OUT", quantity=quantity)
    db.session.add(txn)
    db.session.commit()

    return redirect("/inventory")

# Return Inventory (Move from Absent to Present)
@app.route("/inventory/return", methods=["POST"])
def return_inventory():
    barcode = request.form.get("barcode")
    quantity = int(request.form.get("quantity", 0))

    item = Item.query.filter_by(barcode=barcode).first()
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item.absent_quantity < quantity:
        return jsonify({"error": "Not enough absent stock"}), 400

    item.absent_quantity -= quantity
    item.quantity += quantity

    txn = Transaction(item_id=item.id, type="IN", quantity=quantity)
    db.session.add(txn)
    db.session.commit()

    return redirect("/inventory")

# Inventory View
@app.route("/inventory", methods=["GET"])
def list_inventory():
    present_items = Item.query.filter(Item.quantity > 0).all()
    absent_items = Item.query.filter(Item.absent_quantity > 0).all()
    return render_template("inventory.html", present_items=present_items, absent_items=absent_items)

# Scan Item Route
@app.route("/scan", methods=["GET", "POST"])
def scan_item():
    barcode = request.args.get("barcode") or request.form.get("barcode")
    if not barcode:
        return render_template("scan_input.html")

    item = Item.query.filter_by(barcode=barcode).first()
    if not item:
        return f"Item with barcode '{barcode}' not found.", 404

    return render_template("scan_result.html", item=item)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)
