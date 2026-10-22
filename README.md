Computer Equipment Warehouse Management
A Python and Flask web application for managing computer equipment inventory across warehouse locations. Built around the “Mladinović d.o.o.” project scenario, it tracks stock, shelf capacity, movements, suppliers, and purchase orders. The interface is in Croatian.
Features
- Login and user roles: administrator (admin), manager (poslovoda), and warehouse worker (skladistar).
- Product records with item codes, quantities, minimum stock levels, prices, categories, and suppliers.
- Warehouse locations organised by sector, rack, and shelf.
- Stock distribution across multiple locations and transfers between locations.
- Capacity checks when adding or moving stock.
- Stock receipts, issues, and a transaction history.
- Purchase orders with pending, ordered, and received statuses.
- Generation of purchase order suggestions for low-stock items.
- Inventory overview, reports, CSV exports, and purchase order PDFs.
- Management of users, suppliers, categories, and locations.
Technology
Layer	Tools
Backend	Python, Flask, Werkzeug
Database	SQLite
Frontend	Jinja templates, HTML, CSS, JavaScript
Documents	fpdf2 and CSV export


Run locally
Use Python 3.9 or newer with pip and virtual environment support. Dependencies are listed in requirements.txt.
git clone https://github.com/Luka0082/skladiste-aplikacija.git
cd skladiste-aplikacija
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
On Windows, create the environment with py -m venv venv and activate it with venv\Scripts\activate in Command Prompt.

Open http://127.0.0.1:5000.

Run the application from the repository root. On first launch, app.py creates database.db from schema.sql and adds initial users and sample inventory. Startup also runs the application's database upgrade routine. Launch with python app.py so these steps run.
Local demo accounts
Username	Password	Role
admin	123456	Administrator
poslovoda	123456	Manager
skladistar	123456	Warehouse worker


These are the demo credentials explicitly seeded by the application, for local evaluation only. The current code also uses a fixed session secret and enables Flask debug mode. Replace the credentials and secret, disable debug mode, and review security before any public deployment.

database.db and the venv/ virtual environment directory are excluded from Git.
Project structure
Path	Purpose
app.py	Routes, business logic, database setup, and exports
schema.sql	Initial SQLite schema
requirements.txt	Python dependencies
templates/	Jinja page templates
static/css/style.css	Styles
static/js/main.js	Browser-side behaviour


Suggested manual testing
These are review scenarios, not a record of executed tests. No automated test suite is included.
- Sign in with each demo role and compare available actions.
- Create a product and check its appearance in the inventory overview.
- Add stock up to a location's capacity, then try exceeding it.
- Move stock between locations and check quantities at both ends.
- Try issuing more stock than is available and inspect the result.
- Generate low-stock order suggestions and inspect repeat-generation behaviour.
- Receive a purchase order and verify inventory and transaction records.
- Compare CSV and PDF exports with the corresponding records.
- Log out and check that protected pages require authentication.
Project notes
This is a portfolio application with seeded demonstration data. The local setup above is not a production deployment guide. No production-readiness or security certification is claimed.

Author
Luka Mladinović
