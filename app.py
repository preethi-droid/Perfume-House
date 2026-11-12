import os
import sys
import tkinter as tk
from datetime import date, datetime
from decimal import Decimal
from tkinter import messagebox, ttk

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 is missing.  Install it with:  pip install psycopg2-binary")

APP_TITLE = "Aroma House - Perfume & Fragrance Management"
# wine / rose / cream
INK, PLUM, GOLD = "#2d2326", "#7b2d4e", "#d9a7b4"
CREAM, BLUSH, ROSE, MUTED, SIDE = "#fdf7f2", "#f5e6e6", "#ecc6d0", "#7a6a6e", "#4d1a31"
SANS = "Segoe UI"
SERIF = "Georgia"


#  Database layer
class Database:
    """Thin wrapper around a psycopg2 connection."""

    def __init__(self, host, port, dbname, user, password):
        self.conn = psycopg2.connect(host=host, port=port, dbname=dbname,
                                     user=user, password=password, connect_timeout=5)
        self.info = f"{user}@{host}:{port}/{dbname}"

    def fetch(self, sql, params=None):
        """Run a SELECT. Returns (column_names, rows)."""
        cur = self.conn.cursor()
        try:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            return cols, rows
        finally:
            self.conn.rollback()          # close the read-only transaction
            cur.close()

    def scalar(self, sql, params=None):
        return self.fetch(sql, params)[1][0][0]

    def execute(self, sql, params=None):
        """Run INSERT / UPDATE / DELETE and commit (rollback on error)."""
        cur = self.conn.cursor()
        try:
            cur.execute(sql, params)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def transaction(self, work):
        """Run work(cursor) as ONE transaction: all-or-nothing."""
        cur = self.conn.cursor()
        try:
            result = work(cur)
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()


def pretty_error(e):
    """Turn a database error into a message a normal person can read."""
    if isinstance(e, psycopg2.Error):
        code = e.pgcode or ""
        primary = (e.diag.message_primary or str(e)).strip()
        detail = e.diag.message_detail or ""
        if code == "23505":
            return "That record already exists (duplicate value).\n" + detail
        if code == "23503":
            return ("This conflicts with related records: either the linked record "
                    "doesn't exist, or other records still depend on this one.\n" + detail)
        if code == "23514":
            return f"A value breaks a database rule (CHECK: {e.diag.constraint_name})."
        if code == "23502":
            return f"A required value is missing ({e.diag.column_name})."
        if code == "22P02":
            return "A value has the wrong format."
        if code == "22003":
            return "A number is out of the allowed range."
        return primary + (("\n" + detail) if detail else "")
    return str(e)


#  UI helpers
def setup_style(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    root.configure(bg=CREAM)
    edge = "#e3cdd3"                                   # soft rose-grey used for all borders
    s.configure(".", background=CREAM, foreground=INK, font=(SANS, 10), bordercolor=edge,
                lightcolor=CREAM, darkcolor=CREAM, troughcolor=BLUSH)
    s.configure("TFrame", background=CREAM)
    s.configure("TLabel", background=CREAM)
    s.configure("TLabelframe", background=CREAM, bordercolor=edge)
    s.configure("TLabelframe.Label", background=CREAM, foreground=PLUM, font=(SANS, 10, "bold"))
    s.configure("TButton", padding=(14, 6), background=PLUM, foreground="white",
                borderwidth=0, focusthickness=0)
    s.map("TButton", background=[("active", "#9a3d63")])
    s.configure("TEntry", fieldbackground="white", bordercolor=edge, padding=5)
    s.configure("TCombobox", fieldbackground="white", bordercolor=edge, padding=5, arrowcolor=PLUM)
    s.map("TCombobox", fieldbackground=[("readonly", "white")],
          selectbackground=[("readonly", "white")], selectforeground=[("readonly", INK)])
    s.configure("TSpinbox", fieldbackground="white", bordercolor=edge, padding=5)
    s.configure("TScrollbar", background=BLUSH, bordercolor=edge, arrowcolor=PLUM)
    s.configure("Treeview", rowheight=28, background="white", fieldbackground="white",
                bordercolor=edge, borderwidth=1)
    s.configure("Treeview.Heading", background=PLUM, foreground="white", font=(SANS, 10, "bold"),
                padding=(8, 7), relief="flat")
    s.map("Treeview.Heading", background=[("active", "#9a3d63")])
    s.map("Treeview", background=[("selected", ROSE)], foreground=[("selected", INK)])
    s.configure("Status.TLabel", foreground="#2e7d32")


def fmt(v):
    """Format a database value for display."""
    if v is None:
        return ""
    if isinstance(v, Decimal):
        if -v.as_tuple().exponent <= 2:
            return f"{v:.2f}"
        return format(v.normalize(), "f")
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    return str(v)


def make_tree(parent, height=8):
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, show="headings", height=height, selectmode="browse")
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    tree.tag_configure("odd", background="#fcf5f5")
    tree.tag_configure("even", background="white")
    return frame, tree


def fill_tree(tree, cols, rows):
    tree.delete(*tree.get_children())
    tree["columns"] = cols
    for c in cols:
        tree.heading(c, text=c.replace("_", " ").title())
        tree.column(c, width=max(90, min(230, len(c) * 11)), anchor="w")
    for i, r in enumerate(rows):
        tree.insert("", "end", values=[fmt(v) for v in r],
                    tags=("odd" if i % 2 else "even",))


def draw_bottle(c, cx, top, h, glass=PLUM, liquid=ROSE, line=INK):
    """A simple flat perfume bottle. cx = centre x, top = y of the cap, h = total height."""
    u = h / 100.0
    c.create_rectangle(cx - 9 * u, top, cx + 9 * u, top + 20 * u, fill=line, outline="")          # cap
    c.create_rectangle(cx - 5 * u, top + 20 * u, cx + 5 * u, top + 30 * u, fill=glass, outline=line)  # neck
    c.create_polygon(cx - 30 * u, top + 40 * u, cx - 22 * u, top + 30 * u,                         # body
                     cx + 22 * u, top + 30 * u, cx + 30 * u, top + 40 * u,
                     cx + 30 * u, top + 90 * u, cx + 22 * u, top + 100 * u,
                     cx - 22 * u, top + 100 * u, cx - 30 * u, top + 90 * u,
                     fill=glass, outline=line, width=2)
    c.create_polygon(cx - 26 * u, top + 56 * u, cx + 26 * u, top + 56 * u,                         # perfume
                     cx + 26 * u, top + 88 * u, cx + 19 * u, top + 96 * u,
                     cx - 19 * u, top + 96 * u, cx - 26 * u, top + 88 * u,
                     fill=liquid, outline="")
    c.create_rectangle(cx - 14 * u, top + 64 * u, cx + 14 * u, top + 80 * u, fill=CREAM, outline=line)


