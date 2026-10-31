# Perfume & Fragrance House Management System

A small desktop application for running a perfume company: it keeps track of perfumes and their formulas, raw materials, suppliers, production batches, customers, orders and payments.

- **Database:** PostgreSQL
- **Application:** Python (Tkinter window, no web browser needed)

You do **not** need to know programming to run this. Just follow the steps in order.

---

## What's in this folder

| File | What it is |
|------|------------|
| `schema.sql` | Creates all the tables, views and triggers, and fills them with sample data |
| `app.py` | The application you actually open and use |
| `requirements.txt` | The list of extra Python packages the app needs |
| `README.md` | This guide |

---

## Step 1 - Install the software (one time only)

You need two things: **Python** and **PostgreSQL**.

### 1a. Python (version 3.8 or newer)

1. Go to https://www.python.org/downloads/ and download the latest version.
2. Run the installer.
   - **Windows:** on the first screen, tick **"Add python.exe to PATH"** before clicking Install. This is the most common beginner mistake.
   - **Mac:** the installer from python.org already includes the window toolkit (Tkinter) the app needs.
   - **Linux (Ubuntu/Debian):** open a terminal and run:
     ```
     sudo apt update
     sudo apt install python3 python3-pip python3-tk
     ```
3. Check it worked. Open a terminal (Windows: search for **Command Prompt** or **PowerShell**; Mac: **Terminal**) and type:
   ```
   python --version
   ```
   You should see something like `Python 3.12.1`. On Mac/Linux, if that fails, use `python3 --version`. If so, use `python3` instead of `python` in all commands below.

### 1b. PostgreSQL (version 11 or newer)

1. Go to https://www.postgresql.org/download/ and download the installer for your system.
2. Run it and keep clicking **Next** with the default options. Make sure **pgAdmin 4** stays ticked, because it is a friendly visual tool we will use.
3. When it asks for a **password** for the database superuser (named `postgres`), choose one and **write it down**. You will need it in the app.
4. Keep the default port **5432**.

**Linux alternative:**
```
sudo apt install postgresql postgresql-contrib
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'choose_a_password';"
```

---

## Step 2 - Install the Python package

Open a terminal **inside this project folder**.

- **Windows:** open the folder in File Explorer, click on the address bar, type `cmd`, press Enter.
- **Mac:** right-click the folder and choose *New Terminal at Folder* (or open Terminal and use `cd path/to/folder`).

Then run:

```
pip install -r requirements.txt
```

If `pip` is not recognised, try `python -m pip install -r requirements.txt` (or `python3 -m pip ...`).

---

## Step 3 - Create the database

Choose **one** of these two ways. Option A needs no typing of commands.

### Option A - using pgAdmin (visual, recommended for beginners)

1. Open **pgAdmin 4** from your Start menu / Applications. Enter the password you chose if asked.
2. On the left, expand **Servers**, then **PostgreSQL**. Enter your password again if asked.
3. Right-click **Databases** -> **Create** -> **Database...**
4. Type the name `perfume_house` (exactly like this, no spaces) and click **Save**.
5. Click on the new `perfume_house` database, then open the menu **Tools** -> **Query Tool**.
6. In the Query Tool, click the **folder icon (Open File)**, choose `schema.sql` from this project folder.
7. Click the **Play / Execute** button (or press **F5**).
8. At the bottom you should see *"Query returned successfully"*. Done.

### Option B - using the command line

Open a terminal in this project folder and run:

```
createdb -U postgres perfume_house
psql -U postgres -d perfume_house -f schema.sql
```

(It asks for your PostgreSQL password each time. On Windows, if the commands are not found, use pgAdmin instead, or open **SQL Shell (psql)** from the Start menu.)

> You can run `schema.sql` again at any time. It wipes the tables and recreates them with fresh sample data, which is handy if you want to reset everything.

---

## Step 4 - Run the application

In the terminal, inside the project folder:

```
python app.py
```

