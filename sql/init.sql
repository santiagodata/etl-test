-- Crear base de datos
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'juju_db')
    CREATE DATABASE juju_db;
GO

USE juju_db;
GO

-- Tabla usuarios
IF OBJECT_ID('dbo.users', 'U') IS NOT NULL DROP TABLE dbo.users;
CREATE TABLE dbo.users (
    user_id    VARCHAR(64)  PRIMARY KEY,
    email      VARCHAR(255),
    created_at DATE,
    country    VARCHAR(8)
);
GO

-- Tabla productos
IF OBJECT_ID('dbo.products', 'U') IS NOT NULL DROP TABLE dbo.products;
CREATE TABLE dbo.products (
    sku        VARCHAR(64)    PRIMARY KEY,
    name       VARCHAR(255),
    category   VARCHAR(100),
    price      DECIMAL(12,2)
);
GO

-- Tabla orders (legacy)
IF OBJECT_ID('dbo.orders_db', 'U') IS NOT NULL DROP TABLE dbo.orders_db;
CREATE TABLE dbo.orders_db (
    order_id     VARCHAR(64)    PRIMARY KEY,
    user_id      VARCHAR(64),
    total_amount DECIMAL(12,2),
    created_at   DATETIME2,
    metadata     NVARCHAR(MAX)
);
GO

-- Insertar usuarios
INSERT INTO dbo.users VALUES
('emp_001', 'incentivos@exito.com',      '2024-01-15', 'CO'),
('emp_002', 'rrhh@falabella.com.co',     '2024-02-20', 'CO'),
('emp_003', 'bienestar@kokoriko.com',    '2024-04-10', 'CO'),
('emp_004', 'logistica@cencosud.com',    '2024-06-01', 'CO'),
('emp_005', 'talento@crepes.com.co',     '2024-07-18', 'CO'),
('emp_006', 'comercial@alkosto.com',     '2024-08-05', 'CO'),
('emp_007', 'premios@homecenter.com',    '2024-09-12', 'CO');
GO

-- Insertar productos
INSERT INTO dbo.products VALUES
('BONO-EXITO-50K',      'Bono Regalo Exito 50000',      'Almacenes de Cadena',   50000.00),
('BONO-D1-25K',         'Bono Regalo D1 25000',         'Almacenes de Cadena',   25000.00),
('BONO-AMAZON-100K',    'Bono Regalo Amazon 100000',    'E-Commerce',           100000.00),
('BONO-JUMBO-50K',      'Bono Regalo Jumbo 50000',      'Supermercados',         50000.00),
('BONO-FALABELLA-100K', 'Bono Regalo Falabella 100000', 'Moda y Hogar',         100000.00),
('BONO-RAPPI-25K',      'Bono Regalo Rappi 25000',      'Comidas y Delivery',    25000.00),
('BONO-NETFLIX-50K',    'Bono Regalo Netflix 50000',    'Entretenimiento',       50000.00),
('BONO-HOMECENTER-100K','Bono Regalo Homecenter 100000','Hogar y Construccion', 100000.00),
('BONO-CARULLA-50K',    'Bono Regalo Carulla 50000',    'Supermercados',         50000.00);
GO

-- Insertar orders (legacy)
INSERT INTO dbo.orders_db VALUES
('JJ-1001', 'emp_001', 150000, '2025-08-18T08:30:00', '{"source":"instant_rewards","promo":null}'),
('JJ-1002', 'emp_002', 200000, '2025-08-18T09:15:00', '{"source":"bonos_express","promo":"SAVE10"}'),
('JJ-1003', 'emp_003',  50000, '2025-08-19T10:00:00', '{"source":"comprafacil","promo":null}'),
('JJ-1004', 'emp_004', 300000, '2025-08-19T11:45:00', NULL),
('JJ-1005', 'emp_005',  75000, '2025-08-20T07:00:00', '{"source":"instant_rewards","promo":null}'),
('JJ-1006', 'emp_001', 100000, '2025-08-20T13:20:00', '{"source":"bonos_express","promo":"WELCOME"}'),
('JJ-1007', 'emp_006', 250000, '2025-08-21T08:00:00', '{"source":"comprafacil","promo":null}'),
('JJ-1008', 'emp_003',  50000, '2025-08-21T09:30:00', '{"source":"instant_rewards","promo":null}');
GO