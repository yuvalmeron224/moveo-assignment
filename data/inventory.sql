CREATE TABLE IF NOT EXISTS vehicles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    make        TEXT NOT NULL,
    model       TEXT NOT NULL,
    year        INTEGER NOT NULL,
    price       INTEGER NOT NULL,
    mileage     INTEGER NOT NULL,
    fuel_type   TEXT NOT NULL CHECK(fuel_type IN ('Electric', 'Gasoline', 'Hybrid')),
    color       TEXT NOT NULL,
    stock_count INTEGER NOT NULL DEFAULT 1 CHECK(stock_count >= 0),
    vin         TEXT UNIQUE NOT NULL
);

INSERT INTO vehicles (make, model, year, price, mileage, fuel_type, color, stock_count, vin) VALUES

-- 2022+ vehicles (sellable) --

-- Tesla
('Tesla', 'Model 3', 2024, 42990, 0, 'Electric', 'Pearl White', 3, 'VIN-TSL-M3-2024-001'),
('Tesla', 'Model 3', 2023, 39990, 8200, 'Electric', 'Midnight Silver', 2, 'VIN-TSL-M3-2023-002'),
('Tesla', 'Model Y', 2024, 47990, 0, 'Electric', 'Deep Blue', 4, 'VIN-TSL-MY-2024-003'),
('Tesla', 'Model Y', 2023, 44990, 12400, 'Electric', 'Red Multi-Coat', 2, 'VIN-TSL-MY-2023-004'),
('Tesla', 'Model S', 2024, 74990, 0, 'Electric', 'Obsidian Black', 1, 'VIN-TSL-MS-2024-005'),
('Tesla', 'Model S', 2023, 69990, 5500, 'Electric', 'Ultra Red', 1, 'VIN-TSL-MS-2023-006'),
('Tesla', 'Model X', 2024, 84990, 0, 'Electric', 'Pearl White', 1, 'VIN-TSL-MX-2024-007'),
('Tesla', 'Cybertruck', 2024, 61990, 0, 'Electric', 'Stainless Steel', 2, 'VIN-TSL-CT-2024-008'),

-- BMW
('BMW', 'iX', 2024, 87900, 0, 'Electric', 'Sophisto Grey', 2, 'VIN-BMW-IX-2024-009'),
('BMW', 'iX', 2023, 83900, 9100, 'Electric', 'Mineral White', 1, 'VIN-BMW-IX-2023-010'),
('BMW', 'i4', 2024, 65900, 0, 'Electric', 'Brooklyn Grey', 3, 'VIN-BMW-I4-2024-011'),
('BMW', 'i4', 2023, 61900, 7300, 'Electric', 'Dravit Grey', 2, 'VIN-BMW-I4-2023-012'),
('BMW', 'X5', 2024, 72900, 0, 'Gasoline', 'Carbon Black', 3, 'VIN-BMW-X5-2024-013'),
('BMW', 'X5', 2023, 68900, 14200, 'Gasoline', 'Alpine White', 2, 'VIN-BMW-X5-2023-014'),
('BMW', 'X5', 2022, 65000, 22000, 'Gasoline', 'Phytonic Blue', 1, 'VIN-BMW-X5-2022-015'),
('BMW', 'M3', 2024, 79900, 0, 'Gasoline', 'Isle of Man Green', 1, 'VIN-BMW-M3-2024-016'),
('BMW', 'M3', 2023, 75900, 6800, 'Gasoline', 'Frozen Black', 1, 'VIN-BMW-M3-2023-017'),
('BMW', '530e', 2024, 59900, 0, 'Hybrid', 'Mineral White', 2, 'VIN-BMW-53-2024-018'),
('BMW', '530e', 2022, 54000, 18000, 'Hybrid', 'Carbon Black', 1, 'VIN-BMW-53-2022-019'),