A login window appears. Fill it in:

| Field | What to type |
|-------|--------------|
| Host | `localhost` |
| Port | `5432` |
| Database | `perfume_house` |
| User | `postgres` |
| Password | the password you chose when installing PostgreSQL |

Click **Connect**. The main window opens with the sample data already loaded.

---

## How to use the app (quick tour)

The tabs along the top are the different parts of the business.

| Tab | What you can do |
|-----|-----------------|
| **Dashboard** | Overview numbers, low-stock materials, recent orders, best sellers |
| **Perfumes** | Add/edit/delete perfumes. Select one and click **Edit Formula** to set its ingredients |
| **Families** | Fragrance families such as Floral, Woody, Citrus |
| **Raw Materials** | Oils and aroma chemicals with cost and stock |
| **Suppliers** | Who you buy materials from |
| **Purchases** | Record buying raw materials (stock goes up automatically) |
| **Production** | Plan batches. Select one and click **Mark Completed** to use up materials and add finished bottles |
| **Customers** | Customer records and loyalty points |
| **Orders** | **New Order** (cart), **Record Payment**, **Mark Shipped**, **Cancel Order** |
| **Employees** | Perfumers, lab technicians, sales staff, managers |
| **Reports** | 16 ready-made SQL queries; pick one to see the SQL and its results |

**General tips**
- To **edit** a record: click a row in the table, change the form at the bottom, press **Update Selected**.
- To **add** a record: fill the form, press **Add New**. Fields marked with `*` are required.
- Dates are typed as `YYYY-MM-DD`, for example `2026-11-05`.
- Some numbers (stock, order totals, loyalty points) are updated automatically by the database. You can't type them directly, and that is intentional.

**Things worth trying**
1. Orders -> New Order -> pick a customer and sales executive, add some perfumes, **Place Order**. Check how the stock drops in the Perfumes tab.
2. Select that order -> **Record Payment** -> pay the full amount. The status changes to *Paid* and the customer earns loyalty points.
3. Try ordering more bottles than are in stock. The database refuses, and the app shows a clear message.
4. Cancel an unpaid order and watch the bottles return to stock.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `'python' is not recognized` (Windows) | Reinstall Python and tick **Add python.exe to PATH**, or try `py app.py` |
| `psycopg2 is missing` | Run `pip install -r requirements.txt` again (or `python -m pip install -r requirements.txt`) |
| `No module named tkinter` (Linux) | `sudo apt install python3-tk` |
| `password authentication failed` | You typed the wrong PostgreSQL password. Use the one you set during installation |
| `connection refused` / `could not connect to server` | PostgreSQL isn't running. On Windows, open **Services** and start `postgresql-x64-xx`. On Linux: `sudo systemctl start postgresql` |
| `database "perfume_house" does not exist` | Do Step 3 and make sure the name is exactly `perfume_house` |
| `relation ... does not exist` inside the app | The tables are missing. Run `schema.sql` (Step 3) on the `perfume_house` database |
| `Insufficient stock...` or `Not enough ... in stock` | Not a bug. The database is protecting your stock. Produce more bottles or buy more materials |
| Window text looks tiny or cut off | Maximise the window; the layout is made for roughly 1300x800 or larger |

---

## For the project report (database concepts used)

- **Design:** 12 tables in a normalised design with primary keys, foreign keys, NOT NULL, UNIQUE and CHECK constraints, and a many-to-many relationship (perfume <-> raw_material).
- **SQL:** SELECT with WHERE and ORDER BY, aggregates (COUNT, SUM, AVG, MIN, MAX), GROUP BY and HAVING, joins, subqueries, INSERT/UPDATE/DELETE, and views. See the **Reports** tab.
- **Triggers:** automatic stock updates, order totals, payment status, cancellations and locked production batches.
- **Transactions:** a new order and all its items are saved together or not at all.
- **Application:** Python Tkinter interface talking to PostgreSQL through `psycopg2`.
