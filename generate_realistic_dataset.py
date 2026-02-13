import csv
import random
from datetime import date, timedelta

random.seed(42)

# =========================================================
# HELPERS
# =========================================================

def money(x):
    return f"{x:.2f}"

def rand_date(start, end, month_weights):
    """Generate random date with seasonal bias"""
    days = (end - start).days
    while True:
        d = start + timedelta(days=random.randint(0, days))
        if random.random() < month_weights[d.month]:
            return d

def weighted_choice(mapping):
    """Choose item based on weights"""
    r = random.random()
    cum = 0
    for k, w in mapping.items():
        cum += w
        if r <= cum:
            return k
    return list(mapping.keys())[-1]

# =========================================================
# REGIONS / CITIES
# =========================================================

REGION_MAP = {
    "West": [("Los Angeles","CA"),("San Diego","CA"),("San Jose","CA"),("Sacramento","CA"),("San Francisco","CA")],
    "Southwest": [("Houston","TX"),("Dallas","TX"),("Phoenix","AZ"),("San Antonio","TX"),("Austin","TX")],
    "Southeast": [("Miami","FL"),("Orlando","FL"),("Atlanta","GA"),("Tampa","FL"),("Jacksonville","FL")],
    "Northeast": [("Boston","MA"),("New York","NY"),("Buffalo","NY"),("Newark","NJ"),("Providence","RI")],
    "Midwest": [("Chicago","IL"),("Detroit","MI"),("Cleveland","OH"),("Indianapolis","IN"),("Milwaukee","WI")],
    "Northwest": [("Seattle","WA"),("Portland","OR"),("Boise","ID"),("Spokane","WA")],
    "South Central": [("Oklahoma City","OK"),("Tulsa","OK"),("Little Rock","AR"),("Kansas City","MO")],
    "Mid-Atlantic": [("Philadelphia","PA"),("Baltimore","MD"),("Richmond","VA"),("Pittsburgh","PA")]
}

REGION_WEIGHTS = {
    "West": 0.22,
    "Southwest": 0.20,
    "Southeast": 0.18,
    "Northeast": 0.14,
    "Midwest": 0.12,
    "Mid-Atlantic": 0.08,
    "Northwest": 0.04,
    "South Central": 0.02
}

# =========================================================
# CUSTOMER GENERATION
# =========================================================

END_USE_LIST = (
    ["General Construction"] * 20 +
    ["Residential Construction"] * 20 +
    ["Painting"] * 15 +
    ["Plumbing"] * 15 +
    ["Electrical"] * 10 +
    ["HVAC"] * 10 +
    ["Roofing"] * 3 +
    ["Flooring"] * 2 +
    ["Landscaping"] * 2 +
    ["Carpentry"] * 2 +
    ["Masonry"] * 1
)

CUSTOMER_TYPE_LIST = (
    ["Large Commercial"] * 30 +
    ["Small Commercial"] * 35 +
    ["Small Business"] * 25 +
    ["Independent Contractor"] * 10
)

ADJ = ["Precision","Metro","Pro","Elite","Prime","Reliable","Summit","Pioneer",
       "Dynamic","Rapid","Superior","National","Advanced","Quality","Expert",
       "Professional","Certified","Premier","Ultimate","Complete"]

SUFFIX = ["LLC","Inc","Group","Services","Contractors","Solutions","Pros",
          "Experts","Co","Works","Specialists","Supply","Enterprises"]

OWNER_NAMES = ["Johnson","Smith","Martinez","Brown","Lee","Garcia","Clark",
               "Davis","Rodriguez","Wilson","Anderson","Taylor","Thomas","Moore"]

def make_business_name(city, end_use):
    """Generate realistic business name"""
    trade = end_use.replace(" Construction", "").replace("General ", "")
    
    styles = [
        lambda: f"{random.choice(ADJ)} {trade} {random.choice(SUFFIX)}",
        lambda: f"{city} {trade} {random.choice(SUFFIX)}",
        lambda: f"{random.choice(OWNER_NAMES)} & Sons {trade}",
        lambda: f"{random.choice(OWNER_NAMES)} {trade} {random.choice(SUFFIX)}",
        lambda: f"{trade} {random.choice(['Works','Specialists','Supply','Experts','Pros','Masters'])}"
    ]
    return random.choice(styles)()

