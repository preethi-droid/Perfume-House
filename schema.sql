--  HOW TO RUN
--    1.  createdb -U postgres perfume_house
--    2.  psql -U postgres -d perfume_house -f schema.sql
--  (The script is re-runnable: it drops and recreates everything.)

-- 0. CLEAN-UP
DROP VIEW  IF EXISTS v_perfume_catalog, v_order_summary, v_low_stock_materials, v_perfume_sales CASCADE;
DROP TABLE IF EXISTS payment, order_item, sales_order, customer,
                     material_purchase, production_batch, perfume_ingredient,
                     perfume, raw_material, employee, fragrance_family, supplier CASCADE;

-- 1. TABLES

CREATE TABLE supplier (
    supplier_id     SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    contact_person  VARCHAR(100),
    phone           VARCHAR(25),
    email           VARCHAR(100) UNIQUE,
    city            VARCHAR(50),
    country         VARCHAR(50)  NOT NULL DEFAULT 'India'
);

CREATE TABLE fragrance_family (
    family_id    SERIAL PRIMARY KEY,
    family_name  VARCHAR(50) NOT NULL UNIQUE,
    description  TEXT
);

CREATE TABLE employee (
    employee_id  SERIAL PRIMARY KEY,
    full_name    VARCHAR(100) NOT NULL,
    role         VARCHAR(20)  NOT NULL
                 CHECK (role IN ('Perfumer', 'Lab Technician', 'Sales Executive', 'Manager')),
    email        VARCHAR(100) NOT NULL UNIQUE,
    phone        VARCHAR(25),
    salary       NUMERIC(10,2) NOT NULL CHECK (salary > 0),
    hire_date    DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE raw_material (
    material_id        SERIAL PRIMARY KEY,
    material_name      VARCHAR(100) NOT NULL UNIQUE,
    material_type      VARCHAR(10)  NOT NULL CHECK (material_type IN ('Natural', 'Synthetic')),
    note_position      VARCHAR(10)  NOT NULL CHECK (note_position IN ('Top', 'Middle', 'Base')),
    unit_cost_per_ml   NUMERIC(10,2) NOT NULL CHECK (unit_cost_per_ml > 0),
    stock_ml           NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (stock_ml >= 0),
    reorder_level      NUMERIC(12,2) NOT NULL DEFAULT 100 CHECK (reorder_level >= 0),
    supplier_id        INT REFERENCES supplier(supplier_id)
);

CREATE TABLE perfume (
    perfume_id       SERIAL PRIMARY KEY,
    perfume_name     VARCHAR(100) NOT NULL UNIQUE,
    family_id        INT NOT NULL REFERENCES fragrance_family(family_id),
    concentration    VARCHAR(20) NOT NULL
                     CHECK (concentration IN ('Eau de Cologne', 'Eau de Toilette', 'Eau de Parfum', 'Parfum')),
    target_gender    VARCHAR(10) NOT NULL CHECK (target_gender IN ('Men', 'Women', 'Unisex')),
    bottle_size_ml   INT NOT NULL CHECK (bottle_size_ml > 0),
    selling_price    NUMERIC(10,2) NOT NULL CHECK (selling_price > 0),
    stock_qty        INT NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
    launch_date      DATE
);

-- Formula (recipe) of a perfume: M:N between perfume and raw_material
CREATE TABLE perfume_ingredient (
    perfume_id         INT NOT NULL REFERENCES perfume(perfume_id) ON DELETE CASCADE,
    material_id        INT NOT NULL REFERENCES raw_material(material_id),
    qty_per_bottle_ml  NUMERIC(8,3) NOT NULL CHECK (qty_per_bottle_ml > 0),
    PRIMARY KEY (perfume_id, material_id)
);

CREATE TABLE production_batch (
    batch_id     SERIAL PRIMARY KEY,
    perfume_id   INT NOT NULL REFERENCES perfume(perfume_id),
    perfumer_id  INT NOT NULL REFERENCES employee(employee_id),
    batch_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    quantity     INT  NOT NULL CHECK (quantity > 0),
    status       VARCHAR(15) NOT NULL DEFAULT 'Planned'
                 CHECK (status IN ('Planned', 'In Progress', 'Completed', 'Cancelled'))
);

CREATE TABLE material_purchase (
    purchase_id       SERIAL PRIMARY KEY,
    supplier_id       INT NOT NULL REFERENCES supplier(supplier_id),
    material_id       INT NOT NULL REFERENCES raw_material(material_id),
    quantity_ml       NUMERIC(12,2) NOT NULL CHECK (quantity_ml > 0),
    unit_cost_per_ml  NUMERIC(10,2) NOT NULL CHECK (unit_cost_per_ml > 0),
    purchase_date     DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE customer (
    customer_id     SERIAL PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(100) NOT NULL UNIQUE,
    phone           VARCHAR(25),
    city            VARCHAR(50),
    loyalty_points  INT NOT NULL DEFAULT 0 CHECK (loyalty_points >= 0),
    registered_on   DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE sales_order (
    order_id      SERIAL PRIMARY KEY,
    customer_id   INT NOT NULL REFERENCES customer(customer_id),
    employee_id   INT REFERENCES employee(employee_id),
    order_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    status        VARCHAR(10) NOT NULL DEFAULT 'Pending'
                  CHECK (status IN ('Pending', 'Paid', 'Shipped', 'Cancelled')),
    total_amount  NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0)
);

CREATE TABLE order_item (
    order_id    INT NOT NULL REFERENCES sales_order(order_id) ON DELETE CASCADE,
    perfume_id  INT NOT NULL REFERENCES perfume(perfume_id),
    quantity    INT NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(10,2) NOT NULL CHECK (unit_price > 0),
    PRIMARY KEY (order_id, perfume_id)
);

CREATE TABLE payment (
    payment_id  SERIAL PRIMARY KEY,
    order_id    INT NOT NULL REFERENCES sales_order(order_id) ON DELETE CASCADE,
    amount      NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    method      VARCHAR(15) NOT NULL CHECK (method IN ('Cash', 'Card', 'UPI', 'Net Banking')),
    paid_on     TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 2. INDEXES (on foreign keys / frequently searched columns)
CREATE INDEX idx_material_supplier ON raw_material(supplier_id);
CREATE INDEX idx_perfume_family    ON perfume(family_id);
CREATE INDEX idx_batch_perfume     ON production_batch(perfume_id);
CREATE INDEX idx_order_customer    ON sales_order(customer_id);
CREATE INDEX idx_order_date        ON sales_order(order_date);
CREATE INDEX idx_item_perfume      ON order_item(perfume_id);
CREATE INDEX idx_payment_order     ON payment(order_id);

-- 3. VIEWS

-- Perfume catalogue with ingredient cost and profit margin per bottle
CREATE VIEW v_perfume_catalog AS
SELECT  p.perfume_id,
        p.perfume_name,
        f.family_name,
        p.concentration,
        p.target_gender,
        p.bottle_size_ml,
        p.selling_price,
        p.stock_qty,
        ROUND(COALESCE(SUM(pi.qty_per_bottle_ml * rm.unit_cost_per_ml), 0), 2)                AS material_cost,
        ROUND(p.selling_price - COALESCE(SUM(pi.qty_per_bottle_ml * rm.unit_cost_per_ml), 0), 2) AS margin
FROM perfume p
JOIN fragrance_family f           ON f.family_id = p.family_id
LEFT JOIN perfume_ingredient pi   ON pi.perfume_id = p.perfume_id
LEFT JOIN raw_material rm         ON rm.material_id = pi.material_id
GROUP BY p.perfume_id, f.family_name;

-- Orders with customer, salesperson and payment status
CREATE VIEW v_order_summary AS
SELECT  o.order_id,
        c.full_name                              AS customer,
        e.full_name                              AS sales_executive,
        o.order_date,
        o.status,
        o.total_amount,
        COALESCE(pay.paid, 0)                    AS amount_paid,
        o.total_amount - COALESCE(pay.paid, 0)   AS balance_due
FROM sales_order o
JOIN customer c            ON c.customer_id = o.customer_id
LEFT JOIN employee e       ON e.employee_id = o.employee_id
LEFT JOIN (SELECT order_id, SUM(amount) AS paid
           FROM payment GROUP BY order_id) pay ON pay.order_id = o.order_id;

-- Raw materials that need restocking
CREATE VIEW v_low_stock_materials AS
SELECT  m.material_id,
        m.material_name,
        m.stock_ml,
        m.reorder_level,
        s.name AS supplier
FROM raw_material m
LEFT JOIN supplier s ON s.supplier_id = m.supplier_id
WHERE m.stock_ml <= m.reorder_level;

-- Units sold and revenue per perfume (cancelled orders excluded)
CREATE VIEW v_perfume_sales AS
SELECT  p.perfume_id,
        p.perfume_name,
        COALESCE(SUM(x.quantity), 0)                 AS units_sold,
        COALESCE(SUM(x.quantity * x.unit_price), 0)  AS revenue
FROM perfume p
LEFT JOIN (SELECT oi.perfume_id, oi.quantity, oi.unit_price
           FROM order_item oi
           JOIN sales_order o ON o.order_id = oi.order_id
           WHERE o.status <> 'Cancelled') x ON x.perfume_id = p.perfume_id
GROUP BY p.perfume_id, p.perfume_name;

-- 4. TRIGGERS  (business rules enforced inside the database)

-- 4.1  Order item: default the unit price from the perfume's current price
CREATE OR REPLACE FUNCTION fn_order_item_before() RETURNS trigger AS $$
BEGIN
    IF NEW.unit_price IS NULL THEN
        SELECT selling_price INTO NEW.unit_price
        FROM perfume WHERE perfume_id = NEW.perfume_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_order_item_before
BEFORE INSERT ON order_item
FOR EACH ROW EXECUTE FUNCTION fn_order_item_before();

-- 4.2  Order item: reduce stock, refuse if insufficient, recompute order total
CREATE OR REPLACE FUNCTION fn_order_item_after() RETURNS trigger AS $$
DECLARE
    v_status VARCHAR(10);
    v_name   VARCHAR(100);
BEGIN
    SELECT status INTO v_status FROM sales_order WHERE order_id = NEW.order_id;
    IF v_status <> 'Pending' THEN
        RAISE EXCEPTION 'Items can only be added to a Pending order (order % is %)', NEW.order_id, v_status;
    END IF;

    UPDATE perfume
       SET stock_qty = stock_qty - NEW.quantity
     WHERE perfume_id = NEW.perfume_id
       AND stock_qty >= NEW.quantity;
    IF NOT FOUND THEN
        SELECT perfume_name INTO v_name FROM perfume WHERE perfume_id = NEW.perfume_id;
        RAISE EXCEPTION 'Insufficient stock for perfume "%"', v_name;
    END IF;

    UPDATE sales_order
       SET total_amount = (SELECT SUM(quantity * unit_price)
                           FROM order_item WHERE order_id = NEW.order_id)
     WHERE order_id = NEW.order_id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_order_item_after
AFTER INSERT ON order_item
FOR EACH ROW EXECUTE FUNCTION fn_order_item_after();

-- 4.3  Payment: validate, mark the order Paid when fully settled, award loyalty points
CREATE OR REPLACE FUNCTION fn_payment_after() RETURNS trigger AS $$
DECLARE
    v_total  NUMERIC(12,2);
    v_status VARCHAR(10);
    v_cust   INT;
    v_paid   NUMERIC(12,2);
BEGIN
    SELECT total_amount, status, customer_id INTO v_total, v_status, v_cust
    FROM sales_order WHERE order_id = NEW.order_id;

    IF v_status = 'Cancelled' THEN
        RAISE EXCEPTION 'Cannot accept payment for a cancelled order';
    END IF;

    SELECT SUM(amount) INTO v_paid FROM payment WHERE order_id = NEW.order_id;
    IF v_paid > v_total THEN
        RAISE EXCEPTION 'Payment exceeds the balance due (order total %, already paid before this %)',
                        v_total, v_paid - NEW.amount;
    END IF;

    IF v_paid = v_total AND v_status = 'Pending' THEN
        UPDATE sales_order SET status = 'Paid' WHERE order_id = NEW.order_id;
        UPDATE customer
           SET loyalty_points = loyalty_points + FLOOR(v_total / 100)::INT
         WHERE customer_id = v_cust;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_payment_after
AFTER INSERT ON payment
FOR EACH ROW EXECUTE FUNCTION fn_payment_after();

-- 4.4  Order status changes: valid transitions, restock on cancellation
CREATE OR REPLACE FUNCTION fn_order_status_change() RETURNS trigger AS $$
BEGIN
    IF OLD.status = NEW.status THEN
        RETURN NULL;
    END IF;
    IF OLD.status = 'Cancelled' THEN
        RAISE EXCEPTION 'A cancelled order cannot be reopened';
    END IF;
    IF NEW.status = 'Shipped' AND OLD.status <> 'Paid' THEN
        RAISE EXCEPTION 'Only fully paid orders can be shipped';
    END IF;
    IF NEW.status = 'Cancelled' THEN
        IF OLD.status = 'Shipped' THEN
            RAISE EXCEPTION 'Shipped orders cannot be cancelled';
        END IF;
        -- return the bottles to stock
        UPDATE perfume p
           SET stock_qty = p.stock_qty + oi.quantity
          FROM order_item oi
         WHERE oi.order_id = NEW.order_id AND oi.perfume_id = p.perfume_id;
        -- take back loyalty points if they had been awarded
        IF OLD.status = 'Paid' THEN
            UPDATE customer
               SET loyalty_points = GREATEST(0, loyalty_points - FLOOR(NEW.total_amount / 100)::INT)
             WHERE customer_id = NEW.customer_id;
        END IF;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_order_status_change
AFTER UPDATE OF status ON sales_order
FOR EACH ROW EXECUTE FUNCTION fn_order_status_change();

-- 4.5  Material purchase: add to stock and remember the latest unit cost
CREATE OR REPLACE FUNCTION fn_purchase_after() RETURNS trigger AS $$
BEGIN
    UPDATE raw_material
       SET stock_ml = stock_ml + NEW.quantity_ml,
           unit_cost_per_ml = NEW.unit_cost_per_ml
     WHERE material_id = NEW.material_id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_purchase_after
AFTER INSERT ON material_purchase
FOR EACH ROW EXECUTE FUNCTION fn_purchase_after();

-- 4.6  Production batch: completed batches are locked
CREATE OR REPLACE FUNCTION fn_batch_lock() RETURNS trigger AS $$
BEGIN
    IF OLD.status = 'Completed' THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'A completed batch cannot be deleted';
        END IF;
        IF NEW.perfume_id <> OLD.perfume_id OR NEW.quantity <> OLD.quantity
           OR NEW.status <> 'Completed' THEN
            RAISE EXCEPTION 'A completed batch cannot be modified';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_batch_lock
BEFORE UPDATE OR DELETE ON production_batch
FOR EACH ROW EXECUTE FUNCTION fn_batch_lock();

-- 4.7  Production batch completion: consume raw materials, add finished bottles
CREATE OR REPLACE FUNCTION fn_batch_complete() RETURNS trigger AS $$
DECLARE
    v_was_done BOOLEAN := FALSE;
    v_short    VARCHAR(100);
BEGIN
    IF TG_OP = 'UPDATE' THEN
        v_was_done := (OLD.status = 'Completed');
    END IF;

    IF NEW.status = 'Completed' AND NOT v_was_done THEN
        -- is there enough of every ingredient?
        SELECT rm.material_name INTO v_short
        FROM perfume_ingredient pi
        JOIN raw_material rm ON rm.material_id = pi.material_id
        WHERE pi.perfume_id = NEW.perfume_id
          AND rm.stock_ml < pi.qty_per_bottle_ml * NEW.quantity
        LIMIT 1;
        IF v_short IS NOT NULL THEN
            RAISE EXCEPTION 'Not enough "%" in stock to complete this batch', v_short;
        END IF;

        UPDATE raw_material rm
           SET stock_ml = rm.stock_ml - pi.qty_per_bottle_ml * NEW.quantity
          FROM perfume_ingredient pi
         WHERE pi.perfume_id = NEW.perfume_id AND pi.material_id = rm.material_id;

        UPDATE perfume
           SET stock_qty = stock_qty + NEW.quantity
         WHERE perfume_id = NEW.perfume_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_batch_complete
AFTER INSERT OR UPDATE OF status ON production_batch
FOR EACH ROW EXECUTE FUNCTION fn_batch_complete();

-- 5. SAMPLE DATA
--    (order matters: triggers update stock / totals as rows are inserted)

INSERT INTO supplier (name, contact_person, phone, email, city, country) VALUES
('Grasse Aromatics',            'Claire Dubois',      '+33-493-555-0101',  'sales@grasse-aromatics.fr', 'Grasse',    'France'),
('Mysore Sandal Traders',       'R. Venkatesh',       '+91-98450-11223',   'info@mysoresandal.in',      'Mysuru',    'India'),
('Kannauj Attar Co.',           'Imran Siddiqui',     '+91-98390-44556',   'contact@kannaujattar.in',   'Kannauj',   'India'),
('Givaudan Distribution India', 'Anita Rao',          '+91-80-4000-1234',  'anita.rao@gdi.in',          'Bengaluru', 'India'),
('Oud Emirates Trading',        'Khalid Al Mansoori', '+971-4-555-0199',   'khalid@oudemirates.ae',     'Dubai',     'United Arab Emirates');

INSERT INTO fragrance_family (family_name, description) VALUES
('Floral',   'Blooms such as jasmine, rose and ylang-ylang'),
('Woody',    'Warm notes of sandalwood, cedar and vetiver'),
('Oriental', 'Rich, spicy and resinous blends with oud and amber'),
('Fresh',    'Clean aquatic and aromatic accords'),
('Citrus',   'Sparkling bergamot, lemon and orange'),
('Gourmand', 'Sweet edible notes like vanilla and caramel');

INSERT INTO employee (full_name, role, email, phone, salary, hire_date) VALUES
('Priya Raman',        'Perfumer',        'priya.raman@aromahouse.in',   '+91-98400-10001',  85000, '2019-04-15'),
('Arjun Mehta',        'Perfumer',        'arjun.mehta@aromahouse.in',   '+91-98400-10002',  78000, '2020-08-03'),
('Sneha Iyer',         'Lab Technician',  'sneha.iyer@aromahouse.in',    '+91-98400-10003',  45000, '2021-01-11'),
('Karthik Subramanian','Sales Executive', 'karthik.s@aromahouse.in',     '+91-98400-10004',  38000, '2022-06-20'),
('Divya Nair',         'Sales Executive', 'divya.nair@aromahouse.in',    '+91-98400-10005',  36000, '2023-02-01'),
('Rahul Menon',        'Manager',         'rahul.menon@aromahouse.in',   '+91-98400-10006', 120000, '2018-01-08');

INSERT INTO raw_material (material_name, material_type, note_position, unit_cost_per_ml, stock_ml, reorder_level, supplier_id) VALUES
('Bergamot Oil',       'Natural',   'Top',    18.50, 3000, 500, 1),   -- 1
('Lemon Oil',          'Natural',   'Top',    12.00, 2500, 400, 1),   -- 2
('Lavender Absolute',  'Natural',   'Middle', 25.00, 2000, 400, 1),   -- 3
('Jasmine Absolute',   'Natural',   'Middle',150.00,  800, 200, 1),   -- 4
('Rose Otto',          'Natural',   'Middle',220.00,  280, 150, 3),   -- 5
('Sandalwood Oil',     'Natural',   'Base',  180.00, 1500, 300, 2),   -- 6
('Oud Oil',            'Natural',   'Base',  450.00,  150, 100, 5),   -- 7
('Vetiver Oil',        'Natural',   'Base',   60.00, 1800, 300, 3),   -- 8
('Ambroxan',           'Synthetic', 'Base',   35.00, 3000, 500, 4),   -- 9
('Hedione',            'Synthetic', 'Middle', 22.00, 3500, 500, 4),   -- 10
('Iso E Super',        'Synthetic', 'Base',   15.00, 4000, 600, 4),   -- 11
('Vanilla Absolute',   'Natural',   'Base',   90.00, 1200, 250, 4);   -- 12

-- stock_qty starts at 0; it grows when production batches are completed
INSERT INTO perfume (perfume_name, family_id, concentration, target_gender, bottle_size_ml, selling_price, launch_date) VALUES
('Chennai Jasmine Nights', 1, 'Eau de Parfum',   'Women',  50, 4200, '2024-02-14'),  -- 1
('Royal Mysore Sandal',    2, 'Parfum',          'Unisex', 30, 6800, '2023-11-01'),  -- 2
('Midnight Oud',           3, 'Parfum',          'Unisex', 50, 9500, '2024-09-20'),  -- 3
('Ocean Breeze',           4, 'Eau de Toilette', 'Men',   100, 2800, '2023-05-10'),  -- 4
('Citrus Dawn',            5, 'Eau de Cologne',  'Unisex',100, 1800, '2023-03-21'),  -- 5
('Vanilla Velvet',         6, 'Eau de Parfum',   'Women',  50, 3900, '2025-01-30'),  -- 6
('Rose Reverie',           1, 'Eau de Parfum',   'Women',  50, 5200, '2025-02-14'),  -- 7
('Vetiver Noir',           2, 'Eau de Toilette', 'Men',   100, 3500, '2024-06-05');  -- 8

-- Formulas: ml of each material per bottle
INSERT INTO perfume_ingredient (perfume_id, material_id, qty_per_bottle_ml) VALUES
(1, 4, 3.0), (1, 1, 1.0), (1, 10, 2.0), (1, 9, 1.0),
(2, 6, 4.0), (2, 8, 0.5), (2, 11, 1.5),
(3, 7, 2.0), (3, 5, 1.0), (3, 6, 1.5), (3, 9, 1.5),
(4, 1, 2.0), (4, 3, 1.5), (4, 11, 2.0), (4, 9, 1.0),
(5, 2, 3.0), (5, 1, 2.0), (5, 10, 1.0), (5, 8, 0.5),
(6, 12, 2.5), (6, 6, 1.0), (6, 4, 0.5), (6, 9, 1.0),
(7, 5, 1.5), (7, 4, 1.0), (7, 10, 2.0), (7, 1, 0.5),
(8, 8, 3.0), (8, 1, 1.5), (8, 11, 3.0), (8, 3, 1.0);

-- Completed batches consume materials & add finished stock via trigger
INSERT INTO production_batch (perfume_id, perfumer_id, batch_date, quantity, status) VALUES
(1, 1, '2026-06-02', 100, 'Completed'),
(2, 1, '2026-06-05',  60, 'Completed'),
(3, 2, '2026-06-10',  40, 'Completed'),
(4, 2, '2026-06-15', 150, 'Completed'),
(5, 1, '2026-06-20', 200, 'Completed'),
(6, 2, '2026-07-01',  80, 'Completed'),
(7, 1, '2026-07-08',  70, 'Completed'),
(8, 2, '2026-07-15',  90, 'Completed'),
(3, 2, '2026-10-20',  20, 'In Progress'),
(2, 1, '2026-11-05',  30, 'Planned');

-- Restocking raw materials (trigger adds to stock)
INSERT INTO material_purchase (supplier_id, material_id, quantity_ml, unit_cost_per_ml, purchase_date) VALUES
(1, 4, 200, 148.00, '2026-08-01'),
(2, 6, 300, 175.00, '2026-08-10'),
(1, 1, 500,  18.00, '2026-09-05');

INSERT INTO customer (full_name, email, phone, city, registered_on) VALUES
('Aditi Sharma',      'aditi.sharma@example.com',   '+91-98765-00001', 'Chennai',    '2026-07-20'),
('Rohan Verma',       'rohan.verma@example.com',    '+91-98765-00002', 'Mumbai',     '2026-07-25'),
('Meera Krishnan',    'meera.k@example.com',        '+91-98765-00003', 'Chennai',    '2026-08-15'),
('Vikram Singh',      'vikram.singh@example.com',   '+91-98765-00004', 'Delhi',      '2026-08-30'),
('Ananya Das',        'ananya.das@example.com',     '+91-98765-00005', 'Kolkata',    '2026-09-10'),
('Suresh Babu',       'suresh.babu@example.com',    '+91-98765-00006', 'Coimbatore', '2026-09-22'),
('Fatima Sheikh',     'fatima.sheikh@example.com',  '+91-98765-00007', 'Hyderabad',  '2026-10-02'),
('Lakshmi Narayanan', 'lakshmi.n@example.com',      '+91-98765-00008', 'Chennai',    '2026-10-12');

INSERT INTO sales_order (customer_id, employee_id, order_date) VALUES
(1, 4, '2026-08-05'),   -- 1
(2, 5, '2026-08-12'),   -- 2
(3, 4, '2026-09-02'),   -- 3
(4, 5, '2026-09-15'),   -- 4
(5, 4, '2026-10-01'),   -- 5
(6, 5, '2026-10-10'),   -- 6
(1, 4, '2026-10-20'),   -- 7  (will be cancelled)
(8, 5, '2026-10-25');   -- 8

-- unit_price is filled automatically by trigger; stock and totals are updated too
INSERT INTO order_item (order_id, perfume_id, quantity) VALUES
(1, 1, 2), (1, 6, 1),
(2, 3, 1), (2, 4, 2),
(3, 2, 1), (3, 7, 1),
(4, 5, 3), (4, 8, 1),
(5, 7, 2),
(6, 4, 1), (6, 8, 2),
(7, 3, 1),
(8, 1, 1), (8, 5, 2);

-- Payments (trigger flips fully-paid orders to 'Paid' and awards loyalty points)
INSERT INTO payment (order_id, amount, method, paid_on) VALUES
(1, 12300, 'UPI',         '2026-08-05 11:30'),
(2, 10000, 'Card',        '2026-08-12 16:10'),
(2,  5100, 'UPI',         '2026-08-14 10:05'),
(3, 12000, 'Card',        '2026-09-02 13:45'),
(4,  5000, 'UPI',         '2026-09-15 18:20'),   -- partial payment: stays Pending
(5, 10400, 'Cash',        '2026-10-01 12:00'),
(8,  7800, 'Net Banking', '2026-10-25 09:40');

-- UPDATE examples: ship paid orders, cancel an unpaid order (stock is restored by trigger)
UPDATE sales_order SET status = 'Shipped'   WHERE order_id IN (1, 2);
UPDATE sales_order SET status = 'Cancelled' WHERE order_id = 7;

-- INSERT / UPDATE / DELETE demonstration on a throw-away record
INSERT INTO customer (full_name, email, city) VALUES ('Test Customer', 'test@example.com', 'Madurai');
UPDATE customer SET city = 'Trichy' WHERE email = 'test@example.com';
DELETE FROM customer WHERE email = 'test@example.com';