class NavButton(tk.Label):
    """Sidebar entry (a Label, so the colours also work on macOS). The active one looks like a tab."""

    def __init__(self, parent, text, command):
        super().__init__(parent, text=text, anchor="w", padx=20, pady=9, font=(SANS, 11),
                         bg=SIDE, fg="#f6e4ea", cursor="hand2")
        self.active = False
        self.bind("<Button-1>", lambda _e: command())
        self.bind("<Enter>", lambda _e: None if self.active else self.config(bg="#6a2646"))
        self.bind("<Leave>", lambda _e: self.set_active(self.active))

    def set_active(self, flag):
        self.active = flag
        if flag:
            self.config(bg=CREAM, fg=PLUM, font=(SANS, 11, "bold"))
        else:
            self.config(bg=SIDE, fg="#f6e4ea", font=(SANS, 11))


def fk_id(text):
    """'3 - Some name'  ->  3"""
    return int(text.split(" - ", 1)[0])


def show_error(e):
    messagebox.showerror("Database error", pretty_error(e))


#  Generic CRUD tab (used for most master tables)
class CrudTab(ttk.Frame):
    """
    A reusable Add / Update / Delete / Search screen for one table.

    fields : list of dicts  {col, label, kind, [choices], [sql], [required], [default]}
             kind = text | int | num | date | choice | fk
    """

    def __init__(self, parent, db, table, pk, list_sql, fields, order="1",
                 allow_update=True, allow_delete=True, extra_buttons=()):
        super().__init__(parent, padding=8)
        self.db, self.table, self.pk = db, table, pk
        self.list_sql, self.fields, self.order = list_sql, fields, order
        self.selected_id = None
        self.vars, self.widgets = {}, {}

        # ---- search bar
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.search_var, width=32)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda _e: self.refresh())
        ttk.Button(bar, text="Search", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Show All", command=self.clear_search).pack(side="left", padx=4)

        # ---- table
        frame, self.tree = make_tree(self, height=11)
        frame.pack(fill="both", expand=True, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # ---- form
        form = ttk.LabelFrame(self, text="Record details", padding=10)
        form.pack(fill="x")
        for i, f in enumerate(fields):
            r, c = divmod(i, 3)
            star = " *" if f.get("required", True) else ""
            ttk.Label(form, text=f["label"] + star).grid(
                row=r, column=c * 2, sticky="e", padx=(8, 4), pady=4)
            var = tk.StringVar()
            if f["kind"] in ("choice", "fk"):
                w = ttk.Combobox(form, textvariable=var, state="readonly", width=28,
                                 values=f.get("choices", []))
            else:
                w = ttk.Entry(form, textvariable=var, width=30)
            w.grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 8), pady=4)
            self.vars[f["col"]], self.widgets[f["col"]] = var, w

        # ---- buttons
        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Add New", command=self.add).pack(side="left", padx=2)
        if allow_update:
            ttk.Button(btns, text="Update Selected", command=self.update).pack(side="left", padx=2)
        if allow_delete:
            ttk.Button(btns, text="Delete Selected", command=self.delete).pack(side="left", padx=2)
        ttk.Button(btns, text="Clear Form", command=self.clear_form).pack(side="left", padx=2)
        for label, fn in extra_buttons:
            ttk.Button(btns, text=label, command=lambda fn=fn: fn(self)).pack(side="left", padx=2)
        self.status = ttk.Label(btns, text="", style="Status.TLabel")
        self.status.pack(side="right")

        self.clear_form()

    # ---------- helpers
    def say(self, msg):
        self.status.config(text=msg)

    def load_fk(self):
        for f in self.fields:
            if f["kind"] == "fk":
                _, rows = self.db.fetch(f["sql"])
                self.widgets[f["col"]]["values"] = [f"{r[0]} - {r[1]}" for r in rows]

    def clear_search(self):
        self.search_var.set("")
        self.refresh()

    def clear_form(self):
        self.selected_id = None
        for f in self.fields:
            d = f.get("default", "")
            if d == "today":
                d = date.today().isoformat()
            self.vars[f["col"]].set(d)
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())

    def refresh(self):
        try:
            self.load_fk()
            sql = f"SELECT * FROM ({self.list_sql}) t"
            params = []
            term = self.search_var.get().strip()
            if term:
                sql += " WHERE t::text ILIKE %s"
                params.append(f"%{term}%")
            sql += f" ORDER BY {self.order}"
            cols, rows = self.db.fetch(sql, params)
            fill_tree(self.tree, cols, rows)
            self.say(f"{len(rows)} record(s)")
        except Exception as e:
            show_error(e)

    def collect(self):
        """Read + validate the form. Returns a list of values in field order."""
        hints = {"int": "a whole number", "num": "a number",
                 "date": "a date as YYYY-MM-DD", "fk": "a choice from the list"}
        vals = []
        for f in self.fields:
            raw = self.vars[f["col"]].get().strip()
            if not raw:
                if f.get("required", True):
                    raise ValueError(f"'{f['label']}' is required.")
                vals.append(None)
                continue
            try:
                if f["kind"] == "int":
                    raw = int(raw)
                elif f["kind"] == "num":
                    float(raw)
                elif f["kind"] == "date":
                    datetime.strptime(raw, "%Y-%m-%d")
                elif f["kind"] == "fk":
                    raw = fk_id(raw)
            except ValueError:
                raise ValueError(f"'{f['label']}' must be {hints[f['kind']]}.")
            vals.append(raw)
        return vals

    # ---------- row selection
    def on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = str(self.tree.item(sel[0])["values"][0])
        cols = [f["col"] for f in self.fields]
        try:
            _, rows = self.db.fetch(
                f"SELECT {', '.join(cols)} FROM {self.table} WHERE {self.pk} = %s",
                (self.selected_id,))
        except Exception as e:
            show_error(e)
            return
        if not rows:
            return
        for f, val in zip(self.fields, rows[0]):
            if val is None:
                text = ""
            elif f["kind"] == "fk":
                options = self.widgets[f["col"]]["values"]
                text = next((o for o in options if o.split(" - ", 1)[0] == str(val)), "")
            elif isinstance(val, date):
                text = val.isoformat()
            else:
                text = str(val)
            self.vars[f["col"]].set(text)

    # ---------- CRUD actions
    def add(self):
        try:
            vals = self.collect()
        except ValueError as e:
            messagebox.showwarning("Check the form", str(e))
            return
        cols = [f["col"] for f in self.fields]
        sql = (f"INSERT INTO {self.table} ({', '.join(cols)}) "
               f"VALUES ({', '.join(['%s'] * len(cols))})")
        try:
            self.db.execute(sql, vals)
        except Exception as e:
            show_error(e)
            return
        self.clear_form()
        self.refresh()
        self.say("Record added.")

    def update(self):
        if not self.selected_id:
            messagebox.showinfo("Select a record", "Click a row in the table first.")
            return
        try:
            vals = self.collect()
        except ValueError as e:
            messagebox.showwarning("Check the form", str(e))
            return
        sets = ", ".join(f"{f['col']} = %s" for f in self.fields)
        try:
            self.db.execute(f"UPDATE {self.table} SET {sets} WHERE {self.pk} = %s",
                            vals + [self.selected_id])
        except Exception as e:
            show_error(e)
            return
        self.refresh()
        self.say("Record updated.")

    def delete(self):
        if not self.selected_id:
            messagebox.showinfo("Select a record", "Click a row in the table first.")
            return
        if not messagebox.askyesno("Confirm delete", "Delete the selected record permanently?"):
            return
        try:
            self.db.execute(f"DELETE FROM {self.table} WHERE {self.pk} = %s", (self.selected_id,))
        except Exception as e:
            show_error(e)
            return
        self.clear_form()
        self.refresh()
        self.say("Record deleted.")

    def run_action(self, sql, params, ok_msg):
        """Used by extra buttons that run a custom UPDATE on the selected row."""
        try:
            self.db.execute(sql, params)
        except Exception as e:
            show_error(e)
            return
        self.refresh()
        self.say(ok_msg)