def credit_for_type(customer_type):
    """Assign realistic credit limit"""
    if customer_type == "Large Commercial":
        return random.randrange(100000, 500001, 5000)
    if customer_type == "Small Commercial":
        return random.randrange(50000, 200001, 5000)
    if customer_type == "Small Business":
        return random.randrange(20000, 100001, 5000)
    return random.randrange(5000, 40001, 5000)

def generate_customers():
    """Generate 5000 unique customers"""
    customers = []
    used_names = set()

    for i in range(1, 5001):
        cid = f"C{i:05d}"
        region = weighted_choice(REGION_WEIGHTS)
        city, state = random.choice(REGION_MAP[region])
        end_use = random.choice(END_USE_LIST)
        cust_type = random.choice(CUSTOMER_TYPE_LIST)
        
        name = make_business_name(city, end_use)
        counter = 1
        while name in used_names:
            name = make_business_name(city, end_use) + f" {counter}"
            counter += 1
        used_names.add(name)

        customers.append([
            cid,
            name,
            region,
            end_use,
            cust_type,
            city,
            state,
            random.randint(1, 15),
            credit_for_type(cust_type)
        ])
    
    return customers

# =========================================================
# PRODUCTS - DETAILED WITH PROPER L3 CATEGORIES
# =========================================================