-- Mercedes
('Mercedes', 'EQS', 2024, 104400, 0, 'Electric', 'High-Tech Silver', 1, 'VIN-MRC-EQS-2024-020'),
('Mercedes', 'EQS', 2023, 97400, 8800, 'Electric', 'Obsidian Black', 1, 'VIN-MRC-EQS-2023-021'),
('Mercedes', 'EQB', 2024, 55900, 0, 'Electric', 'Digital White', 2, 'VIN-MRC-EQB-2024-022'),
('Mercedes', 'GLE', 2024, 76900, 0, 'Gasoline', 'Selenite Grey', 3, 'VIN-MRC-GLE-2024-023'),
('Mercedes', 'GLE', 2023, 72900, 11000, 'Gasoline', 'Obsidian Black', 2, 'VIN-MRC-GLE-2023-024'),
('Mercedes', 'GLE', 2022, 68000, 24000, 'Gasoline', 'Polar White', 1, 'VIN-MRC-GLE-2022-025'),
('Mercedes', 'C300', 2024, 48900, 0, 'Gasoline', 'Spectral Blue', 3, 'VIN-MRC-C30-2024-026'),
('Mercedes', 'C300', 2023, 45900, 9600, 'Gasoline', 'Mojave Silver', 2, 'VIN-MRC-C30-2023-027'),
('Mercedes', 'GLC 300e', 2024, 62900, 0, 'Hybrid', 'High-Tech Silver', 2, 'VIN-MRC-GLC-2024-028'),

-- Audi
('Audi', 'e-tron GT', 2024, 102900, 0, 'Electric', 'Tactical Green', 1, 'VIN-AUD-ETG-2024-029'),
('Audi', 'e-tron GT', 2023, 97900, 7200, 'Electric', 'Kemora Grey', 1, 'VIN-AUD-ETG-2023-030'),
('Audi', 'Q8 e-tron', 2024, 74900, 0, 'Electric', 'Plasma Blue', 2, 'VIN-AUD-Q8E-2024-031'),
('Audi', 'Q8 e-tron', 2023, 71900, 10500, 'Electric', 'Chronos Grey', 1, 'VIN-AUD-Q8E-2023-032'),
('Audi', 'A6', 2024, 58900, 0, 'Gasoline', 'Florett Silver', 3, 'VIN-AUD-A6-2024-033'),
('Audi', 'A6', 2023, 55900, 13000, 'Gasoline', 'Navarra Blue', 2, 'VIN-AUD-A6-2023-034'),
('Audi', 'Q7', 2024, 59900, 0, 'Gasoline', 'Glacier White', 2, 'VIN-AUD-Q7-2024-035'),
('Audi', 'Q7', 2022, 53000, 26000, 'Gasoline', 'Daytona Grey', 1, 'VIN-AUD-Q7-2022-036'),
('Audi', 'A7 TFSI e', 2024, 78900, 0, 'Hybrid', 'Firmament Blue', 1, 'VIN-AUD-A7-2024-037'),

-- Porsche
('Porsche', 'Taycan', 2024, 89900, 0, 'Electric', 'Frozen Blue', 2, 'VIN-PRS-TAY-2024-038'),
('Porsche', 'Taycan', 2023, 84900, 6100, 'Electric', 'Carmine Red', 1, 'VIN-PRS-TAY-2023-039'),
('Porsche', 'Cayenne E-Hybrid', 2024, 92900, 0, 'Hybrid', 'Jet Black', 2, 'VIN-PRS-CAY-2024-040'),
('Porsche', 'Cayenne E-Hybrid', 2023, 87900, 8900, 'Hybrid', 'Crayon', 1, 'VIN-PRS-CAY-2023-041'),
('Porsche', 'Macan', 2024, 67900, 0, 'Electric', 'Papaya Metallic', 2, 'VIN-PRS-MAC-2024-042'),
('Porsche', 'Panamera', 2024, 99900, 0, 'Gasoline', 'Dark Blue', 1, 'VIN-PRS-PAN-2024-043'),

-- Lexus
('Lexus', 'RZ 450e', 2024, 55900, 0, 'Electric', 'Sonic Titanium', 2, 'VIN-LXS-RZ-2024-044'),
('Lexus', 'RZ 450e', 2023, 52900, 7800, 'Electric', 'Eminent White', 1, 'VIN-LXS-RZ-2023-045'),
('Lexus', 'ES 300h', 2024, 44900, 0, 'Hybrid', 'Atomic Silver', 3, 'VIN-LXS-ES-2024-046'),
('Lexus', 'ES 300h', 2023, 42900, 11200, 'Hybrid', 'Caviar Black', 2, 'VIN-LXS-ES-2023-047'),
('Lexus', 'LX 600', 2024, 89900, 0, 'Gasoline', 'Sonic Quartz', 1, 'VIN-LXS-LX-2024-048'),
('Lexus', 'NX 450h+', 2022, 54000, 19000, 'Hybrid', 'Nori Green', 1, 'VIN-LXS-NX-2022-049'),