#  Perfume formula (recipe) dialog
class FormulaDialog(tk.Toplevel):
    def __init__(self, parent, db, perfume_id, perfume_name, on_done):
        super().__init__(parent)
        self.db, self.perfume_id, self.on_done = db, perfume_id, on_done
        self.title(f"Formula - {perfume_name}")
        self.geometry("1100x570")
        self.transient(parent)
        self.configure(bg=CREAM)

        ttk.Label(self, text=f"Formula of '{perfume_name}'  (ml of each material per bottle)",
                  font=(SERIF, 14, "bold"), foreground=PLUM).pack(pady=(12, 4))
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=6)
        self.pyramid = tk.Canvas(body, width=340, height=300, bg=CREAM, highlightthickness=0)
        self.pyramid.pack(side="left", padx=(0, 10))
        frame, self.tree = make_tree(body, height=10)
        frame.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        self.summary = ttk.Label(self, text="")
        self.summary.pack(pady=2)

        form = ttk.Frame(self, padding=8)
        form.pack(fill="x")
        _, mats = db.fetch("SELECT material_id, material_name FROM raw_material ORDER BY 2")
        self.mat_var, self.qty_var = tk.StringVar(), tk.StringVar()
        ttk.Label(form, text="Material:").grid(row=0, column=0, padx=4)
        self.mat_cb = ttk.Combobox(form, textvariable=self.mat_var, state="readonly", width=30,
                                   values=[f"{m[0]} - {m[1]}" for m in mats])
        self.mat_cb.grid(row=0, column=1, padx=4)
        ttk.Label(form, text="ml per bottle:").grid(row=0, column=2, padx=4)
        ttk.Entry(form, textvariable=self.qty_var, width=10).grid(row=0, column=3, padx=4)
        ttk.Button(form, text="Add / Update", command=self.save).grid(row=0, column=4, padx=6)
        ttk.Button(form, text="Remove Selected", command=self.remove).grid(row=0, column=5, padx=2)
        self.refresh()

    def refresh(self):
        try:
            cols, rows = self.db.fetch("""
                SELECT rm.material_id, rm.material_name, rm.material_type, rm.note_position,
                       pi.qty_per_bottle_ml,
                       ROUND(pi.qty_per_bottle_ml * rm.unit_cost_per_ml, 2) AS cost
                FROM perfume_ingredient pi
                JOIN raw_material rm ON rm.material_id = pi.material_id
                WHERE pi.perfume_id = %s
                ORDER BY CASE rm.note_position WHEN 'Top' THEN 1 WHEN 'Middle' THEN 2 ELSE 3 END,
                         rm.material_name""", (self.perfume_id,))
            fill_tree(self.tree, cols, rows)
            self.draw_pyramid(rows)
            total_ml = sum(r[4] for r in rows) if rows else Decimal(0)
            total_cost = sum(r[5] for r in rows) if rows else Decimal(0)
            size = self.db.scalar("SELECT bottle_size_ml FROM perfume WHERE perfume_id = %s",
                                  (self.perfume_id,))
            warn = "   (more than the bottle holds!)" if total_ml > size else ""
            self.summary.config(
                text=f"Oil/ingredient volume: {fmt(total_ml)} ml of a {size} ml bottle{warn}"
                     f"   |   Material cost per bottle: Rs {fmt(total_cost)}")
        except Exception as e:
            show_error(e)

    def draw_pyramid(self, rows):
        """Top / heart / base notes of this formula, drawn as the usual fragrance pyramid."""
        c = self.pyramid
        c.delete("all")
        groups = {"Top": [], "Middle": [], "Base": []}
        for r in rows:
            groups[r[3]].append(r[1])

        def half(y):                                   # half-width of the triangle at height y
            return 80 * (y - 20) / 260

        spec = [("Top", "Top notes", 20, 110, "#f7dde3"),
                ("Middle", "Heart notes", 110, 200, "#e3a3b4"),
                ("Base", "Base notes", 200, 280, "#9c4466")]
        for key, label, y1, y2, col in spec:
            c.create_polygon(90 - half(y1), y1, 90 + half(y1), y1, 90 + half(y2), y2, 90 - half(y2), y2,
                             fill=col, outline=PLUM)
            c.create_text(185, y1 + 8, anchor="nw", text=label, font=(SANS, 10, "bold"), fill=PLUM)
            c.create_text(185, y1 + 26, anchor="nw", text=", ".join(groups[key]) or "-",
                          width=150, font=(SANS, 9), fill=INK)

    def on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0])["values"]
        match = next((o for o in self.mat_cb["values"]
                      if o.split(" - ", 1)[0] == str(v[0])), "")
        self.mat_var.set(match)
        self.qty_var.set(str(v[4]))

    def save(self):
        if not self.mat_var.get():
            messagebox.showwarning("Material", "Choose a material.", parent=self)
            return
        try:
            qty = float(self.qty_var.get())
        except ValueError:
            messagebox.showwarning("Quantity", "Enter the quantity as a number.", parent=self)
            return
        try:
            self.db.execute("""
                INSERT INTO perfume_ingredient (perfume_id, material_id, qty_per_bottle_ml)
                VALUES (%s, %s, %s)
                ON CONFLICT (perfume_id, material_id)
                DO UPDATE SET qty_per_bottle_ml = EXCLUDED.qty_per_bottle_ml""",
                            (self.perfume_id, fk_id(self.mat_var.get()), qty))
        except Exception as e:
            show_error(e)
            return
        self.refresh()
        self.on_done()

    def remove(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select an ingredient row first.", parent=self)
            return
        mid = self.tree.item(sel[0])["values"][0]
        try:
            self.db.execute("DELETE FROM perfume_ingredient WHERE perfume_id=%s AND material_id=%s",
                            (self.perfume_id, mid))
        except Exception as e:
            show_error(e)
            return
        self.refresh()
        self.on_done()


def open_formula(tab):
    if not tab.selected_id:
        messagebox.showinfo("Select a perfume", "Click a perfume in the table first.")
        return
    name = tab.vars["perfume_name"].get()
    FormulaDialog(tab, tab.db, int(tab.selected_id), name, tab.refresh)


def complete_batch(tab):
    if not tab.selected_id:
        messagebox.showinfo("Select a batch", "Click a batch in the table first.")
        return
    if not messagebox.askyesno(
            "Complete batch",
            "Mark this batch as Completed?\n\nRaw materials will be consumed and the finished "
            "bottles added to stock. A completed batch can no longer be edited."):
        return
    tab.run_action("UPDATE production_batch SET status = 'Completed' WHERE batch_id = %s",
                   (tab.selected_id,), "Batch completed - stock updated.")


#  Orders: new-order dialog, payment dialog, orders tab
class NewOrderDialog(tk.Toplevel):
    def __init__(self, parent, db, on_done):
        super().__init__(parent)
        self.db, self.on_done = db, on_done
        self.title("New Order")
        self.geometry("760x560")
        self.transient(parent)
        self.after(50, self.grab_set)
        self.configure(bg=CREAM)
        self.cart = {}                                    # perfume_id -> quantity

        _, cust = db.fetch("SELECT customer_id, full_name FROM customer ORDER BY full_name")
        _, emps = db.fetch("SELECT employee_id, full_name FROM employee "
                           "WHERE role = 'Sales Executive' ORDER BY full_name")
        _, perf = db.fetch("SELECT perfume_id, perfume_name, selling_price, stock_qty "
                           "FROM perfume ORDER BY perfume_name")
        self.perfumes = {r[0]: {"name": r[1], "price": r[2], "stock": r[3]} for r in perf}

        top = ttk.LabelFrame(self, text="Order details", padding=10)
        top.pack(fill="x", padx=10, pady=10)
        self.cust_var, self.emp_var = tk.StringVar(), tk.StringVar()
        ttk.Label(top, text="Customer *").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Combobox(top, textvariable=self.cust_var, state="readonly", width=32,
                     values=[f"{r[0]} - {r[1]}" for r in cust]).grid(row=0, column=1, padx=4)
        ttk.Label(top, text="Sales executive *").grid(row=0, column=2, sticky="e", padx=4)
        ttk.Combobox(top, textvariable=self.emp_var, state="readonly", width=28,
                     values=[f"{r[0]} - {r[1]}" for r in emps]).grid(row=0, column=3, padx=4)

        add = ttk.LabelFrame(self, text="Add perfume", padding=10)
        add.pack(fill="x", padx=10)
        self.perf_var, self.qty_var = tk.StringVar(), tk.StringVar(value="1")
        ttk.Combobox(add, textvariable=self.perf_var, state="readonly", width=52,
                     values=[f"{pid} - {p['name']}  (Rs {fmt(p['price'])}, stock {p['stock']})"
                             for pid, p in self.perfumes.items()]).grid(row=0, column=0, padx=4)
        ttk.Label(add, text="Qty").grid(row=0, column=1, padx=4)
        ttk.Spinbox(add, from_=1, to=500, textvariable=self.qty_var, width=6).grid(row=0, column=2)
        ttk.Button(add, text="Add to Cart", command=self.add_item).grid(row=0, column=3, padx=8)

        frame, self.tree = make_tree(self, height=8)
        frame.pack(fill="both", expand=True, padx=10, pady=8)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        self.total_lbl = ttk.Label(bottom, text="Total: Rs 0.00", font=("Segoe UI", 12, "bold"),
                                   foreground=PLUM)
        self.total_lbl.pack(side="left")
        ttk.Button(bottom, text="Place Order", command=self.place).pack(side="right", padx=4)
        ttk.Button(bottom, text="Remove Selected", command=self.remove_item).pack(side="right", padx=4)
        ttk.Button(bottom, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        self.refresh_cart()

    def add_item(self):
        if not self.perf_var.get():
            messagebox.showwarning("Perfume", "Choose a perfume.", parent=self)
            return
        try:
            qty = int(self.qty_var.get())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Quantity", "Quantity must be a positive whole number.", parent=self)
            return
        pid = fk_id(self.perf_var.get())
        if self.cart.get(pid, 0) + qty > self.perfumes[pid]["stock"]:
            messagebox.showwarning("Stock", f"Only {self.perfumes[pid]['stock']} bottles of "
                                   f"{self.perfumes[pid]['name']} in stock.", parent=self)
            return
        self.cart[pid] = self.cart.get(pid, 0) + qty
        self.refresh_cart()

    def remove_item(self):
        sel = self.tree.selection()
        if sel:
            self.cart.pop(int(sel[0]), None)
            self.refresh_cart()

    def refresh_cart(self):
        cols = ["perfume", "quantity", "unit_price", "line_total"]
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = cols
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=150, anchor="w")
        total = Decimal(0)
        for i, (pid, q) in enumerate(self.cart.items()):
            p = self.perfumes[pid]
            line = p["price"] * q
            total += line
            self.tree.insert("", "end", iid=str(pid), tags=("odd" if i % 2 else "even",),
                             values=(p["name"], q, fmt(p["price"]), fmt(line)))
        self.total_lbl.config(text=f"Total: Rs {fmt(total)}")

    def place(self):
        if not self.cust_var.get() or not self.emp_var.get():
            messagebox.showwarning("Missing", "Choose a customer and a sales executive.", parent=self)
            return
        if not self.cart:
            messagebox.showwarning("Empty cart", "Add at least one perfume.", parent=self)
            return
        cid, eid = fk_id(self.cust_var.get()), fk_id(self.emp_var.get())

        def work(cur):
            cur.execute("INSERT INTO sales_order (customer_id, employee_id) "
                        "VALUES (%s, %s) RETURNING order_id", (cid, eid))
            oid = cur.fetchone()[0]
            for pid, q in self.cart.items():
                cur.execute("INSERT INTO order_item (order_id, perfume_id, quantity) "
                            "VALUES (%s, %s, %s)", (oid, pid, q))
            return oid

        try:
            oid = self.db.transaction(work)          # order + items in ONE transaction
        except Exception as e:
            messagebox.showerror("Could not place order", pretty_error(e), parent=self)
            return
        messagebox.showinfo("Order placed", f"Order #{oid} created (status: Pending).", parent=self)
        self.on_done()
        self.destroy()


class PaymentDialog(tk.Toplevel):
    def __init__(self, parent, db, order_id, balance, on_done):
        super().__init__(parent)
        self.db, self.order_id, self.on_done = db, order_id, on_done
        self.title("Record Payment")
        self.transient(parent)
        self.after(50, self.grab_set)
        self.configure(bg=CREAM)
        body = ttk.Frame(self, padding=20)
        body.pack()
        ttk.Label(body, text=f"Order #{order_id}  -  balance due: Rs {fmt(balance)}",
                  font=("Segoe UI", 11, "bold"), foreground=PLUM).grid(row=0, column=0, columnspan=2, pady=8)
        self.amount = tk.StringVar(value=fmt(balance))
        self.method = tk.StringVar(value="UPI")
        ttk.Label(body, text="Amount (Rs)").grid(row=1, column=0, sticky="e", pady=4, padx=4)
        ttk.Entry(body, textvariable=self.amount, width=18).grid(row=1, column=1, pady=4)
        ttk.Label(body, text="Method").grid(row=2, column=0, sticky="e", pady=4, padx=4)
        ttk.Combobox(body, textvariable=self.method, state="readonly", width=16,
                     values=["Cash", "Card", "UPI", "Net Banking"]).grid(row=2, column=1, pady=4)
        row = ttk.Frame(body)
        row.grid(row=3, column=0, columnspan=2, pady=12)
        ttk.Button(row, text="Pay", command=self.pay).pack(side="left", padx=4)
        ttk.Button(row, text="Cancel", command=self.destroy).pack(side="left", padx=4)

    def pay(self):
        try:
            amt = float(self.amount.get())
            if amt <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Amount", "Enter a positive amount.", parent=self)
            return
        try:
            self.db.execute("INSERT INTO payment (order_id, amount, method) VALUES (%s, %s, %s)",
                            (self.order_id, amt, self.method.get()))
        except Exception as e:
            messagebox.showerror("Payment failed", pretty_error(e), parent=self)
            return
        self.on_done()
        self.destroy()


class OrdersTab(ttk.Frame):
    def __init__(self, parent, db):
        super().__init__(parent, padding=8)
        self.db = db
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        for text, cmd in [("New Order", self.new_order), ("Record Payment", self.pay),
                          ("Mark Shipped", self.ship), ("Cancel Order", self.cancel),
                          ("Delete (cancelled only)", self.delete), ("Refresh", self.refresh)]:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.status = ttk.Label(bar, text="", style="Status.TLabel")
        self.status.pack(side="right")

        frame, self.tree = make_tree(self, height=10)
        frame.pack(fill="both", expand=True, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self.show_details)
        for tag, bg, fg in [("pending", "#fff1d6", INK), ("paid", "#e4f1e6", INK),
                            ("shipped", "#ece2f3", INK), ("cancelled", "#efefef", "#999999")]:
            self.tree.tag_configure(tag, background=bg, foreground=fg)

        lower = ttk.Frame(self)
        lower.pack(fill="both", expand=True)
        lower.columnconfigure(0, weight=3)
        lower.columnconfigure(1, weight=2)
        lower.rowconfigure(0, weight=1)
        lf = ttk.LabelFrame(lower, text="Items in selected order", padding=6)
        lf.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        f1, self.items_tree = make_tree(lf, height=6)
        f1.pack(fill="both", expand=True)
        rf = ttk.LabelFrame(lower, text="Payments for selected order", padding=6)
        rf.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        f2, self.pay_tree = make_tree(rf, height=6)
        f2.pack(fill="both", expand=True)

    def refresh(self):
        try:
            cols, rows = self.db.fetch("SELECT * FROM v_order_summary ORDER BY order_id DESC")
            fill_tree(self.tree, cols, rows)
            for iid in self.tree.get_children():          # colour rows by order status
                status = str(self.tree.item(iid)["values"][4]).lower()
                self.tree.item(iid, tags=(status,))
            fill_tree(self.items_tree, ["perfume", "quantity", "unit_price", "line_total"], [])
            fill_tree(self.pay_tree, ["payment_id", "amount", "method", "paid_on"], [])
            self.status.config(text=f"{len(rows)} order(s)")
        except Exception as e:
            show_error(e)

    def selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select an order", "Click an order in the table first.")
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def order_info(self, oid):
        _, rows = self.db.fetch("SELECT status, balance_due FROM v_order_summary WHERE order_id = %s",
                                (oid,))
        return rows[0]

    def show_details(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        oid = int(self.tree.item(sel[0])["values"][0])
        try:
            c, r = self.db.fetch("""
                SELECT p.perfume_name AS perfume, oi.quantity, oi.unit_price,
                       oi.quantity * oi.unit_price AS line_total
                FROM order_item oi JOIN perfume p ON p.perfume_id = oi.perfume_id
                WHERE oi.order_id = %s ORDER BY p.perfume_name""", (oid,))
            fill_tree(self.items_tree, c, r)
            c, r = self.db.fetch("SELECT payment_id, amount, method, paid_on FROM payment "
                                 "WHERE order_id = %s ORDER BY paid_on", (oid,))
            fill_tree(self.pay_tree, c, r)
        except Exception as e:
            show_error(e)

    def new_order(self):
        NewOrderDialog(self, self.db, self.refresh)

    def pay(self):
        oid = self.selected_id()
        if oid is None:
            return
        status, balance = self.order_info(oid)
        if status != "Pending":
            messagebox.showinfo("Payment", f"Order #{oid} is {status}; only Pending orders take payments.")
            return
        PaymentDialog(self, self.db, oid, balance, self.refresh)

    def _set_status(self, oid, new_status, msg):
        try:
            self.db.execute("UPDATE sales_order SET status = %s WHERE order_id = %s", (new_status, oid))
        except Exception as e:
            show_error(e)
            return
        self.refresh()
        self.status.config(text=msg)

    def ship(self):
        oid = self.selected_id()
        if oid is not None:
            self._set_status(oid, "Shipped", f"Order #{oid} marked as shipped.")

    def cancel(self):
        oid = self.selected_id()
        if oid is None:
            return
        if messagebox.askyesno("Cancel order", f"Cancel order #{oid}?\nBottles go back into stock."):
            self._set_status(oid, "Cancelled", f"Order #{oid} cancelled and stock restored.")

    def delete(self):
        oid = self.selected_id()
        if oid is None:
            return
        status, _ = self.order_info(oid)
        if status != "Cancelled":
            messagebox.showinfo("Delete", "Only cancelled orders can be deleted. Cancel it first.")
            return
        if not messagebox.askyesno("Delete order", f"Permanently delete order #{oid}?"):
            return
        try:
            self.db.execute("DELETE FROM sales_order WHERE order_id = %s", (oid,))
        except Exception as e:
            show_error(e)
            return
        self.refresh()
        self.status.config(text=f"Order #{oid} deleted.")


#  Dashboard
class DashboardTab(ttk.Frame):
    """Home page: recent orders, best sellers and the materials that need restocking.
    (The headline numbers live in the status line at the top of the window.)"""

    def __init__(self, parent, db):
        super().__init__(parent, padding=(6, 4))
        self.db = db
        grid = ttk.Frame(self)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=3)
        grid.columnconfigure(1, weight=2)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        self.trees = {}
        layout = [("recent", "Recent orders", 0, 0, 2),
                  ("top", "Top-selling perfumes", 0, 1, 1),
                  ("low", "Raw materials to reorder", 1, 1, 1)]
        for key, title, r, c, span in layout:
            lf = ttk.LabelFrame(grid, text=title, padding=10)
            lf.grid(row=r, column=c, rowspan=span, sticky="nsew", padx=6, pady=6)
            f, t = make_tree(lf, height=8)
            f.pack(fill="both", expand=True)
            self.trees[key] = t
        for tag, bg, fg in [("pending", "#fff1d6", INK), ("paid", "#e4f1e6", INK),
                            ("shipped", "#ece2f3", INK), ("cancelled", "#efefef", "#999999")]:
            self.trees["recent"].tag_configure(tag, background=bg, foreground=fg)
        ttk.Button(self, text="Refresh", command=self.refresh).pack(anchor="e", padx=6, pady=(4, 0))

    def refresh(self):
        try:
            cols, rows = self.db.fetch(
                "SELECT order_id, customer, order_date, status, total_amount, balance_due "
                "FROM v_order_summary ORDER BY order_id DESC LIMIT 15")
            fill_tree(self.trees["recent"], cols, rows)
            for iid in self.trees["recent"].get_children():
                status = str(self.trees["recent"].item(iid)["values"][3]).lower()
                self.trees["recent"].item(iid, tags=(status,))
            fill_tree(self.trees["top"], *self.db.fetch(
                "SELECT perfume_name, units_sold, revenue FROM v_perfume_sales "
                "ORDER BY units_sold DESC, revenue DESC LIMIT 10"))
            fill_tree(self.trees["low"], *self.db.fetch(
                "SELECT material_name, stock_ml, reorder_level FROM v_low_stock_materials"))
        except Exception as e:
            show_error(e)


#  Reports / SQL query showcase
REPORTS = [
    ("1. Perfumes priced above Rs 5000   [WHERE, ORDER BY]",
     """SELECT perfume_name, concentration, target_gender, selling_price
FROM perfume
WHERE selling_price > 5000
ORDER BY selling_price DESC"""),
    ("2. Price range per concentration   [MIN, MAX, COUNT, GROUP BY]",
     """SELECT concentration,
       COUNT(*)           AS perfumes,
       MIN(selling_price) AS cheapest,
       MAX(selling_price) AS costliest
FROM perfume
GROUP BY concentration
ORDER BY cheapest"""),
    ("3. Perfumes and average price per family   [JOIN, AVG, GROUP BY]",
     """SELECT f.family_name,
       COUNT(p.perfume_id)            AS perfumes,
       ROUND(AVG(p.selling_price), 2) AS avg_price
FROM fragrance_family f
LEFT JOIN perfume p ON p.family_id = f.family_id
GROUP BY f.family_name
ORDER BY perfumes DESC, f.family_name"""),
    ("4. Families whose average price exceeds Rs 4000   [HAVING]",
     """SELECT f.family_name, ROUND(AVG(p.selling_price), 2) AS avg_price
FROM fragrance_family f
JOIN perfume p ON p.family_id = f.family_id
GROUP BY f.family_name
HAVING AVG(p.selling_price) > 4000
ORDER BY avg_price DESC"""),
    ("5. Perfumes priced above the overall average   [SUBQUERY]",
     """SELECT perfume_name, selling_price
FROM perfume
WHERE selling_price > (SELECT AVG(selling_price) FROM perfume)
ORDER BY selling_price DESC"""),
    ("6. Catalogue with material cost and margin   [VIEW]",
     "SELECT * FROM v_perfume_catalog ORDER BY margin DESC"),
    ("7. Formula of every perfume   [3-TABLE JOIN]",
     """SELECT p.perfume_name, rm.material_name, rm.note_position, pi.qty_per_bottle_ml
FROM perfume p
JOIN perfume_ingredient pi ON pi.perfume_id = p.perfume_id
JOIN raw_material rm       ON rm.material_id = pi.material_id
ORDER BY p.perfume_name,
         CASE rm.note_position WHEN 'Top' THEN 1 WHEN 'Middle' THEN 2 ELSE 3 END"""),
    ("8. Orders with amount paid and balance due   [VIEW + JOIN]",
     "SELECT * FROM v_order_summary ORDER BY order_id"),
    ("9. Top customers by spending   [JOIN, SUM, COUNT, GROUP BY]",
     """SELECT c.full_name, c.city, c.loyalty_points,
       COUNT(o.order_id)   AS orders,
       SUM(o.total_amount) AS total_spent
FROM customer c
JOIN sales_order o ON o.customer_id = c.customer_id
WHERE o.status <> 'Cancelled'
GROUP BY c.customer_id, c.full_name, c.city, c.loyalty_points
ORDER BY total_spent DESC"""),
    ("10. Customers who never ordered   [NOT EXISTS subquery]",
     """SELECT customer_id, full_name, city, registered_on
FROM customer c
WHERE NOT EXISTS (SELECT 1 FROM sales_order o WHERE o.customer_id = c.customer_id)"""),
    ("11. Best-selling perfumes   [VIEW]",
     "SELECT * FROM v_perfume_sales ORDER BY units_sold DESC, revenue DESC"),
    ("12. Monthly revenue   [GROUP BY, TO_CHAR, SUM]",
     """SELECT TO_CHAR(order_date, 'YYYY-MM') AS month,
       COUNT(*)           AS orders,
       SUM(total_amount)  AS revenue
FROM sales_order
WHERE status <> 'Cancelled'
GROUP BY 1
ORDER BY 1"""),
    ("13. Sales executive performance   [LEFT JOIN, SUM]",
     """SELECT e.full_name AS sales_executive,
       COUNT(o.order_id)                  AS orders_handled,
       COALESCE(SUM(o.total_amount), 0)   AS revenue
FROM employee e
LEFT JOIN sales_order o ON o.employee_id = e.employee_id AND o.status <> 'Cancelled'
WHERE e.role = 'Sales Executive'
GROUP BY e.full_name
ORDER BY revenue DESC"""),
    ("14. Bottles produced per perfumer   [JOIN, SUM, COUNT]",
     """SELECT e.full_name AS perfumer,
       COUNT(b.batch_id) AS completed_batches,
       SUM(b.quantity)   AS bottles_produced
FROM production_batch b
JOIN employee e ON e.employee_id = b.perfumer_id
WHERE b.status = 'Completed'
GROUP BY e.full_name
ORDER BY bottles_produced DESC"""),
    ("15. Raw materials below reorder level   [VIEW]",
     "SELECT * FROM v_low_stock_materials ORDER BY stock_ml"),
    ("16. Stock value held per supplier   [JOIN, SUM, GROUP BY]",
     """SELECT s.name AS supplier,
       COUNT(rm.material_id) AS materials,
       ROUND(SUM(rm.stock_ml * rm.unit_cost_per_ml), 2) AS stock_value
FROM supplier s
JOIN raw_material rm ON rm.supplier_id = s.supplier_id
GROUP BY s.name
ORDER BY stock_value DESC"""),
]


class ReportsTab(ttk.Frame):
    def __init__(self, parent, db):
        super().__init__(parent, padding=8)
        self.db = db
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Choose a report / query:").pack(side="left")
        self.choice = tk.StringVar()
        cb = ttk.Combobox(top, textvariable=self.choice, state="readonly", width=85,
                          values=[t for t, _ in REPORTS])
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.run())
        ttk.Button(top, text="Run", command=self.run).pack(side="left")

        lf = ttk.LabelFrame(self, text="SQL", padding=6)
        lf.pack(fill="x", pady=8)
        self.sql_box = tk.Text(lf, height=8, font=("Consolas", 10), bg="#fffdf7", wrap="word")
        self.sql_box.pack(fill="x")
        self.sql_box.config(state="disabled")

        frame, self.tree = make_tree(self, height=12)
        frame.pack(fill="both", expand=True)
        self.status = ttk.Label(self, text="", style="Status.TLabel")
        self.status.pack(anchor="w", pady=4)

    def run(self):
        title = self.choice.get()
        if not title:
            return
        sql = dict(REPORTS)[title]
        self.sql_box.config(state="normal")
        self.sql_box.delete("1.0", "end")
        self.sql_box.insert("1.0", sql)
        self.sql_box.config(state="disabled")
        try:
            cols, rows = self.db.fetch(sql)
            fill_tree(self.tree, cols, rows)
            self.status.config(text=f"{len(rows)} row(s) returned")
        except Exception as e:
            show_error(e)

    def refresh(self):
        if self.choice.get():
            self.run()