PRODUCT_CATALOG = {
    "Power Tools": {
        "l3_categories": {
            "Cordless Drills": ("Drilling", 120, 300),
            "Corded Drills": ("Drilling", 60, 180),
            "Impact Drivers": ("Fastening", 100, 250),
            "Circular Saws": ("Cutting", 100, 350),
            "Miter Saws": ("Cutting", 200, 600),
            "Reciprocating Saws": ("Cutting", 80, 250),
            "Jigsaws": ("Cutting", 50, 180),
            "Angle Grinders": ("Grinding", 60, 200),
            "Sanders": ("Sanding", 40, 180),
            "Nail Guns": ("Fastening", 150, 500),
            "Impact Wrenches": ("Fastening", 120, 350)
        },
        "brands": ["DeWalt", "Milwaukee", "Makita", "Bosch", "Ryobi", "Black+Decker"],
        "count": 500
    },
    "Hand Tools": {
        "l3_categories": {
            "Hammers": ("Fastening", 15, 60),
            "Screwdrivers": ("Fastening", 8, 40),
            "Screwdriver Sets": ("Fastening", 20, 120),
            "Pliers": ("Gripping", 12, 50),
            "Wrenches": ("Fastening", 15, 80),
            "Socket Sets": ("Fastening", 30, 200),
            "Tape Measures": ("Measuring", 10, 40),
            "Levels": ("Measuring", 20, 150),
            "Utility Knives": ("Cutting", 5, 25),
            "Chisels": ("Cutting", 10, 60),
            "Hand Saws": ("Cutting", 15, 80),
            "Clamps": ("Holding", 8, 50)
        },
        "brands": ["Stanley", "Craftsman", "Klein Tools", "Irwin", "Channellock", "Husky"],
        "count": 800
    },
    "Fasteners": {
        "l3_categories": {
            "Framing Nails": ("Fastening", 30, 80),
            "Finishing Nails": ("Fastening", 20, 60),
            "Roofing Nails": ("Fastening", 25, 70),
            "Brad Nails": ("Fastening", 15, 50),
            "Wood Screws": ("Fastening", 20, 90),
            "Drywall Screws": ("Fastening", 15, 60),
            "Deck Screws": ("Fastening", 30, 120),
            "Construction Screws": ("Fastening", 40, 150),
            "Concrete Screws": ("Fastening", 30, 100),
            "Bolts & Nuts": ("Fastening", 10, 80),
            "Anchors": ("Fastening", 8, 40)
        },
        "brands": ["Grip-Rite", "GRK", "Simpson Strong-Tie", "Tapcon", "Hillman"],
        "count": 1000
    },
    "Paints & Coatings": {
        "l3_categories": {
            "Interior Latex Paint": ("Coating", 25, 60),
            "Exterior Latex Paint": ("Coating", 30, 70),
            "Primers": ("Coating", 20, 50),
            "Stains": ("Coating", 25, 80),
            "Varnishes": ("Coating", 30, 90),
            "Specialty Paints": ("Coating", 35, 100)
        },
        "brands": ["Behr", "Sherwin-Williams", "Benjamin Moore", "Valspar", "PPG"],
        "count": 400
    },
    "Painting Supplies": {
        "l3_categories": {
            "Paint Brushes": ("Application", 8, 40),
            "Roller Covers": ("Application", 5, 25),
            "Roller Frames": ("Application", 10, 30),
            "Paint Trays": ("Application", 3, 15),
            "Painters Tape": ("Masking", 5, 20),
            "Drop Cloths": ("Protection", 10, 50),
            "Paint Sprayers": ("Application", 150, 600)
        },
        "brands": ["Purdy", "Wooster", "3M", "Wagner", "Graco", "Trimaco"],
        "count": 300
    },
    "Plumbing": {
        "l3_categories": {
            "PVC Pipes": ("Piping", 10, 40),
            "Copper Pipes": ("Piping", 20, 100),
            "PEX Tubing": ("Piping", 15, 80),
            "Pipe Fittings": ("Connection", 5, 50),
            "Valves": ("Control", 15, 100),
            "Faucets": ("Fixtures", 40, 200),
            "Shower Heads": ("Fixtures", 30, 150),
            "Drain Assemblies": ("Drainage", 20, 80),
            "Water Heaters": ("Fixtures", 400, 1500),
            "Plumbing Tools": ("Installation", 20, 150)
        },
        "brands": ["SharkBite", "Charlotte Pipe", "Moen", "Delta", "Kohler", "Oatey"],
        "count": 500
    },
    "Electrical": {
        "l3_categories": {
            "Romex Wire": ("Wiring", 50, 200),
            "Conduit": ("Wiring", 10, 60),
            "Wire Nuts": ("Connection", 3, 15),
            "Electrical Tape": ("Insulation", 2, 10),
            "Outlets": ("Electrical Outlets", 5, 30),
            "Switches": ("Switching", 5, 40),
            "GFCI Outlets": ("Electrical Outlets", 15, 50),
            "Circuit Breakers": ("Protection", 20, 100),
            "Junction Boxes": ("Housing", 5, 25),
            "Cable Ties": ("Organization", 5, 20)
        },
        "brands": ["Southwire", "Leviton", "Lutron", "Square D", "GE", "Eaton"],
        "count": 400
    },
    "HVAC": {
        "l3_categories": {
            "Air Filters": ("Filtration", 10, 40),
            "Thermostats": ("Climate Control", 50, 300),
            "Refrigerants": ("Cooling", 80, 200),
            "Duct Tape": ("Sealing", 5, 20),
            "Registers": ("Ventilation", 10, 50),
            "Condensate Pumps": ("Drainage", 60, 150)
        },
        "brands": ["Honeywell", "Nest", "Trane", "Carrier", "Rheem", "Goodman"],
        "count": 200
    },
    "Building Materials": {
        "l3_categories": {
            "Drywall Sheets": ("Wall Construction", 10, 25),
            "Plywood": ("Structural", 30, 80),
            "Lumber 2x4": ("Structural", 5, 15),
            "Lumber 2x6": ("Structural", 8, 20),
            "Insulation": ("Thermal", 30, 100),
            "Roofing Shingles": ("Roofing", 70, 150),
            "Concrete Mix": ("Foundations", 5, 15),
            "Mortar Mix": ("Masonry", 6, 18)
        },
        "brands": ["USG", "Georgia-Pacific", "CertainTeed", "Owens Corning", "Quikrete"],
        "count": 600
    },
    "Safety Equipment": {
        "l3_categories": {
            "Hard Hats": ("Head Protection", 15, 50),
            "Safety Glasses": ("Eye Protection", 5, 30),
            "Work Gloves": ("Hand Protection", 8, 40),
            "Respirators": ("Respiratory Protection", 20, 100),
            "Safety Vests": ("Visibility", 10, 40),
            "Hearing Protection": ("Ear Protection", 8, 35)
        },
        "brands": ["3M", "Honeywell", "DeWalt", "Milwaukee", "Carhartt"],
        "count": 200
    },
    "Adhesives & Sealants": {
        "l3_categories": {
            "Construction Adhesive": ("Bonding", 5, 20),
            "Wood Glue": ("Bonding", 5, 25),
            "Silicone Caulk": ("Sealing", 4, 15),
            "Acrylic Caulk": ("Sealing", 3, 12),
            "Spray Foam": ("Insulation", 8, 30)
        },
        "brands": ["Loctite", "Gorilla", "Liquid Nails", "DAP", "GE", "3M"],
        "count": 200
    },
    "Ladders & Scaffolding": {
        "l3_categories": {
            "Step Ladders": ("Access", 60, 200),
            "Extension Ladders": ("Access", 120, 400),
            "Platform Ladders": ("Access", 150, 500),
            "Scaffolding": ("Access", 300, 1500)
        },
        "brands": ["Werner", "Louisville Ladder", "Little Giant", "Gorilla Ladders"],
        "count": 100
    },
    "Material Handling": {
        "l3_categories": {
            "Hand Trucks": ("Transport", 50, 200),
            "Wheelbarrows": ("Transport", 60, 180),
            "Tool Bags": ("Storage", 20, 100),
            "Tool Boxes": ("Storage", 30, 200)
        },
        "brands": ["Milwaukee", "DeWalt", "Klein Tools", "Rubbermaid", "Vestil"],
        "count": 100
    },
    "Measuring & Layout": {
        "l3_categories": {
            "Laser Levels": ("Measuring", 80, 400),
            "Chalk Lines": ("Marking", 10, 30),
            "Stud Finders": ("Detection", 20, 80),
            "Squares": ("Layout", 15, 60)
        },
        "brands": ["Bosch", "DeWalt", "Stanley", "Johnson Level", "Stabila"],
        "count": 100
    },
    "Abrasives": {
        "l3_categories": {
            "Sandpaper": ("Smoothing", 5, 20),
            "Sanding Discs": ("Smoothing", 10, 40),
            "Grinding Wheels": ("Grinding", 8, 35),
            "Cut-Off Wheels": ("Cutting", 10, 40)
        },
        "brands": ["3M", "Norton", "DeWalt", "Diablo", "Avanti"],
        "count": 100
    }
}