-- Genesis
('Genesis', 'GV60', 2024, 47900, 0, 'Electric', 'Haze Gray', 3, 'VIN-GNS-G60-2024-050'),
('Genesis', 'GV60', 2023, 44900, 9400, 'Electric', 'Icy Blue', 2, 'VIN-GNS-G60-2023-051'),
('Genesis', 'GV70 Electrified', 2024, 57900, 0, 'Electric', 'Savile Silver', 2, 'VIN-GNS-G7E-2024-052'),
('Genesis', 'G80 Electrified', 2024, 67900, 0, 'Electric', 'Himalayan Gray', 1, 'VIN-GNS-G8E-2024-053'),
('Genesis', 'GV80', 2024, 58900, 0, 'Gasoline', 'Uyuni White', 2, 'VIN-GNS-G80-2024-054'),
('Genesis', 'GV80', 2022, 52000, 21000, 'Gasoline', 'Cardiff Green', 1, 'VIN-GNS-G80-2022-055'),

-- Volvo
('Volvo', 'XC40 Recharge', 2024, 55900, 0, 'Electric', 'Crystal White', 3, 'VIN-VLV-X4R-2024-056'),
('Volvo', 'XC40 Recharge', 2023, 52900, 8600, 'Electric', 'Fjord Blue', 2, 'VIN-VLV-X4R-2023-057'),
('Volvo', 'EX90', 2024, 79900, 0, 'Electric', 'Denim Blue', 2, 'VIN-VLV-EX9-2024-058'),
('Volvo', 'XC60 Recharge', 2024, 62900, 0, 'Hybrid', 'Pine Grey', 2, 'VIN-VLV-X6R-2024-059'),
('Volvo', 'XC90 Recharge', 2024, 73900, 0, 'Hybrid', 'Onyx Black', 1, 'VIN-VLV-X9R-2024-060'),
('Volvo', 'XC90 Recharge', 2022, 66000, 23000, 'Hybrid', 'Bright Silver', 1, 'VIN-VLV-X9R-2022-061'),

-- Out of stock edge cases (2022+ but stock=0)
('BMW', 'M5', 2024, 109900, 0, 'Gasoline', 'Frozen Black', 0, 'VIN-BMW-M5-2024-062'),
('Tesla', 'Roadster', 2024, 199900, 0, 'Electric', 'Pearl White', 0, 'VIN-TSL-RD-2024-063'),
('Porsche', '911 GT3', 2024, 174900, 0, 'Gasoline', 'Guards Red', 0, 'VIN-PRS-GT3-2024-064'),

-- ─────────────────────────────────────────────────────────────────
-- PRE-2022 vehicles (pending_delisting) — edge cases for conflict resolution
-- ─────────────────────────────────────────────────────────────────
('BMW', 'X5', 2021, 58000, 34000, 'Gasoline', 'Alpine White', 1, 'VIN-BMW-X5-2021-065'),
('BMW', 'X5', 2020, 52000, 48000, 'Gasoline', 'Carbon Black', 1, 'VIN-BMW-X5-2020-066'),
('BMW', '5 Series', 2021, 49000, 29000, 'Gasoline', 'Mineral White', 2, 'VIN-BMW-5S-2021-067'),
('Tesla', 'Model 3', 2021, 33000, 41000, 'Electric', 'Midnight Silver', 2, 'VIN-TSL-M3-2021-068'),
('Tesla', 'Model Y', 2021, 36000, 38000, 'Electric', 'Red Multi-Coat', 1, 'VIN-TSL-MY-2021-069'),
('Tesla', 'Model S', 2020, 61000, 52000, 'Electric', 'Obsidian Black', 1, 'VIN-TSL-MS-2020-070'),
('Mercedes', 'GLE', 2021, 64000, 31000, 'Gasoline', 'Selenite Grey', 2, 'VIN-MRC-GLE-2021-071'),
('Mercedes', 'GLE', 2020, 59000, 46000, 'Gasoline', 'Obsidian Black', 1, 'VIN-MRC-GLE-2020-072'),
('Mercedes', 'C300', 2021, 38000, 27000, 'Gasoline', 'Spectral Blue', 2, 'VIN-MRC-C30-2021-073'),
('Audi', 'Q7', 2021, 51000, 36000, 'Gasoline', 'Glacier White', 1, 'VIN-AUD-Q7-2021-074'),
('Audi', 'A6', 2020, 44000, 55000, 'Gasoline', 'Navarra Blue', 1, 'VIN-AUD-A6-2020-075'),
('Porsche', 'Cayenne', 2021, 74000, 28000, 'Gasoline', 'Jet Black', 1, 'VIN-PRS-CAY-2021-076'),
('Porsche', 'Taycan', 2021, 81000, 22000, 'Electric', 'Frozen Blue', 1, 'VIN-PRS-TAY-2021-077'),
('Lexus', 'ES 300h', 2021, 38000, 33000, 'Hybrid', 'Atomic Silver', 1, 'VIN-LXS-ES-2021-078'),
('Volvo', 'XC60', 2020, 44000, 61000, 'Gasoline', 'Pine Grey', 1, 'VIN-VLV-X60-2020-079'),

