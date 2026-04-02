-- Seed data for local development
-- Covers all 6 intents in semantic_layer_v2.json

-- Countries
INSERT INTO dim_country (f_country_code, f_country_name) VALUES
  ('SG', 'Singapore'),
  ('TH', 'Thailand'),
  ('MY', 'Malaysia'),
  ('JP', 'Japan')
ON CONFLICT DO NOTHING;

-- Cities
INSERT INTO dim_city (f_city_code, f_city_name, f_country_code) VALUES
  ('SIN', 'Singapore',      'SG'),
  ('BKK', 'Bangkok',        'TH'),
  ('CNX', 'Chiang Mai',     'TH'),
  ('KUL', 'Kuala Lumpur',   'MY'),
  ('NRT', 'Tokyo',          'JP')
ON CONFLICT DO NOTHING;

-- Airports
INSERT INTO dim_airport (f_airport_code, f_airport_name, f_city_code) VALUES
  ('SIN', 'Singapore Changi Airport',        'SIN'),
  ('BKK', 'Suvarnabhumi Airport',            'BKK'),
  ('CNX', 'Chiang Mai International Airport','CNX'),
  ('KUL', 'Kuala Lumpur International',      'KUL'),
  ('NRT', 'Narita International Airport',    'NRT')
ON CONFLICT DO NOTHING;

-- Airlines
INSERT INTO dim_airline (f_airline_code, f_airline_name) VALUES
  ('SQ', 'Singapore Airlines'),
  ('TG', 'Thai Airways'),
  ('AK', 'AirAsia'),
  ('MH', 'Malaysia Airlines')
ON CONFLICT DO NOTHING;

-- Aircraft
INSERT INTO dim_aircraft (f_aircraft_code, f_aircraft_model) VALUES
  ('773', 'Boeing 777-300'),
  ('320', 'Airbus A320'),
  ('333', 'Airbus A330-300')
ON CONFLICT DO NOTHING;

-- Currency
INSERT INTO dim_currency_rate (f_currency_code, f_currency_name, f_currency_rate) VALUES
  ('SGD', 'Singapore Dollar', 1.00),
  ('THB', 'Thai Baht',        0.037)
ON CONFLICT DO NOTHING;

-- fact_flight_info
-- SIN → BKK (multiple airlines, cabin classes, seat availability) — covers intents 1,4,5,6
-- SIN → CNX (Thailand, different city)                            — covers intent 3
-- SIN → KUL (Malaysia, cheap)                                     — covers intent 2
-- SIN → NRT (Japan, expensive)                                     — covers intent 2

INSERT INTO fact_flight_info (
  f_flight_combination, f_departure_airport_code, f_destination_airport_code,
  f_airline_code, f_currency_code, f_aircraft_code,
  f_departure_date, f_arrival_date,
  f_cabin_class, f_trip_type,
  f_num_of_last_seats, f_flight_duration, f_total_amount_fare_total
) VALUES
  -- SIN → BKK, AirAsia, Economy (cheapest)
  (1001, 'SIN', 'BKK', 'AK', 'SGD', '320', '2025-06-05 08:00', '2025-06-05 11:30', 'Economy', 'OW', 12, 210, 89.00),
  -- SIN → BKK, Thai Airways, Economy
  (1002, 'SIN', 'BKK', 'TG', 'SGD', '333', '2025-06-05 14:00', '2025-06-05 17:30', 'Economy', 'OW', 3,  210, 145.00),
  -- SIN → BKK, Singapore Airlines, Business
  (1003, 'SIN', 'BKK', 'SQ', 'SGD', '773', '2025-06-05 10:00', '2025-06-05 13:30', 'Business','OW', 2,  210, 520.00),
  -- SIN → BKK, AirAsia, Economy (different date)
  (1004, 'SIN', 'BKK', 'AK', 'SGD', '320', '2025-06-10 09:00', '2025-06-10 12:30', 'Economy', 'OW', 1,  210, 95.00),
  -- SIN → BKK, Malaysia Airlines, Economy
  (1005, 'SIN', 'BKK', 'MH', 'SGD', '320', '2025-06-08 07:00', '2025-06-08 10:30', 'Economy', 'OW', 5,  210, 118.00),
  -- SIN → BKK, Thai Airways, Business (last seat urgency)
  (1006, 'SIN', 'BKK', 'TG', 'SGD', '333', '2025-06-12 16:00', '2025-06-12 19:30', 'Business','OW', 1,  210, 480.00),

  -- SIN → CNX (Chiang Mai, Thailand) — destinations_by_country_from_origin
  (2001, 'SIN', 'CNX', 'AK', 'SGD', '320', '2025-06-07 07:00', '2025-06-07 11:30', 'Economy', 'OW', 20, 270, 112.00),
  (2002, 'SIN', 'CNX', 'TG', 'SGD', '333', '2025-06-15 13:00', '2025-06-15 17:30', 'Economy', 'OW', 8,  270, 178.00),

  -- SIN → KUL (cheap, under budget) — destinations_under_budget
  (3001, 'SIN', 'KUL', 'AK', 'SGD', '320', '2025-06-03 06:00', '2025-06-03 07:30', 'Economy', 'OW', 30, 90,  55.00),
  (3002, 'SIN', 'KUL', 'MH', 'SGD', '320', '2025-06-03 12:00', '2025-06-03 13:30', 'Economy', 'OW', 15, 90,  72.00),

  -- SIN → NRT (expensive, over budget) — destinations_under_budget (should NOT appear for budget 300)
  (4001, 'SIN', 'NRT', 'SQ', 'SGD', '773', '2025-06-05 09:00', '2025-06-05 17:00', 'Economy', 'OW', 10, 480, 450.00),
  (4002, 'SIN', 'NRT', 'SQ', 'SGD', '773', '2025-06-05 09:00', '2025-06-05 17:00', 'Business','OW', 4,  480, 1200.00)
ON CONFLICT DO NOTHING;