def generate_products():
    """Generate 5000+ products with proper L2/L3 categories"""
    products = []
    pid = 1
    
    for l2_category, specs in PRODUCT_CATALOG.items():
        l3_cats = specs["l3_categories"]
        brands = specs["brands"]
        target_count = specs["count"]
        
        products_per_l3 = max(1, target_count // len(l3_cats))
        
        for l3_category, (functionality, min_price, max_price) in l3_cats.items():
            for _ in range(products_per_l3):
                brand = random.choice(brands)
                
                # Generate product name with specs
                size_specs = {
                    "Cordless Drills": f"{random.choice(['18V', '20V', '24V'])} MAX",
                    "Circular Saws": f"{random.choice(['7-1/4', '6-1/2', '10'])} inch",
                    "Paint": f"{random.choice(['1 Gallon', '5 Gallon', '1 Quart'])}",
                    "Wire": f"{random.choice(['250ft', '500ft', '1000ft'])}",
                    "Lumber": f"{random.choice(['8ft', '10ft', '12ft', '16ft'])}",
                    "Nails": f"{random.choice(['1lb', '5lb', '25lb', '50lb'])} Box"
                }
                
                # Find matching spec
                spec = ""
                for key in size_specs:
                    if key in l3_category or key in l2_category:
                        spec = size_specs[key]
                        break
                
                if not spec:
                    spec = f"Model {random.randint(100, 999)}"
                
                product_name = f"{brand} {spec} {l3_category}"
                
                price = round(random.uniform(min_price, max_price), 2)
                
                # Unit of measure based on category
                if l2_category in ["Paints & Coatings"]:
                    uom = "Gallon"
                elif l2_category in ["Fasteners", "Adhesives & Sealants"]:
                    uom = "Box"
                elif "Wire" in l3_category or "Lumber" in l2_category:
                    uom = "Each"
                else:
                    uom = "Each"
                
                in_stock = "TRUE" if random.random() < 0.95 else "FALSE"
                
                products.append([
                    f"P{pid:05d}",
                    product_name,
                    brand,
                    l2_category,
                    l3_category,
                    functionality,
                    money(price),
                    uom,
                    in_stock
                ])
                pid += 1
                
                if pid > 5500:
                    return products
    
    return products

# =========================================================
# REALISTIC PURCHASING PATTERNS
# =========================================================

PURCHASE_PATTERNS = {
    "General Construction": {
        "Power Tools": 0.25,
        "Hand Tools": 0.20,
        "Fasteners": 0.25,
        "Building Materials": 0.15,
        "Safety Equipment": 0.08,
        "Measuring & Layout": 0.04,
        "Ladders & Scaffolding": 0.03
    },
    "Residential Construction": {
        "Power Tools": 0.25,
        "Hand Tools": 0.20,
        "Fasteners": 0.25,
        "Building Materials": 0.15,
        "Safety Equipment": 0.08,
        "Measuring & Layout": 0.04,
        "Ladders & Scaffolding": 0.03
    },
    "Painting": {
        "Paints & Coatings": 0.45,
        "Painting Supplies": 0.38,
        "Hand Tools": 0.10,
        "Safety Equipment": 0.05,
        "Ladders & Scaffolding": 0.02
    },
    "Plumbing": {
        "Plumbing": 0.55,
        "Hand Tools": 0.18,
        "Power Tools": 0.12,
        "Adhesives & Sealants": 0.08,
        "Safety Equipment": 0.05,
        "Measuring & Layout": 0.02
    },
    "Electrical": {
        "Electrical": 0.50,
        "Power Tools": 0.20,
        "Hand Tools": 0.15,
        "Safety Equipment": 0.10,
        "Measuring & Layout": 0.03,
        "Ladders & Scaffolding": 0.02
    },
    "HVAC": {
        "HVAC": 0.55,
        "Electrical": 0.18,
        "Hand Tools": 0.12,
        "Power Tools": 0.08,
        "Safety Equipment": 0.05,
        "Ladders & Scaffolding": 0.02
    },
    "Roofing": {
        "Building Materials": 0.35,
        "Fasteners": 0.30,
        "Power Tools": 0.15,
        "Safety Equipment": 0.12,
        "Hand Tools": 0.05,
        "Ladders & Scaffolding": 0.03
    },
    "Flooring": {
        "Building Materials": 0.30,
        "Adhesives & Sealants": 0.28,
        "Power Tools": 0.18,
        "Hand Tools": 0.12,
        "Safety Equipment": 0.08,
        "Measuring & Layout": 0.04
    },
    "Landscaping": {
        "Power Tools": 0.45,
        "Material Handling": 0.25,
        "Hand Tools": 0.18,
        "Safety Equipment": 0.10,
        "Fasteners": 0.02
    },
    "Carpentry": {
        "Power Tools": 0.32,
        "Hand Tools": 0.28,
        "Fasteners": 0.18,
        "Measuring & Layout": 0.10,
        "Safety Equipment": 0.08,
        "Building Materials": 0.04
    },
    "Masonry": {
        "Building Materials": 0.42,
        "Power Tools": 0.22,
        "Hand Tools": 0.18,
        "Safety Equipment": 0.12,
        "Adhesives & Sealants": 0.04,
        "Measuring & Layout": 0.02
    }
}

# Seasonal patterns (higher in construction season)
MONTH_WEIGHTS = {
    1: 0.4, 2: 0.5, 3: 0.8, 4: 0.95, 5: 1.0, 6: 1.0,
    7: 1.0, 8: 1.0, 9: 0.95, 10: 0.8, 11: 0.6, 12: 0.5
}

def generate_invoices(customers, products):
    """Generate 50,000 invoices with realistic purchasing patterns"""
    
    # Group products by L2 category for fast lookup
    products_by_category = {}
    for product in products:
        l2_cat = product[3]
        if l2_cat not in products_by_category:
            products_by_category[l2_cat] = []
        products_by_category[l2_cat].append(product)
    
    start_date = date(2023, 1, 1)
    end_date = date(2025, 12, 31)
    
    invoices = []
    inv_id = 1
    
    print("Generating invoices with realistic purchasing patterns...")
    
    for idx, cust in enumerate(customers):
        if (idx + 1) % 1000 == 0:
            print(f"  Processing customer {idx + 1}/5000...")
        
        cid = cust[0]
        end_use = cust[3]
        cust_type = cust[4]
        
        # Get purchasing pattern for this customer type
        pattern = PURCHASE_PATTERNS.get(end_use, PURCHASE_PATTERNS["General Construction"])
        
        # Determine number of purchases based on customer type
        if cust_type == "Large Commercial":
            num_purchases = random.randint(50, 100)
        elif cust_type == "Small Commercial":
            num_purchases = random.randint(20, 50)
        elif cust_type == "Small Business":
            num_purchases = random.randint(10, 30)
        else:  # Independent Contractor
            num_purchases = random.randint(5, 20)
        
        for _ in range(num_purchases):
            # Choose category based on customer's purchasing pattern
            category = weighted_choice(pattern)
            
            # Get products in this category
            if category in products_by_category and products_by_category[category]:
                product = random.choice(products_by_category[category])
                
                pid = product[0]
                base_price = float(product[6])
                
                # Quantity varies by product type
                if category in ["Paints & Coatings", "Building Materials"]:
                    qty = random.randint(5, 50)
                elif category == "Fasteners":
                    qty = random.randint(10, 100)
                elif category in ["Power Tools", "HVAC", "Ladders & Scaffolding"]:
                    qty = random.randint(1, 5)
                elif category == "Electrical" and "Wire" in product[4]:
                    qty = random.randint(1, 10)
                else:
                    qty = random.randint(2, 25)
                
                # Add some price variation (promotions, bulk discounts)
                price = round(base_price * random.uniform(0.90, 1.05), 2)
                total = round(qty * price, 2)
                
                # Generate date with seasonal pattern
                invoice_date = rand_date(start_date, end_date, MONTH_WEIGHTS)
                
                invoices.append([
                    f"INV{inv_id:06d}",
                    cid,
                    pid,
                    qty,
                    invoice_date.isoformat(),
                    money(price),
                    money(total)
                ])
                inv_id += 1
    
    # Pad to exactly 50,000 if needed
    print(f"  Generated {len(invoices)} invoices, padding to 50,000...")
    while len(invoices) < 50000:
        cust = random.choice(customers)
        end_use = cust[3]
        pattern = PURCHASE_PATTERNS.get(end_use, PURCHASE_PATTERNS["General Construction"])
        category = weighted_choice(pattern)
        
        if category in products_by_category and products_by_category[category]:
            product = random.choice(products_by_category[category])
            
            pid = product[0]
            base_price = float(product[6])
            
            if category in ["Paints & Coatings", "Building Materials"]:
                qty = random.randint(5, 50)
            elif category == "Fasteners":
                qty = random.randint(10, 100)
            elif category in ["Power Tools", "HVAC"]:
                qty = random.randint(1, 5)
            else:
                qty = random.randint(2, 25)
            
            price = round(base_price * random.uniform(0.90, 1.05), 2)
            total = round(qty * price, 2)
            invoice_date = rand_date(start_date, end_date, MONTH_WEIGHTS)
            
            invoices.append([
                f"INV{inv_id:06d}",
                cust[0],
                pid,
                qty,
                invoice_date.isoformat(),
                money(price),
                money(total)
            ])
            inv_id += 1
    
    return invoices[:50000]

# =========================================================
# CSV WRITING
# =========================================================

def write_csv(filename, header, rows):
    """Write data to CSV file"""
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"✅ Written {filename} ({len(rows)} rows)")