-- Additional 2022+ to reach 100 --
('Rivian', 'R1T', 2024, 69900, 0, 'Electric', 'Launch Green', 2, 'VIN-RVN-R1T-2024-080'),
('Rivian', 'R1S', 2024, 77900, 0, 'Electric', 'Midnight', 2, 'VIN-RVN-R1S-2024-081'),
('Rivian', 'R1S', 2023, 73900, 9800, 'Electric', 'El Cap Granite', 1, 'VIN-RVN-R1S-2023-082'),
('Polestar', '2', 2024, 48900, 0, 'Electric', 'Snow', 3, 'VIN-PLR-P2-2024-083'),
('Polestar', '3', 2024, 73900, 0, 'Electric', 'Space', 2, 'VIN-PLR-P3-2024-084'),
('Polestar', '2', 2023, 45900, 11000, 'Electric', 'Midnight', 2, 'VIN-PLR-P2-2023-085'),
('Lucid', 'Air Pure', 2024, 69900, 0, 'Electric', 'Stellar White', 1, 'VIN-LCD-AP-2024-086'),
('Lucid', 'Air Grand Touring', 2024, 138000, 0, 'Electric', 'Cosmos Silver', 1, 'VIN-LCD-AG-2024-087'),
('Range Rover', 'Sport P400e', 2024, 89900, 0, 'Hybrid', 'Fuji White', 2, 'VIN-RRV-SP-2024-088'),
('Range Rover', 'Defender', 2024, 72900, 0, 'Gasoline', 'Gondwana Stone', 2, 'VIN-RRV-DF-2024-089'),
('Range Rover', 'Evoque P300e', 2023, 58900, 10200, 'Hybrid', 'Seoul Pearl Silver', 1, 'VIN-RRV-EV-2023-090'),
('Maserati', 'GranTurismo Folgore', 2024, 196900, 0, 'Electric', 'Bianco Astro', 1, 'VIN-MSR-GT-2024-091'),
('Maserati', 'Grecale Folgore', 2024, 94900, 0, 'Electric', 'Grigio Granito', 1, 'VIN-MSR-GR-2024-092'),
('Bentley', 'Bentayga EWB', 2024, 259900, 0, 'Gasoline', 'Beluga', 1, 'VIN-BNT-BE-2024-093'),
('Bentley', 'Continental GT Speed', 2024, 274900, 0, 'Gasoline', 'Glacier Blue', 1, 'VIN-BNT-CG-2024-094'),
('Lamborghini', 'Urus SE', 2024, 249900, 0, 'Hybrid', 'Giallo Orion', 1, 'VIN-LMB-US-2024-095'),
('Ferrari', 'SF90 Spider', 2024, 579900, 0, 'Hybrid', 'Rosso Corsa', 1, 'VIN-FRR-SF-2024-096'),
('Rolls-Royce', 'Spectre', 2024, 419900, 0, 'Electric', 'Arctic White', 1, 'VIN-RR-SP-2024-097'),
('Aston Martin', 'DBX707', 2024, 239900, 0, 'Gasoline', 'Lunar White', 1, 'VIN-AM-DB-2024-098'),
('McLaren', 'Artura', 2024, 241900, 0, 'Hybrid', 'Lantana Purple', 1, 'VIN-MCL-AR-2024-099'),
('Cadillac', 'LYRIQ', 2024, 58590, 0, 'Electric', 'Opulent Blue', 2, 'VIN-CAD-LY-2024-100');