#  Main application window
class App(tk.Tk):
    NAV = [("Dashboard", "Dashboard"), ("Perfumes", "Perfume Collection"), ("Families", "Fragrance Families"),
           ("Raw Materials", "Ingredients"), ("Suppliers", "Suppliers"), ("Purchases", "Purchases"),
           ("Production", "Blending & Batches"), ("Customers", "Customers"), ("Orders", "Orders"),
           ("Employees", "Staff"), ("Reports", "Reports")]

    STATUS_SQL = """
        SELECT (SELECT COUNT(*) FROM perfume),
               (SELECT COALESCE(SUM(stock_qty), 0) FROM perfume),
               (SELECT COUNT(*) FROM sales_order WHERE status = 'Pending'),
               (SELECT COUNT(*) FROM v_low_stock_materials),
               (SELECT COALESCE(SUM(p.amount), 0) FROM payment p
                  JOIN sales_order o ON o.order_id = p.order_id WHERE o.status <> 'Cancelled')"""

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        setup_style(self)
        self.current, self.pages, self.nav_items, self._tick_job = None, {}, {}, None
        self.show_login()

    # ---------- login screen
    def show_login(self):
        if self._tick_job:
            self.after_cancel(self._tick_job)
            self._tick_job = None
        for w in self.winfo_children():
            w.destroy()
        self.current, self.pages, self.nav_items = None, {}, {}
        self.minsize(1, 1)
        self.configure(bg=CREAM)
        self.geometry("420x520")
        box = ttk.Frame(self, padding=30)
        box.place(relx=0.5, rely=0.5, anchor="center")
        cv = tk.Canvas(box, width=120, height=120, bg=CREAM, highlightthickness=0)
        cv.grid(row=0, column=0, columnspan=2)
        draw_bottle(cv, 60, 4, 110)
        ttk.Label(box, text="Aroma House", font=(SERIF, 22, "bold"),
                  foreground=PLUM).grid(row=1, column=0, columnspan=2, pady=(6, 0))
        ttk.Label(box, text="Perfume & Fragrance Management", foreground=MUTED
                  ).grid(row=2, column=0, columnspan=2, pady=(0, 16))
        defaults = [("Host", os.getenv("PGHOST", "localhost")),
                    ("Port", os.getenv("PGPORT", "5432")),
                    ("Database", os.getenv("PGDATABASE", "perfume_house")),
                    ("User", os.getenv("PGUSER", "postgres")),
                    ("Password", os.getenv("PGPASSWORD", ""))]
        self.login_vars = {}
        for i, (label, val) in enumerate(defaults, start=3):
            ttk.Label(box, text=label).grid(row=i, column=0, sticky="e", padx=6, pady=5)
            var = tk.StringVar(value=val)
            e = ttk.Entry(box, textvariable=var, width=26, show="*" if label == "Password" else "")
            e.grid(row=i, column=1, pady=5)
            e.bind("<Return>", lambda _e: self.connect())
            self.login_vars[label] = var
        ttk.Button(box, text="Connect", command=self.connect).grid(row=8, column=0, columnspan=2, pady=16)

    def connect(self):
        v = {k: x.get().strip() for k, x in self.login_vars.items()}
        try:
            self.db = Database(v["Host"], v["Port"], v["Database"], v["User"],
                               self.login_vars["Password"].get())
        except Exception as e:
            messagebox.showerror("Connection failed", pretty_error(e))
            return
        self.build_main()

    def disconnect(self):
        try:
            self.db.conn.close()
        except Exception:
            pass
        self.show_login()

    # ---------- status line in the header (shown on every page)
    def update_status(self):
        try:
            _, rows = self.db.fetch(self.STATUS_SQL)
            n, stock, pending, low, revenue = rows[0]
            self.status_lbl.config(
                text=f"Perfumes: {n}   |   Bottles in stock: {stock}   |   Pending orders: {pending}"
                     f"   |   Low-stock materials: {low}   |   Revenue: Rs {revenue:,.0f}")
        except Exception:
            pass

    def _tick(self):
        if self.current is None:
            return
        self.update_status()
        self._tick_job = self.after(15000, self._tick)

    # ---------- main screen
    def build_main(self):
        for w in self.winfo_children():
            w.destroy()
        self.geometry("1320x800")
        self.minsize(1100, 680)
        db = self.db

        header = tk.Frame(self, bg=PLUM)
        header.pack(fill="x")
        logo = tk.Canvas(header, width=40, height=52, bg=PLUM, highlightthickness=0)
        logo.pack(side="left", padx=(14, 6), pady=4)
        draw_bottle(logo, 20, 4, 44, glass="#a34a6e", liquid=ROSE, line="#fbe8ee")
        tk.Label(header, text="Aroma House", font=(SERIF, 15, "bold"), fg="white", bg=PLUM).pack(side="left")
        self.status_lbl = tk.Label(header, text="", font=(SANS, 10), fg="#f8e1e7", bg=PLUM)
        self.status_lbl.pack(side="right", padx=14)

        body = tk.Frame(self, bg=CREAM)
        body.pack(fill="both", expand=True)
        side = tk.Frame(body, bg=SIDE, width=210)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        ttk.Button(side, text="Log out", command=self.disconnect).pack(side="bottom", pady=(0, 12))
        tk.Label(side, text=f"Connected to\n{db.info}", font=(SANS, 8), fg="#d9aebb", bg=SIDE,
                 justify="center").pack(side="bottom", pady=6)
        tk.Frame(side, bg=SIDE, height=10).pack()

        main = tk.Frame(body, bg=CREAM)
        main.pack(side="left", fill="both", expand=True)
        self.page_title = tk.Label(main, text="", font=(SERIF, 18, "bold"), fg=PLUM, bg=CREAM)
        self.page_title.pack(anchor="w", padx=24, pady=(18, 4))
        self.content = ttk.Frame(main)
        self.content.pack(fill="both", expand=True, padx=18, pady=(4, 12))
        c = self.content

        pages = [
            ("Dashboard", DashboardTab(c, db)),
            ("Perfumes", CrudTab(
                c, db, "perfume", "perfume_id", "SELECT * FROM v_perfume_catalog",
                [dict(col="perfume_name", label="Perfume name", kind="text"),
                 dict(col="family_id", label="Fragrance family", kind="fk",
                      sql="SELECT family_id, family_name FROM fragrance_family ORDER BY 2"),
                 dict(col="concentration", label="Concentration", kind="choice",
                      choices=["Eau de Cologne", "Eau de Toilette", "Eau de Parfum", "Parfum"]),
                 dict(col="target_gender", label="Target gender", kind="choice",
                      choices=["Men", "Women", "Unisex"]),
                 dict(col="bottle_size_ml", label="Bottle size (ml)", kind="int"),
                 dict(col="selling_price", label="Selling price (Rs)", kind="num"),
                 dict(col="launch_date", label="Launch date", kind="date",
                      required=False, default="today")],
                extra_buttons=[("Edit Formula (ingredients)", open_formula)])),
            ("Families", CrudTab(
                c, db, "fragrance_family", "family_id",
                "SELECT * FROM fragrance_family",
                [dict(col="family_name", label="Family name", kind="text"),
                 dict(col="description", label="Description", kind="text", required=False)])),
            ("Raw Materials", CrudTab(
                c, db, "raw_material", "material_id",
                """SELECT m.material_id, m.material_name, m.material_type, m.note_position,
                          m.unit_cost_per_ml, m.stock_ml, m.reorder_level, s.name AS supplier
                   FROM raw_material m LEFT JOIN supplier s ON s.supplier_id = m.supplier_id""",
                [dict(col="material_name", label="Material name", kind="text"),
                 dict(col="material_type", label="Type", kind="choice", choices=["Natural", "Synthetic"]),
                 dict(col="note_position", label="Note position", kind="choice",
                      choices=["Top", "Middle", "Base"]),
                 dict(col="unit_cost_per_ml", label="Cost per ml (Rs)", kind="num"),
                 dict(col="stock_ml", label="Stock (ml)", kind="num", default="0"),
                 dict(col="reorder_level", label="Reorder level (ml)", kind="num", default="100"),
                 dict(col="supplier_id", label="Supplier", kind="fk", required=False,
                      sql="SELECT supplier_id, name FROM supplier ORDER BY 2")])),
            ("Suppliers", CrudTab(
                c, db, "supplier", "supplier_id", "SELECT * FROM supplier",
                [dict(col="name", label="Supplier name", kind="text"),
                 dict(col="contact_person", label="Contact person", kind="text", required=False),
                 dict(col="phone", label="Phone", kind="text", required=False),
                 dict(col="email", label="Email", kind="text", required=False),
                 dict(col="city", label="City", kind="text", required=False),
                 dict(col="country", label="Country", kind="text", default="India")])),
            ("Purchases", CrudTab(
                c, db, "material_purchase", "purchase_id",
                """SELECT mp.purchase_id, mp.purchase_date, s.name AS supplier, rm.material_name,
                          mp.quantity_ml, mp.unit_cost_per_ml,
                          mp.quantity_ml * mp.unit_cost_per_ml AS total_cost
                   FROM material_purchase mp
                   JOIN supplier s      ON s.supplier_id = mp.supplier_id
                   JOIN raw_material rm ON rm.material_id = mp.material_id""",
                [dict(col="supplier_id", label="Supplier", kind="fk",
                      sql="SELECT supplier_id, name FROM supplier ORDER BY 2"),
                 dict(col="material_id", label="Material", kind="fk",
                      sql="SELECT material_id, material_name FROM raw_material ORDER BY 2"),
                 dict(col="quantity_ml", label="Quantity (ml)", kind="num"),
                 dict(col="unit_cost_per_ml", label="Cost per ml (Rs)", kind="num"),
                 dict(col="purchase_date", label="Purchase date", kind="date", default="today")],
                order="1 DESC", allow_update=False, allow_delete=False)),
            ("Production", CrudTab(
                c, db, "production_batch", "batch_id",
                """SELECT b.batch_id, p.perfume_name, e.full_name AS perfumer,
                          b.batch_date, b.quantity, b.status
                   FROM production_batch b
                   JOIN perfume p  ON p.perfume_id = b.perfume_id
                   JOIN employee e ON e.employee_id = b.perfumer_id""",
                [dict(col="perfume_id", label="Perfume", kind="fk",
                      sql="SELECT perfume_id, perfume_name FROM perfume ORDER BY 2"),
                 dict(col="perfumer_id", label="Perfumer", kind="fk",
                      sql="SELECT employee_id, full_name FROM employee WHERE role = 'Perfumer' ORDER BY 2"),
                 dict(col="batch_date", label="Batch date", kind="date", default="today"),
                 dict(col="quantity", label="Bottles to make", kind="int"),
                 dict(col="status", label="Status", kind="choice", default="Planned",
                      choices=["Planned", "In Progress", "Completed", "Cancelled"])],
                order="1 DESC", extra_buttons=[("Mark Completed", complete_batch)])),
            ("Customers", CrudTab(
                c, db, "customer", "customer_id", "SELECT * FROM customer",
                [dict(col="full_name", label="Full name", kind="text"),
                 dict(col="email", label="Email", kind="text"),
                 dict(col="phone", label="Phone", kind="text", required=False),
                 dict(col="city", label="City", kind="text", required=False),
                 dict(col="registered_on", label="Registered on", kind="date", default="today")])),
            ("Orders", OrdersTab(c, db)),
            ("Employees", CrudTab(
                c, db, "employee", "employee_id", "SELECT * FROM employee",
                [dict(col="full_name", label="Full name", kind="text"),
                 dict(col="role", label="Role", kind="choice",
                      choices=["Perfumer", "Lab Technician", "Sales Executive", "Manager"]),
                 dict(col="email", label="Email", kind="text"),
                 dict(col="phone", label="Phone", kind="text", required=False),
                 dict(col="salary", label="Salary (Rs)", kind="num"),
                 dict(col="hire_date", label="Hire date", kind="date", default="today")])),
            ("Reports", ReportsTab(c, db)),
        ]
        self.pages = dict(pages)
        for key, label in self.NAV:
            item = NavButton(side, label, lambda k=key: self.show_page(k))
            item.pack(fill="x")
            self.nav_items[key] = item
        self.show_page("Dashboard")
        self._tick_job = self.after(15000, self._tick)

    def show_page(self, key):
        """Swap the visible page and reload its data so it is always up to date."""
        if self.current:
            self.pages[self.current].pack_forget()
            self.nav_items[self.current].set_active(False)
        self.current = key
        self.nav_items[key].set_active(True)
        self.page_title.config(text=dict(self.NAV)[key])
        page = self.pages[key]
        page.pack(fill="both", expand=True)
        if hasattr(page, "refresh"):
            page.refresh()
        self.update_status()


if __name__ == "__main__":
    App().mainloop()