# =========================================================
# MAIN EXECUTION
# =========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("REALISTIC DATASET GENERATOR")
    print("=" * 60)
    
    print("\n📊 Generating customers...")
    customers = generate_customers()
    
    print("\n📦 Generating products...")
    products = generate_products()
    
    print(f"\n🛒 Generating invoices...")
    invoices = generate_invoices(customers, products)
    
    print("\n💾 Writing CSV files...")
    write_csv(
        "customers.csv",
        ["customer_id", "customer_name", "region", "end_use", "customer_type",
         "city", "state", "years_as_customer", "credit_limit"],
        customers
    )
    
    write_csv(
        "products.csv",
        ["product_id", "product_name", "brand", "l2_category", "l3_category",
         "functionality", "unit_price", "unit_of_measure", "in_stock"],
        products
    )
    
    write_csv(
        "invoices.csv",
        ["invoice_id", "customer_id", "product_id", "quantity", "invoice_date",
         "unit_price", "line_total"],
        invoices
    )
    
    print("\n" + "=" * 60)
    print("✅ DATASET GENERATION COMPLETE!")
    print("=" * 60)
    print(f"\nGenerated:")
    print(f"  • {len(customers)} customers")
    print(f"  • {len(products)} products")
    print(f"  • {len(invoices)} invoices")
    print("\nFiles created:")
    print("  • customers.csv")
    print("  • products.csv")
    print("  • invoices.csv")
